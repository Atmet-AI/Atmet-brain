"""Operator-selected bindings and bounded reconciliation."""

from pathlib import Path
import re

from .auth import authorize, validate_audience
from .connectors import files, gmail
from .db import audit
from .errors import BrainError, require
from .util import dumps, loads, now, text, uid


class ConnectorsMixin:
    def register_connector(self, actor, space_id, kind, config, audience=None, authority="observation"):
        """Local operator registration. Server filesystem paths are not exposed through RPC."""
        require(kind in {"files", "gmail"} and isinstance(config, dict), "invalid_connector", "Unsupported connector.")
        require(authority in {"observation", "reference", "authoritative"}, "invalid_authority", "Invalid authority.")
        if kind == "files":
            require(set(config) == {"root"}, "invalid_connector", "File connector needs only a root.")
            root = Path(config["root"]).expanduser()
            require(root.is_dir() and not root.is_symlink(), "invalid_root", "Choose a non-symlink import directory.")
            config = {"root": str(root.resolve())}
        else:
            require(set(config) == {"token_env", "label_ids"} and isinstance(config["label_ids"], list)
                    and 0 < len(config["label_ids"]) <= 20 and all(isinstance(v, str) and v for v in config["label_ids"])
                    and re.fullmatch(r"ATMET_[A-Z0-9_]{1,80}", config["token_env"]),
                    "invalid_connector", "Gmail needs selected label_ids and an ATMET_ token environment name.")
        with self.store.transaction(write=True) as conn:
            authorize(conn, actor, space_id, "manage")
            values = validate_audience(conn, actor.org_id, audience if audience is not None else ["space"])
            ident = uid("connector")
            conn.execute("INSERT INTO connectors(id,space_id,kind,config,audience,authority) VALUES(?,?,?,?,?,?)",
                         (ident, space_id, kind, dumps(config), dumps(values), authority))
            audit(conn, actor, "connector.register", ident, space_id, {"kind": kind})
            return {"id": ident, "kind": kind}

    def list_connectors(self, actor, space_id):
        with self.store.transaction() as conn:
            authorize(conn, actor, space_id, "manage")
            return [{k: row[k] for k in ("id", "kind", "enabled", "last_sync", "last_error")}
                    for row in conn.execute("SELECT * FROM connectors WHERE space_id=?", (space_id,))]

    def disable_connector(self, actor, connector_id):
        with self.store.transaction(write=True) as conn:
            row = conn.execute("SELECT c.* FROM connectors c JOIN spaces s ON s.id=c.space_id "
                               "WHERE c.id=? AND s.org_id=?", (connector_id, actor.org_id)).fetchone()
            require(row is not None, "not_found", "Connector not found.", 404)
            authorize(conn, actor, row["space_id"], "manage")
            conn.execute("UPDATE connectors SET enabled=0 WHERE id=?", (connector_id,))
            for source in conn.execute("SELECT id FROM sources WHERE connector_id=?", (connector_id,)).fetchall():
                self._invalidate_source(conn, source[0])
            audit(conn, actor, "connector.disable", connector_id, row["space_id"])
            return {"status": "disabled"}

    def sync_connector(self, actor, connector_id, _scan=None):
        with self.store.transaction() as conn:
            row = conn.execute("SELECT c.* FROM connectors c JOIN spaces s ON s.id=c.space_id "
                               "WHERE c.id=? AND s.org_id=?", (connector_id, actor.org_id)).fetchone()
            require(row is not None, "not_found", "Connector not found.", 404)
            authorize(conn, actor, row["space_id"], "manage")
            authorize(conn, actor, row["space_id"], "contribute")
            require(row["enabled"], "connector_disabled", "Connector is disabled.", 409)
            binding = dict(row)
        try:
            scan = _scan or (lambda config: files.scan(config["root"])) if binding["kind"] == "files" else _scan or gmail.scan
            items = scan(loads(binding["config"]))
            require(isinstance(items, list) and len(items) <= 500, "connector_limit", "Invalid connector snapshot.")
            seen, results = set(), []
            for item in items:
                external = connector_id + ":" + text(item["external_id"], "external_id", 300)
                require(external not in seen, "connector_duplicate", "Duplicate provider resource ID.")
                seen.add(external)
                with self.store.transaction() as conn:
                    old = conn.execute("SELECT * FROM sources WHERE connector_id=? AND external_id=?", (connector_id, external)).fetchone()
                if old and old["status"] == "deleted":
                    # A permanent tombstone wins over future replays.
                    continue
                if old and old["status"] != "active":
                    self.set_source_access(actor, old["id"], loads(binding["audience"]), True)
                result = self.put_source(actor, binding["space_id"], external, item["title"], item["content"], item["mime"],
                                         loads(binding["audience"]), binding["authority"], old["revision"] if old else None,
                                         _connector_id=connector_id)
                results.append(result)
            with self.store.transaction() as conn:
                prior = conn.execute("SELECT * FROM sources WHERE connector_id=? AND status='active'", (connector_id,)).fetchall()
            for source in prior:
                if source["external_id"] not in seen:
                    self.set_source_access(actor, source["id"], loads(source["audience"]), False)
            with self.store.transaction(write=True) as conn:
                authorize(conn, actor, binding["space_id"], "manage")
                conn.execute("UPDATE connectors SET checkpoint=?,last_sync=?,last_error=NULL WHERE id=?",
                             (dumps({"resource_count": len(seen)}), now(), connector_id))
            return {"connector_id": connector_id, "status": "synced", "resources": len(seen), "sources": results}
        except Exception as error:
            code = error.code if isinstance(error, BrainError) else "connector_failed"
            if code == "gmail_authorization":
                with self.store.transaction(write=True) as conn:
                    conn.execute("UPDATE connectors SET enabled=0 WHERE id=?", (connector_id,))
            with self.store.transaction(write=True) as conn:
                conn.execute("UPDATE connectors SET last_error=? WHERE id=?", (code, connector_id))
            raise BrainError(code, "Connector synchronization failed. Inspect its status and local configuration.", 502) from None
