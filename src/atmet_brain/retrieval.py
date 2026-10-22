"""Permission-first lexical retrieval, task envelopes and relationship inspection."""

import math
import re

from ._version import __version__
from .artifacts import effective_version
from .auth import authorize, audience_allows, can
from .db import SCHEMA_VERSION, audit
from .errors import BrainError, require
from .util import dumps, loads, now, sha, text, uid


def tokens(value):
    return re.findall(r"\w+", value.casefold(), re.UNICODE)


def rank(query, items, limit):
    terms = set(tokens(query))
    scored = []
    for item in items:
        words = tokens(item["text"])
        if not words:
            continue
        score = sum(1 + math.log(1 + words.count(term)) for term in terms if term in words)
        if score:
            scored.append({**item, "score": round(score / math.sqrt(1 + len(words) / 100), 5)})
    return sorted(scored, key=lambda i: (-i["score"], i["id"]))[:limit]


class RetrievalMixin:
    def _search(self, conn, actor, space_id, query, limit):
        authorize(conn, actor, space_id, "read")
        items = []
        for row in conn.execute("SELECT * FROM memories WHERE space_id=? AND status='active' AND effective_at<=? "
                                "AND (valid_until IS NULL OR valid_until>?)", (space_id, now(), now())):
            if self._evidence_readable(conn, actor, space_id, row["evidence"]):
                items.append({"id": row["id"], "type": "memory", "kind": row["kind"], "text": row["statement"],
                              "revision": row["revision"], "evidence": loads(row["evidence"]), "recorded_at": row["recorded_at"]})
        for source in conn.execute("SELECT s.*,r.body,r.recorded_at,r.effective_at FROM sources s JOIN source_revisions r "
                                   "ON r.source_id=s.id AND r.revision=s.revision WHERE s.space_id=? AND s.status='active' AND s.category='document' "
                                   "AND r.effective_at<=?", (space_id, now())):
            if not self._source_readable(conn, actor, source["id"]):
                continue
            content = bytes(source["body"]).decode("utf-8")
            for index in range(0, len(content), 1200):
                snippet = content[index:index + 1200]
                items.append({"id": source["id"] + ":" + str(index), "type": "source", "title": source["title"],
                              "text": snippet, "revision": source["revision"], "recorded_at": source["recorded_at"], "effective_at": source["effective_at"],
                              "evidence": [{"source_id": source["id"], "revision": source["revision"]}],
                              "character_range": [index, index + len(snippet)], "instruction_authority": False})
        return rank(query, items, limit)

    def search(self, actor, space_id, query, limit=10):
        text(query, "query", 4000)
        require(type(limit) is int and 1 <= limit <= 100, "invalid_limit", "limit must be between 1 and 100.")
        with self.store.transaction() as conn:
            results = self._search(conn, actor, space_id, query, min(limit, self.settings.max_results))
            return {"results": results, "retrieval": "authorized-lexical-v1", "returned": len(results)}

    def get_context(self, actor, space_id, query, artifact_ids=None, task_path="shared", max_chars=None):
        text(query, "query", 4000)
        require(isinstance(task_path, str) and len(task_path) <= 200
                and re.fullmatch(r"[a-z0-9_-]+(?:/[a-z0-9_-]+)*", task_path), "invalid_path", "Invalid task path.")
        require(artifact_ids is None or (isinstance(artifact_ids, list) and len(artifact_ids) <= 20),
                "invalid_input", "Provide up to 20 artifact IDs.")
        if max_chars is not None:
            require(type(max_chars) is int and 500 <= max_chars <= 100_000,
                    "invalid_limit", "max_chars must be between 500 and 100000.")
        with self.store.transaction(write=True) as conn:
            authorize(conn, actor, space_id, "read")
            rows = conn.execute("SELECT * FROM artifacts WHERE space_id=? ORDER BY instruction_path,kind,slug", (space_id,)).fetchall()
            chosen, loaded, layers = set(artifact_ids or []), {}, []
            paths = {task_path}
            for ident in chosen:
                row = self._artifact(conn, actor, ident)
                require(row["space_id"] == space_id, "not_found", "Artifact not found.", 404)
                paths.add(row["instruction_path"])
            if not chosen:
                options = []
                for row in rows:
                    if row["kind"] not in {"workflow", "skill"} or not audience_allows(conn, actor, row["audience"]):
                        continue
                    version = effective_version(conn, row["id"])
                    if version and self._evidence_readable(conn, actor, space_id, version["evidence"]):
                        body = loads(version["body"])
                        options.append({"id": row["id"], "text": row["slug"] + " " + body.get("description", "")})
                chosen.update(item["id"] for item in rank(query, options, 3))
                paths.update(row["instruction_path"] for row in rows if row["id"] in chosen)

            def load(ident, visiting=None):
                if ident in loaded:
                    return
                visiting = set() if visiting is None else visiting
                require(ident not in visiting, "dependency_cycle", "Artifact dependency cycle.", 409)
                visiting.add(ident)
                row = self._artifact(conn, actor, ident)
                require(row["space_id"] == space_id, "not_found", "Artifact not found.", 404)
                version = effective_version(conn, ident)
                require(version is not None, "incomplete_context", "Required approved context is unavailable.", 409)
                try:
                    self._evidence(conn, actor, space_id, loads(version["evidence"]), allow_empty=True)
                    refs = self._dependencies(conn, actor, space_id, loads(version["dependencies"]))
                except BrainError:
                    raise BrainError("incomplete_context", "Required approved context needs revalidation.", 409) from None
                for dep in refs:
                    load(dep["artifact_id"], visiting)
                body = loads(version["body"])
                if row["kind"] == "config":
                    layers.append(body)
                if row["kind"] == "skill":
                    body = {**body, "resources": sorted(body.get("resources", {}))}
                loaded[ident] = {"id": ident, "kind": row["kind"], "slug": row["slug"], "revision": version["revision"],
                                 "content_hash": version["content_hash"], "body": body,
                                 "evidence": loads(version["evidence"]), "instruction_path": row["instruction_path"]}
                visiting.remove(ident)

            for row in rows:
                applicable = row["instruction_path"] == "shared" or any(
                    p == row["instruction_path"] or p.startswith(row["instruction_path"] + "/") for p in paths)
                if row["kind"] in {"policy", "instructions", "config"} and applicable:
                    version = effective_version(conn, row["id"])
                    if version:
                        # An applicable rule is required even if the actor cannot read it.
                        # Return a generic incomplete response rather than silently omit it.
                        try:
                            load(row["id"])
                        except BrainError:
                            raise BrainError("incomplete_context", "Required approved context is unavailable.", 409) from None
                    else:
                        blocked = conn.execute("SELECT state FROM artifact_versions WHERE artifact_id=? AND reviewed_at IS NOT NULL "
                                               "AND effective_at<=? ORDER BY effective_at DESC,revision DESC LIMIT 1", (row["id"], now())).fetchone()
                        require(not blocked or blocked[0] != "retracted", "incomplete_context", "Required approved context was retracted.", 409)
            for ident in sorted(chosen):
                load(ident)
            settings = self.settings.constrain(*layers, *([{"max_context_chars": max_chars}] if max_chars is not None else []))
            manifest_id = uid("context")
            envelope = {"status": "ready", "space_id": space_id, "task": query, "task_path": task_path,
                        "approved_context": list(loaded.values()), "reference_evidence": [],
                        "constraints": {"external_actions_authorized": False, "source_text_is_instruction": False},
                        "warnings": [], "manifest_id": manifest_id, "budget_chars": settings["max_context_chars"]}
            require(len(dumps(envelope)) <= settings["max_context_chars"], "incomplete_context",
                    "Required approved context exceeds the budget. Narrow the task or adjust the permitted budget.", 409)
            results = self._search(conn, actor, space_id, query, settings["max_results"])
            for item in results:
                envelope["reference_evidence"].append(item)
                if len(dumps(envelope)) > settings["max_context_chars"] - 150:
                    envelope["reference_evidence"].pop()
                    envelope["warnings"].append("Some reference evidence did not fit the context budget.")
                    break
            if not results:
                envelope["warnings"].append("No matching source evidence. Do not infer missing business facts.")
            for conflict in conn.execute("SELECT * FROM memories WHERE space_id=? AND status='conflict'", (space_id,)):
                if self._evidence_readable(conn, actor, space_id, conflict["evidence"]) and set(tokens(query)) & set(tokens(conflict["statement"])):
                    envelope["warnings"].append("Relevant source evidence has an unresolved memory conflict. Review before relying on it.")
                    break
            require(len(dumps(envelope)) <= settings["max_context_chars"], "incomplete_context", "Context metadata exceeds the permitted budget.", 409)
            source_refs = []
            for item in envelope["approved_context"] + envelope["reference_evidence"]:
                for ref in item["evidence"]:
                    if ref not in source_refs:
                        source_refs.append(ref)
            revisions = {"engine": __version__, "schema": SCHEMA_VERSION, "retrieval": "authorized-lexical-v1",
                         "artifacts": [{k: v[k] for k in ("id", "revision", "content_hash")} for v in loaded.values()],
                         "sources": source_refs, "permission_check_at": now(), "settings": settings}
            require(len(source_refs) <= 50, "incomplete_context", "Narrow tasks requiring more than 50 source revisions.", 409)
            conn.execute("INSERT INTO manifests VALUES(?,?,?,?,?,?)",
                         (manifest_id, space_id, actor.principal_id, sha(query), dumps(revisions), now()))
            audit(conn, actor, "context.read", manifest_id, space_id)
            return envelope

    def get_manifest(self, actor, manifest_id):
        with self.store.transaction() as conn:
            row = conn.execute("SELECT m.* FROM manifests m JOIN spaces s ON s.id=m.space_id WHERE m.id=? AND s.org_id=?",
                               (manifest_id, actor.org_id)).fetchone()
            require(row is not None and row["actor_id"] == actor.principal_id,
                    "not_found", "Manifest not found.", 404)
            authorize(conn, actor, row["space_id"], "read")
            value = loads(row["revisions"])
            self._evidence(conn, actor, row["space_id"], value["sources"], current=False, allow_empty=True)
            for ref in value["artifacts"]:
                artifact = self._artifact(conn, actor, ref["id"])
                version = conn.execute("SELECT evidence FROM artifact_versions WHERE artifact_id=? AND revision=?",
                                       (ref["id"], ref["revision"])).fetchone()
                require(version and self._evidence_readable(conn, actor, artifact["space_id"], version[0], current=False),
                        "not_found", "Manifest evidence is unavailable.", 404)
            return {"id": row["id"], "created_at": row["created_at"], "revisions": value}

    def graph(self, actor, space_id):
        sources = self.list_sources(actor, space_id)
        memories = self.list_memories(actor, space_id)
        artifacts = self.list_artifacts(actor, space_id)
        nodes = [{"id": s["id"], "type": "source", "label": s["title"]} for s in sources]
        nodes += [{"id": m["id"], "type": "memory", "label": m["statement"][:100]} for m in memories]
        nodes += [{"id": a["id"], "type": a["kind"], "label": a["slug"]} for a in artifacts]
        allowed = {n["id"] for n in nodes}
        edges = []
        for m in memories:
            edges.extend({"from": m["id"], "to": ref["source_id"], "type": "evidence"} for ref in m["evidence"] if ref["source_id"] in allowed)
        for a in artifacts:
            item = self.get_artifact(actor, a["id"])
            edges.extend({"from": a["id"], "to": ref["artifact_id"], "type": "depends_on"}
                         for ref in item["dependencies"] if ref["artifact_id"] in allowed)
        return {"nodes": nodes, "edges": edges}

    def skill_resource(self, actor, artifact_id, path):
        item = self.get_artifact(actor, artifact_id)
        require(item["kind"] == "skill", "invalid_kind", "This artifact is not a skill.")
        with self.store.transaction() as conn:
            self._dependencies(conn, actor, item["space_id"], item["dependencies"])
        resources = item["body"].get("resources", {})
        require(path in resources, "not_found", "Skill resource not found.", 404)
        return {"artifact_id": artifact_id, "revision": item["revision"], "path": path, "content": resources[path], "executable": False}

    def export_space(self, actor, space_id):
        sources = self.list_sources(actor, space_id)
        artifacts = self.list_artifacts(actor, space_id)
        return {"format": "atmet-brain-export-v1", "space_id": space_id, "exported_at": now(),
                "sources": [self.get_source(actor, s["id"]) for s in sources],
                "memories": self.list_memories(actor, space_id),
                "artifacts": [self.get_artifact(actor, a["id"]) for a in artifacts],
                "includes_credentials": False, "includes_operational_backup": False}

    def list_audit(self, actor, space_id, limit=100):
        require(type(limit) is int and 1 <= limit <= 500, "invalid_limit", "limit must be between 1 and 500.")
        with self.store.transaction() as conn:
            authorize(conn, actor, space_id, "history")
            authorize(conn, actor, space_id, "read")
            result = []
            for row in conn.execute("SELECT * FROM audit_events WHERE space_id=? ORDER BY recorded_at DESC", (space_id,)):
                target = row["target"] or ""
                if target.startswith("source_") and not self._source_readable(conn, actor, target):
                    continue
                if target.startswith("artifact_"):
                    try:
                        artifact = self._artifact(conn, actor, target)
                        version = effective_version(conn, target)
                        if not version or not self._evidence_readable(conn, actor, space_id, version["evidence"]):
                            continue
                    except BrainError:
                        continue
                if target.startswith("taskrun_"):
                    run = conn.execute("SELECT * FROM task_runs WHERE id=?", (target,)).fetchone()
                    try:
                        if run is None:
                            continue
                        self._read_task_run(conn, actor, run)
                    except BrainError:
                        continue
                if target.startswith("report_"):
                    try:
                        self._read_report(conn, actor, target)
                    except BrainError:
                        continue
                if row["operation"].startswith(("grant.", "credential.", "principal.", "group.")) and not can(conn, actor, space_id, "manage"):
                    continue
                if target.startswith(("memory_", "job_", "context_")) and row["actor_id"] != actor.principal_id:
                    continue
                if target.startswith("memory_"):
                    memory = conn.execute("SELECT evidence FROM memories WHERE id=?", (target,)).fetchone()
                    if not memory or not self._evidence_readable(conn, actor, space_id, memory[0], current=False):
                        continue
                if target.startswith("job_"):
                    job = conn.execute("SELECT source_id FROM jobs WHERE id=?", (target,)).fetchone()
                    if not job or not self._source_readable(conn, actor, job[0]):
                        continue
                if target.startswith("event_"):
                    event = conn.execute("SELECT evidence FROM process_events WHERE id=?", (target,)).fetchone()
                    if not event or not self._evidence_readable(conn, actor, space_id, event[0]):
                        continue
                value = dict(row)
                value["details"] = loads(value["details"])
                result.append(value)
                if len(result) >= limit:
                    break
            return result
