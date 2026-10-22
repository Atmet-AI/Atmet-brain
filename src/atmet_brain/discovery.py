"""Evidence-linked process discovery from explicit case identifiers."""

from collections import Counter, defaultdict

from .auth import authorize
from .db import audit
from .errors import require
from .util import dumps, loads, now, text, timestamp, uid


class DiscoveryMixin:
    def record_event(self, actor, space_id, event_key, case_id, activity, evidence, happened_at=None):
        text(event_key, "event_key", 200)
        text(case_id, "case_id", 200)
        text(activity, "activity", 200)
        with self.store.transaction(write=True) as conn:
            authorize(conn, actor, space_id, "observe")
            proof = self._evidence(conn, actor, space_id, evidence)
            old = conn.execute("SELECT * FROM process_events WHERE space_id=? AND event_key=?", (space_id, event_key)).fetchone()
            if old:
                require(old["case_id"] == case_id and old["activity"] == activity and old["evidence"] == dumps(proof),
                        "event_conflict", "Event key already identifies different evidence.", 409)
                return {"id": old["id"], "status": "unchanged"}
            ident = uid("event")
            conn.execute("INSERT INTO process_events VALUES(?,?,?,?,?,?,?,?)",
                         (ident, space_id, event_key, case_id, activity, dumps(proof), timestamp(happened_at), actor.principal_id))
            audit(conn, actor, "event.observe", ident, space_id)
            return {"id": ident, "status": "recorded"}

    def discover_workflow(self, actor, space_id):
        with self.store.transaction() as conn:
            authorize(conn, actor, space_id, "read")
            cases, evidence = defaultdict(list), []
            for row in conn.execute("SELECT * FROM process_events WHERE space_id=? ORDER BY happened_at,id", (space_id,)):
                if self._evidence_readable(conn, actor, space_id, row["evidence"]):
                    cases[row["case_id"]].append(row["activity"])
                    for ref in loads(row["evidence"]):
                        if ref not in evidence:
                            evidence.append(ref)
            require(bool(cases), "insufficient_evidence", "No permitted linked process events are available.", 409)
            sequences = Counter(tuple(steps) for steps in cases.values())
            typical, support = sequences.most_common(1)[0]
            edges = Counter((left, right) for steps in cases.values() for left, right in zip(steps, steps[1:]))
            return {"status": "draft", "publication_authorized": False, "visible_case_count": len(cases),
                    "typical_sequence_support": support, "observed_transitions": [
                        {"from": a, "to": b, "observations": count} for (a, b), count in edges.most_common()],
                    "workflow_body": {"instructions": "Draft inferred from observed event order. Confirm required steps and exceptions before publication.",
                                      "description": "Observed business process", "trigger": typical[0],
                                      "steps": [{"id": "step_" + str(i + 1), "instruction": step} for i, step in enumerate(typical)],
                                      "exceptions": ["Unobserved or incomplete cases need review."]},
                    "evidence": evidence[:50], "evidence_truncated": len(evidence) > 50,
                    "questions": ["Which observed steps are required?", "What conditions require approval?",
                                  "Which exceptions and off-system steps are missing?"],
                    "limitations": ["Case IDs are provided by the integration; semantic cross-tool identity matching is not performed.",
                                    "Observed time order does not prove causality or company policy."]}
