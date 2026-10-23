"""Authenticated principals, operation grants and credential narrowing."""

from dataclasses import dataclass
import secrets

from .db import audit, recovery_event
from .errors import BrainError, require
from .util import dumps, loads, now, sha, slug, text, timestamp, uid

OPERATIONS = {"read", "contribute", "review", "publish", "manage", "history", "erase", "process", "observe"}
ROLES = {
    "reader": ["read"],
    "contributor": ["read", "contribute", "observe"],
    "reporter": ["read", "observe", "contribute", "history"],
    "reviewer": ["read", "review", "history"],
    "publisher": ["read", "contribute", "review", "publish", "history"],
    "worker": ["read", "contribute", "process", "observe"],
    "owner": sorted(OPERATIONS),
}


@dataclass(frozen=True)
class Actor:
    principal_id: str
    org_id: str
    credential_id: str


def live_principal(conn, actor):
    row = conn.execute("SELECT p.*,c.operations,c.space_ids,c.expires_at,c.revoked,c.parent_id FROM principals p "
                       "JOIN credentials c ON c.principal_id=p.id WHERE c.id=? AND p.id=? AND p.org_id=?",
                       (actor.credential_id, actor.principal_id, actor.org_id)).fetchone()
    recovery = conn.execute("SELECT value FROM meta WHERE key='recovery_mode'").fetchone()[0]
    require(row and row["active"] and not row["revoked"] and recovery == "0"
            and (row["expires_at"] is None or row["expires_at"] > now()),
            "unauthenticated", "A current credential is required.", 401)
    parent, seen = row["parent_id"], {actor.credential_id}
    while parent:
        require(parent not in seen and len(seen) <= 32, "unauthenticated", "Invalid credential lineage.", 401)
        seen.add(parent)
        ancestor = conn.execute("SELECT c.parent_id,c.revoked,c.expires_at,p.active FROM credentials c "
                                "JOIN principals p ON p.id=c.principal_id WHERE c.id=? AND p.org_id=?", (parent, actor.org_id)).fetchone()
        require(ancestor and ancestor["active"] and not ancestor["revoked"]
                and (ancestor["expires_at"] is None or ancestor["expires_at"] > now()),
                "unauthenticated", "Credential lineage is no longer active.", 401)
        parent = ancestor["parent_id"]
    return row


def operation_names(operations):
    require(isinstance(operations, list) and bool(operations)
            and all(isinstance(x, str) and x in OPERATIONS for x in operations),
            "invalid_grant", "Choose supported operation names.")
    return sorted(set(operations))


def credential_allows(principal, operation, space_id):
    operations, spaces = loads(principal["operations"]), loads(principal["space_ids"])
    return ("*" in operations or operation in operations) and ("*" in spaces or space_id in spaces)


def authorize(conn, actor, space_id, operation):
    principal = live_principal(conn, actor)
    space = conn.execute("SELECT * FROM spaces WHERE id=? AND org_id=?", (space_id, actor.org_id)).fetchone()
    require(space is not None, "not_found", "Resource not found.", 404)
    allowed = credential_allows(principal, operation, space_id)
    grants = conn.execute("SELECT operations FROM grants WHERE principal_id=? AND space_id=? "
                          "AND revoked=0 AND (expires_at IS NULL OR expires_at>?)",
                          (actor.principal_id, space_id, now())).fetchall()
    allowed = allowed and any(operation in loads(g[0]) for g in grants)
    require(allowed, "forbidden", "This operation is not granted for this space.", 403)
    return space


def can(conn, actor, space_id, operation):
    try:
        authorize(conn, actor, space_id, operation)
        return True
    except BrainError:
        return False


def organization_admin(conn, actor):
    principal = live_principal(conn, actor)
    require(principal["org_admin"] and credential_allows(principal, "manage", "*"),
            "forbidden", "An organization administrator credential is required.", 403)
    return principal


def validate_audience(conn, org_id, audience):
    require(isinstance(audience, list) and 0 < len(audience) <= 100
            and all(isinstance(v, str) for v in audience), "invalid_audience", "Provide audience selectors.")
    for value in audience:
        if value == "space":
            continue
        kind, _, ident = value.partition(":")
        require(kind in {"principal", "group"} and ident, "invalid_audience", "Invalid audience selector.")
        table = "principals" if kind == "principal" else "groups"
        require(conn.execute(f"SELECT 1 FROM {table} WHERE id=? AND org_id=?", (ident, org_id)).fetchone(),
                "invalid_audience", "Audience identity is not in this organization.")
    return sorted(set(audience))


def audience_allows(conn, actor, audience):
    choices = set(loads(audience) if isinstance(audience, str) else audience)
    if "space" in choices or "principal:" + actor.principal_id in choices:
        return True
    groups = conn.execute("SELECT group_id FROM group_members WHERE principal_id=?", (actor.principal_id,))
    return any("group:" + g[0] in choices for g in groups)


def issue(conn, principal_id, operations=None, space_ids=None, expires_at=None, parent_id=None):
    token = "atmet_" + secrets.token_urlsafe(32)
    ident = uid("key")
    conn.execute("INSERT INTO credentials VALUES(?,?,?,?,?,?,0,?,?)",
                 (ident, principal_id, sha(token), dumps(operations or ["*"]), dumps(space_ids or ["*"]),
                  timestamp(expires_at) if expires_at is not None else None, now(), parent_id))
    return {"credential_id": ident, "token": token}


class IdentityMixin:
    def add_team_member(self, actor, name, space_ids, role="reader", kind="human", expires_at=None):
        """Atomic, bounded team provisioning. Returns the new credential once."""
        require(role in ROLES and role != "owner" and kind in {"human", "service"},
                "invalid_role", "Choose a non-owner team role and a human or service identity.")
        require(isinstance(space_ids, list) and 0 < len(space_ids) <= 100 and all(isinstance(s, str) for s in space_ids),
                "invalid_input", "Choose one or more space IDs.")
        name = text(name, maximum=120)
        expiry = timestamp(expires_at) if expires_at is not None else now() + 30 * 86400
        require(expiry > now(), "invalid_time", "The credential must expire in the future.")
        spaces, operations = sorted(set(space_ids)), ROLES[role]
        with self.store.transaction(write=True) as conn:
            principal = organization_admin(conn, actor)
            require(principal["expires_at"] is None or expiry <= principal["expires_at"],
                    "forbidden", "A credential cannot outlive its issuer.", 403)
            for sid in spaces:
                authorize(conn, actor, sid, "manage")
                for operation in operations:
                    authorize(conn, actor, sid, operation)
            pid = uid("principal")
            conn.execute("INSERT INTO principals VALUES(?,?,?,?,0,1,?)", (pid, actor.org_id, name, kind, now()))
            for sid in spaces:
                conn.execute("INSERT INTO grants VALUES(?,?,?,?,?,0)", (uid("grant"), pid, sid, dumps(operations), expiry))
            issued = issue(conn, pid, operations, spaces, expiry, actor.credential_id)
            audit(conn, actor, "team.add", pid, details={"space_ids": spaces, "role": role, "expires_at": expiry})
            return {"principal_id": pid, **issued, "space_ids": spaces, "role": role, "expires_at": expiry}

    def bootstrap(self, organization="example", owner="Owner", _allow_existing=False):
        """Local operator only. Never exposed through RPC or MCP."""
        with self.store.transaction(write=True) as conn:
            require(_allow_existing or not conn.execute("SELECT 1 FROM organizations").fetchone(),
                    "already_initialized", "This installation is already initialized.", 409)
            require(not conn.execute("SELECT 1 FROM organizations WHERE slug=?", (slug(organization),)).fetchone(),
                    "already_exists", "Organization already exists.", 409)
            oid, pid = uid("org"), uid("principal")
            conn.execute("INSERT INTO organizations VALUES(?,?,?)", (oid, slug(organization), now()))
            conn.execute("INSERT INTO principals VALUES(?,?,?,?,1,1,?)", (pid, oid, text(owner, maximum=120), "human", now()))
            issued = issue(conn, pid)
            actor = Actor(pid, oid, issued["credential_id"])
            audit(conn, actor, "organization.bootstrap", oid)
            return {"organization_id": oid, "principal_id": pid, **issued}

    def provision_organization(self, organization, owner="Owner"):
        """Additional company provisioning is a local installation-owner operation."""
        return self.bootstrap(organization, owner, _allow_existing=True)

    def authenticate(self, token):
        require(isinstance(token, str) and 20 <= len(token) <= 300,
                "unauthenticated", "A current credential is required.", 401)
        with self.store.transaction() as conn:
            row = conn.execute("SELECT c.id,p.id AS pid,p.org_id FROM credentials c JOIN principals p "
                               "ON p.id=c.principal_id WHERE token_hash=?", (sha(token),)).fetchone()
            require(row is not None, "unauthenticated", "A current credential is required.", 401)
            actor = Actor(row["pid"], row["org_id"], row["id"])
            live_principal(conn, actor)
            return actor

    def whoami(self, actor):
        with self.store.transaction() as conn:
            row = live_principal(conn, actor)
            return {"principal_id": row["id"], "organization_id": row["org_id"], "name": row["name"],
                    "kind": row["kind"], "credential_id": actor.credential_id,
                    "credential_operations": loads(row["operations"]), "credential_spaces": loads(row["space_ids"]),
                    "expires_at": row["expires_at"]}

    def check_access(self, actor, space_id):
        """Describe only this authenticated caller's current space permissions."""
        with self.store.transaction() as conn:
            authorize(conn, actor, space_id, "read")
            operations = sorted(operation for operation in OPERATIONS if can(conn, actor, space_id, operation))
            try:
                organization_admin(conn, actor)
                admin = True
            except BrainError:
                admin = False
            return {"space_id": space_id, "operations": operations,
                    "can_add_members": admin and "manage" in operations}

    def create_space(self, actor, name):
        with self.store.transaction(write=True) as conn:
            organization_admin(conn, actor)
            name = slug(name)
            require(not conn.execute("SELECT 1 FROM spaces WHERE org_id=? AND slug=?", (actor.org_id, name)).fetchone(),
                    "already_exists", "Space already exists.", 409)
            ident = uid("space")
            conn.execute("INSERT INTO spaces VALUES(?,?,?,?)", (ident, actor.org_id, name, now()))
            conn.execute("INSERT INTO grants VALUES(?,?,?,?,NULL,0)",
                         (uid("grant"), actor.principal_id, ident, dumps(sorted(OPERATIONS))))
            audit(conn, actor, "space.create", ident, ident)
            return {"id": ident, "slug": name, "organization_id": actor.org_id}

    def list_spaces(self, actor):
        with self.store.transaction() as conn:
            live_principal(conn, actor)
            return [dict(s) for s in conn.execute("SELECT * FROM spaces WHERE org_id=? ORDER BY slug", (actor.org_id,))
                    if can(conn, actor, s["id"], "read") or can(conn, actor, s["id"], "manage")]

    def create_principal(self, actor, name, kind="service", org_admin=False):
        require(kind in {"human", "service"} and type(org_admin) is bool, "invalid_principal", "Invalid principal type.")
        with self.store.transaction(write=True) as conn:
            organization_admin(conn, actor)
            ident = uid("principal")
            conn.execute("INSERT INTO principals VALUES(?,?,?,?,?,1,?)",
                         (ident, actor.org_id, text(name, maximum=120), kind, int(org_admin), now()))
            audit(conn, actor, "principal.create", ident)
            return {"id": ident, "name": name, "kind": kind}

    def grant(self, actor, principal_id, space_id, operations, expires_at=None):
        operations = operation_names(operations)
        with self.store.transaction(write=True) as conn:
            authorize(conn, actor, space_id, "manage")
            require(conn.execute("SELECT 1 FROM principals WHERE id=? AND org_id=? AND active=1",
                                 (principal_id, actor.org_id)).fetchone(), "not_found", "Principal not found.", 404)
            for operation in operations:
                authorize(conn, actor, space_id, operation)
            ident = uid("grant")
            conn.execute("INSERT INTO grants VALUES(?,?,?,?,?,0)",
                         (ident, principal_id, space_id, dumps(operations),
                          timestamp(expires_at) if expires_at is not None else None))
            audit(conn, actor, "grant.create", ident, space_id, {"principal_id": principal_id, "operations": operations})
            return {"id": ident, "operations": operations}

    def revoke_grant(self, actor, grant_id):
        with self.store.transaction(write=True) as conn:
            row = conn.execute("SELECT * FROM grants WHERE id=?", (grant_id,)).fetchone()
            require(row is not None, "not_found", "Grant not found.", 404)
            authorize(conn, actor, row["space_id"], "manage")
            conn.execute("UPDATE grants SET revoked=1 WHERE id=?", (grant_id,))
            recovery_event(conn, "grant.revoke", grant_id)
            audit(conn, actor, "grant.revoke", grant_id, row["space_id"])
        self.flush_recovery_journal()
        return {"status": "revoked"}

    def create_credential(self, actor, principal_id=None, operations=None, space_ids=None, expires_at=None):
        with self.store.transaction(write=True) as conn:
            live_principal(conn, actor)
            target = principal_id or actor.principal_id
            if target != actor.principal_id:
                organization_admin(conn, actor)
            require(conn.execute("SELECT 1 FROM principals WHERE id=? AND org_id=? AND active=1",
                                 (target, actor.org_id)).fetchone(), "not_found", "Principal not found.", 404)
            if operations is not None:
                operation_names(operations)
            if space_ids is not None:
                require(isinstance(space_ids, list) and bool(space_ids), "invalid_input", "Choose space IDs.")
                for sid in space_ids:
                    require(conn.execute("SELECT 1 FROM spaces WHERE id=? AND org_id=?", (sid, actor.org_id)).fetchone(),
                            "not_found", "Space not found.", 404)
            # Tokens minted by a narrowed token cannot escape its restrictions.
            current = live_principal(conn, actor)
            old_ops, old_spaces = loads(current["operations"]), loads(current["space_ids"])
            chosen_ops, chosen_spaces = operations or old_ops, space_ids or old_spaces
            require(("*" in old_ops or set(chosen_ops) <= set(old_ops))
                    and ("*" in old_spaces or set(chosen_spaces) <= set(old_spaces)),
                    "forbidden", "A credential cannot widen its issuer's scope.", 403)
            expiry = timestamp(expires_at) if expires_at is not None else current["expires_at"]
            require(current["expires_at"] is None or (expiry is not None and expiry <= current["expires_at"]),
                    "forbidden", "A credential cannot outlive its issuer.", 403)
            issued = issue(conn, target, chosen_ops, chosen_spaces, expiry, actor.credential_id)
            audit(conn, actor, "credential.create", issued["credential_id"], details={"principal_id": target})
            return issued

    def revoke_credential(self, actor, credential_id):
        with self.store.transaction(write=True) as conn:
            live_principal(conn, actor)
            row = conn.execute("SELECT c.*,p.org_id FROM credentials c JOIN principals p ON p.id=c.principal_id "
                               "WHERE c.id=? AND p.org_id=?", (credential_id, actor.org_id)).fetchone()
            require(row is not None, "not_found", "Credential not found.", 404)
            if row["principal_id"] != actor.principal_id:
                organization_admin(conn, actor)
            conn.execute("UPDATE credentials SET revoked=1 WHERE id=?", (credential_id,))
            recovery_event(conn, "credential.revoke", credential_id)
            audit(conn, actor, "credential.revoke", credential_id)
        self.flush_recovery_journal()
        return {"status": "revoked"}

    def create_group(self, actor, name, principal_ids):
        require(isinstance(principal_ids, list) and len(principal_ids) <= 100,
                "invalid_input", "Provide up to 100 principal IDs.")
        with self.store.transaction(write=True) as conn:
            organization_admin(conn, actor)
            for pid in principal_ids:
                require(conn.execute("SELECT 1 FROM principals WHERE id=? AND org_id=? AND active=1", (pid, actor.org_id)).fetchone(),
                        "not_found", "Principal not found.", 404)
            ident = uid("group")
            conn.execute("INSERT INTO groups VALUES(?,?,?)", (ident, actor.org_id, text(name, maximum=120)))
            for pid in set(principal_ids):
                conn.execute("INSERT INTO group_members VALUES(?,?)", (ident, pid))
            audit(conn, actor, "group.create", ident)
            return {"id": ident}

    def remove_group_member(self, actor, group_id, principal_id):
        with self.store.transaction(write=True) as conn:
            organization_admin(conn, actor)
            require(conn.execute("SELECT 1 FROM groups WHERE id=? AND org_id=?", (group_id, actor.org_id)).fetchone(),
                    "not_found", "Group not found.", 404)
            conn.execute("DELETE FROM group_members WHERE group_id=? AND principal_id=?", (group_id, principal_id))
            recovery_event(conn, "group.remove", group_id, {"principal_id": principal_id})
            audit(conn, actor, "group.remove", group_id)
        self.flush_recovery_journal()
        return {"status": "removed"}
