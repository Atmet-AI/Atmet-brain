from pathlib import Path
import tempfile
import unittest

from atmet_brain import Brain, BrainError
from atmet_brain.rpc import dispatch


class ExternalConnectorsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.brain = Brain(Path(self.tmp.name) / "company")
        self.owner = self.brain.bootstrap("example")
        self.actor = self.brain.authenticate(self.owner["token"])
        self.space = self.brain.create_space(self.actor, "sales")["id"]
        self.connector = self.brain.register_external_connector(self.actor, self.space, "example-crm", "fixture-account")["id"]
        self.item = {"external_id": "item-1", "title": "Example", "content": "Fact[delivery]: Five days."}

    def fails(self, code, function, *args, **kwargs):
        with self.assertRaises(BrainError) as failure:function(*args, **kwargs)
        self.assertEqual(code, failure.exception.code)

    def test_batch_stages_content_and_replay_is_idempotent(self):
        value = dispatch(self.brain, self.actor, "connectors.batch", {"connector_id": self.connector, "items": [self.item], "checkpoint": {"cursor": "first"}})
        self.assertEqual("pending_classification", value["sources"][0]["status"])
        self.assertEqual([], self.brain.search(self.actor, self.space, "Five")["results"])
        repeated = self.brain.apply_connector_batch(self.actor, self.connector, [self.item], checkpoint={"cursor": "first"})
        self.assertEqual("unchanged", repeated["status"])
        with self.brain.store.transaction() as conn:self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM source_revisions").fetchone()[0])

    def test_omissions_are_not_deletions_and_checkpoint_is_checked(self):
        self.brain.apply_connector_batch(self.actor, self.connector, [self.item], checkpoint={"cursor": "first"})
        self.fails("checkpoint_conflict", self.brain.apply_connector_batch, self.actor, self.connector, [], checkpoint={"cursor": "second"})
        self.brain.apply_connector_batch(self.actor, self.connector, [], checkpoint={"cursor": "second"}, expected_checkpoint={"cursor": "first"})
        with self.brain.store.transaction() as conn:self.assertEqual("intake", conn.execute("SELECT status FROM sources").fetchone()[0])

    def test_explicit_deletion_and_reappearance_are_restricted(self):
        self.brain.apply_connector_batch(self.actor, self.connector, [self.item])
        self.brain.apply_connector_batch(self.actor, self.connector, [], ["item-1"], {"cursor": "deleted"})
        with self.brain.store.transaction() as conn:self.assertEqual("revoked", conn.execute("SELECT status FROM sources").fetchone()[0])
        result = self.brain.apply_connector_batch(self.actor, self.connector, [self.item], checkpoint={"cursor": "returned"}, expected_checkpoint={"cursor": "deleted"})
        self.assertEqual(2, result["sources"][0]["revision"])
        self.assertEqual("pending_classification", result["sources"][0]["status"])

    def test_reader_and_other_company_cannot_ingest_or_purge(self):
        reader = self.brain.add_team_member(self.actor, "Reader", [self.space], "reader")
        actor = self.brain.authenticate(reader["token"])
        self.fails("forbidden", self.brain.apply_connector_batch, actor, self.connector, [self.item])
        self.fails("forbidden", self.brain.purge_connector, actor, self.connector, True)
        other = self.brain.provision_organization("other")
        self.fails("not_found", self.brain.apply_connector_batch, self.brain.authenticate(other["token"]), self.connector, [])

    def test_disconnect_blocks_sync_and_purge_erases_retained_bodies(self):
        self.brain.apply_connector_batch(self.actor, self.connector, [self.item])
        self.brain.disable_connector(self.actor, self.connector)
        self.fails("connector_disabled", self.brain.apply_connector_batch, self.actor, self.connector, [])
        self.fails("erase_confirmation", self.brain.purge_connector, self.actor, self.connector)
        self.assertEqual(1, self.brain.purge_connector(self.actor, self.connector, True)["sources"])
        with self.brain.store.transaction() as conn:
            self.assertEqual(b"", conn.execute("SELECT body FROM source_revisions").fetchone()[0])
            self.assertEqual("deleted", conn.execute("SELECT status FROM sources").fetchone()[0])

    def test_permanent_erasure_wins_over_provider_replay(self):
        value = self.brain.apply_connector_batch(self.actor, self.connector, [self.item])
        self.brain.erase_source(self.actor, value["sources"][0]["id"])
        result = self.brain.apply_connector_batch(self.actor, self.connector, [self.item], checkpoint={"cursor": "later"})
        self.assertEqual([], result["sources"])

    def test_invalid_and_duplicate_batches_do_not_advance_checkpoint(self):
        self.fails("connector_duplicate", self.brain.apply_connector_batch, self.actor, self.connector, [self.item], ["item-1"])
        self.fails("invalid_connector_item", self.brain.apply_connector_batch, self.actor, self.connector, [{**self.item, "permissions": ["*"]}])
        self.fails("connector_limit", self.brain.apply_connector_batch, self.actor, self.connector, [self.item] * 501)
        self.fails("external_adapter_required", self.brain.sync_connector, self.actor, self.connector)

    def test_registration_has_no_provider_credentials_and_same_binding_reuses_id(self):
        self.assertEqual(self.connector, self.brain.register_external_connector(self.actor, self.space, "example-crm", "fixture-account")["id"])
        self.fails("invalid_connector", self.brain.register_connector, self.actor, self.space, "external", {"provider": "crm", "account": "example", "token": "forbidden"})

    def test_rename_retains_ids_access_and_requires_current_name(self):
        reader = self.brain.add_team_member(self.actor, "Reader", [self.space], "reader")
        self.fails("forbidden", self.brain.rename_space, self.brain.authenticate(reader["token"]), self.space, "new", "sales")
        result = self.brain.rename_space(self.actor, self.space, "revenue", "sales")
        self.assertEqual(self.space, result["id"])
        self.assertEqual("revenue", self.brain.list_spaces(self.brain.authenticate(reader["token"]))[0]["slug"])
        self.fails("revision_conflict", self.brain.rename_space, self.actor, self.space, "new", "sales")
        self.brain.create_space(self.actor, "finance")
        self.fails("already_exists", self.brain.rename_space, self.actor, self.space, "finance", "revenue")

    def test_pending_artifacts_are_explicit_and_not_shared_with_readers(self):
        artifact=self.brain.propose_artifact(self.actor,self.space,'skill','example',{'instructions':'Review before use','description':'A pending example skill'},idempotency_key='draft')
        self.assertEqual([],self.brain.list_artifacts(self.actor,self.space))
        listed=self.brain.list_artifacts(self.actor,self.space,include_pending=True)
        self.assertEqual(artifact['id'],listed[0]['id'])
        self.assertEqual('pending',listed[0]['state'])
        reader=self.brain.add_team_member(self.actor,'Reader',[self.space],'reader')
        with self.assertRaises(BrainError):self.brain.list_artifacts(self.brain.authenticate(reader['token']),self.space,include_pending=True)


if __name__ == "__main__":unittest.main()
