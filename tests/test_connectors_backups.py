import base64
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from atmet_brain import Brain, BrainError
from atmet_brain.backups import generate_backup_key
from atmet_brain.config import Settings
from atmet_brain.connectors import gmail
from atmet_brain.skills import install_skill

from tests.test_core import CoreCase


class ConnectorCase(CoreCase):
    # This subclass intentionally adds only its own tests below. The loader in
    # load_tests filters inherited CoreCase tests to avoid duplicate execution.
    def directory(self):
        root = Path(self.tmp.name) / "documents"
        root.mkdir()
        (root / "catalogue.txt").write_text("Fact[price]: The price is 100 USD.")
        connector = self.brain.register_connector(self.actor, self.space, "files", {"root": str(root)}, authority="authoritative")
        return root, connector["id"]

    def test_file_sync_revisions_and_deletion(self):
        root, connector = self.directory()
        first = self.brain.sync_connector(self.actor, connector)
        ident = first["sources"][0]["id"]
        self.brain.run_jobs(self.actor, self.space)
        (root / "catalogue.txt").write_text("Fact[price]: The price is 120 USD.")
        second = self.brain.sync_connector(self.actor, connector)
        self.assertEqual(2, second["sources"][0]["revision"])
        self.brain.run_jobs(self.actor, self.space)
        self.assertIn("120", self.brain.list_memories(self.actor, self.space)[0]["statement"])
        (root / "catalogue.txt").unlink()
        self.brain.sync_connector(self.actor, connector)
        self.assertEqual([], self.brain.list_sources(self.actor, self.space))
        self.fails("not_found", self.brain.get_source, self.actor, ident)

    def test_file_reappearance_reprocesses_memory(self):
        root, connector = self.directory()
        self.brain.sync_connector(self.actor, connector)
        self.brain.run_jobs(self.actor, self.space)
        content = (root / "catalogue.txt").read_text()
        (root / "catalogue.txt").unlink()
        self.brain.sync_connector(self.actor, connector)
        (root / "catalogue.txt").write_text(content)
        self.brain.sync_connector(self.actor, connector)
        self.brain.run_jobs(self.actor, self.space)
        self.assertTrue(self.brain.list_memories(self.actor, self.space))

    def test_file_symlink_is_never_imported(self):
        root, connector = self.directory()
        outside = Path(self.tmp.name) / "secret.txt"
        outside.write_text("Secret outside selected root")
        (root / "link.txt").symlink_to(outside)
        result = self.brain.sync_connector(self.actor, connector)
        self.assertEqual(1, result["resources"])
        self.assertEqual([], self.brain.search(self.actor, self.space, "Secret outside")["results"])

    def test_disabled_connector_blocks_raw_and_derived_reads(self):
        _, connector = self.directory()
        first = self.brain.sync_connector(self.actor, connector)
        self.brain.run_jobs(self.actor, self.space)
        self.brain.disable_connector(self.actor, connector)
        self.assertEqual([], self.brain.list_sources(self.actor, self.space))
        self.assertEqual([], self.brain.search(self.actor, self.space, "price")["results"])
        self.fails("connector_disabled", self.brain.sync_connector, self.actor, connector)

    def test_file_replay_does_not_revive_permanent_erasure(self):
        _, connector = self.directory()
        first = self.brain.sync_connector(self.actor, connector)
        self.brain.erase_source(self.actor, first["sources"][0]["id"])
        self.brain.sync_connector(self.actor, connector)
        self.assertEqual([], self.brain.list_sources(self.actor, self.space))

    def test_gmail_adapter_has_no_send_operations(self):
        seen = []
        def fetch(url):
            seen.append(url)
            if "format=full" in url:
                return {"id": "m1", "payload": {"mimeType": "text/plain", "headers": [{"name": "Subject", "value": "Quotation"}],
                                                    "body": {"data": base64.urlsafe_b64encode(b"Please quote three products.").decode().rstrip("=")}}}
            return {"messages": [{"id": "m1"}]}
        with patch.dict(os.environ, {"ATMET_GMAIL_TEST": "fixture-token"}):
            result = gmail.scan({"token_env": "ATMET_GMAIL_TEST", "label_ids": ["Label_sales"]}, fetch)
        self.assertEqual(1, len(result))
        self.assertIn("three products", result[0]["content"])
        self.assertTrue(all(url.startswith(gmail.BASE) for url in seen))
        self.assertIn("labelIds=Label_sales", seen[0])

    def test_failed_snapshot_does_not_deselect_every_source(self):
        _, connector = self.directory()
        self.brain.sync_connector(self.actor, connector)
        def broken(config):
            raise RuntimeError("Provider temporarily unavailable")
        self.fails("connector_failed", self.brain.sync_connector, self.actor, connector, _scan=broken)
        self.assertEqual(1, len(self.brain.list_sources(self.actor, self.space)))


class BackupCase(CoreCase):
    def backup(self):
        key = Path(self.tmp.name) / "key"
        archive = Path(self.tmp.name) / "snapshot.atmet"
        generate_backup_key(key)
        self.brain.create_backup(archive, key)
        return archive, key

    def test_backup_is_encrypted_and_tampering_fails(self):
        self.source("Unique private payload")
        archive, key = self.backup()
        self.assertNotIn(b"Unique private payload", archive.read_bytes())
        damaged = bytearray(archive.read_bytes())
        damaged[-30] ^= 1
        archive.write_bytes(damaged)
        self.fails("invalid_backup", Brain.restore_backup, archive, Path(self.tmp.name) / "restored", key)

    def test_restore_never_overwrites_a_home(self):
        archive, key = self.backup()
        self.fails("already_exists", Brain.restore_backup, archive, self.home, key)

    def test_restore_quarantines_and_replays_later_erasure(self):
        removed = self.source("Unique erased customer data")
        retained = self.source("Retained current source")
        self.brain.run_jobs(self.actor, self.space)
        artifact = self.artifact(evidence=self.proof(removed))
        archive, key = self.backup()
        self.brain.erase_source(self.actor, removed["id"])
        journal = Path(self.tmp.name) / "latest-journal.json"
        self.brain.flush_recovery_journal(journal)
        home = Path(self.tmp.name) / "restored"
        Brain.restore_backup(archive, home, key)
        restored = Brain(home)
        self.fails("unauthenticated", restored.authenticate, self.owner["token"])
        self.fails("journal_confirmation", restored.finish_recovery, journal, "New owner")
        result = restored.finish_recovery(journal, "New owner", True)
        actor = restored.authenticate(result["owners"][0]["token"])
        self.assertEqual([], restored.list_sources(actor, self.space))
        restored.set_source_access(actor, retained["id"], ["principal:" + actor.principal_id], True)
        self.assertEqual(1, len(restored.list_sources(actor, self.space)))
        with restored.store.transaction() as conn:
            self.assertEqual(b"", bytes(conn.execute("SELECT body FROM source_revisions WHERE source_id=?", (removed["id"],)).fetchone()[0]))
        self.fails("not_found", restored.get_artifact, actor, artifact["id"])
        self.fails("unauthenticated", restored.authenticate, self.owner["token"])

    def test_recovery_rejects_other_installation_journal(self):
        archive, key = self.backup()
        home = Path(self.tmp.name) / "restored"
        Brain.restore_backup(archive, home, key)
        journal = self.home / "recovery-journal.json"
        value = json.loads(journal.read_text())
        value["instance_id"] = "wrong"
        journal.write_text(json.dumps(value))
        self.fails("invalid_journal", Brain(home).finish_recovery, journal, "Owner", True)

    def test_backups_preserve_skills_and_configuration(self):
        self.brain = Brain(self.home, Settings(max_context_chars=8000))
        package = Path(__file__).resolve().parents[1] / "examples/skills/prepare-quotation"
        skill = install_skill(self.brain, self.actor, self.space, package)
        self.brain.review_artifact(self.actor, skill["id"], 1, True, "Reviewed")
        archive, key = self.backup()
        home = Path(self.tmp.name) / "restored"
        Brain.restore_backup(archive, home, key)
        restored = Brain(home)
        self.assertEqual(8000, restored.settings.max_context_chars)
        result = restored.finish_recovery(self.home / "recovery-journal.json", "Owner", True)
        actor = restored.authenticate(result["owners"][0]["token"])
        self.assertEqual(skill["id"], restored.list_artifacts(actor, self.space, "skill")[0]["id"])


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for cls in [ConnectorCase, BackupCase]:
        for name, value in cls.__dict__.items():
            if name.startswith("test_"):
                suite.addTest(cls(name))
    return suite
