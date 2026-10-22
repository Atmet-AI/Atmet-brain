"""Reviewed policies, workflows, instructions, configuration and portable skills."""

import re

from .auth import authorize, audience_allows, validate_audience
from .config import validate_settings
from .db import audit
from .errors import BrainError, require
from .util import dumps, loads, now, safe_resource_path, sha, slug, text, timestamp, uid

KINDS = {"policy", "workflow", "skill", "instructions", "config", "automation"}


def validate_body(kind, body):
    require(isinstance(body, dict), "invalid_artifact", "Artifact body must be an object.")
    require(len(dumps(body)) <= 200_000, "invalid_artifact", "Artifact is too large.")
    if kind == "config":
        return validate_settings(body)
    if kind == "automation":
        from .automations import validate_automation_body
        return validate_automation_body(body)
    keys = {"instructions", "description", "inputs", "outputs", "tags"}
    if kind == "workflow":
        keys |= {"trigger", "steps", "exceptions"}
    if kind == "skill":
        keys |= {"required_tools", "resources", "checks"}
    require(not (set(body) - keys), "invalid_artifact", "Unknown artifact field.")
    text(body.get("instructions"), "instructions", 60_000)
    for key in {"description", "trigger"} & set(body):
        text(body[key], key, 4000)
    for key in {"inputs", "outputs", "tags", "exceptions", "required_tools", "checks"} & set(body):
        require(isinstance(body[key], list) and len(body[key]) <= 100, "invalid_artifact", f"{key} must be a list.")
        for value in body[key]:
            text(value, key, 1000)
    if kind == "workflow":
        steps = body.get("steps")
        require(isinstance(steps, list) and 0 < len(steps) <= 100, "invalid_workflow", "Provide workflow steps.")
        seen = set()
        for step in steps:
            require(isinstance(step, dict) and set(step) <= {"id", "instruction", "skill_id"},
                    "invalid_workflow", "Steps need id, instruction and optional skill_id.")
            ident = slug(step.get("id"))
            require(ident not in seen, "invalid_workflow", "Workflow step IDs must be unique.")
            seen.add(ident)
            text(step.get("instruction"), "step instruction", 4000)
            if "skill_id" in step:
                text(step["skill_id"], "skill_id", 100)
    if kind == "skill":
        text(body.get("description"), "description", 4000)
        resources = body.get("resources", {})
        require(isinstance(resources, dict) and len(resources) <= 40, "invalid_skill", "Provide a resource map.")
        for path, content in resources.items():
            safe_resource_path(path)
            text(content, "resource content", 40_000)
    return body


def effective_version(conn, artifact_id, at=None, known_at=None):
    row = conn.execute("SELECT * FROM artifact_versions WHERE artifact_id=? AND reviewed_at IS NOT NULL "
                       "AND state IN ('approved','retired','retracted') AND effective_at<=? AND reviewed_at<=? "
                       "ORDER BY revision DESC LIMIT 1", (artifact_id, now() if at is None else at, now() if known_at is None else known_at)).fetchone()
    return row if row and row["state"] == "approved" else None


class ArtifactsMixin:
    def _artifact(self, conn, actor, artifact_id, operation="read"):
        row = conn.execute("SELECT a.* FROM artifacts a JOIN spaces s ON s.id=a.space_id "
                           "WHERE a.id=? AND s.org_id=?", (artifact_id, actor.org_id)).fetchone()
        require(row is not None, "not_found", "Artifact not found.", 404)
        authorize(conn, actor, row["space_id"], operation)
        require(audience_allows(conn, actor, row["audience"]), "not_found", "Artifact not found.", 404)
        return row

    def _dependencies(self, conn, actor, space_id, dependencies, at=None):
        require(isinstance(dependencies, list) and len(dependencies) <= 30,
                "invalid_dependencies", "Provide up to 30 dependency references.")
        result = []
        for ref in dependencies:
            require(isinstance(ref, dict) and set(ref) == {"artifact_id", "revision"}
                    and type(ref["revision"]) is int, "invalid_dependencies", "Dependency needs artifact_id and revision.")
            artifact = self._artifact(conn, actor, ref["artifact_id"])
            require(artifact["space_id"] == space_id, "invalid_dependencies", "Dependencies must use the same space.")
            version = effective_version(conn, ref["artifact_id"], at)
            require(version and version["revision"] == ref["revision"], "dependency_changed",
                    "A dependency is unavailable or needs revalidation.", 409)
            self._evidence(conn, actor, space_id, loads(version["evidence"]), allow_empty=True)
            if ref not in result:
                result.append(ref)
        return result

    def propose_artifact(self, actor, space_id, kind, name, body, expected_revision=0, artifact_id=None,
                         evidence=None, dependencies=None, instruction_path="shared", audience=None,
                         effective_at=None, reason="Proposed update", idempotency_key=None):
        require(kind in KINDS, "invalid_kind", "Choose a supported artifact kind.")
        validate_body(kind, body)
        slug(name)
        text(reason, "reason", 500)
        text(idempotency_key, "idempotency_key", 200)
        require(type(expected_revision) is int and expected_revision >= 0, "invalid_revision", "Provide expected_revision.")
        require(isinstance(instruction_path, str) and len(instruction_path) <= 200
                and re.fullmatch(r"[a-z0-9_-]+(?:/[a-z0-9_-]+)*", instruction_path),
                "invalid_path", "Use a relative instruction path with lowercase segments.")
        fingerprint = sha(dumps({"kind": kind, "name": name, "body": body, "expected": expected_revision,
                                  "artifact_id": artifact_id, "evidence": evidence, "dependencies": dependencies,
                                  "path": instruction_path, "audience": audience, "effective": effective_at, "reason": reason}))
        with self.store.transaction(write=True) as conn:
            authorize(conn, actor, space_id, "contribute")
            authorize(conn, actor, space_id, "read")
            proof = self._evidence(conn, actor, space_id, evidence or [], allow_empty=True)
            old = conn.execute("SELECT * FROM idempotency WHERE principal_id=? AND space_id=? AND request_key=?",
                               (actor.principal_id, space_id, idempotency_key)).fetchone()
            if old:
                require(old["fingerprint"] == fingerprint, "idempotency_conflict", "Request key was used with different content.", 409)
                return loads(old["result"])
            allowed_audience = validate_audience(conn, actor.org_id, audience if audience is not None else ["space"])
            effective = timestamp(effective_at)
            refs = self._dependencies(conn, actor, space_id, dependencies or [], effective)
            if artifact_id:
                artifact = self._artifact(conn, actor, artifact_id)
                require(artifact["space_id"] == space_id and artifact["kind"] == kind and artifact["slug"] == name,
                        "artifact_mismatch", "Artifact identity cannot change.")
                require(artifact["instruction_path"] == instruction_path and artifact["audience"] == dumps(allowed_audience),
                        "artifact_mismatch", "Scope and audience are fixed for this artifact. Create a separate reviewed artifact.")
                previous = conn.execute("SELECT evidence FROM artifact_versions WHERE artifact_id=? AND revision=?",
                                        (artifact_id, artifact["head"])).fetchone()
                self._evidence(conn, actor, space_id, loads(previous[0]), current=False, allow_empty=True)
            else:
                artifact = conn.execute("SELECT * FROM artifacts WHERE space_id=? AND kind=? AND slug=?",
                                        (space_id, kind, name)).fetchone()
                require(artifact is None, "already_exists", "Use artifact_id and expected_revision to update.", 409)
            require((artifact["head"] if artifact else 0) == expected_revision,
                    "revision_conflict", "Artifact revision changed. Reload before proposing.", 409)
            ident = artifact["id"] if artifact else uid("artifact")
            revision = expected_revision + 1
            if not artifact:
                conn.execute("INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?)",
                             (ident, space_id, kind, name, revision, instruction_path, dumps(allowed_audience), now()))
            else:
                conn.execute("UPDATE artifacts SET head=? WHERE id=?", (revision, ident))
            conn.execute("INSERT INTO artifact_versions VALUES(?,?,?,?,?,'pending',?,?,NULL,NULL,?,?,NULL,?)",
                         (ident, revision, dumps(body), dumps(proof), dumps(refs), actor.principal_id, now(),
                          effective, reason, sha(dumps(body))))
            result = {"id": ident, "revision": revision, "status": "pending_review", "effective_at": effective}
            conn.execute("INSERT INTO idempotency VALUES(?,?,?,?,?)",
                         (actor.principal_id, space_id, idempotency_key, fingerprint, dumps(result)))
            audit(conn, actor, "artifact.propose", ident, space_id, {"revision": revision, "kind": kind})
            return result

    def review_artifact(self, actor, artifact_id, expected_revision, approve, reason):
        require(type(approve) is bool and type(expected_revision) is int, "invalid_input", "Invalid review request.")
        text(reason, "reason", 500)
        with self.store.transaction(write=True) as conn:
            artifact = self._artifact(conn, actor, artifact_id, "publish")
            require(artifact["head"] == expected_revision, "revision_conflict", "Review is stale. Reload the current draft.", 409)
            version = conn.execute("SELECT * FROM artifact_versions WHERE artifact_id=? AND revision=?",
                                   (artifact_id, expected_revision)).fetchone()
            require(version and version["state"] == "pending", "invalid_state", "This revision is not pending review.", 409)
            self._evidence(conn, actor, artifact["space_id"], loads(version["evidence"]), allow_empty=True)
            if approve:
                validate_body(artifact["kind"], loads(version["body"]))
                self._dependencies(conn, actor, artifact["space_id"], loads(version["dependencies"]), version["effective_at"])
                if artifact["kind"] == "automation":
                    self._validate_automation(conn, actor, artifact, version)
                if artifact["kind"] == "workflow":
                    skill_ids = {step["skill_id"] for step in loads(version["body"])["steps"] if "skill_id" in step}
                    dependencies = {ref["artifact_id"] for ref in loads(version["dependencies"])}
                    require(skill_ids <= dependencies, "missing_skill_dependency", "Workflow skill steps need pinned dependencies.")
                    for skill_id in skill_ids:
                        require(self._artifact(conn, actor, skill_id)["kind"] == "skill", "invalid_skill", "Step dependency is not a skill.")
            state = "approved" if approve else "rejected"
            conn.execute("UPDATE artifact_versions SET state=?,reviewed_by=?,reviewed_at=?,reason=? "
                         "WHERE artifact_id=? AND revision=?",
                         (state, actor.principal_id, now(), reason, artifact_id, expected_revision))
            audit(conn, actor, "artifact.review", artifact_id, artifact["space_id"], {"revision": expected_revision, "state": state})
            return {"id": artifact_id, "revision": expected_revision, "status": state,
                    "activation": "scheduled" if version["effective_at"] > now() else "current"}

    def get_artifact(self, actor, artifact_id, revision=None, at=None, known_at=None):
        with self.store.transaction() as conn:
            artifact = self._artifact(conn, actor, artifact_id)
            current = effective_version(conn, artifact_id, timestamp(at) if at is not None else None,
                                        timestamp(known_at) if known_at is not None else None)
            if revision is not None or at is not None or known_at is not None:
                authorize(conn, actor, artifact["space_id"], "history")
            version = conn.execute("SELECT * FROM artifact_versions WHERE artifact_id=? AND revision=?",
                                   (artifact_id, revision)).fetchone() if revision is not None else current
            require(version is not None, "not_found", "Artifact version not found or not active.", 404)
            self._evidence(conn, actor, artifact["space_id"], loads(version["evidence"]),
                           current=revision is None and at is None and known_at is None, allow_empty=True)
            result = dict(artifact)
            result.update(dict(version))
            for field in ("body", "evidence", "dependencies", "audience"):
                result[field] = loads(result[field])
            return result

    def list_artifacts(self, actor, space_id, kind=None):
        require(kind is None or kind in KINDS, "invalid_kind", "Unknown artifact kind.")
        with self.store.transaction() as conn:
            authorize(conn, actor, space_id, "read")
            result = []
            for item in conn.execute("SELECT * FROM artifacts WHERE space_id=? ORDER BY kind,slug", (space_id,)):
                if kind is not None and item["kind"] != kind:
                    continue
                version = effective_version(conn, item["id"])
                if version and audience_allows(conn, actor, item["audience"]) \
                        and self._evidence_readable(conn, actor, space_id, version["evidence"]):
                    result.append({"id": item["id"], "kind": item["kind"], "slug": item["slug"], "revision": version["revision"],
                                   "description": loads(version["body"]).get("description", ""), "content_hash": version["content_hash"]})
            return result

    def artifact_history(self, actor, artifact_id):
        with self.store.transaction() as conn:
            artifact = self._artifact(conn, actor, artifact_id, "history")
            result = []
            for version in conn.execute("SELECT * FROM artifact_versions WHERE artifact_id=? ORDER BY revision", (artifact_id,)):
                if self._evidence_readable(conn, actor, artifact["space_id"], version["evidence"], current=False):
                    result.append({k: version[k] for k in ("revision", "state", "submitted_by", "submitted_at",
                                                          "reviewed_by", "reviewed_at", "effective_at", "rollback_of", "content_hash")})
            return result

    def rollback_artifact(self, actor, artifact_id, target_revision, expected_revision, reason, idempotency_key):
        old = self.get_artifact(actor, artifact_id, revision=target_revision)
        require(old["state"] == "approved", "invalid_state", "Rollback requires a retained approved version.")
        proposal = self.propose_artifact(actor, old["space_id"], old["kind"], old["slug"], old["body"],
                                         expected_revision, artifact_id, old["evidence"], old["dependencies"],
                                         old["instruction_path"], old["audience"], reason=reason,
                                         idempotency_key=idempotency_key)
        with self.store.transaction(write=True) as conn:
            authorize(conn, actor, old["space_id"], "contribute")
            conn.execute("UPDATE artifact_versions SET rollback_of=? WHERE artifact_id=? AND revision=?",
                         (target_revision, artifact_id, proposal["revision"]))
        return proposal

    def retire_artifact(self, actor, artifact_id, expected_revision, reason):
        text(reason, "reason", 500)
        with self.store.transaction(write=True) as conn:
            artifact = self._artifact(conn, actor, artifact_id, "publish")
            require(artifact["head"] == expected_revision, "revision_conflict", "Artifact changed.", 409)
            prior = conn.execute("SELECT evidence FROM artifact_versions WHERE artifact_id=? AND revision=?",
                                 (artifact_id, artifact["head"])).fetchone()
            self._evidence(conn, actor, artifact["space_id"], loads(prior[0]), current=False, allow_empty=True)
            revision = expected_revision + 1
            conn.execute("UPDATE artifacts SET head=? WHERE id=?", (revision, artifact_id))
            conn.execute("INSERT INTO artifact_versions VALUES(?,?,?,'[]','[]','retired',?,?,?,?,?,?,NULL,?)",
                         (artifact_id, revision, '{}', actor.principal_id, now(), actor.principal_id, now(), now(), reason, sha('{}')))
            audit(conn, actor, "artifact.retire", artifact_id, artifact["space_id"], {"revision": revision})
            return {"id": artifact_id, "revision": revision, "status": "retired"}

    def artifact_diff(self, actor, artifact_id, from_revision, to_revision):
        import difflib
        import json
        before = self.get_artifact(actor, artifact_id, revision=from_revision)
        after = self.get_artifact(actor, artifact_id, revision=to_revision)
        left = json.dumps(before["body"], indent=2, sort_keys=True, ensure_ascii=False).splitlines()
        right = json.dumps(after["body"], indent=2, sort_keys=True, ensure_ascii=False).splitlines()
        return {"artifact_id": artifact_id, "from_revision": from_revision, "to_revision": to_revision,
                "diff": "\n".join(difflib.unified_diff(left, right, fromfile=str(from_revision), tofile=str(to_revision), lineterm=""))}
