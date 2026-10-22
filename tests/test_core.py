import json
from pathlib import Path
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from atmet_brain import Brain, BrainError
from atmet_brain.auth import Actor, ROLES
from atmet_brain.config import Settings, validate_settings
from atmet_brain.extraction import Candidate, LocalExtractor
from atmet_brain.rpc import dispatch
from atmet_brain.skills import install_skill
from atmet_brain.util import dumps, uid


class CoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.brain = Brain(self.home)
        self.owner = self.brain.bootstrap("example")
        self.actor = self.brain.authenticate(self.owner["token"])
        self.space = self.brain.create_space(self.actor, "sales")["id"]

    def member(self, role="reader", name="Member"):
        principal = self.brain.create_principal(self.actor, name, "service")
        grant = self.brain.grant(self.actor, principal["id"], self.space, ROLES[role])
        key = self.brain.create_credential(self.actor, principal["id"])
        return self.brain.authenticate(key["token"]), key, grant

    def source(self, content="Fact[product.price]: Product price is 100 USD.", external=None, audience=None, authority="authoritative"):
        return self.brain.put_source(self.actor, self.space, external or uid("external"), "Example source", content,
                                     audience=audience, authority=authority)

    def proof(self, source):
        return [{"source_id": source["id"], "revision": source["revision"]}]

    def artifact(self, instructions="Approval is required.", kind="policy", name=None, evidence=None, body=None, dependencies=None, effective=None):
        proposal = self.brain.propose_artifact(self.actor, self.space, kind, name or uid("example"),
                                               body or {"instructions": instructions}, evidence=evidence,
                                               dependencies=dependencies, effective_at=effective, idempotency_key=uid("request"))
        self.brain.review_artifact(self.actor, proposal["id"], 1, True, "Reviewed example")
        return proposal

    def fails(self, code, function, *args, **kwargs):
        with self.assertRaises(BrainError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)

    def test_bootstrap_is_local_and_one_time(self):
        self.fails("already_initialized", self.brain.bootstrap)
        self.fails("unknown_method", dispatch, self.brain, self.actor, "bootstrap", {})

    def test_read_credential_cannot_write(self):
        reader, _, _ = self.member()
        self.fails("forbidden", self.brain.put_source, reader, self.space, "x", "x", "x")
        self.assertEqual([], self.brain.list_sources(reader, self.space))

    def test_space_boundary(self):
        reader, _, _ = self.member()
        hr = self.brain.create_space(self.actor, "hr")["id"]
        self.fails("forbidden", self.brain.search, reader, hr, "salary")
        self.assertNotIn(hr, [s["id"] for s in self.brain.list_spaces(reader)])

    def test_organization_boundary(self):
        other = self.brain.provision_organization("other")
        actor = self.brain.authenticate(other["token"])
        space = self.brain.create_space(actor, "other")["id"]
        self.brain.put_source(actor, space, "private", "Other company", "Other company secret")
        self.fails("not_found", self.brain.search, self.actor, space, "anything")

    def test_organization_admin_does_not_bypass_content_grants(self):
        principal = self.brain.create_principal(self.actor, "Billing administrator", "human", org_admin=True)
        key = self.brain.create_credential(self.actor, principal["id"])
        admin = self.brain.authenticate(key["token"])
        self.fails("forbidden", self.brain.search, admin, self.space, "anything")

    def test_revoked_credential_fails_existing_actor(self):
        reader, key, _ = self.member()
        self.brain.revoke_credential(self.actor, key["credential_id"])
        self.fails("unauthenticated", self.brain.search, reader, self.space, "price")

    def test_revoked_parent_revokes_child(self):
        reader, key, _ = self.member()
        child = self.brain.create_credential(reader)
        self.brain.revoke_credential(self.actor, key["credential_id"])
        self.fails("unauthenticated", self.brain.authenticate, child["token"])

    def test_narrow_credential_cannot_widen(self):
        key = self.brain.create_credential(self.actor, operations=["read"], space_ids=[self.space])
        narrow = self.brain.authenticate(key["token"])
        self.fails("forbidden", self.brain.create_credential, narrow, operations=["publish"])
        self.fails("forbidden", self.brain.create_space, narrow, "new")

    def test_credential_cannot_extend_expiry(self):
        key = self.brain.create_credential(self.actor, expires_at=time.time() + 30)
        narrow = self.brain.authenticate(key["token"])
        self.fails("forbidden", self.brain.create_credential, narrow, expires_at=time.time() + 100)

    def test_expired_credential(self):
        key = self.brain.create_credential(self.actor, expires_at=time.time() - 1)
        self.fails("unauthenticated", self.brain.authenticate, key["token"])

    def test_grant_revocation_is_immediate(self):
        reader, _, grant = self.member()
        self.brain.revoke_grant(self.actor, grant["id"])
        self.fails("forbidden", self.brain.search, reader, self.space, "price")

    def test_source_audience_filters_all_read_surfaces(self):
        reader, _, _ = self.member()
        source = self.source("Confidential payroll is 5000.", audience=["principal:" + self.actor.principal_id])
        self.brain.run_jobs(self.actor, self.space)
        self.assertEqual([], self.brain.search(reader, self.space, "payroll")["results"])
        self.assertEqual([], self.brain.list_sources(reader, self.space))
        self.assertEqual([], self.brain.graph(reader, self.space)["nodes"])
        self.fails("not_found", self.brain.get_source, reader, source["id"])

    def test_empty_audience_is_rejected(self):
        self.fails("invalid_audience", self.source, audience=[])

    def test_group_removal_changes_access(self):
        reader, _, _ = self.member()
        group = self.brain.create_group(self.actor, "Sales", [reader.principal_id, self.actor.principal_id])
        source = self.source(audience=["group:" + group["id"]])
        self.assertTrue(self.brain.get_source(reader, source["id"]))
        self.brain.remove_group_member(self.actor, group["id"], reader.principal_id)
        self.fails("not_found", self.brain.get_source, reader, source["id"])

    def test_source_update_requires_revision_and_invalidates_memory(self):
        source = self.source(external="catalogue")
        self.brain.run_jobs(self.actor, self.space)
        self.assertTrue(self.brain.list_memories(self.actor, self.space))
        self.fails("revision_conflict", self.brain.put_source, self.actor, self.space, "catalogue", "New", "Changed", authority="authoritative")
        updated = self.brain.put_source(self.actor, self.space, "catalogue", "New", "Fact[product.price]: Product price is 120 USD.",
                                         authority="authoritative", expected_revision=1)
        self.assertEqual(2, updated["revision"])
        self.assertEqual([], self.brain.list_memories(self.actor, self.space))
        self.brain.run_jobs(self.actor, self.space)
        self.assertIn("120", self.brain.list_memories(self.actor, self.space)[0]["statement"])

    def test_duplicate_capture_does_not_duplicate_job(self):
        self.source(external="same")
        duplicate = self.source(external="same")
        self.assertEqual("unchanged", duplicate["status"])
        self.assertEqual(1, len(self.brain.list_jobs(self.actor, self.space)))

    def test_ordinary_fact_and_policy_take_different_paths(self):
        self.source("Fact[price]: The price is 100 USD.\nPolicy: Manager approval is required.")
        self.brain.run_jobs(self.actor, self.space)
        memories = self.brain.list_memories(self.actor, self.space, True)
        self.assertEqual({"active", "pending"}, {m["status"] for m in memories})
        rule = next(m for m in memories if m["kind"] == "rule_candidate")
        self.fails("policy_requires_publication", self.brain.review_memory, self.actor, rule["id"], 1, True, "Attempt")

    def test_untrusted_fact_needs_review(self):
        self.source("Fact[price]: The price is 100 USD.", authority="observation")
        self.brain.run_jobs(self.actor, self.space)
        self.assertEqual([], self.brain.list_memories(self.actor, self.space))
        pending = self.brain.list_memories(self.actor, self.space, True)[0]
        self.brain.review_memory(self.actor, pending["id"], 1, True, "Checked evidence")
        self.assertEqual(1, len(self.brain.list_memories(self.actor, self.space)))

    def test_conflicting_authoritative_fact_is_reviewable(self):
        self.source("Fact[price]: The price is 100 USD.")
        self.brain.run_jobs(self.actor, self.space)
        self.source("Fact[price]: The price is 200 USD.")
        self.brain.run_jobs(self.actor, self.space)
        self.assertIn("conflict", [m["status"] for m in self.brain.list_memories(self.actor, self.space, True)])

    def test_no_resurrection_when_source_revoked_during_extraction(self):
        source = self.source()
        brain, actor = self.brain, self.actor
        class RacingExtractor(LocalExtractor):
            def extract(self, content):
                brain.set_source_access(actor, source["id"], ["space"], False)
                return super().extract(content)
        result = self.brain.run_jobs(self.actor, self.space, extractor=RacingExtractor())
        self.assertEqual("cancelled", result[0]["status"])
        self.assertEqual([], self.brain.list_memories(self.actor, self.space))

    def test_revoked_requester_cannot_feed_a_worker(self):
        self.source()
        worker, _, _ = self.member("worker")
        self.brain.revoke_credential(self.actor, self.owner["credential_id"])
        # Worker is also derived from the owner key, so lineage revocation blocks it.
        self.fails("unauthenticated", self.brain.run_jobs, worker, self.space)

    def test_extraction_retry_is_bounded(self):
        self.source()
        class Broken(LocalExtractor):
            def extract(self, content):
                raise RuntimeError("private provider response")
        self.brain.run_jobs(self.actor, self.space, 10, Broken())
        job = self.brain.list_jobs(self.actor, self.space)[0]
        self.assertEqual("failed", job["status"])
        self.assertEqual(3, job["attempts"])
        self.assertNotIn("private", json.dumps(job))

    def test_remote_processing_is_opt_in(self):
        self.source()
        class Remote(LocalExtractor):
            remote = True
            def extract(self, content):
                raise AssertionError("Must not call remote extraction")
        result = self.brain.run_jobs(self.actor, self.space, extractor=Remote())
        self.assertEqual("remote_processing_disabled", result[0]["error_code"])

    def test_invalid_extraction_cannot_publish(self):
        self.source()
        class Hallucination(LocalExtractor):
            def extract(self, content):
                return [Candidate("Invented fact", "fact", "Not in source", "price")]
        self.brain.run_jobs(self.actor, self.space, extractor=Hallucination())
        self.assertEqual([], self.brain.list_memories(self.actor, self.space))

    def test_agent_cannot_publish(self):
        worker, _, _ = self.member("worker")
        proposal = self.brain.propose_artifact(worker, self.space, "policy", "attempt", {"instructions": "New rule"}, idempotency_key="request")
        self.fails("forbidden", self.brain.review_artifact, worker, proposal["id"], 1, True, "Self approval")

    def test_idempotency_replay_and_conflict(self):
        params = dict(space_id=self.space, kind="policy", name="idempotent", body={"instructions": "Check approval"}, idempotency_key="key")
        a = self.brain.propose_artifact(self.actor, **params)
        self.assertEqual(a, self.brain.propose_artifact(self.actor, **params))
        params["body"] = {"instructions": "Changed"}
        self.fails("idempotency_conflict", self.brain.propose_artifact, self.actor, **params)

    def test_stale_review_is_rejected(self):
        first = self.brain.propose_artifact(self.actor, self.space, "policy", "stale", {"instructions": "One"}, idempotency_key="one")
        self.brain.propose_artifact(self.actor, self.space, "policy", "stale", {"instructions": "Two"}, 1, first["id"], idempotency_key="two")
        self.fails("revision_conflict", self.brain.review_artifact, self.actor, first["id"], 1, True, "Old review")

    def test_concurrent_writers_cannot_lose_an_update(self):
        first = self.artifact(name="concurrent")
        def update(number):
            try:
                self.brain.propose_artifact(self.actor, self.space, "policy", "concurrent", {"instructions": str(number)},
                                             1, first["id"], idempotency_key="parallel" + str(number))
                return "ok"
            except BrainError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(["ok", "revision_conflict"], list(pool.map(update, [1, 2])))

    def test_future_policy_does_not_apply_today(self):
        first = self.artifact(name="future", instructions="Current rule")
        later = time.time() + 1000
        self.brain.propose_artifact(self.actor, self.space, "policy", "future", {"instructions": "Future rule"}, 1,
                                     first["id"], effective_at=later, idempotency_key="future")
        self.brain.review_artifact(self.actor, first["id"], 2, True, "Scheduled")
        self.assertEqual("Current rule", self.brain.get_artifact(self.actor, first["id"])["body"]["instructions"])
        self.assertEqual("Future rule", self.brain.get_artifact(self.actor, first["id"], at=later + 1)["body"]["instructions"])

    def test_rollback_is_new_pending_revision(self):
        first = self.artifact(name="rollback", instructions="Original")
        self.brain.propose_artifact(self.actor, self.space, "policy", "rollback", {"instructions": "Changed"}, 1, first["id"], idempotency_key="change")
        self.brain.review_artifact(self.actor, first["id"], 2, True, "Change approved")
        rollback = self.brain.rollback_artifact(self.actor, first["id"], 1, 2, "Restore behavior", "rollback-key")
        self.assertEqual(3, rollback["revision"])
        self.assertEqual("pending_review", rollback["status"])
        self.brain.review_artifact(self.actor, first["id"], 3, True, "Rollback approved")
        self.assertEqual("Original", self.brain.get_artifact(self.actor, first["id"])["body"]["instructions"])
        self.assertEqual(3, len(self.brain.artifact_history(self.actor, first["id"])))

    def test_retired_artifact_does_not_fall_back(self):
        first = self.artifact(name="retire")
        self.brain.retire_artifact(self.actor, first["id"], 1, "No longer used")
        self.fails("not_found", self.brain.get_artifact, self.actor, first["id"])

    def test_skill_dependency_changes_require_revalidation(self):
        policy = self.artifact(name="rules")
        skill = self.artifact(kind="skill", name="quote", body={"description": "Prepare quotation", "instructions": "Use current approval", "resources": {}},
                              dependencies=[{"artifact_id": policy["id"], "revision": 1}])
        self.brain.propose_artifact(self.actor, self.space, "policy", "rules", {"instructions": "New approval rule"}, 1,
                                     policy["id"], idempotency_key="policy-change")
        self.brain.review_artifact(self.actor, policy["id"], 2, True, "Changed")
        self.fails("incomplete_context", self.brain.get_context, self.actor, self.space, "quote", [skill["id"]])

    def test_history_uses_current_source_access(self):
        reader, _, _ = self.member("publisher")
        source = self.source()
        artifact = self.artifact(evidence=self.proof(source))
        self.assertTrue(self.brain.get_artifact(reader, artifact["id"], revision=1))
        self.brain.set_source_access(self.actor, source["id"], ["principal:" + self.actor.principal_id], True)
        self.fails("not_found", self.brain.get_artifact, reader, artifact["id"], revision=1)

    def test_derived_memory_requires_all_evidence(self):
        reader, _, _ = self.member()
        public = self.source("Public source")
        private = self.source("Private payroll", audience=["principal:" + self.actor.principal_id])
        memory = self.brain.propose_memory(self.actor, self.space, "Combined payroll summary", self.proof(public) + self.proof(private))
        self.brain.review_memory(self.actor, memory["id"], 1, True, "Checked")
        self.assertEqual([], self.brain.search(reader, self.space, "payroll")["results"])

    def test_required_policy_never_silently_truncates(self):
        self.artifact(instructions="Mandatory approval. " * 100)
        self.fails("incomplete_context", self.brain.get_context, self.actor, self.space, "quote", max_chars=1000)

    def test_inaccessible_required_policy_returns_incomplete(self):
        reader, _, _ = self.member()
        private = self.source("Restricted rule", audience=["principal:" + self.actor.principal_id])
        self.artifact(evidence=self.proof(private))
        self.fails("incomplete_context", self.brain.get_context, reader, self.space, "quote")

    def test_context_manifest_loses_access_after_revocation(self):
        reader, _, _ = self.member()
        source = self.source()
        envelope = self.brain.get_context(reader, self.space, "product price")
        self.assertTrue(self.brain.get_manifest(reader, envelope["manifest_id"]))
        self.brain.set_source_access(self.actor, source["id"], ["principal:" + self.actor.principal_id], True)
        self.fails("not_found", self.brain.get_manifest, reader, envelope["manifest_id"])

    def test_config_cannot_grant_access_and_only_narrows(self):
        self.fails("invalid_config", validate_settings, {"permissions": ["admin"]})
        self.artifact(kind="config", body={"max_context_chars": 1000, "allow_remote_processing": True})
        envelope = self.brain.get_context(self.actor, self.space, "unknown", max_chars=10000)
        self.assertEqual(1000, envelope["budget_chars"])
        self.assertFalse(self.brain.get_manifest(self.actor, envelope["manifest_id"])["revisions"]["settings"]["allow_remote_processing"])

    def test_source_erasure_removes_derived_content(self):
        source = self.source()
        self.brain.run_jobs(self.actor, self.space)
        artifact = self.artifact(evidence=self.proof(source))
        self.brain.erase_source(self.actor, source["id"])
        self.assertEqual([], self.brain.search(self.actor, self.space, "price")["results"])
        self.fails("not_found", self.brain.get_source, self.actor, source["id"])
        self.fails("not_found", self.brain.get_artifact, self.actor, artifact["id"])
        with self.brain.store.transaction() as conn:
            self.assertEqual(b"", bytes(conn.execute("SELECT body FROM source_revisions WHERE source_id=?", (source["id"],)).fetchone()[0]))

    def test_discovery_uses_permitted_case_events(self):
        source = self.source("A request and quotation were recorded.")
        for case in ["deal_a", "deal_b"]:
            for order, activity in enumerate(["request", "draft", "review"]):
                self.brain.record_event(self.actor, self.space, case + activity, case, activity, self.proof(source), happened_at=100 + order)
        result = self.brain.discover_workflow(self.actor, self.space)
        self.assertEqual(2, result["visible_case_count"])
        self.assertEqual(["request", "draft", "review"], [step["instruction"] for step in result["workflow_body"]["steps"]])
        self.assertFalse(result["publication_authorized"])

    def test_event_replays_are_idempotent(self):
        source = self.source()
        first = self.brain.record_event(self.actor, self.space, "e1", "c1", "request", self.proof(source))
        second = self.brain.record_event(self.actor, self.space, "e1", "c1", "request", self.proof(source))
        self.assertEqual(first["id"], second["id"])
        self.fails("event_conflict", self.brain.record_event, self.actor, self.space, "e1", "c2", "request", self.proof(source))

    def test_export_never_contains_credentials(self):
        self.source()
        exported = dumps(self.brain.export_space(self.actor, self.space))
        self.assertNotIn(self.owner["token"], exported)
        self.assertNotIn("token_hash", exported)

    def test_rpc_cannot_accept_identity_or_private_injectors(self):
        self.fails("invalid_params", dispatch, self.brain, self.actor, "search", {"space_id": self.space, "query": "x", "actor": "CEO"})
        self.fails("invalid_params", dispatch, self.brain, self.actor, "jobs.run", {"space_id": self.space, "extractor": "malicious"})

    def test_portable_skill_import_and_resource_read(self):
        package = Path(__file__).resolve().parents[1] / "examples/skills/prepare-quotation"
        proposal = install_skill(self.brain, self.actor, self.space, package)
        self.brain.review_artifact(self.actor, proposal["id"], 1, True, "Package reviewed")
        resource = self.brain.skill_resource(self.actor, proposal["id"], "templates/quotation.md")
        self.assertFalse(resource["executable"])
        self.assertIn("Quotation", resource["content"])

    def test_skill_resource_traversal_is_rejected(self):
        self.fails("invalid_resource", self.brain.propose_artifact, self.actor, self.space, "skill", "unsafe",
                   {"description": "Unsafe", "instructions": "Example", "resources": {"../secret": "x"}}, idempotency_key="unsafe")

    def test_known_time_excludes_later_approval(self):
        checkpoint = time.time() - 10
        artifact = self.artifact()
        self.fails("not_found", self.brain.get_artifact, self.actor, artifact["id"], known_at=checkpoint)

    def test_artifact_diff_uses_retained_bodies(self):
        artifact = self.artifact(name="diff", instructions="Before")
        self.brain.propose_artifact(self.actor, self.space, "policy", "diff", {"instructions": "After"}, 1, artifact["id"], idempotency_key="after")
        self.brain.review_artifact(self.actor, artifact["id"], 2, True, "Reviewed")
        diff = self.brain.artifact_diff(self.actor, artifact["id"], 1, 2)
        self.assertIn('-  "instructions": "Before"', diff["diff"])
        self.assertIn('+  "instructions": "After"', diff["diff"])

    def test_publisher_cannot_blindly_replace_denied_derived_artifact(self):
        publisher, _, _ = self.member("publisher")
        private = self.source("Private procedure", audience=["principal:" + self.actor.principal_id])
        artifact = self.artifact(name="private-rule", evidence=self.proof(private))
        self.fails("not_found", self.brain.propose_artifact, publisher, self.space, "policy", "private-rule",
                   {"instructions": "Blind replacement"}, 1, artifact["id"], idempotency_key="blind")

    def test_context_warns_about_visible_fact_conflict(self):
        self.source("Fact[price]: The product price is 100 USD.")
        self.brain.run_jobs(self.actor, self.space)
        self.source("Fact[price]: The product price is 200 USD.")
        self.brain.run_jobs(self.actor, self.space)
        self.assertTrue(any("conflict" in warning for warning in self.brain.get_context(self.actor, self.space, "product price")["warnings"]))

    def test_future_source_is_not_current_task_evidence(self):
        self.brain.put_source(self.actor, self.space, "future-price", "Future price", "Fact[future.price]: The future price is 500 USD.",
                               authority="authoritative", effective_at=time.time() + 1000)
        self.brain.run_jobs(self.actor, self.space)
        self.assertEqual([], self.brain.search(self.actor, self.space, "future price")["results"])

    def test_explicit_source_effective_time_change_creates_revision(self):
        source = self.source(external="time-change")
        result = self.brain.put_source(self.actor, self.space, "time-change", "Example source", "Fact[product.price]: Product price is 100 USD.",
                                       authority="authoritative", expected_revision=1, effective_at=time.time() + 1000)
        self.assertEqual(2, result["revision"])
