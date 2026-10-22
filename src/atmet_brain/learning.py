"""Durable learning jobs with leases and current-permission publication checks."""

from .auth import Actor, authorize, live_principal
from .artifacts import effective_version
from .db import audit
from .errors import BrainError, require
from .extraction import configured_extractor, exact_fact
from .util import dumps, loads, now, sha, uid


class LearningMixin:
    def _processing_settings(self, conn, actor, space_id):
        layers = []
        for artifact in conn.execute("SELECT * FROM artifacts WHERE space_id=? AND kind='config'", (space_id,)):
            version = effective_version(conn, artifact["id"])
            if version:
                self._artifact(conn, actor, artifact["id"])
                self._evidence(conn, actor, space_id, loads(version["evidence"]), allow_empty=True)
                layers.append(loads(version["body"]))
        return self.settings.constrain(*layers)

    def _job_access(self, conn, actor, job):
        authorize(conn, actor, job["space_id"], "process")
        original = Actor(job["requested_by"], actor.org_id, job["requested_credential"])
        authorize(conn, original, job["space_id"], "contribute")
        source = self._source(conn, actor, job["source_id"])
        self._source(conn, original, job["source_id"])
        require(source["status"] == "active" and source["revision"] == job["source_revision"],
                "stale_job", "Source changed or access was revoked.", 409)
        return source

    def run_jobs(self, actor, space_id, max_jobs=10, extractor=None):
        require(type(max_jobs) is int and 1 <= max_jobs <= 100, "invalid_limit", "max_jobs must be between 1 and 100.")
        extractor = extractor or configured_extractor()
        results = []
        for _ in range(max_jobs):
            lease = uid("lease")
            with self.store.transaction(write=True) as conn:
                authorize(conn, actor, space_id, "process")
                job = conn.execute("SELECT * FROM jobs WHERE space_id=? AND attempts<3 AND "
                                   "(status IN ('pending','retry') OR (status='running' AND lease_until<?)) "
                                   "ORDER BY created_at LIMIT 1", (space_id, now())).fetchone()
                if not job:
                    break
                conn.execute("UPDATE jobs SET status='running',attempts=attempts+1,lease_until=?,lease_token=?,updated_at=? WHERE id=?",
                             (now() + 120, lease, now(), job["id"]))
                job = dict(job)
            try:
                with self.store.transaction() as conn:
                    source = self._job_access(conn, actor, job)
                    row = conn.execute("SELECT * FROM source_revisions WHERE source_id=? AND revision=?",
                                       (source["id"], job["source_revision"])).fetchone()
                    content = bytes(row["body"]).decode("utf-8")
                    if extractor.remote:
                        require(self._processing_settings(conn, actor, space_id)["allow_remote_processing"],
                                "remote_processing_disabled", "Enable remote processing explicitly before model calls.", 403)
                candidates = extractor.extract(content)
                require(isinstance(candidates, list) and len(candidates) <= 64,
                        "invalid_extraction", "Extractor must return a bounded candidate list.")
                with self.store.transaction(write=True) as conn:
                    source = self._job_access(conn, actor, job)
                    if extractor.remote:
                        require(self._processing_settings(conn, actor, space_id)["allow_remote_processing"],
                                "remote_processing_disabled", "Processing policy changed before publication.", 403)
                    live = conn.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()
                    require(live["lease_token"] == lease and live["status"] == "running",
                            "stale_lease", "Job lease no longer belongs to this worker.", 409)
                    count = 0
                    for candidate in candidates:
                        require(candidate.quote in content and candidate.kind in {"fact", "observation", "inference", "rule_candidate"}
                                and bool(candidate.statement.strip()) and len(candidate.statement) <= 4000,
                                "invalid_extraction", "Extractor returned unsupported evidence.")
                        eligible = source["authority"] == "authoritative" and candidate.kind == "fact" and exact_fact(content, candidate)
                        state = "active" if eligible or candidate.kind == "observation" else "pending"
                        if eligible and candidate.claim_key:
                            for other in conn.execute("SELECT * FROM memories WHERE space_id=? AND claim_key=? AND status='active'",
                                                      (space_id, candidate.claim_key)):
                                if self._evidence_readable(conn, actor, space_id, other["evidence"]) \
                                        and other["statement"].strip().casefold() != candidate.statement.strip().casefold():
                                    state = "conflict"
                        ident = "memory_" + sha(dumps([source["id"], job["source_revision"], candidate.statement]))[:32]
                        evidence = [{"source_id": source["id"], "revision": job["source_revision"]}]
                        old_memory = conn.execute("SELECT * FROM memories WHERE id=?", (ident,)).fetchone()
                        conn.execute("INSERT OR IGNORE INTO memories VALUES(?,?,?,?,?,?,?,1,?,?,NULL,?)",
                                     (ident, space_id, candidate.statement, candidate.claim_key, candidate.kind,
                                      dumps(evidence), state, now(), row["effective_at"], extractor.name))
                        revision = 1
                        if old_memory and old_memory["status"] == "stale":
                            revision = old_memory["revision"] + 1
                            conn.execute("UPDATE memories SET status=?,revision=? WHERE id=?", (state, revision, ident))
                        conn.execute("INSERT OR IGNORE INTO memory_history VALUES(?,?,?,?,?,?)",
                                     (ident, revision, state, actor.principal_id, "Source extraction", now()))
                        count += 1
                    conn.execute("UPDATE jobs SET status='done',error_code=NULL,extractor=?,lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=?",
                                 (extractor.name, now(), job["id"]))
                    audit(conn, actor, "learning.publish", job["id"], space_id, {"count": count, "extractor": extractor.name})
                    results.append({"job_id": job["id"], "status": "done", "candidates": count})
            except Exception as error:
                code = error.code if isinstance(error, BrainError) else "processing_failed"
                with self.store.transaction(write=True) as conn:
                    live = conn.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()
                    if live["lease_token"] == lease:
                        blocked = code in {"forbidden", "unauthenticated", "not_found", "stale_job", "remote_processing_disabled"}
                        state = "blocked" if blocked else "failed" if live["attempts"] >= 3 else "retry"
                        conn.execute("UPDATE jobs SET status=?,error_code=?,lease_until=NULL,lease_token=NULL,updated_at=? WHERE id=?",
                                     (state, code, now(), job["id"]))
                    else:
                        state = live["status"]
                results.append({"job_id": job["id"], "status": state, "error_code": code})
        return results

    def list_jobs(self, actor, space_id):
        with self.store.transaction() as conn:
            authorize(conn, actor, space_id, "read")
            result = []
            for row in conn.execute("SELECT * FROM jobs WHERE space_id=? ORDER BY created_at DESC", (space_id,)):
                if self._source_readable(conn, actor, row["source_id"]):
                    result.append({k: row[k] for k in ("id", "source_id", "source_revision", "status", "attempts", "error_code", "extractor", "updated_at")})
            return result

    def retry_job(self, actor, job_id):
        with self.store.transaction(write=True) as conn:
            job = conn.execute("SELECT j.* FROM jobs j JOIN spaces s ON s.id=j.space_id WHERE j.id=? AND s.org_id=?",
                               (job_id, actor.org_id)).fetchone()
            require(job is not None, "not_found", "Job not found.", 404)
            authorize(conn, actor, job["space_id"], "process")
            self._source(conn, actor, job["source_id"])
            require(job["status"] in {"failed", "retry", "blocked"}, "invalid_state", "Job cannot be retried now.", 409)
            conn.execute("UPDATE jobs SET status='pending',attempts=0,error_code=NULL,requested_by=?,requested_credential=?,updated_at=? WHERE id=?",
                         (actor.principal_id, actor.credential_id, now(), job_id))
            audit(conn, actor, "job.retry", job_id, job["space_id"])
            return {"status": "pending"}
