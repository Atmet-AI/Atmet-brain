"""Explicit task outcomes, permissioned operational history and reviewed skill drafts."""

from .auth import authorize, validate_audience
from .db import audit
from .errors import BrainError, require
from .retrieval import rank
from .util import dumps, loads, now, sha, slug, text, uid


def lines(values, name, maximum=30):
    require(isinstance(values, list) and len(values) <= maximum, "invalid_report", f"{name} must be a bounded list of text.")
    return [text(value, name, 1000) for value in values]


class TaskReportsMixin:
    def _read_report(self, conn, actor, report_id):
        row = conn.execute("SELECT r.* FROM task_reports r JOIN spaces s ON s.id=r.space_id "
                           "WHERE r.id=? AND s.org_id=?", (report_id, actor.org_id)).fetchone()
        require(row is not None, "not_found", "Task report not found.", 404)
        authorize(conn, actor, row["space_id"], "read")
        authorize(conn, actor, row["space_id"], "history")
        source = self._source(conn, actor, row["source_id"])
        require(source["status"] == "reported", "not_found", "Task report not found.", 404)
        version = conn.execute("SELECT body FROM source_revisions WHERE source_id=? AND revision=1", (source["id"],)).fetchone()
        require(version and version["body"], "not_found", "Task report not found.", 404)
        result = {key: row[key] for key in ("id", "space_id", "task_key", "recorded_by", "created_at", "source_id")}
        result.update({"report_key_hash": row["report_key_hash"], "recorded_credential": row["recorded_credential"],
                       "body": loads(bytes(version["body"]).decode()), "evidence": loads(row["evidence"]),
                       "audience": loads(source["audience"]), "outcome_verified": False,
                       "instruction_authority": False})
        return result

    def record_task_report(self, actor, space_id, report_key, task_key, summary, outcome, result, evidence,
                           steps=None, corrections=None, checks=None, audience=None):
        text(report_key, "report_key", 200)
        text(task_key, "task_key", 200)
        text(summary, "summary", 2000)
        text(result, "result", 10000)
        require(outcome in {"succeeded", "failed", "corrected"}, "invalid_report", "Choose succeeded, failed or corrected.")
        body = {"summary": summary, "outcome": outcome, "result": result,
                "steps": lines(steps if steps is not None else [], "steps"),
                "corrections": lines(corrections if corrections is not None else [], "corrections", 20),
                "checks": lines(checks if checks is not None else [], "checks", 20)}
        require(len(dumps(body)) <= 40000, "invalid_report", "Keep the complete report within 40000 characters.")
        with self.store.transaction(write=True) as conn:
            for operation in ("read", "observe", "contribute"):
                authorize(conn, actor, space_id, operation)
            allowed = validate_audience(conn, actor.org_id, audience if audience is not None else ["principal:" + actor.principal_id])
            fingerprint = sha(dumps({"body": body, "task_key": task_key, "evidence": evidence, "audience": allowed}))
            old = conn.execute("SELECT * FROM task_reports WHERE space_id=? AND recorded_by=? AND report_key_hash=?",
                               (space_id, actor.principal_id, sha(report_key))).fetchone()
            if old:
                # Revalidate access before acknowledging a replay, even after a source update.
                require(self._source_readable(conn, actor, old["source_id"]), "not_found", "Task report not found.", 404)
                require(old["request_hash"] == fingerprint, "report_conflict", "Report key was already used for different content.", 409)
                return {"id": old["id"], "source_id": old["source_id"], "status": "unchanged", "outcome_verified": False}
            proof = self._evidence(conn, actor, space_id, evidence)
            for ref in proof:
                require(self._source(conn, actor, ref["source_id"])["category"] == "document",
                        "invalid_report", "Report evidence must cite original business sources, not other task reports.")
            ident, source_id, recorded = uid("report"), uid("source"), now()
            encoded = dumps(body)
            conn.execute("INSERT INTO sources(id,space_id,external_id,title,revision,audience,authority,status,created_at,updated_at,category) "
                         "VALUES(?,?,?,?,1,?,'observation','reported',?,?,'task_report')",
                         (source_id, space_id, "atmet-report:" + ident, "Task report", dumps(allowed), recorded, recorded))
            conn.execute("INSERT INTO source_revisions VALUES(?,1,?,'application/json',?,?,?)",
                         (source_id, encoded.encode(), sha(encoded), recorded, recorded))
            conn.execute("INSERT INTO task_reports VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (ident, space_id, source_id, sha(report_key), task_key, dumps(proof), actor.principal_id,
                          actor.credential_id, fingerprint, recorded))
            audit(conn, actor, "report.record", ident, space_id)
            return {"id": ident, "source_id": source_id, "status": "recorded", "outcome_verified": False,
                    "publication_authorized": False, "next": "Use reports.search/get to inspect history, then skills.learn to propose a reviewed method."}

    def get_task_report(self, actor, report_id):
        with self.store.transaction(write=True) as conn:
            result = self._read_report(conn, actor, report_id)
            audit(conn, actor, "report.read", report_id, result["space_id"])
            return result

    def search_task_reports(self, actor, space_id, query="", task_key=None, limit=10):
        text(query, "query", 4000, allow_empty=True)
        require(type(limit) is int and 1 <= limit <= 50, "invalid_limit", "Choose a limit from 1 to 50.")
        if task_key is not None:
            text(task_key, "task_key", 200)
        with self.store.transaction() as conn:
            authorize(conn, actor, space_id, "read")
            authorize(conn, actor, space_id, "history")
            visible = []
            for row in conn.execute("SELECT id FROM task_reports WHERE space_id=? AND (? IS NULL OR task_key=?) ORDER BY created_at DESC,id",
                                    (space_id, task_key, task_key)):
                try:
                    report = self._read_report(conn, actor, row["id"])
                except BrainError:
                    continue
                body = report["body"]
                visible.append({"id": report["id"], "task_key": report["task_key"], "summary": body["summary"],
                                "outcome": body["outcome"], "created_at": report["created_at"], "recorded_by": report["recorded_by"],
                                "outcome_verified": False, "instruction_authority": False,
                                "text": " ".join([report["task_key"], body["summary"], body["result"], *body["steps"], *body["corrections"], *body["checks"]])})
            selected = rank(query, visible, limit) if query.strip() else visible[:limit]
            for item in selected:
                item.pop("text", None)
            return {"results": selected, "returned": len(selected), "retrieval": "authorized-report-lexical-v1"}

    def erase_task_report(self, actor, report_id):
        with self.store.transaction() as conn:
            report = self._read_report(conn, actor, report_id)
        return self.erase_source(actor, report["source_id"])

    def learn_skill_from_reports(self, actor, space_id, report_ids, name, idempotency_key,
                                artifact_id=None, expected_revision=0, instruction_path="shared", audience=None):
        slug(name)
        require(isinstance(report_ids, list) and 1 <= len(report_ids) <= 10
                and all(isinstance(value, str) for value in report_ids) and len(set(report_ids)) == len(report_ids),
                "invalid_reports", "Select 1 to 10 distinct task reports.")
        with self.store.transaction() as conn:
            authorize(conn, actor, space_id, "contribute")
            reports = [self._read_report(conn, actor, ident) for ident in report_ids]
            require(all(report["space_id"] == space_id for report in reports), "not_found", "Task report not found.", 404)
            require(len({report["task_key"] for report in reports}) == 1, "mixed_tasks", "Choose reports for the same task key.")
            proof, approaches, corrections, checks = [], [], [], []
            for report in reports:
                refs = [{"source_id": report["source_id"], "revision": 1}, *report["evidence"]]
                self._evidence(conn, actor, space_id, refs)
                for ref in refs:
                    if ref not in proof:
                        proof.append(ref)
                body = report["body"]
                if body["outcome"] in {"succeeded", "corrected"} and body["steps"]:
                    approaches.append("Reported approach " + str(len(approaches) + 1) + ":\n" +
                                      "\n".join(str(index + 1) + ". " + step for index, step in enumerate(body["steps"])))
                corrections.extend(value for value in body["corrections"] if value not in corrections)
                checks.extend(value for value in body["checks"] if value not in checks)
            require(approaches, "insufficient_evidence", "At least one succeeded/corrected report needs explicit steps. Failed-only reports cannot establish a method.", 409)
            require(len(proof) <= 50, "invalid_evidence", "Select fewer reports or a narrower evidence set.")
            require(len(checks) <= 99, "invalid_reports", "Select fewer reports so every result check fits the skill.")
            instructions = ("Draft method assembled from client-reported task outcomes. Validate applicability and reconcile differences before publication. "
                            "Reported success is not independently verified business success.\n\n" + "\n\n".join(approaches))
            if corrections:
                instructions += "\n\nReported corrections and pitfalls:\n" + "\n".join("- " + item for item in corrections)
            body = {"description": "Proposed reusable method for " + reports[0]["task_key"], "instructions": instructions,
                    "checks": checks + ["Validate applicability, required approvals and result quality before use."],
                    "resources": {"references/task-evidence.json": dumps({"report_ids": report_ids, "outcomes_verified": False,
                                  "review_questions": ["Are these steps reusable?", "Do corrections agree?", "Which tools and approvals are required?" ]})}}
        # The normal artifact transaction rechecks every evidence audience/version.
        # No publication or execution is performed by this operation.
        proposal = self.propose_artifact(actor, space_id, "skill", name, body, expected_revision,
                                        artifact_id=artifact_id, evidence=proof, instruction_path=instruction_path,
                                        audience=audience, reason="Skill draft from task outcomes", idempotency_key=idempotency_key)
        return {**proposal, "report_ids": report_ids, "outcomes_verified": False, "publication_authorized": False,
                "model_calls": 0, "review_required": True}
