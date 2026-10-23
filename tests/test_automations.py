import copy
from decimal import localcontext
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
import unittest

from tests.legacy_imports import legacy_imports
from atmet_brain import Brain, BrainError
from atmet_brain.auth import ROLES
from atmet_brain.automations import python_script
from atmet_brain.backups import generate_backup_key
from atmet_brain.client import Client
from atmet_brain.mcp import MCPServer
from atmet_brain.rpc import dispatch, input_schema
from atmet_brain.server import make_server


CASES = [
    ({"records": [{"department": "Sales", "amount": "10.10"}, {"department": "Ops", "amount": "2.30"},
                  {"department": "Sales", "amount": "0.20"}]},
     {"totals": [{"group": "Ops", "total": "2.30"}, {"group": "Sales", "total": "10.30"}], "count": 3}),
    ({"records": [{"department": "Ops", "amount": "12.40"}, {"department": "Sales", "amount": "3.05"}]},
     {"totals": [{"group": "Ops", "total": "12.40"}, {"group": "Sales", "total": "3.05"}], "count": 2}),
    ({"records": [{"department": "Sales", "amount": "9.99"}, {"department": "Sales", "amount": "-1.00"}]},
     {"totals": [{"group": "Sales", "total": "8.99"}], "count": 2}),
]


class AutomationCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.brain = Brain(legacy_imports(self.root / "brain"))
        self.owner = self.brain.bootstrap("example-company")
        self.actor = self.brain.authenticate(self.owner["token"])
        self.space = self.brain.create_space(self.actor, "operations")["id"]
        self.source = self.brain.put_source(self.actor, self.space, "report", "Activity report",
                                            "Fictional company task inputs and accepted outputs.")
        self.proof = [{"source_id": self.source["id"], "revision": 1}]
        self.workflow = self.brain.propose_artifact(self.actor, self.space, "workflow", "weekly-report",
                        {"instructions": "Produce a report from the supplied records.",
                         "steps": [{"id": "report", "instruction": "Group and total the supplied decimal amounts."}]},
                        evidence=self.proof, idempotency_key="workflow")
        self.brain.review_artifact(self.actor, self.workflow["id"], 1, True, "Reviewed")

    def fails(self, code, function, *args, **kwargs):
        with self.assertRaises(BrainError) as result:
            function(*args, **kwargs)
        self.assertEqual(code, result.exception.code)

    def observe(self, index, run_key=None, actor=None, succeeded=True, inputs=None, output=None):
        request, response = CASES[index]
        return self.brain.record_task_run(actor or self.actor, self.space, run_key or "run-" + str(index),
                    "weekly-report", self.workflow["id"], inputs if inputs is not None else request,
                    output if output is not None else response, self.proof, succeeded=succeeded, ai_tokens=100)

    def train(self, approve=True):
        for index in range(3):
            result = self.observe(index)
        candidate = result["automation"]
        self.assertEqual("pending_review", candidate["status"])
        if approve:
            self.brain.review_artifact(self.actor, candidate["artifact_id"], 1, True, "Reviewed generated Python and examples")
        return candidate

    def execute(self, actor=None, inputs=None, key="execution"):
        return self.brain.run_task(actor or self.actor, self.space, "weekly-report", self.workflow["id"],
                                   inputs if inputs is not None else CASES[0][0], key)

    def member(self, role):
        person = self.brain.create_principal(self.actor, "Example " + role)
        grant = self.brain.grant(self.actor, person["id"], self.space, ROLES[role])
        credential = self.brain.create_credential(self.actor, person["id"])
        return self.brain.authenticate(credential["token"]), credential, grant

    def test_repetition_compiles_pending_code_and_never_publishes_it(self):
        candidate = self.train(approve=False)
        self.assertEqual("records.aggregate", candidate["template"])
        self.assertEqual("fallback_required", self.execute()["status"])
        draft = self.brain.get_artifact(self.actor, candidate["artifact_id"], revision=1)
        self.assertIn("Decimal", draft["body"]["python_source"])
        self.assertEqual(3, len(draft["body"]["training_run_ids"]))

    def test_approved_script_handles_new_data_with_exact_decimals_and_no_model(self):
        self.train()
        result = self.execute(inputs={"records": [{"department": "Sales", "amount": "0.10"},
                                                  {"department": "Sales", "amount": "0.20"}]})
        self.assertEqual({"totals": [{"group": "Sales", "total": "0.30"}], "count": 2}, result["output"])
        self.assertEqual(0, result["model_calls"])
        self.assertFalse(result["external_actions_authorized"])
        with localcontext() as ambient:
            ambient.prec = 2
            large = self.execute(inputs={"records": [{"department": "Ops", "amount": "999999999999.99"},
                                                     {"department": "Ops", "amount": "0.01"}]}, key="precision")
        self.assertEqual("1000000000000.00", large["output"]["totals"][0]["total"])

    def test_identical_inputs_are_not_distinct_learning_cases(self):
        for index in range(4):
            result = self.observe(0, run_key="duplicate-" + str(index))
        self.assertEqual("learning", result["automation"]["status"])
        self.assertEqual(1, result["automation"]["distinct_successful_inputs"])

    def test_failed_example_prevents_automatic_compilation(self):
        self.observe(0, succeeded=False)
        self.observe(1)
        result = self.observe(2)
        self.assertEqual("observed_failure_requires_review", result["automation"]["reason"])

    def test_judgment_outputs_stay_with_agent(self):
        for index in range(3):
            result = self.observe(index, output={"recommendation": "Requires business judgment " + str(index)})
        self.assertEqual("no_supported_deterministic_recipe", result["automation"]["reason"])

    def test_malformed_records_do_not_crash_learning(self):
        for index in range(3):
            result = self.observe(index, inputs={"records": index}, output={"records": []})
        self.assertEqual("ai_required", result["automation"]["status"])

    def test_observation_replay_is_idempotent_and_conflicting_keys_fail(self):
        first = self.observe(0)
        self.assertEqual(first["id"], self.observe(0)["id"])
        self.fails("idempotency_conflict", self.observe, 1, run_key="run-0")

    def test_execution_replay_is_idempotent_and_does_not_duplicate_history(self):
        self.train()
        self.assertEqual(self.execute()["execution_id"], self.execute()["execution_id"])
        self.fails("idempotency_conflict", self.execute, inputs=CASES[1][0])
        with self.brain.store.transaction() as conn:
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM automation_executions").fetchone()[0])

    def test_reader_can_check_route_but_cannot_run_or_record(self):
        self.train()
        reader, _, _ = self.member("reader")
        route = self.brain.route_task(reader, self.space, "weekly-report", self.workflow["id"], CASES[0][0])
        self.assertEqual("script", route["mode"])
        self.fails("forbidden", self.execute, actor=reader)
        self.fails("forbidden", self.observe, 0, run_key="reader", actor=reader)

    def test_worker_can_execute_but_not_publish(self):
        candidate = self.train(approve=False)
        worker, _, _ = self.member("worker")
        self.fails("forbidden", self.brain.review_artifact, worker, candidate["artifact_id"], 1, True, "Attempt")
        self.brain.review_artifact(self.actor, candidate["artifact_id"], 1, True, "Reviewed")
        self.assertEqual("completed", self.execute(actor=worker)["status"])

    def test_revoked_credential_stops_replay(self):
        self.train()
        worker, key, _ = self.member("worker")
        self.execute(actor=worker)
        self.brain.revoke_credential(self.actor, key["credential_id"])
        self.fails("unauthenticated", self.execute, actor=worker)

    def test_out_of_contract_input_returns_fallback_without_a_model(self):
        self.train()
        for request in [{"records": [{"department": "Sales", "amount": "unknown"}]},
                        {"records": [{"amount": "10.00"}]}, {"records": [], "run_shell": "anything"},
                        {"records": [{"department": "Sales", "amount": "1.00"}]} | {"extra": True}]:
            result = self.execute(inputs=request)
            self.assertEqual("fallback_required", result["status"])
            self.assertFalse(result["model_called"])

    def test_workflow_change_invalidates_approved_script(self):
        self.train()
        old = self.brain.get_artifact(self.actor, self.workflow["id"])
        update = self.brain.propose_artifact(self.actor, self.space, "workflow", old["slug"], old["body"],
                    expected_revision=1, artifact_id=old["id"], evidence=self.proof, idempotency_key="workflow-change")
        self.brain.review_artifact(self.actor, update["id"], 2, True, "New workflow version")
        self.assertEqual("fallback_required", self.execute()["status"])
        for index in range(3):
            result = self.observe(index, run_key="version-2-" + str(index))
        self.assertEqual("pending_review", result["automation"]["status"])

    def test_new_applicable_policy_invalidates_a_script(self):
        self.train()
        policy = self.brain.propose_artifact(self.actor, self.space, "policy", "report-approval",
                    {"instructions": "A manager must review the report."}, idempotency_key="new-policy")
        self.brain.review_artifact(self.actor, policy["id"], 1, True, "Reviewed rule")
        self.assertEqual("fallback_required", self.execute()["status"])

    def test_pending_candidate_cannot_publish_after_policy_change(self):
        candidate = self.train(approve=False)
        policy = self.brain.propose_artifact(self.actor, self.space, "policy", "new-rule",
                    {"instructions": "Use new reporting rules."}, idempotency_key="new-rule")
        self.brain.review_artifact(self.actor, policy["id"], 1, True, "Reviewed")
        self.fails("automation_context_changed", self.brain.review_artifact,
                   self.actor, candidate["artifact_id"], 1, True, "Stale approval")

    def test_conflicting_output_pauses_current_recipe(self):
        self.train()
        self.observe(0, run_key="correction", output={"totals": [], "count": 0})
        self.assertEqual("fallback_required", self.execute()["status"])

    def test_conflicting_output_blocks_pending_approval(self):
        candidate = self.train(approve=False)
        self.observe(0, run_key="correction", output={"totals": [], "count": 0})
        self.fails("regression_failed", self.brain.review_artifact, self.actor, candidate["artifact_id"], 1, True, "Attempt")

    def test_ambiguous_approved_recipes_fall_back(self):
        candidate = self.train()
        item = self.brain.get_artifact(self.actor, candidate["artifact_id"])
        duplicate = self.brain.propose_artifact(self.actor, self.space, "automation", "another-recipe", item["body"],
                    evidence=item["evidence"], dependencies=item["dependencies"], idempotency_key="second")
        self.brain.review_artifact(self.actor, duplicate["id"], 1, True, "Reviewed second recipe")
        self.assertEqual("fallback_required", self.execute()["status"])

    def test_sensitive_training_evidence_is_not_exposed_in_lists_or_audit(self):
        source = self.brain.put_source(self.actor, self.space, "private", "Private report", "Private example data.",
                                      audience=["principal:" + self.actor.principal_id])
        self.proof = [{"source_id": source["id"], "revision": 1}]
        candidate = self.train()
        reviewer, _, _ = self.member("reviewer")
        self.assertEqual([], self.brain.list_task_runs(reviewer, self.space, "weekly-report", include_payload=True))
        self.assertFalse(any(a["kind"] == "automation" for a in self.brain.list_artifacts(reviewer, self.space)))
        self.assertFalse(any(a["operation"] == "task.observe" for a in self.brain.list_audit(reviewer, self.space)))
        self.fails("not_found", self.brain.get_artifact, reviewer, candidate["artifact_id"], revision=1)

    def test_payload_history_requires_history_permission(self):
        self.observe(0)
        worker, _, _ = self.member("worker")
        self.assertEqual(1, len(self.brain.list_task_runs(worker, self.space, "weekly-report")))
        self.fails("forbidden", self.brain.list_task_runs, worker, self.space, "weekly-report", include_payload=True)

    def test_observed_conflict_cannot_be_bypassed_with_new_artifact_identity(self):
        candidate = self.train()
        item = self.brain.get_artifact(self.actor, candidate["artifact_id"])
        self.observe(0, run_key="correction", output={"totals": [], "count": 0})
        duplicate = self.brain.propose_artifact(self.actor, self.space, "automation", "renamed", item["body"],
                    evidence=item["evidence"], dependencies=item["dependencies"], idempotency_key="renamed")
        self.fails("regression_failed", self.brain.review_artifact, self.actor, duplicate["id"], 1, True, "Attempt")

    def test_changed_source_or_audience_stops_routing_and_hides_runs(self):
        self.train()
        worker, _, _ = self.member("worker")
        self.brain.set_source_access(self.actor, self.source["id"], ["principal:" + self.actor.principal_id])
        self.assertEqual([], self.brain.list_task_runs(worker, self.space, "weekly-report"))
        self.fails("not_found", self.execute, actor=worker)

    def test_source_revision_change_stops_execution(self):
        self.train()
        self.brain.put_source(self.actor, self.space, "report", "Activity report", "New report definition.", expected_revision=1)
        self.fails("stale_evidence", self.execute)

    def test_erasure_removes_training_payloads_and_retracts_recipes(self):
        candidate = self.train()
        self.brain.erase_source(self.actor, self.source["id"])
        with self.brain.store.transaction() as conn:
            rows = conn.execute("SELECT inputs,output,succeeded FROM task_runs").fetchall()
            self.assertTrue(all(tuple(row) == ("{}", "{}", 0) for row in rows))
            body, state = conn.execute("SELECT body,state FROM artifact_versions WHERE artifact_id=?",
                                       (candidate["artifact_id"],)).fetchone()
            self.assertEqual(("{}", "retracted"), (body, state))

    def test_arbitrary_python_cannot_be_proposed_as_an_automation(self):
        candidate = self.train(approve=False)
        draft = self.brain.get_artifact(self.actor, candidate["artifact_id"], revision=1)
        draft["body"]["python_source"] += "\nprint('unreviewed extra code')\n"
        self.fails("invalid_automation", self.brain.propose_artifact, self.actor, self.space, "automation", "injected",
                   draft["body"], evidence=self.proof, dependencies=draft["dependencies"], idempotency_key="injected")

    def test_modified_parameters_must_reproduce_observed_outputs(self):
        candidate = self.train(approve=False)
        draft = self.brain.get_artifact(self.actor, candidate["artifact_id"], revision=1)
        body = copy.deepcopy(draft["body"])
        body["parameters"] = {"group_by": "amount", "value_field": "department"}
        body["python_source"] = python_script(body["template"], body["parameters"])
        proposal = self.brain.propose_artifact(self.actor, self.space, "automation", "bad-recipe", body,
                    evidence=self.proof, dependencies=draft["dependencies"], idempotency_key="bad-recipe")
        self.fails("regression_failed", dispatch, self.brain, self.actor, "artifacts.review",
                   {"artifact_id": proposal["id"], "expected_revision": 1, "approve": True, "reason": "Attempt"})

    def test_normalization_is_inferred_and_exported_script_matches_core(self):
        data = [
            ({"records": [{"email": " Z@EXAMPLE.COM ", "name": " Zoe "}, {"email": "A@EXAMPLE.COM", "name": " Ada "}]},
             {"records": [{"email": "a@example.com", "name": "Ada"}, {"email": "z@example.com", "name": "Zoe"}]}),
            ({"records": [{"email": "B@EXAMPLE.COM", "name": " Ben "}, {"email": "B@EXAMPLE.COM", "name": " Ben "}]},
             {"records": [{"email": "b@example.com", "name": "Ben"}]}),
            ({"records": [{"email": "C@EXAMPLE.COM", "name": " Cam "}]},
             {"records": [{"email": "c@example.com", "name": "Cam"}]})]
        for index, (request, response) in enumerate(data):
            result = self.observe(index, inputs=request, output=response)
        candidate = result["automation"]
        self.assertEqual("records.normalize", candidate["template"])
        self.brain.review_artifact(self.actor, candidate["artifact_id"], 1, True, "Reviewed normalization semantics")
        artifact = self.brain.get_artifact(self.actor, candidate["artifact_id"])
        script = self.root / "normalize.py"
        script.write_text(artifact["body"]["python_source"])
        process = subprocess.run([sys.executable, str(script)], input=json.dumps(data[0][0]), capture_output=True, text=True, check=True)
        self.assertEqual(data[0][1], json.loads(process.stdout))
        self.assertEqual(data[0][1], self.execute(inputs=data[0][0])["output"])

    def test_mcp_execution_is_opt_in_and_never_overrides_core_grants(self):
        self.train()
        reader, credential, _ = self.member("reader")
        request = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "brain_run_task", "arguments":
                   {"space_id": self.space, "task_key": "weekly-report", "workflow_id": self.workflow["id"],
                    "inputs": CASES[0][0], "idempotency_key": "mcp"}}}
        default = MCPServer(self.brain, self.owner["token"])
        default.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(-32602, default.handle(request)["error"]["code"])
        restricted = MCPServer(self.brain, credential["token"], allow_automations=True)
        restricted.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertTrue(restricted.handle(request)["result"]["isError"])
        self.assertEqual("forbidden", json.loads(restricted.handle(request)["result"]["content"][0]["text"])["error"]["code"])

    def test_rpc_schemas_match_actual_json_and_boolean_inputs(self):
        schema = input_schema(self.brain, "tasks.record")
        self.assertEqual("object", schema["properties"]["inputs"]["type"])
        self.assertEqual("object", schema["properties"]["output"]["type"])
        self.assertEqual("boolean", schema["properties"]["succeeded"]["type"])

    def test_rest_executes_the_same_recipe_with_json_inputs(self):
        self.train()
        server = make_server(self.brain, "127.0.0.1", 0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = Client("http://127.0.0.1:" + str(server.server_port), self.owner["token"])
            result = client.call("tasks.run", space_id=self.space, task_key="weekly-report", workflow_id=self.workflow["id"],
                                 inputs=CASES[0][0], idempotency_key="http")
            self.assertEqual(CASES[0][1], result["output"])
            self.assertEqual(0, result["model_calls"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_mcp_executes_the_same_recipe_when_enabled_and_granted(self):
        self.train()
        server = MCPServer(self.brain, self.owner["token"], allow_automations=True)
        server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        response = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "brain_run_task", "arguments": {"space_id": self.space, "task_key": "weekly-report",
            "workflow_id": self.workflow["id"], "inputs": CASES[0][0], "idempotency_key": "mcp-success"}}})
        self.assertFalse(response["result"]["isError"])
        self.assertEqual(CASES[0][1], json.loads(response["result"]["content"][0]["text"])["output"])

    def test_backup_and_journal_recovery_do_not_revive_erased_training_data(self):
        self.train()
        key, backup, journal = self.root / "backup.key", self.root / "backup.atmet", self.root / "journal.json"
        generate_backup_key(key)
        self.brain.create_backup(backup, key)
        self.brain.erase_source(self.actor, self.source["id"])
        self.brain.flush_recovery_journal(journal)
        destination = self.root / "restored"
        Brain.restore_backup(backup, destination, key)
        restored = Brain(destination)
        restored.finish_recovery(journal, "Recovery owner", True)
        with restored.store.transaction() as conn:
            self.assertTrue(all(row[0] == "{}" for row in conn.execute("SELECT inputs FROM task_runs")))


if __name__ == "__main__":
    unittest.main()
