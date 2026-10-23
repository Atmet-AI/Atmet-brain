"""Operator-selected bindings and bounded reconciliation."""

from pathlib import Path
import re

from .auth import authorize, validate_audience
from .connectors import files, gmail
from .db import audit, recovery_event
from .errors import BrainError, require
from .util import dumps, loads, now, text, uid, slug, sha


class ConnectorsMixin:
    def register_connector(self, actor, space_id, kind, config, audience=None, authority="observation"):
        """Local operator registration. Server filesystem paths are not exposed through RPC."""
        require(kind in {"files", "gmail", "external"} and isinstance(config, dict), "invalid_connector", "Unsupported connector.")
        require(authority in {"observation", "reference", "authoritative"}, "invalid_authority", "Invalid authority.")
        if kind == "files":
            require(set(config) == {"root"}, "invalid_connector", "File connector needs only a root.")
            root = Path(config["root"]).expanduser()
            require(root.is_dir() and not root.is_symlink(), "invalid_root", "Choose a non-symlink import directory.")
            config = {"root": str(root.resolve())}
        elif kind == "gmail":
            require(set(config) == {"token_env", "label_ids"} and isinstance(config["label_ids"], list)
                    and 0 < len(config["label_ids"]) <= 20 and all(isinstance(v, str) and v for v in config["label_ids"])
                    and re.fullmatch(r"ATMET_[A-Z0-9_]{1,80}", config["token_env"]),
                    "invalid_connector", "Gmail needs selected label_ids and an ATMET_ token environment name.")
        else:
            require(set(config) == {"provider", "account"}, "invalid_connector", "External bindings contain provider/account metadata, never credentials.")
            slug(config["provider"])
            text(config["account"], "account", 200)
        with self.store.transaction(write=True) as conn:
            authorize(conn, actor, space_id, "manage")
            values = validate_audience(conn, actor.org_id, audience if audience is not None else ["space"])
            ident = uid("connector")
            conn.execute("INSERT INTO connectors(id,space_id,kind,config,audience,authority) VALUES(?,?,?,?,?,?)",
                         (ident, space_id, kind, dumps(config), dumps(values), authority))
            audit(conn, actor, "connector.register", ident, space_id, {"kind": kind})
            return {"id": ident, "kind": kind}

    def register_external_connector(self, actor, space_id, provider, account, audience=None, authority="observation"):
        """Credential-free binding for a user-selected external adapter."""
        config = {"provider": slug(provider), "account": text(account, "account", 200)}
        with self.store.transaction() as conn:
            authorize(conn, actor, space_id, "manage")
            previous = conn.execute("SELECT * FROM connectors WHERE space_id=? AND kind='external' AND config=?", (space_id, dumps(config))).fetchone()
            if previous:
                require(previous["enabled"] and previous["audience"] == dumps(audience or ["space"]) and previous["authority"] == authority,
                        "connector_binding_conflict", "Existing binding differs or was disabled. Use a new explicit connection.", 409)
                return {"id": previous["id"], "kind": "external", "status": "existing"}
        return self.register_connector(actor, space_id, "external", config, audience, authority)

    def apply_connector_batch(self, actor, connector_id, items, deleted_ids=None, checkpoint=None, expected_checkpoint=None):
        """Bounded incremental input. Only explicit deletions count; omitted records remain."""
        deleted_ids = [] if deleted_ids is None else deleted_ids
        checkpoint = {} if checkpoint is None else checkpoint
        expected_checkpoint = {} if expected_checkpoint is None else expected_checkpoint
        require(isinstance(items, list) and isinstance(deleted_ids, list) and len(items) + len(deleted_ids) <= 500,
                "connector_limit", "Use at most 500 records per batch.")
        require(isinstance(checkpoint, dict) and isinstance(expected_checkpoint, dict)
                and len(dumps(checkpoint)) <= 4000 and len(dumps(expected_checkpoint)) <= 4000,
                "invalid_checkpoint", "Use a bounded checkpoint object.")
        ids = []
        for item in items:
            require(isinstance(item, dict) and set(item) <= {"external_id", "title", "content", "mime"}
                    and {"external_id", "title", "content"} <= set(item), "invalid_connector_item", "Provide external_id, title and UTF-8 content.")
            ids.append(text(item["external_id"], "external_id", 300))
            text(item["title"], "title", 200);text(item["content"], "content", 200_000)
        ids += [text(value, "external_id", 300) for value in deleted_ids]
        require(len(set(ids)) == len(ids), "connector_duplicate", "A batch cannot repeat an external ID.")
        fingerprint = sha(dumps({"items": items, "deleted_ids": deleted_ids, "checkpoint": checkpoint}))
        with self.store.transaction() as conn:
            row = conn.execute("SELECT c.* FROM connectors c JOIN spaces s ON s.id=c.space_id WHERE c.id=? AND s.org_id=?", (connector_id, actor.org_id)).fetchone()
            require(row and row["kind"] == "external", "not_found", "External connector not found.", 404)
            authorize(conn, actor, row["space_id"], "manage");authorize(conn, actor, row["space_id"], "contribute")
            require(row["enabled"], "connector_disabled", "Connector is disabled.", 409)
            current = loads(row["checkpoint"])
            if current.get("batch_hash") == fingerprint:
                return {"connector_id": connector_id, "status": "unchanged", "checkpoint": current.get("cursor", {})}
            require(current.get("cursor", {}) == expected_checkpoint, "checkpoint_conflict", "Connector checkpoint changed. Refresh and retry.", 409)
            binding = dict(row)
        results = []
        for item in items:
            external = connector_id + ":" + item["external_id"]
            with self.store.transaction() as conn:
                old = conn.execute("SELECT * FROM sources WHERE connector_id=? AND external_id=?", (connector_id, external)).fetchone()
            if old and old["status"] == "deleted":
                continue  # A permanent erasure always wins over adapter replays.
            results.append(self.put_source(actor, binding["space_id"], external, item["title"], item["content"], item.get("mime", "text/plain"),
                                           loads(binding["audience"]), binding["authority"], old["revision"] if old else None, _connector_id=connector_id))
        with self.store.transaction(write=True) as conn:
            authorize(conn, actor, binding["space_id"], "manage")
            latest = conn.execute("SELECT enabled,checkpoint FROM connectors WHERE id=?", (connector_id,)).fetchone()
            require(latest["enabled"] and latest["checkpoint"] == binding["checkpoint"], "checkpoint_conflict", "Connector changed during processing. The checkpoint was not advanced.", 409)
            for ident in deleted_ids:
                source = conn.execute("SELECT * FROM sources WHERE connector_id=? AND external_id=? AND status!='deleted'", (connector_id, connector_id + ":" + ident)).fetchone()
                if source:
                    self._source(conn, actor, source["id"], "manage")
                    conn.execute("UPDATE sources SET status='revoked',updated_at=? WHERE id=?", (now(), source["id"]))
                    self._invalidate_source(conn, source["id"])
                    recovery_event(conn, "source.access", source["id"], {"audience": loads(source["audience"]), "active": False})
            conn.execute("UPDATE connectors SET checkpoint=?,last_sync=?,last_error=NULL WHERE id=?", (dumps({"cursor": checkpoint, "batch_hash": fingerprint}), now(), connector_id))
            audit(conn, actor, "connector.batch", connector_id, binding["space_id"], {"items": len(items), "deletions": len(deleted_ids)})
        self.flush_recovery_journal()
        return {"connector_id": connector_id, "status": "synced", "sources": results, "checkpoint": checkpoint}

    def purge_connector(self, actor, connector_id, confirm=False):
        require(confirm is True, "erase_confirmation", "Confirm permanent removal of this connector's captured source bodies.")
        with self.store.transaction(write=True) as conn:
            row = conn.execute("SELECT c.* FROM connectors c JOIN spaces s ON s.id=c.space_id WHERE c.id=? AND s.org_id=?", (connector_id, actor.org_id)).fetchone()
            require(row, "not_found", "Connector not found.", 404)
            authorize(conn, actor, row["space_id"], "manage");authorize(conn, actor, row["space_id"], "erase")
            sources = conn.execute("SELECT id FROM sources WHERE connector_id=? AND status!='deleted'", (connector_id,)).fetchall()
            for source in sources:
                self._source(conn, actor, source["id"], "erase")
            conn.execute("UPDATE connectors SET enabled=0 WHERE id=?", (connector_id,))
            for source in sources:
                conn.execute("UPDATE source_revisions SET body=X'' WHERE source_id=?", (source["id"],))
                conn.execute("UPDATE sources SET status='deleted',title='Erased source',updated_at=? WHERE id=?", (now(), source["id"]))
                self._invalidate_source(conn, source["id"], erase=True);recovery_event(conn, "source.erase", source["id"])
            audit(conn, actor, "connector.purge", connector_id, row["space_id"], {"sources": len(sources)})
        self.flush_recovery_journal()
        return {"connector_id": connector_id, "status": "purged", "sources": len(sources)}

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
            require(row["kind"] != "external", "external_adapter_required", "Use connectors.batch with your configured external adapter.")
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
                if old and old["status"] not in {"active", "intake"}:
                    self.set_source_access(actor, old["id"], loads(binding["audience"]), True)
                result = self.put_source(actor, binding["space_id"], external, item["title"], item["content"], item["mime"],
                                         loads(binding["audience"]), binding["authority"], old["revision"] if old else None,
                                         _connector_id=connector_id)
                results.append(result)
            with self.store.transaction() as conn:
                prior = conn.execute("SELECT * FROM sources WHERE connector_id=? AND status IN ('active','intake')", (connector_id,)).fetchall()
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
