"""Encrypted whole-installation snapshots and conservative offline recovery."""

import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import zipfile
from dataclasses import asdict

from cryptography.fernet import Fernet, InvalidToken

from ._version import __version__
from .auth import issue, OPERATIONS
from .config import validate_settings
from .db import SCHEMA_VERSION, Store
from .errors import BrainError, require
from .util import dumps, loads, now, private_write, sha, text, uid

MAGIC = b"ATMET-BRAIN-BACKUP-1\n"
MAX_BACKUP_BYTES = 256 * 1024 * 1024


def generate_backup_key(path):
    private_write(path, Fernet.generate_key() + b"\n", overwrite=False)
    return {"key_file": str(path)}


def load_key(path):
    try:
        return Fernet(Path(path).read_bytes().strip())
    except (OSError, ValueError):
        raise BrainError("invalid_backup_key", "Cannot read a valid backup key.") from None


class BackupsMixin:
    def flush_recovery_journal(self, destination=None):
        """Local operator journal. Mirror it outside this disk's failure domain."""
        path = Path(destination or os.environ.get("ATMET_RECOVERY_JOURNAL", self.store.home / "recovery-journal.json"))
        with self.store.transaction(write=True) as conn:
            events = [dict(row) for row in conn.execute("SELECT * FROM recovery_events ORDER BY sequence")]
            instance = conn.execute("SELECT value FROM meta WHERE key='instance_id'").fetchone()[0]
            value = {"format": "atmet-recovery-journal-v1", "instance_id": instance, "events": events,
                     "last_sequence": events[-1]["sequence"] if events else 0, "sha256": sha(dumps(events))}
            private_write(path, dumps(value))
        return {"path": str(path), "last_sequence": value["last_sequence"]}

    def create_backup(self, destination, key_file):
        """Filesystem-owner operation, intentionally absent from public RPC."""
        cipher = load_key(key_file)
        destination = Path(destination)
        require(not destination.exists(), "already_exists", "Backup destination already exists.", 409)
        self.flush_recovery_journal()
        with tempfile.TemporaryDirectory(prefix="atmet-backup-") as temporary:
            snapshot = Path(temporary) / "brain.sqlite3"
            source = self.store.connect()
            target = sqlite3.connect(snapshot)
            try:
                source.backup(target)
                require(target.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                        "backup_integrity", "Snapshot integrity verification failed.")
                instance = target.execute("SELECT value FROM meta WHERE key='instance_id'").fetchone()[0]
                sequence = target.execute("SELECT COALESCE(MAX(sequence),0) FROM recovery_events").fetchone()[0]
            finally:
                source.close()
                target.close()
            data = snapshot.read_bytes()
            require(len(data) <= MAX_BACKUP_BYTES, "backup_size", "This release supports snapshots up to 256 MiB.")
            manifest = {"format": "atmet-brain-backup-v1", "engine_version": __version__, "schema_version": SCHEMA_VERSION,
                        "created_at": now(), "instance_id": instance, "recovery_sequence": sequence,
                        "database_sha256": sha(data), "database_bytes": len(data)}
            manifest["deployment_settings"] = asdict(self.settings)
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", dumps(manifest))
                archive.writestr("brain.sqlite3", data)
            encrypted = MAGIC + cipher.encrypt(buffer.getvalue())
            private_write(destination, encrypted, overwrite=False)
            return {"path": str(destination), "manifest": manifest, "encrypted": True}

    @staticmethod
    def restore_backup(backup_file, destination_home, key_file):
        """Restore to a fresh home, never over a running installation."""
        destination = Path(destination_home)
        require(not destination.exists(), "already_exists", "Restore needs a new destination directory.", 409)
        encrypted = Path(backup_file).read_bytes()
        require(len(encrypted) <= MAX_BACKUP_BYTES * 2 and encrypted.startswith(MAGIC),
                "invalid_backup", "Invalid backup envelope or size.")
        try:
            plain = load_key(key_file).decrypt(encrypted[len(MAGIC):])
        except InvalidToken:
            raise BrainError("invalid_backup", "Backup authentication failed.") from None
        try:
            with zipfile.ZipFile(io.BytesIO(plain)) as archive:
                require(sorted(archive.namelist()) == ["brain.sqlite3", "manifest.json"]
                        and sum(v.file_size for v in archive.infolist()) <= MAX_BACKUP_BYTES + 100_000,
                        "invalid_backup", "Invalid backup inventory.")
                manifest = loads(archive.read("manifest.json"))
                data = archive.read("brain.sqlite3")
            require(manifest["format"] == "atmet-brain-backup-v1" and manifest["schema_version"] in {1, SCHEMA_VERSION}
                    and sha(data) == manifest["database_sha256"] and len(data) == manifest["database_bytes"],
                    "invalid_backup", "Backup manifest or database checksum mismatch.")
        except (KeyError, ValueError, zipfile.BadZipFile):
            raise BrainError("invalid_backup", "Invalid backup payload.") from None
        destination.mkdir(parents=True, mode=0o700)
        private_write(destination / "brain.sqlite3", data)
        with sqlite3.connect(destination / "brain.sqlite3") as check:
            actual = check.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            require(actual and actual[0] == str(manifest["schema_version"]), "invalid_backup", "Database schema differs from the backup manifest.")
        Store(destination)  # Transactionally upgrade supported old snapshots before quarantine/replay.
        settings = validate_settings(manifest.get("deployment_settings", {}))
        private_write(destination / "config.toml", "[brain]\n" + "".join(
            f"{key} = {str(value).lower() if isinstance(value, bool) else value}\n" for key, value in settings.items()))
        conn = sqlite3.connect(destination / "brain.sqlite3")
        try:
            require(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "backup_integrity", "Restored database is invalid.")
            instance = conn.execute("SELECT value FROM meta WHERE key='instance_id'").fetchone()[0]
            require(instance == manifest["instance_id"], "invalid_backup", "Instance identity mismatch.")
            conn.execute("UPDATE meta SET value='1' WHERE key='recovery_mode'")
            conn.execute("INSERT OR REPLACE INTO meta VALUES('backup_sequence',?)", (str(manifest["recovery_sequence"]),))
            conn.execute("UPDATE credentials SET revoked=1")
            conn.execute("UPDATE principals SET active=0")
            conn.execute("UPDATE grants SET revoked=1")
            conn.execute("DELETE FROM group_members")
            conn.execute("UPDATE sources SET status='quarantined' WHERE status!='deleted'")
            conn.execute("UPDATE connectors SET enabled=0")
            conn.execute("UPDATE jobs SET status='blocked',error_code='recovery_revalidation',lease_token=NULL,lease_until=NULL WHERE status!='done'")
            conn.commit()
        finally:
            conn.close()
        return {"home": str(destination), "status": "quarantined", "old_credentials_revoked": True,
                "next": "Reconcile the latest independent journal and provision a recovery owner before serving."}

    def finish_recovery(self, journal_file, owner_name, confirm_journal_complete=False):
        """Local operator attests journal freshness. A stale journal cannot be detected from an old backup alone."""
        require(confirm_journal_complete is True, "journal_confirmation",
                "Confirm the journal includes all known deletion and revocation decisions.")
        journal = loads(Path(journal_file).read_text())
        require(isinstance(journal, dict) and journal.get("format") == "atmet-recovery-journal-v1"
                and isinstance(journal.get("events"), list), "invalid_journal", "Invalid recovery journal.")
        require(sha(dumps(journal["events"])) == journal.get("sha256"), "invalid_journal", "Journal checksum mismatch.")
        text(owner_name, "owner_name", 120)
        owners = []
        with self.store.transaction(write=True) as conn:
            require(conn.execute("SELECT value FROM meta WHERE key='recovery_mode'").fetchone()[0] == "1",
                    "not_recovering", "This installation is not in recovery mode.")
            instance = conn.execute("SELECT value FROM meta WHERE key='instance_id'").fetchone()[0]
            checkpoint = int(conn.execute("SELECT value FROM meta WHERE key='backup_sequence'").fetchone()[0])
            require(instance == journal.get("instance_id"), "invalid_journal", "Journal belongs to another installation.")
            events = journal["events"]
            require([e.get("sequence") for e in events] == list(range(1, len(events) + 1))
                    and journal.get("last_sequence") == len(events) and len(events) >= checkpoint,
                    "invalid_journal", "Journal is incomplete or out of order.")
            for event in events:
                require(event.get("instance_id") == instance, "invalid_journal", "Event instance mismatch.")
                if event["sequence"] <= checkpoint:
                    continue
                operation, target = event["operation"], event["target"]
                payload = loads(event["payload"])
                if operation == "source.erase":
                    conn.execute("UPDATE source_revisions SET body=X'' WHERE source_id=?", (target,))
                    conn.execute("UPDATE sources SET status='deleted',title='Erased source' WHERE id=?", (target,))
                    self._invalidate_source(conn, target, erase=True)
                elif operation == "source.access" and not payload["active"]:
                    conn.execute("UPDATE sources SET status='revoked' WHERE id=? AND status!='deleted'", (target,))
                    self._invalidate_source(conn, target)
                elif operation == "credential.revoke":
                    conn.execute("UPDATE credentials SET revoked=1 WHERE id=?", (target,))
                elif operation == "grant.revoke":
                    conn.execute("UPDATE grants SET revoked=1 WHERE id=?", (target,))
                elif operation == "group.remove":
                    conn.execute("DELETE FROM group_members WHERE group_id=? AND principal_id=?", (target, payload["principal_id"]))
                require(operation in {"source.erase", "source.access", "credential.revoke", "grant.revoke", "group.remove"},
                        "invalid_journal", "Unsupported recovery operation.")
                conn.execute("INSERT OR IGNORE INTO recovery_events VALUES(?,?,?,?,?,?)",
                             (event["sequence"], instance, operation, target, event["payload"], event["recorded_at"]))
            for org in conn.execute("SELECT * FROM organizations").fetchall():
                principal = uid("principal")
                conn.execute("INSERT INTO principals VALUES(?,?,?,?,1,1,?)", (principal, org["id"], owner_name, "human", now()))
                credential = issue(conn, principal)
                for space in conn.execute("SELECT id FROM spaces WHERE org_id=?", (org["id"],)).fetchall():
                    conn.execute("INSERT INTO grants VALUES(?,?,?,?,NULL,0)",
                                 (uid("grant"), principal, space[0], dumps(sorted(OPERATIONS))))
                    conn.execute("UPDATE sources SET audience=? WHERE space_id=? AND status!='deleted'",
                                 (dumps(["principal:" + principal]), space[0]))
                owners.append({"organization_id": org["id"], "organization": org["slug"], "principal_id": principal, **credential})
            conn.execute("UPDATE meta SET value='0' WHERE key='recovery_mode'")
        self.flush_recovery_journal()
        return {"status": "owner_provisioned", "owners": owners,
                "sources": "Remain quarantined or revoked until individually revalidated.",
                "memberships": "Old principals and grants remain disabled. Regrant only after current identity checks."}
