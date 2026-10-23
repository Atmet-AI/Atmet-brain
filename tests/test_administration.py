"""Human-bound security changes and fail-closed document intake across adapters."""

import concurrent.futures
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from atmet_brain import Brain, BrainError
from atmet_brain.auth import ROLES
from atmet_brain.backups import generate_backup_key
from atmet_brain.client import Client
from atmet_brain.mcp import MCPServer
from atmet_brain.rpc import dispatch
from atmet_brain.server import make_server

PASSWORD = "Fictional administration passphrase 2026!"


class AdministrationCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "company";self.brain = Brain(self.home)
        self.owner = self.brain.bootstrap("company", "Owner");self.actor = self.brain.authenticate(self.owner["token"])
        self.finance = self.brain.create_space(self.actor, "finance")["id"]
        self.operations = self.brain.create_space(self.actor, "operations")["id"]
        self.brain.setup_account(self.actor, "owner", PASSWORD)
        self.session = self.brain.login("company", "owner", PASSWORD);self.human = self.brain.authenticate(self.session["token"])
        self.control = self.brain.create_control_credential(self.human);self.agent = self.brain.authenticate(self.control["token"])
        self.employee = self.brain.add_team_member(self.actor, "Operations employee", [self.finance, self.operations], "user")
        self.reader = self.brain.authenticate(self.employee["token"])
        finance = self.brain.add_team_member(self.actor, "Finance employee", [self.finance], "user")
        self.finance_actor = self.brain.authenticate(finance["token"])
        self.group = self.brain.create_group(self.actor, "Finance and owners", [self.actor.principal_id, self.finance_actor.principal_id])["id"]
        self.counter = 0

    def fails(self, code, method, *args, **kwargs):
        with self.assertRaises(BrainError) as error:method(*args, **kwargs)
        self.assertEqual(code, error.exception.code);return error.exception

    def propose(self, operation, params, actor=None, key=None):
        self.counter += 1
        return self.brain.propose_admin_change(actor or self.agent, operation, params, "Requested by the human company owner", key or "request-" + str(self.counter))

    def approve(self, proposal):
        return self.brain.review_admin_change(self.human, proposal["id"], proposal["digest"], True, PASSWORD)

    def rule(self, *, key="salary-privacy", terms=None, audience=None, decision="release", connector=None):
        return {"key": key, "name": "Salary access", "space_ids": [self.finance], "terms_any": terms or ["salary", "salaries", "payroll"],
                "connector_id": connector, "audience": audience or ["group:" + self.group], "decision": decision}

    def activate(self, rule=None):
        head = self.brain.list_access_rules(self.agent)["policy_revision"]
        return self.approve(self.propose("rules.upsert", {"rule": rule or self.rule(), "expected_policy_revision": head}))

    def source(self, content="Salary confidential", key="salary", actor=None):
        return self.brain.put_source(actor or self.actor, self.finance, key, key, content)

    def release(self, source, audience=None):
        return self.approve(self.propose("intake.release", {"source_id": source["id"], "expected_revision": source["revision"],
                      "audience": audience or ["space"], "classification": "Human reviewed exact fictional document"}))

    def test_new_document_is_not_retrievable_or_processable_until_reviewed(self):
        source = self.source(actor=self.reader)
        self.assertEqual("pending_classification", source["status"])
        self.assertEqual([], self.brain.list_sources(self.reader, self.finance))
        self.assertEqual([], self.brain.search(self.reader, self.finance, "Salary")["results"])
        self.fails("not_found", self.brain.get_source, self.reader, source["id"])
        self.fails("not_found", self.brain.get_source, self.human, source["id"])
        self.assertEqual([], self.brain.run_jobs(self.actor, self.finance))
        self.assertEqual(source["id"], self.brain.list_intake(self.agent)[0]["id"])
        self.assertEqual("Salary confidential", self.brain.inspect_intake(self.agent, source["id"])["content"])
        self.fails("forbidden", self.brain.inspect_intake, self.reader, source["id"])
        self.release(source)
        self.assertEqual("Salary confidential", self.brain.get_source(self.reader, source["id"])["content"])
        self.assertEqual("applied", self.brain.list_admin_changes(self.agent)[0]["state"])

    def test_proposal_is_not_application_and_agent_cannot_approve(self):
        change = self.propose("spaces.create", {"name": "marketing"})
        self.assertEqual("pending", change["state"])
        self.assertNotIn("marketing", [s["slug"] for s in self.brain.list_spaces(self.actor)])
        self.fails("forbidden", self.brain.create_space, self.agent, "marketing")
        self.fails("forbidden", self.brain.review_admin_change, self.agent, change["id"], change["digest"], True, PASSWORD)
        self.fails("unknown_method", dispatch, self.brain, self.human, "admin.review", {})
        self.approve(change)
        self.assertIn("marketing", [s["slug"] for s in self.brain.list_spaces(self.actor)])
        self.fails("change_not_pending", self.approve, change)

    def test_wrong_password_forged_digest_and_rejection_do_not_mutate(self):
        change = self.propose("spaces.create", {"name": "marketing"})
        self.fails("invalid_login", self.brain.review_admin_change, self.human, change["id"], change["digest"], True, "wrong")
        self.fails("revision_conflict", self.brain.review_admin_change, self.human, change["id"], "0" * 64, True, PASSWORD)
        result = self.brain.review_admin_change(self.human, change["id"], change["digest"], False, PASSWORD)
        self.assertEqual("rejected", result["state"])
        self.assertNotIn("marketing", [s["slug"] for s in self.brain.list_spaces(self.actor)])

    def test_rule_requires_human_approval_and_unknown_documents_stay_restricted(self):
        change = self.propose("rules.upsert", {"rule": self.rule(), "expected_policy_revision": 0})
        self.assertEqual([], self.brain.list_access_rules(self.agent)["rules"])
        self.approve(change)
        salary = self.source();general = self.source("Invoice terms", "invoice")
        self.assertEqual("accepted", salary["status"])
        self.assertEqual("pending_classification", general["status"])
        self.assertEqual("Salary confidential", self.brain.get_source(self.finance_actor, salary["id"])["content"])
        self.fails("not_found", self.brain.get_source, self.reader, salary["id"])
        self.fails("forbidden", self.brain.inspect_intake, self.reader, salary["id"])

    def test_all_matching_rules_intersect_and_hold_wins(self):
        self.activate()
        self.activate(self.rule(key="extra-review", terms=["salary"], audience=["principal:" + self.actor.principal_id], decision="hold"))
        source = self.source()
        self.assertEqual("pending_classification", source["status"])
        self.fails("not_found", self.brain.get_source, self.finance_actor, source["id"])
        self.fails("classification_hold", self.propose, "intake.release", {"source_id": source["id"], "expected_revision": 1, "audience": ["space"], "classification": "Do not bypass hold"})
        detail = self.brain.inspect_intake(self.agent, source["id"])
        self.assertEqual(2, len(detail["evaluation"]["clauses"]))

    def test_word_match_cannot_authorize_workspace_wide_auto_release(self):
        self.fails("trusted_binding_required", self.activate, self.rule(audience=["space"], terms=["invoice"]))
        root = Path(self.tmp.name) / "approved-invoices";root.mkdir();(root / "invoice.txt").write_text("Invoice amount")
        connector = self.brain.register_connector(self.actor, self.finance, "files", {"root": str(root)})["id"]
        self.activate(self.rule(key="approved-invoices", audience=["space"], terms=["invoice"], connector=connector))
        imported = self.brain.sync_connector(self.actor, connector)["sources"][0]
        self.assertEqual("accepted", imported["status"])
        self.assertEqual("Invoice amount", self.brain.get_source(self.reader, imported["id"])["content"])
        self.assertEqual("pending_classification", self.source("Invoice amount", "not-bound")["status"])

    def test_history_restrictions_survive_content_changes_and_manual_reclassification(self):
        self.activate();source = self.source()
        self.fails("not_found", self.brain.put_source, self.reader, self.finance, "salary", "salary", "Invoice", expected_revision=1)
        updated = self.brain.put_source(self.actor, self.finance, "salary", "salary", "Invoice only", expected_revision=1)
        self.assertEqual("accepted", updated["status"])  # Title still matches salary.
        self.fails("not_found", self.brain.get_source, self.reader, source["id"], 1)
        self.release(updated)
        self.fails("not_found", self.brain.get_source, self.reader, source["id"], 1)
        self.assertEqual("Salary confidential", self.brain.get_source(self.finance_actor, source["id"], 1)["content"])

    def test_changed_policy_invalidates_earlier_classifications_before_search(self):
        source = self.source("General budget", "budget");self.release(source)
        self.assertEqual("General budget", self.brain.get_source(self.reader, source["id"])["content"])
        self.activate()
        self.fails("not_found", self.brain.get_source, self.reader, source["id"])
        self.assertIn(source["id"], [x["id"] for x in self.brain.list_intake(self.agent)])
        self.release(source)
        self.assertEqual("General budget", self.brain.get_source(self.reader, source["id"])["content"])

    def test_changed_document_or_policy_blocks_stale_approval(self):
        source = self.source("Original", "budget")
        change = self.propose("intake.release", {"source_id": source["id"], "expected_revision": 1, "audience": ["space"], "classification": "Reviewed original"})
        self.brain.put_source(self.actor, self.finance, "budget", "budget", "Replacement", expected_revision=1)
        self.fails("revision_conflict", self.approve, change)
        first = self.propose("rules.upsert", {"rule": self.rule(), "expected_policy_revision": 0})
        self.activate(self.rule(key="different"));self.fails("revision_conflict", self.approve, first)

    def test_current_authority_and_agent_parent_revocation_apply_at_review(self):
        change = self.propose("spaces.create", {"name": "marketing"})
        self.brain.revoke_credential(self.human, self.control["credential_id"])
        self.fails("unauthenticated", self.approve, change)
        self.assertNotIn("marketing", [s["slug"] for s in self.brain.list_spaces(self.actor)])

    def test_expiry_idempotency_and_cross_company_identity(self):
        first = self.propose("spaces.create", {"name": "marketing"}, key="same")
        self.assertEqual(first["id"], self.propose("spaces.create", {"name": "marketing"}, key="same")["id"])
        self.fails("idempotency_conflict", self.propose, "spaces.create", {"name": "other"}, key="same")
        other = self.brain.provision_organization("other");actor = self.brain.authenticate(other["token"])
        self.fails("not_found", self.brain.get_admin_change, actor, first["id"])
        with self.brain.store.transaction(write=True) as conn:conn.execute("UPDATE admin_changes SET expires_at=1 WHERE id=?", (first["id"],))
        self.fails("change_not_pending", self.approve, first)

    def test_membership_review_revokes_active_employee_sessions(self):
        member = next(x for x in self.brain.list_members(self.actor) if x["id"] == self.reader.principal_id)
        change = self.propose("members.access", {"principal_id": self.reader.principal_id, "access": [{"space_id": self.operations, "role": "reader"}], "expected_revision": member["revision"]})
        self.approve(change);self.fails("unauthenticated", self.brain.whoami, self.reader)

    def test_group_changes_are_reviewed_and_stale_group_plan_is_rejected(self):
        change = self.propose("groups.membership", {"group_id": self.group, "principal_ids": [self.actor.principal_id]})
        self.brain.remove_group_member(self.actor, self.group, self.finance_actor.principal_id)
        self.fails("revision_conflict", self.approve, change)
        change = self.propose("groups.membership", {"group_id": self.group, "principal_ids": [self.actor.principal_id, self.reader.principal_id]})
        self.approve(change)
        self.activate();source = self.source()
        self.assertEqual("Salary confidential", self.brain.get_source(self.reader, source["id"])["content"])

    def test_pending_sources_cannot_be_released_by_legacy_source_access(self):
        source = self.source()
        self.fails("classification_required", self.brain.set_source_access, self.human, source["id"], ["space"], True)
        self.fails("not_found", self.brain.get_source, self.human, source["id"])

    def test_partial_failure_rolls_back_mutation_and_review(self):
        change = self.propose("spaces.create", {"name": "marketing"})
        with patch("atmet_brain.administration.audit", side_effect=RuntimeError("fixture failure")):
            with self.assertRaises(RuntimeError):self.approve(change)
        self.assertEqual("pending", self.brain.get_admin_change(self.human, change["id"])["state"])
        self.assertNotIn("marketing", [s["slug"] for s in self.brain.list_spaces(self.actor)])

    def test_two_reviewers_cannot_apply_same_request_twice(self):
        change = self.propose("spaces.create", {"name": "marketing"})
        def review(_):
            try:return self.approve(change)["state"]
            except BrainError as error:return error.code
        with concurrent.futures.ThreadPoolExecutor(2) as pool:results=list(pool.map(review,range(2)))
        self.assertCountEqual(["applied","change_not_pending"],results)

    def test_mcp_has_proposal_tools_but_never_password_or_review_tool(self):
        mcp = MCPServer(self.brain, self.control["token"], allow_admin=True)
        self.assertIn("result", mcp.handle({"jsonrpc":"2.0","id":1,"method":"initialize"}))
        tools = mcp.handle({"jsonrpc":"2.0","id":2,"method":"tools/list"})["result"]["tools"]
        names = [t["name"] for t in tools]
        self.assertIn("brain_propose_admin_change", names)
        self.assertNotIn("brain_review_admin_change", names)
        self.assertTrue(all("password" not in t["inputSchema"]["properties"] for t in tools))
        response=mcp.handle({"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"brain_propose_admin_change","arguments":{"operation":"spaces.create","params":{"name":"marketing"},"reason":"Owner asked","idempotency_key":"mcp"}}})
        self.assertFalse(response["result"]["isError"])
        self.assertNotIn("marketing", [s["slug"] for s in self.brain.list_spaces(self.actor)])

    def test_http_human_approval_checks_private_password_and_credential(self):
        server=make_server(self.brain,port=0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(lambda:(server.shutdown(),server.server_close(),thread.join(2)))
        endpoint="http://127.0.0.1:"+str(server.server_port)
        agent=Client(endpoint,self.control["token"]);human=Client(endpoint,self.session["token"])
        proposal=agent.call("admin.propose",operation="spaces.create",params={"name":"marketing"},reason="Owner asked",idempotency_key="http")
        request=dict(change_id=proposal["id"],expected_digest=proposal["digest"],approve=True,password=PASSWORD)
        self.fails("forbidden",agent.review_admin_change,**request)
        self.assertEqual("applied",human.review_admin_change(**request)["state"])

    def test_restore_revokes_controls_pending_changes_rules_and_classifications(self):
        self.activate();source=self.source();pending=self.propose("spaces.create",{"name":"marketing"})
        key=Path(self.tmp.name)/"backup.key";snapshot=Path(self.tmp.name)/"backup.atmet";generate_backup_key(key);self.brain.create_backup(snapshot,key)
        journal=self.brain.flush_recovery_journal()["path"];destination=Path(self.tmp.name)/"restored";Brain.restore_backup(snapshot,destination,key);restored=Brain(destination);restored.finish_recovery(journal,"Recovery owner",True)
        self.fails("unauthenticated",restored.authenticate,self.control["token"])
        with restored.store.transaction() as conn:
            self.assertEqual("rejected",conn.execute("SELECT state FROM admin_changes WHERE id=?",(pending["id"],)).fetchone()[0])
            self.assertEqual("disabled",conn.execute("SELECT state FROM security_rules").fetchone()[0])
            self.assertEqual("pending",conn.execute("SELECT decision FROM source_security WHERE source_id=?",(source["id"],)).fetchone()[0])

    def test_compatibility_setting_cannot_override_approved_or_existing_restrictions(self):
        self.activate();source=self.source()
        (self.home/"config.toml").write_text("[brain]\nrequire_document_classification=false\n")
        reopened=Brain(self.home)
        self.assertEqual("pending_classification",reopened.put_source(self.actor,self.finance,"unknown","Unknown","Unclassified")["status"])
        self.fails("not_found",reopened.get_source,self.reader,source["id"])

    def test_old_salary_restrictions_survive_when_new_title_and_body_no_longer_match(self):
        self.activate();source=self.source()
        updated=self.brain.put_source(self.actor,self.finance,"salary","Invoice","Invoice total",expected_revision=1)
        self.assertEqual("pending_classification",updated["status"])
        self.release(updated)
        self.fails("not_found",self.brain.get_source,self.reader,source["id"])
        self.fails("not_found",self.brain.get_source,self.reader,source["id"],1)
        self.assertEqual("Salary confidential",self.brain.get_source(self.finance_actor,source["id"],1)["content"])

    def test_agent_cannot_mark_new_source_authoritative_without_review(self):
        source=self.source("Fact[delivery.window]: Delivery takes five days.","delivery")
        self.fails("forbidden",self.brain.put_source,self.agent,self.finance,"another","Another","Fact[x]: Safe",authority="authoritative")
        change=self.propose("sources.authority",{"source_id":source["id"],"expected_revision":1,"authority":"authoritative"})
        self.approve(change);self.fails("not_found",self.brain.get_source,self.reader,source["id"])
        self.release(source);self.brain.run_jobs(self.actor,self.finance)
        self.assertTrue(self.brain.search(self.reader,self.finance,"Delivery")["results"])

    def test_source_erasure_redacts_intake_reason_and_administration_previews(self):
        source=self.source("Confidential amount","budget")
        secret="Fictional confidential salary detail for erasure"
        proposal=self.propose("intake.release",{"source_id":source["id"],"expected_revision":1,"audience":["space"],"classification":secret})
        self.approve(proposal);self.approve(self.propose("sources.erase",{"source_id":source["id"],"expected_revision":1}))
        with self.brain.store.transaction() as conn:
            data=' '.join(str(tuple(r)) for r in conn.execute("SELECT params,reason,snapshot,result FROM admin_changes"))
            self.assertNotIn(secret,data)
            self.assertEqual('',conn.execute("SELECT reason FROM source_security WHERE source_id=?",(source["id"],)).fetchone()[0])
        self.fails("not_found",self.brain.inspect_intake,self.agent,source["id"])

    def test_revoked_workspace_access_hides_old_source_change_previews(self):
        source=self.source("Fictional private budget","budget")
        proposal=self.propose("intake.release",{"source_id":source["id"],"expected_revision":1,"audience":["space"],"classification":"Reviewed"})
        with self.brain.store.transaction() as conn:
            grant=conn.execute("SELECT id FROM grants WHERE principal_id=? AND space_id=? AND revoked=0",(self.actor.principal_id,self.finance)).fetchone()[0]
        self.brain.revoke_grant(self.actor,grant)
        self.fails("forbidden",self.brain.get_admin_change,self.agent,proposal["id"])
        self.assertNotIn(proposal["id"],[x["id"] for x in self.brain.list_admin_changes(self.agent)])
        self.fails("forbidden",self.approve,proposal)

    def test_private_review_attempt_limit_survives_restart(self):
        proposal=self.propose("spaces.create",{"name":"marketing"})
        for _ in range(8):self.fails("invalid_login",self.brain.review_admin_change,self.human,proposal["id"],proposal["digest"],True,"wrong")
        restarted=Brain(self.home)
        self.fails("auth_rate_limited",restarted.review_admin_change,self.human,proposal["id"],proposal["digest"],True,PASSWORD)

    def test_unclassified_document_does_not_reach_external_extractor(self):
        self.source()
        extractor=unittest.mock.Mock(remote=True)
        self.assertEqual([],self.brain.run_jobs(self.actor,self.finance,extractor=extractor))
        extractor.extract.assert_not_called()

    def test_another_contributor_cannot_replace_someone_elses_pending_document(self):
        self.source(actor=self.reader)
        self.fails("forbidden",self.brain.put_source,self.finance_actor,self.finance,"salary","salary","Replacement",expected_revision=1)

    def test_forged_approval_and_owner_role_cannot_enter_proposal_parameters(self):
        self.fails("invalid_admin_change",self.propose,"spaces.create",{"name":"marketing","approve":True})
        self.fails("invalid_access",self.propose,"members.access",{"principal_id":self.reader.principal_id,"expected_revision":1,"access":[{"space_id":self.finance,"role":"owner"}]})
        self.fails("invalid_admin_change",self.propose,"principals.create",{"name":"Fake admin","org_admin":True})

    def test_existing_schema_three_source_keeps_access_but_changes_require_classification(self):
        from atmet_brain.config import Settings
        legacy=Brain(self.home,Settings(require_document_classification=False))
        source=legacy.put_source(self.actor,self.finance,"existing","Existing","Previously imported")
        with self.brain.store.transaction(write=True) as conn:conn.execute("UPDATE meta SET value='3' WHERE key='schema_version'")
        upgraded=Brain(self.home)
        self.assertEqual("Previously imported",upgraded.get_source(self.reader,source["id"])["content"])
        updated=upgraded.put_source(self.actor,self.finance,"existing","Existing","Changed",expected_revision=1)
        self.assertEqual("pending_classification",updated["status"])
        self.fails("not_found",upgraded.get_source,self.reader,source["id"])

    def test_actual_schema_three_backup_envelope_is_supported(self):
        import io,sqlite3,zipfile
        from cryptography.fernet import Fernet
        from atmet_brain.backups import MAGIC
        from atmet_brain.util import dumps,sha
        base=Path(self.tmp.name);database=base/"old.sqlite3"
        original=self.brain.store.connect();target=sqlite3.connect(database);original.backup(target);original.close()
        target.execute("PRAGMA foreign_keys=OFF")
        for table in ["admin_changes","control_credentials","source_security","security_rule_history","security_rules","security_heads"]:target.execute("DROP TABLE "+table)
        target.execute("UPDATE meta SET value='3' WHERE key='schema_version'");instance=target.execute("SELECT value FROM meta WHERE key='instance_id'").fetchone()[0];sequence=target.execute("SELECT COALESCE(MAX(sequence),0) FROM recovery_events").fetchone()[0];target.commit();target.close()
        raw=database.read_bytes();manifest={"format":"atmet-brain-backup-v1","engine_version":"0.7.0","schema_version":3,"instance_id":instance,"recovery_sequence":sequence,"database_sha256":sha(raw),"database_bytes":len(raw)}
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:archive.writestr('manifest.json',dumps(manifest));archive.writestr('brain.sqlite3',raw)
        key=Fernet.generate_key();(base/'old.key').write_bytes(key);(base/'old.atmet').write_bytes(MAGIC+Fernet(key).encrypt(stream.getvalue()))
        destination=base/'old-restored';Brain.restore_backup(base/'old.atmet',destination,base/'old.key')
        restored=Brain(destination)
        with restored.store.transaction() as conn:self.assertEqual('4',conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0])
        self.fails("unauthenticated",restored.authenticate,self.session['token'])

    def test_group_membership_cannot_widen_content_without_affected_workspace_management(self):
        self.activate();self.source()
        with self.brain.store.transaction() as conn:grant=conn.execute("SELECT id FROM grants WHERE principal_id=? AND space_id=? AND revoked=0",(self.actor.principal_id,self.finance)).fetchone()[0]
        self.brain.revoke_grant(self.actor,grant)
        self.fails("forbidden",self.propose,"groups.membership",{"group_id":self.group,"principal_ids":[self.actor.principal_id,self.reader.principal_id]})

    def test_task_configuration_cannot_disable_intake(self):
        self.fails("invalid_config",self.brain.propose_artifact,self.actor,self.finance,"config","unsafe",{"require_document_classification":False},idempotency_key="unsafe-config")
