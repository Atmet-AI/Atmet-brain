import contextlib
import io
import json
import os
from pathlib import Path
import plistlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from atmet_brain import Brain, BrainError, __version__
from atmet_brain.cli import execute, parser
from atmet_brain.maintenance import maintenance
from atmet_brain.services import service_spec, update_services
from atmet_brain.updating import inspect_home, inventory, running_processes, verify_records
from atmet_brain.terminal import Console
from atmet_brain.util import sha


class UpdatingCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "company"
        self.brain = Brain(self.home)
        self.owner = self.brain.bootstrap("fictional-company")
        self.actor = self.brain.authenticate(self.owner["token"])
        (self.home / "owner.token").write_text(self.owner["token"])
        self.sales = self.brain.create_space(self.actor, "sales")["id"]
        self.finance = self.brain.create_space(self.actor, "finance")["id"]
        self.reader = self.brain.add_team_member(self.actor, "Sales only", [self.sales], "reader")
        self.brain.put_source(self.actor, self.finance, "salary", "Private payroll", "Fictional salary document")
        self.brain.setup_account(self.actor, "owner", "Fictional-example-password-7591")
        self.backup = self.root / "backup"
        self.key = self.root / "keys" / "before.key"

    def args(self, *extra, approved=True):
        return parser().parse_args(["--home", str(self.home), "--json", "update", "--to", __version__,
                                   "--backup-dir", str(self.backup), "--key-file", str(self.key),
                                   *(["--yes", "--confirm-stopped"] if approved else []), *extra])

    def update(self, args=None):
        with patch("atmet_brain.updating.running_processes", return_value=[]), patch("atmet_brain.updating.update_services", return_value=[]):
            return execute(args or self.args())

    def error(self, code, operation, *args):
        with self.assertRaises(BrainError) as failure:
            operation(*args)
        self.assertEqual(code, failure.exception.code)

    def test_update_preserves_all_records_files_and_scoped_permissions(self):
        before = inventory(self.home / "brain.sqlite3")
        original = (self.home / "owner.token").read_bytes()
        result = self.update()
        self.assertEqual("updated", result["status"])
        verify_records(self.home / "brain.sqlite3", before)
        self.assertEqual(original, (self.home / "owner.token").read_bytes())
        self.assertEqual([self.sales], [v["id"] for v in Brain(self.home).list_spaces(Brain(self.home).authenticate(self.reader["token"]))])
        report = json.loads(Path(result["report"]).read_text())
        self.assertEqual("complete", report["phase"])
        self.assertEqual(0o600, Path(result["report"]).stat().st_mode & 0o777)
        self.assertNotIn(self.owner["token"], json.dumps(result) + json.dumps(report))
        self.assertNotIn(b"Fictional salary document", Path(result["backup"]).read_bytes())
        restored = self.root / "restored"
        Brain.restore_backup(result["backup"], restored, self.key)
        with sqlite3.connect(restored / "brain.sqlite3") as conn:
            self.assertEqual(1, conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0])
            self.assertEqual("1", conn.execute("SELECT value FROM meta WHERE key='recovery_mode'").fetchone()[0])

    def test_missing_home_never_initializes(self):
        args = self.args()
        args.home = self.root / "missing"
        self.error("brain_missing", self.update, args)
        self.assertFalse(args.home.exists())

    def test_no_confirmation_no_backup_or_schema_change(self):
        self.error("update_answers_required", self.update, self.args(approved=False))
        self.assertFalse(self.backup.exists())
        self.assertFalse(self.key.exists())

    def test_unknown_schema_and_recovery_refuse_before_backup(self):
        for key, value, expected in [("schema_version", "999", "schema_version"), ("schema_version", "4", None), ("recovery_mode", "1", "brain_recovering")]:
            with sqlite3.connect(self.home / "brain.sqlite3") as conn:
                conn.execute("UPDATE meta SET value=? WHERE key=?", (value, key))
            if expected:
                self.error(expected, self.update)
                self.assertFalse(self.backup.exists())

    def test_backup_failure_prevents_target_open(self):
        with patch("atmet_brain.updating.snapshot", side_effect=OSError("fictional disk full")), patch("atmet_brain.brain.Brain") as opening:
            self.error("update_failed", self.update)
            opening.assert_not_called()
        report = json.loads((self.backup / "update-report.json").read_text())
        self.assertEqual("creating_backup", report["failed_phase"])

    def test_migration_failure_keeps_backup_and_does_not_restore(self):
        with patch("atmet_brain.brain.Brain", side_effect=BrainError("fictional_migration", "fixture")):
            self.error("fictional_migration", self.update)
        self.assertTrue((self.backup / "brain.atmet").is_file())
        self.assertTrue(self.key.is_file())
        self.assertEqual("opening_target_runtime", json.loads((self.backup / "update-report.json").read_text())["failed_phase"])
        self.assertEqual(4, inspect_home(self.home)["schema"])

    def test_changed_record_is_detected_and_keeps_stopped_report(self):
        real = Brain
        def changed(home):
            brain = real(home)
            with brain.store.transaction(write=True) as conn:
                conn.execute("DELETE FROM grants WHERE principal_id=?", (self.reader["principal_id"],))
            return brain
        with patch("atmet_brain.brain.Brain", side_effect=changed):
            self.error("update_verification", self.update)
        self.assertTrue((self.backup / "brain.atmet").exists())

    def test_backup_paths_cannot_replace_data_or_store_key_beside_snapshot(self):
        for attribute, value in [("backup_dir", self.home / "backups"), ("key_file", self.backup / "key"), ("backup_dir", self.home)]:
            args = self.args()
            setattr(args, attribute, value)
            with self.assertRaises(BrainError):
                self.update(args)
            self.assertFalse(self.key.exists())

    def test_existing_backup_is_never_overwritten(self):
        self.backup.mkdir()
        (self.backup / "precious").write_text("keep")
        self.error("already_exists", self.update)
        self.assertEqual("keep", (self.backup / "precious").read_text())

    def test_maintenance_blocks_other_processes_and_existing_connections(self):
        with maintenance(self.home):
            Brain(self.home)  # Only the operator's current context can open it.
            result = subprocess.run([sys.executable, "-m", "atmet_brain", "--home", str(self.home), "doctor"], capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("brain_busy", result.stderr)
        conn = self.brain.store.connect()
        try:
            self.error("brain_busy", lambda: maintenance(self.home).__enter__())
        finally:
            conn.close()
        with maintenance(self.home):
            pass

    def test_unmanaged_process_refuses_before_snapshot(self):
        with patch("atmet_brain.updating.update_services", return_value=[]), patch("atmet_brain.updating.running_processes", return_value=[12345]):
            self.error("brain_busy", execute, self.args())
        self.assertFalse((self.backup / "brain.atmet").exists())

    def test_process_scan_ignores_other_explicit_company(self):
        output = f'123 python -m atmet_brain --home "{self.home}" mcp\n124 python -m atmet_brain --home /other serve\n125 python -m atmet_brain worker --loop\n'
        with patch("atmet_brain.updating.subprocess.run", return_value=subprocess.CompletedProcess([], 0, output, "")):
            self.assertEqual([123, 125], running_processes(self.home))

    def test_remote_cannot_update_and_downgrades_refuse(self):
        args = self.args()
        args.endpoint = "https://brain.example"
        self.error("local_only", self.update, args)
        args.endpoint, args.to = None, "0.0.1"
        self.error("update_downgrade", self.update, args)

    def test_catalog_selection_preserves_other_company_and_catalog(self):
        catalog = self.root / "catalog"
        catalog.mkdir()
        other = self.root / "other-company"
        Brain(other).bootstrap("other")
        records = {"first": str(self.home), "second": str(other)}
        (catalog / "brains.json").write_text(json.dumps(records))
        before = inventory(other / "brain.sqlite3")
        args = self.args()
        args.home, args.brain = catalog, "first"
        self.update(args)
        self.assertEqual(records, json.loads((catalog / "brains.json").read_text()))
        verify_records(other / "brain.sqlite3", before)

    def test_ambiguous_catalog_requires_company(self):
        (self.home / "brains.json").write_text(json.dumps({"another": str(self.root / "other")}))
        self.error("update_company_required", self.update)

    def test_interactive_cancellation_and_success(self):
        args = self.args(approved=False)
        args.json = False
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=["this-folder", "no"]), contextlib.redirect_stderr(io.StringIO()):
            self.error("update_cancelled", self.update, args)
        self.assertFalse(self.backup.exists())
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", side_effect=["this-folder", "yes", "yes"]), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual("updated", self.update(args)["status"])

    def test_service_refresh_retains_running_state_and_happens_after_backup(self):
        specs = [{"old": {"label": "one"}, "new": {"label": "one-new"}, "running": True},
                 {"old": {"label": "two"}, "new": {"label": "two-new"}, "running": False}]
        calls = []
        def manage(action, spec):
            calls.append((action, spec["label"]))
            if action == "replace":
                self.assertTrue((self.backup / "brain.atmet").is_file())
                self.assertEqual("company_verified", json.loads((self.backup / "update-report.json").read_text())["phase"])
            return {"state": "active"}
        with patch("atmet_brain.updating.update_services", return_value=specs), patch("atmet_brain.updating.running_processes", return_value=[]), patch("atmet_brain.updating.manage_service", side_effect=manage), patch("atmet_brain.services.run_control", return_value=subprocess.CompletedProcess([], 0, __version__ + "\n", "")):
            execute(self.args())
        self.assertEqual([("stop", "one"), ("replace", "one-new"), ("replace", "two-new"), ("start", "one-new"), ("status", "one-new")], calls)

    def test_service_discovery_reads_old_hash_record_and_preserves_port(self):
        for platform in ("darwin", "linux"):
            with patch("pathlib.Path.home", return_value=self.root / platform), patch("atmet_brain.services.sys.platform", platform):
                old = service_spec(self.home, port=8999, python="/old/python")
                path = Path(old["path"])
                path.parent.mkdir(parents=True)
                path.write_text(old["content"])
                directory = self.home / "services"
                directory.mkdir(exist_ok=True)
                record = directory / (old["label"] + ".json")
                record.write_text(json.dumps({"content_hash": sha(old["content"])}))
                with patch("atmet_brain.services.manage_service", return_value={"state": "inactive"}):
                    discovered = update_services(self.home)
                    self.assertEqual("8999", discovered[0]["new"]["command"][-1])
                    self.assertFalse(discovered[0]["running"])
                    path.write_text(old["content"] + "\n")
                    self.error("service_modified", update_services, self.home)
                record.unlink()

    def test_supported_old_schema_snapshot_precedes_migration(self):
        with sqlite3.connect(self.home / "brain.sqlite3") as conn:
            conn.execute("UPDATE meta SET value='3' WHERE key='schema_version'")
            for table in ("security_heads", "security_rules", "security_rule_history", "source_security", "control_credentials", "admin_changes"):
                conn.execute('DROP TABLE IF EXISTS "' + table + '"')
        result = self.update()
        report = json.loads(Path(result["report"]).read_text())
        self.assertEqual(3, report["backup_manifest"]["schema_version"])
        self.assertEqual(4, report["after"]["schema"])
        self.assertEqual([self.sales], [v["id"] for v in Brain(self.home).list_spaces(Brain(self.home).authenticate(self.reader["token"]))])

    def test_service_failure_never_restarts_old_runtime(self):
        services = [{"old": {"label": "old"}, "new": {"label": "new"}, "running": True}]
        calls = []
        def manage(action, spec):
            calls.append((action, spec["label"]))
            if action == "replace":
                raise BrainError("service_control_failed", "fixture")
        with patch("atmet_brain.updating.update_services", return_value=services), patch("atmet_brain.updating.running_processes", return_value=[]), patch("atmet_brain.updating.manage_service", side_effect=manage), patch("atmet_brain.services.run_control", return_value=subprocess.CompletedProcess([], 0, __version__, "")):
            self.error("service_control_failed", execute, self.args())
        self.assertEqual([("stop", "old"), ("replace", "new"), ("stop", "new")], calls)
        self.assertTrue((self.backup / "brain.atmet").is_file())
        self.assertEqual("company_verified", json.loads((self.backup / "update-report.json").read_text())["failed_phase"])

    def test_target_handoff_uses_exact_registry_version_before_opening_data(self):
        args = self.args()
        args.to = "99.0.0"
        with patch("sys.argv", ["atmet-brain", "--home", str(self.home), "update", "--to", "99.0.0"]), patch("atmet_brain.updating.shutil.which", return_value="/example/npx"), patch("atmet_brain.updating.subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as child, patch("atmet_brain.updating.inspect_home") as inspect, contextlib.redirect_stderr(io.StringIO()):
            self.assertIsNone(execute(args))
            self.assertEqual(["/example/npx", "--yes", "--registry=https://registry.npmjs.org", "atmet-brain@99.0.0", "--home", str(self.home), "update", "--to", "99.0.0"], child.call_args.args[0])
            inspect.assert_not_called()
        self.assertFalse(self.backup.exists())

    def test_corrupted_saved_snapshot_blocks_target_core(self):
        from atmet_brain.util import private_write
        def corrupt(path, value, **options):
            if Path(path).name == "brain.atmet":
                value = value[:-40] + b"fictional-corruption"
            return private_write(path, value, **options)
        with patch("atmet_brain.updating.private_write", side_effect=corrupt), patch("atmet_brain.brain.Brain") as opening:
            self.error("update_failed", self.update)
            opening.assert_not_called()

    def test_invalid_database_and_linked_lock_fail_without_migration(self):
        other = self.root / "invalid"
        other.mkdir()
        (other / "brain.sqlite3").write_bytes(b"fictional invalid database")
        self.error("invalid_database", inspect_home, other)
        outside = self.root / "outside"
        outside.write_text("untouched")
        (self.home / ".maintenance.lock").unlink()
        (self.home / ".maintenance.lock").symlink_to(outside)
        self.error("brain_busy", self.update)
        self.assertEqual("untouched", outside.read_text())
        self.assertFalse((self.backup / "brain.atmet").exists())

    def test_worker_discovery_keeps_scope_and_escaped_credential_path(self):
        token_file = self.root / 'key with spaces % and $.token'
        token_file.write_text("fictional-token")
        for platform in ("darwin", "linux"):
            with patch("pathlib.Path.home", return_value=self.root / platform), patch("atmet_brain.services.sys.platform", platform):
                old = service_spec(self.home, kind="worker", space=self.sales, token_file=token_file, python="/old/python")
                path = Path(old["path"])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(old["content"])
                directory = self.home / "services"
                directory.mkdir(exist_ok=True)
                record = directory / (old["label"] + ".json")
                record.write_text(json.dumps({"content_hash": sha(old["content"])}))
                with patch("atmet_brain.services.manage_service", return_value={"state": "active"}):
                    item = update_services(self.home)[0]
                    self.assertIn(str(token_file.resolve()), item["new"]["command"])
                    self.assertIn(self.sales, item["new"]["command"])
                    self.assertTrue(item["running"])
                record.unlink()

    def test_human_summary_has_recovery_paths_and_no_ansi_in_plain_mode(self):
        result = self.update()
        stream = io.StringIO()
        Console(stream, plain=True).update_ready(result)
        value = stream.getvalue()
        self.assertIn("Workspaces: ", value)
        self.assertIn("finance", value)
        self.assertIn("sales", value)
        self.assertIn("Encrypted backup", value)
        self.assertIn("Separate key", value)
        self.assertNotIn("\x1b", value)
        self.assertNotIn(self.owner["token"], value)


if __name__ == "__main__":
    unittest.main()
