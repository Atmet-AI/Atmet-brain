"""Source revisions, evidence access and derived-data invalidation."""

import base64

from .auth import authorize, audience_allows, can, validate_audience
from .db import audit, recovery_event
from .errors import BrainError, require
from .util import dumps, loads, now, sha, text, timestamp, uid

TEXT_MIMES = {"text/plain", "text/markdown", "text/csv", "application/json"}


class SourcesMixin:
    def _source(self, conn, actor, source_id, operation="read"):
        row = conn.execute("SELECT s.* FROM sources s JOIN spaces p ON p.id=s.space_id "
                           "WHERE s.id=? AND p.org_id=?", (source_id, actor.org_id)).fetchone()
        require(row is not None, "not_found", "Source not found.", 404)
        authorize(conn, actor, row["space_id"], operation)
        require(audience_allows(conn, actor, row["audience"]), "not_found", "Source not found.", 404)
        if row["category"] == "task_report" and operation == "read":
            report = conn.execute("SELECT evidence FROM task_reports WHERE source_id=?", (source_id,)).fetchone()
            require(report and self._evidence_readable(conn, actor, row["space_id"], report[0], current=False),
                    "not_found", "Source not found.", 404)
        if operation == "read" and row["connector_id"]:
            binding = conn.execute("SELECT enabled FROM connectors WHERE id=?", (row["connector_id"],)).fetchone()
            require(binding and binding[0], "not_found", "Source not found.", 404)
        return row

    def _source_readable(self, conn, actor, source_id):
        try:
            source = self._source(conn, actor, source_id)
            return source["status"] == ("reported" if source["category"] == "task_report" else "active")
        except BrainError:
            return False

    def _evidence(self, conn, actor, space_id, evidence, current=True, allow_empty=False):
        require(isinstance(evidence, list) and len(evidence) <= 50 and (allow_empty or bool(evidence)),
                "invalid_evidence", "Provide source revision evidence.")
        clean = []
        for item in evidence:
            require(isinstance(item, dict) and set(item) == {"source_id", "revision"}
                    and isinstance(item["source_id"], str) and type(item["revision"]) is int,
                    "invalid_evidence", "Evidence requires source_id and integer revision.")
            source = self._source(conn, actor, item["source_id"])
            require(source["space_id"] == space_id and source["status"] == ("reported" if source["category"] == "task_report" else "active"),
                    "evidence_unavailable", "Required evidence is unavailable.", 409)
            require(not current or source["revision"] == item["revision"],
                    "stale_evidence", "A source changed. Review its current revision.", 409)
            if current and source["category"] == "task_report":
                report = conn.execute("SELECT evidence FROM task_reports WHERE source_id=?", (source["id"],)).fetchone()
                self._evidence(conn, actor, space_id, loads(report[0]), current=True)
            require(conn.execute("SELECT 1 FROM source_revisions WHERE source_id=? AND revision=?",
                                 (source["id"], item["revision"])).fetchone(),
                    "evidence_unavailable", "Required evidence is unavailable.", 409)
            if item not in clean:
                clean.append(item)
        return clean

    def _evidence_readable(self, conn, actor, space_id, evidence, current=True):
        try:
            self._evidence(conn, actor, space_id, loads(evidence) if isinstance(evidence, str) else evidence,
                           current=current, allow_empty=True)
            return True
        except BrainError:
            return False

    def put_source(self, actor, space_id, external_id, title, content, mime="text/plain", audience=None,
                   authority="observation", expected_revision=None, effective_at=None, _connector_id=None):
        text(external_id, "external_id", 500)
        require(not external_id.startswith("atmet-report:"), "reserved_source", "Task report sources are managed through reports.record.")
        text(title, "title", 200)
        text(content, "content", 200_000)
        require(authority in {"observation", "reference", "authoritative"}, "invalid_authority", "Invalid authority.")
        require(mime in TEXT_MIMES, "unsupported_format", "This endpoint accepts UTF-8 text, Markdown, CSV and JSON.")
        if mime == "application/json":
            try:
                loads(content)
            except (ValueError, TypeError):
                raise BrainError("invalid_json", "Source content is not valid JSON.") from None
        with self.store.transaction(write=True) as conn:
            authorize(conn, actor, space_id, "contribute")
            authorize(conn, actor, space_id, "read")
            allowed_audience = validate_audience(conn, actor.org_id, audience if audience is not None else ["space"])
            if _connector_id:
                binding = conn.execute("SELECT * FROM connectors WHERE id=? AND space_id=? AND enabled=1", (_connector_id, space_id)).fetchone()
                require(binding and binding["audience"] == dumps(allowed_audience) and binding["authority"] == authority,
                        "connector_inactive", "Connector binding changed or was disabled.", 409)
            existing = conn.execute("SELECT * FROM sources WHERE space_id=? AND external_id=?", (space_id, external_id)).fetchone()
            if authority != "observation":
                authorize(conn, actor, space_id, "manage")
            if existing:
                require(existing["connector_id"] == _connector_id, "source_binding", "This source belongs to a different binding.", 409)
                self._source(conn, actor, existing["id"])
                require(existing["status"] == "active", "source_inactive", "Revalidate this source before writing.", 409)
                if dumps(allowed_audience) != existing["audience"] or authority != existing["authority"]:
                    authorize(conn, actor, space_id, "manage")
                old = conn.execute("SELECT * FROM source_revisions WHERE source_id=? AND revision=?",
                                   (existing["id"], existing["revision"])).fetchone()
                if old["content_hash"] == sha(content) and old["mime"] == mime and existing["title"] == title \
                        and existing["audience"] == dumps(allowed_audience) and existing["authority"] == authority \
                        and (effective_at is None or old["effective_at"] == timestamp(effective_at)):
                    return {"id": existing["id"], "revision": existing["revision"], "status": "unchanged"}
                require(type(expected_revision) is int and expected_revision == existing["revision"],
                        "revision_conflict", "Source revision changed or expected_revision is missing.", 409)
                ident, revision = existing["id"], existing["revision"] + 1
                conn.execute("UPDATE sources SET title=?,revision=?,audience=?,authority=?,updated_at=? WHERE id=?",
                             (title, revision, dumps(allowed_audience), authority, now(), ident))
                self._invalidate_source(conn, ident)
            else:
                require(expected_revision in (None, 0), "revision_conflict", "New sources start at revision zero.", 409)
                ident, revision = uid("source"), 1
                conn.execute("INSERT INTO sources(id,space_id,external_id,title,revision,audience,authority,status,created_at,updated_at,connector_id) "
                             "VALUES(?,?,?,?,?,?,?,'active',?,?,?)",
                             (ident, space_id, external_id, title, revision, dumps(allowed_audience), authority, now(), now(), _connector_id))
            conn.execute("INSERT INTO source_revisions VALUES(?,?,?,?,?,?,?)",
                         (ident, revision, content.encode(), mime, sha(content), now(), timestamp(effective_at)))
            job = uid("job")
            conn.execute("INSERT INTO jobs(id,space_id,source_id,source_revision,requested_by,requested_credential,created_at,updated_at) "
                         "VALUES(?,?,?,?,?,?,?,?)", (job, space_id, ident, revision, actor.principal_id, actor.credential_id, now(), now()))
            audit(conn, actor, "source.put", ident, space_id, {"revision": revision, "job_id": job})
            return {"id": ident, "revision": revision, "job_id": job, "status": "accepted"}

    def _invalidate_source(self, conn, source_id, erase=False):
        affected = {source_id}
        reports = conn.execute("SELECT source_id,evidence FROM task_reports").fetchall()
        for report in reports:
            if any(ref["source_id"] == source_id for ref in loads(report["evidence"])):
                affected.add(report["source_id"])
                if erase:
                    conn.execute("UPDATE source_revisions SET body=X'' WHERE source_id=?", (report["source_id"],))
                    conn.execute("UPDATE sources SET status='deleted',title='Erased task report' WHERE id=?", (report["source_id"],))
        if erase:
            for ident in affected:
                conn.execute("UPDATE task_reports SET task_key='' WHERE source_id=?", (ident,))
        for row in conn.execute("SELECT id,evidence FROM memories").fetchall():
            if any(e["source_id"] in affected for e in loads(row["evidence"])):
                conn.execute("UPDATE memories SET status=?,statement=CASE WHEN ? THEN '' ELSE statement END WHERE id=?",
                             ("erased" if erase else "stale", int(erase), row["id"]))
        if erase:
            for row in conn.execute("SELECT id,evidence FROM task_runs").fetchall():
                if any(e["source_id"] in affected for e in loads(row["evidence"])):
                    conn.execute("UPDATE task_runs SET inputs='{}',output='{}',succeeded=0 WHERE id=?", (row["id"],))
            for row in conn.execute("SELECT artifact_id,revision,evidence FROM artifact_versions").fetchall():
                if any(e["source_id"] in affected for e in loads(row["evidence"])):
                    conn.execute("UPDATE artifact_versions SET body='{}',state='retracted',reason='Evidence erased',"
                                 "content_hash=? WHERE artifact_id=? AND revision=?",
                                 (sha("{}"), row["artifact_id"], row["revision"]))
        conn.execute("UPDATE jobs SET status='cancelled',lease_token=NULL,updated_at=? WHERE source_id=? "
                     "AND status IN ('pending','running','retry')", (now(), source_id))

    def get_source(self, actor, source_id, revision=None):
        with self.store.transaction() as conn:
            source = self._source(conn, actor, source_id)
            if source["category"] == "task_report":
                authorize(conn, actor, source["space_id"], "history")
            require(source["status"] == ("reported" if source["category"] == "task_report" else "active"), "not_found", "Source not found.", 404)
            if revision is not None and revision != source["revision"]:
                authorize(conn, actor, source["space_id"], "history")
            chosen = source["revision"] if revision is None else revision
            row = conn.execute("SELECT * FROM source_revisions WHERE source_id=? AND revision=?", (source_id, chosen)).fetchone()
            require(row is not None, "not_found", "Source revision not found.", 404)
            return {"id": source_id, "space_id": source["space_id"], "title": source["title"], "revision": chosen,
                    "current_revision": source["revision"], "mime": row["mime"], "content": bytes(row["body"]).decode("utf-8"),
                    "content_hash": row["content_hash"], "recorded_at": row["recorded_at"], "effective_at": row["effective_at"]}

    def list_sources(self, actor, space_id):
        with self.store.transaction() as conn:
            authorize(conn, actor, space_id, "read")
            rows = conn.execute("SELECT * FROM sources WHERE space_id=? AND status='active' AND category='document' ORDER BY title", (space_id,))
            result = []
            for row in rows:
                if self._source_readable(conn, actor, row["id"]):
                    job = conn.execute("SELECT status,error_code FROM jobs WHERE source_id=? AND source_revision=?",
                                       (row["id"], row["revision"])).fetchone()
                    result.append({"id": row["id"], "title": row["title"], "revision": row["revision"],
                                   "authority": row["authority"], "source_status": row["status"],
                                   "memory_status": job["status"] if job else "unknown",
                                   "error_code": job["error_code"] if job else None})
            return result

    def set_source_access(self, actor, source_id, audience, active=True):
        require(type(active) is bool, "invalid_input", "active must be true or false.")
        with self.store.transaction(write=True) as conn:
            source = self._source(conn, actor, source_id, "manage")
            require(source["status"] != "deleted", "source_deleted", "Erased sources cannot be restored.", 409)
            values = validate_audience(conn, actor.org_id, audience)
            live_state = "reported" if source["category"] == "task_report" else "active"
            conn.execute("UPDATE sources SET audience=?,status=?,updated_at=? WHERE id=?",
                         (dumps(values), live_state if active else "revoked", now(), source_id))
            if not active:
                self._invalidate_source(conn, source_id)
            elif source["status"] != live_state:
                conn.execute("UPDATE jobs SET status='pending',attempts=0,error_code=NULL,requested_by=?,requested_credential=?,"
                             "updated_at=? WHERE source_id=? AND source_revision=?",
                             (actor.principal_id, actor.credential_id, now(), source_id, source["revision"]))
            recovery_event(conn, "source.access", source_id, {"audience": values, "active": active})
            audit(conn, actor, "source.access", source_id, source["space_id"], {"active": active})
        self.flush_recovery_journal()
        return {"status": live_state if active else "revoked"}

    def erase_source(self, actor, source_id):
        with self.store.transaction(write=True) as conn:
            source = self._source(conn, actor, source_id, "erase")
            conn.execute("UPDATE source_revisions SET body=X'' WHERE source_id=?", (source_id,))
            conn.execute("UPDATE sources SET status='deleted',title='Erased source',updated_at=? WHERE id=?", (now(), source_id))
            self._invalidate_source(conn, source_id, erase=True)
            recovery_event(conn, "source.erase", source_id)
            audit(conn, actor, "source.erase", source_id, source["space_id"])
        self.flush_recovery_journal()
        return {"status": "erased"}

    def propose_memory(self, actor, space_id, statement, evidence, claim_key=None, kind="inference"):
        require(kind in {"observation", "inference"}, "invalid_kind", "Agent writes are observations or inferences.")
        text(statement, "statement", 4000)
        if claim_key is not None:
            text(claim_key, "claim_key", 200)
        with self.store.transaction(write=True) as conn:
            authorize(conn, actor, space_id, "contribute")
            proof = self._evidence(conn, actor, space_id, evidence)
            ident = uid("memory")
            conn.execute("INSERT INTO memories VALUES(?,?,?,?,?,?,'pending',1,?,?,NULL,'agent-proposal-v1')",
                         (ident, space_id, statement, claim_key, kind, dumps(proof), now(), now()))
            conn.execute("INSERT INTO memory_history VALUES(?,1,'pending',?,?,?)",
                         (ident, actor.principal_id, "Agent proposal", now()))
            audit(conn, actor, "memory.propose", ident, space_id)
            return {"id": ident, "revision": 1, "status": "pending_review"}

    def review_memory(self, actor, memory_id, expected_revision, approve, reason):
        require(type(approve) is bool and type(expected_revision) is int, "invalid_input", "Invalid review request.")
        text(reason, "reason", 500)
        with self.store.transaction(write=True) as conn:
            row = conn.execute("SELECT m.* FROM memories m JOIN spaces s ON s.id=m.space_id "
                               "WHERE m.id=? AND s.org_id=?", (memory_id, actor.org_id)).fetchone()
            require(row is not None, "not_found", "Memory not found.", 404)
            authorize(conn, actor, row["space_id"], "review")
            self._evidence(conn, actor, row["space_id"], loads(row["evidence"]))
            require(row["revision"] == expected_revision and row["status"] in {"pending", "conflict"},
                    "revision_conflict", "Review the current pending memory revision.", 409)
            require(row["kind"] != "rule_candidate", "policy_requires_publication", "Publish operating rules as a policy artifact.")
            state = "active" if approve else "rejected"
            revision = row["revision"] + 1
            conn.execute("UPDATE memories SET status=?,revision=? WHERE id=?", (state, revision, memory_id))
            conn.execute("INSERT INTO memory_history VALUES(?,?,?,?,?,?)", (memory_id, revision, state, actor.principal_id, reason, now()))
            audit(conn, actor, "memory.review", memory_id, row["space_id"], {"revision": revision, "state": state})
            return {"id": memory_id, "revision": revision, "status": state}

    def list_memories(self, actor, space_id, include_pending=False):
        with self.store.transaction() as conn:
            authorize(conn, actor, space_id, "read")
            if include_pending:
                authorize(conn, actor, space_id, "review")
            states = {"active", "pending", "conflict"} if include_pending else {"active"}
            result = []
            for row in conn.execute("SELECT * FROM memories WHERE space_id=? ORDER BY recorded_at DESC", (space_id,)):
                if row["status"] in states and self._evidence_readable(conn, actor, space_id, row["evidence"]):
                    value = dict(row)
                    value["evidence"] = loads(row["evidence"])
                    result.append(value)
            return result
