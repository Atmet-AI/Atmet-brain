"""SQLite transactions and minimal, non-content-bearing audit events."""

from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3

from .errors import require
from .maintenance import acquire, release
from .util import dumps, now, uid

SCHEMA_VERSION = 4


class Connection(sqlite3.Connection):
    def close(self):
        try:
            super().close()
        finally:
            release(getattr(self, "maintenance_lease", None))
            self.maintenance_lease = None


class Store:
    def __init__(self, home):
        self.home = Path(home).expanduser().resolve()
        self.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.home / "brain.sqlite3"
        conn = self.connect()
        try:
            has_meta = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'").fetchone()
            version = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone() if has_meta else None
            require(version is None or version[0] in {"1", "2", "3", "4"}, "schema_version",
                    "Unsupported database schema. Use a compatible release.")
            conn.executescript("BEGIN IMMEDIATE;\n" + Path(__file__).with_name("schema.sql").read_text())
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(sources)")}
            if "category" not in columns:
                conn.execute("ALTER TABLE sources ADD COLUMN category TEXT NOT NULL DEFAULT 'document'")
            # Legacy readers select status='active'. Operational report payloads
            # must never enter that state, even through an old management call.
            for event in ("INSERT", "UPDATE"):
                conn.execute(f"CREATE TRIGGER IF NOT EXISTS report_state_{event.lower()} BEFORE {event} ON sources "
                             "WHEN NEW.category='task_report' AND NEW.status='active' "
                             "BEGIN SELECT RAISE(ABORT,'Task reports require operational state'); END")
            conn.execute("INSERT OR IGNORE INTO meta VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
            conn.execute("UPDATE meta SET value=? WHERE key='schema_version' AND value IN ('1','2','3')", (str(SCHEMA_VERSION),))
            conn.execute("INSERT OR IGNORE INTO meta VALUES('instance_id',?)", (uid("instance"),))
            conn.execute("INSERT OR IGNORE INTO meta VALUES('recovery_mode','0')")
            version = conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0]
            require(int(version) == SCHEMA_VERSION, "schema_version", "Unsupported database schema. Use a compatible release.")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
        os.chmod(self.path, 0o600)

    def connect(self):
        lease = acquire(self.home)
        try:
            conn = sqlite3.connect(self.path, timeout=20, isolation_level=None, factory=Connection)
            conn.maintenance_lease = lease
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=20000")
            conn.execute("PRAGMA secure_delete=ON")
            return conn
        except BaseException:
            if "conn" in locals():
                conn.close()
            else:
                release(lease)
            raise

    @contextmanager
    def transaction(self, write=False):
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()


def audit(conn, actor, operation, target=None, space_id=None, details=None):
    conn.execute("INSERT INTO audit_events VALUES(?,?,?,?,?,?,?,?)",
                 (uid("audit"), actor.org_id, space_id, actor.principal_id, operation,
                  target, dumps(details or {}), now()))


def recovery_event(conn, operation, target, payload=None):
    instance = conn.execute("SELECT value FROM meta WHERE key='instance_id'").fetchone()[0]
    conn.execute("INSERT INTO recovery_events(instance_id,operation,target,payload,recorded_at) VALUES(?,?,?,?,?)",
                 (instance, operation, target, dumps(payload or {}), now()))
