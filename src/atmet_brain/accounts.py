"""Company-local password accounts, single-use invitations and explicit memberships."""

import hashlib
import hmac
import re
import secrets
import threading
import unicodedata

from .auth import Actor, ROLES, authorize, issue, live_principal, organization_admin
from .db import audit, recovery_event
from .errors import BrainError, require
from .util import dumps, loads, now, sha, text, timestamp, uid

SESSION_SECONDS = 12 * 3600
INVITE_SECONDS = 24 * 3600
PASSWORD_WORK = threading.BoundedSemaphore(2)
COMMON_PASSWORDS = {"passwordpassword", "password123456789", "123456789012345", "qwertyuiopasdfgh",
                    "letmeinletmein123", "changemechangeme", "correct horse battery staple"}


def username(value):
    require(isinstance(value, str), "invalid_username", "Enter a work username or email address.")
    value = unicodedata.normalize("NFC", value).strip().casefold()
    require(re.fullmatch(r"[a-z0-9][a-z0-9._+@-]{1,119}", value), "invalid_username",
            "Use 2 to 120 letters, digits, dots, @, +, underscores or hyphens for the login name.")
    return value


def password_text(value, login=None):
    require(isinstance(value, str), "invalid_password", "Enter a password privately.")
    value = unicodedata.normalize("NFC", value)
    require(15 <= len(value) <= 128 and len(value.encode()) <= 512 and not any(ord(c) < 32 for c in value),
            "invalid_password", "Use a password or passphrase of 15 to 128 characters, without control characters.")
    require(value.casefold() not in COMMON_PASSWORDS and len(set(value)) > 3
            and value.casefold() != (login or "").casefold(), "weak_password", "Choose a less predictable passphrase.")
    return value


def password_digest(value, salt):
    require(PASSWORD_WORK.acquire(timeout=2), "auth_busy", "Sign-in is busy. Try again shortly.", 429)
    try:
        return hashlib.scrypt(value.encode(), salt=salt, n=32768, r=8, p=3,
                              maxmem=64 * 1024 * 1024, dklen=32).hex()
    finally:
        PASSWORD_WORK.release()


def hash_password(value, login=None):
    value = password_text(value, login)
    salt = secrets.token_bytes(16)
    return "scrypt-32768-8-3$" + salt.hex() + "$" + password_digest(value, salt)


def verify_password(value, encoded):
    # Unknown users perform the same bounded KDF work without exposing account existence.
    if not isinstance(value, str) or len(value) > 128 or len(value.encode()) > 512:
        return False
    value = unicodedata.normalize("NFC", value)
    try:
        algorithm, salt, expected = encoded.split("$")
        require(algorithm == "scrypt-32768-8-3" and len(salt) == 32 and len(expected) == 64,
                "invalid_password_hash", "Invalid stored password verifier.")
        salt = bytes.fromhex(salt)
    except (ValueError, AttributeError, BrainError):
        salt, expected = b"\0" * 16, "0" * 64
    return hmac.compare_digest(password_digest(value, salt), expected)


def reserve_attempt(conn, key):
    current = now()
    conn.execute("DELETE FROM auth_attempts WHERE window_start<?", (current - 900,))
    row = conn.execute("SELECT * FROM auth_attempts WHERE attempt_key=?", (key,)).fetchone()
    require(row is None or row["count"] < 8, "auth_rate_limited", "Too many attempts. Wait 15 minutes before trying again.", 429)
    require(row is not None or conn.execute("SELECT COUNT(*) FROM auth_attempts").fetchone()[0] < 10000,
            "auth_rate_limited", "Sign-in attempt capacity reached. Try again later.", 429)
    # Reservations commit before password verification, including failed attempts.
    conn.execute("INSERT INTO auth_attempts VALUES(?,1,?) ON CONFLICT(attempt_key) DO UPDATE SET count=count+1", (key, current))


def access_spec(conn, actor, access, allow_empty=False):
    require(isinstance(access, list) and (allow_empty or bool(access)) and len(access) <= 100,
            "invalid_access", "Select workspaces and a role for each.")
    seen, result = set(), []
    for entry in access:
        require(isinstance(entry, dict) and set(entry) == {"space_id", "role"}
                and isinstance(entry["space_id"], str) and isinstance(entry["role"], str)
                and entry["space_id"] not in seen and entry["role"] in ROLES and entry["role"] != "owner",
                "invalid_access", "Choose each workspace once and a non-owner role.")
        sid, role = entry["space_id"], entry["role"]
        authorize(conn, actor, sid, "manage")
        for operation in ROLES[role]:
            authorize(conn, actor, sid, operation)
        seen.add(sid)
        result.append({"space_id": sid, "role": role})
    return result


def current_access(conn, principal_id):
    result = {}
    for grant in conn.execute("SELECT * FROM grants WHERE principal_id=? AND revoked=0 AND (expires_at IS NULL OR expires_at>?)",
                              (principal_id, now())):
        result.setdefault(grant["space_id"], set()).update(loads(grant["operations"]))
    return [{"space_id": sid, "operations": sorted(ops),
             "role": next((name for name, values in ROLES.items() if set(values) == ops), "custom")}
            for sid, ops in sorted(result.items())]


def replace_access(conn, actor, principal_id, access):
    for row in conn.execute("SELECT id FROM grants WHERE principal_id=? AND revoked=0", (principal_id,)).fetchall():
        conn.execute("UPDATE grants SET revoked=1 WHERE id=?", (row["id"],))
        recovery_event(conn, "grant.revoke", row["id"])
    for entry in access:
        conn.execute("INSERT INTO grants VALUES(?,?,?,?,NULL,0)",
                     (uid("grant"), principal_id, entry["space_id"], dumps(ROLES[entry["role"]])))
    revoke_all(conn, principal_id)
    conn.execute("INSERT INTO member_versions VALUES(?,1) ON CONFLICT(principal_id) DO UPDATE SET revision=revision+1", (principal_id,))
    audit(conn, actor, "member.access", principal_id, details={"space_ids": [x["space_id"] for x in access]})


def revoke_all(conn, principal_id):
    for row in conn.execute("SELECT id FROM credentials WHERE principal_id=? AND revoked=0", (principal_id,)).fetchall():
        conn.execute("UPDATE credentials SET revoked=1 WHERE id=?", (row["id"],))
        recovery_event(conn, "credential.revoke", row["id"])


def session(conn, principal):
    access = current_access(conn, principal["id"])
    require(principal["active"] and (access or principal["org_admin"]), "no_access",
            "This account has no active workspace access. Contact your administrator.", 403)
    ops = sorted({op for item in access for op in item["operations"]})
    expiry = now() + SESSION_SECONDS
    credential = issue(conn, principal["id"], ["*"] if principal["org_admin"] else ops,
                       ["*"] if principal["org_admin"] else [item["space_id"] for item in access], expiry)
    actor = Actor(principal["id"], principal["org_id"], credential["credential_id"])
    audit(conn, actor, "account.login", principal["id"])
    return {**credential, "expires_at": expiry, "principal_id": principal["id"], "organization_id": principal["org_id"]}


def recover_owner(brain, username_value, password, organization=None):
    """Filesystem-owner boundary only. Intentionally not a public Brain/RPC method."""
    login = username(username_value)
    with brain.store.transaction() as conn:
        rows = conn.execute("SELECT a.principal_id,a.org_id,o.slug FROM user_accounts a JOIN principals p ON p.id=a.principal_id JOIN organizations o ON o.id=a.org_id WHERE a.username=? AND a.enabled=1 AND p.org_admin=1 AND p.active=1 AND (? IS NULL OR o.id=? OR o.slug=?)",
                            (login, organization, organization, organization)).fetchall()
        require(len(rows) == 1, "owner_account_required", "Choose one active owner login; use --organization if needed.")
        target = rows[0]
    encoded = hash_password(password, login)
    with brain.store.transaction(write=True) as conn:
        require(conn.execute("SELECT value FROM meta WHERE key='recovery_mode'").fetchone()[0] == "0",
                "recovery_required", "Finish journal-based installation recovery first.")
        require(conn.execute("SELECT 1 FROM user_accounts a JOIN principals p ON p.id=a.principal_id WHERE a.principal_id=? AND a.enabled=1 AND p.active=1 AND p.org_admin=1", (target["principal_id"],)).fetchone(),
                "owner_account_required", "The owner account changed. Review it again.")
        conn.execute("UPDATE user_accounts SET password_hash=? WHERE principal_id=?", (encoded, target["principal_id"]))
        conn.execute("DELETE FROM auth_attempts WHERE attempt_key IN (?,?)",
                     (sha("login:" + target["org_id"] + ":" + login), sha("password-change:" + target["principal_id"])))
        revoke_all(conn, target["principal_id"])
        issued = issue(conn, target["principal_id"])
        actor = Actor(target["principal_id"], target["org_id"], issued["credential_id"])
        audit(conn, actor, "account.local_recovery", target["principal_id"])
    brain.flush_recovery_journal()
    return {**issued, "username": login, "company": target["slug"], "principal_id": target["principal_id"]}


class AccountsMixin:
    def setup_account(self, actor, username_value, password):
        login = username(username_value)
        with self.store.transaction() as conn:
            organization_admin(conn, actor)
        encoded = hash_password(password, login)
        with self.store.transaction(write=True) as conn:
            principal = live_principal(conn, actor)
            require(principal["kind"] == "human" and "*" in loads(principal["operations"])
                    and "*" in loads(principal["space_ids"]), "forbidden",
                    "Use the human owner's unrestricted credential to enroll the owner account.", 403)
            organization_admin(conn, actor)
            require(not conn.execute("SELECT 1 FROM user_accounts WHERE principal_id=? OR (org_id=? AND username=?)",
                                     (actor.principal_id, actor.org_id, login)).fetchone(), "already_exists", "An account already exists.", 409)
            conn.execute("INSERT INTO user_accounts VALUES(?,?,?,?,1,?)", (actor.principal_id, login, actor.org_id, encoded, now()))
            audit(conn, actor, "account.enroll", actor.principal_id)
        return {"principal_id": actor.principal_id, "username": login, "status": "enrolled", "next": "Sign in with login. Your local owner credential remains private."}

    def create_invite(self, actor, username_value, name, access, expires_at=None, reset_principal=None):
        login = username(username_value)
        text(name, maximum=120)
        secret, ident = secrets.token_urlsafe(32), uid("invite")
        with self.store.transaction(write=True) as conn:
            issuer = organization_admin(conn, actor)
            selected = access_spec(conn, actor, access)
            expiry = timestamp(expires_at) if expires_at is not None else min(now() + INVITE_SECONDS, issuer["expires_at"] or float("inf"))
            require(now() < expiry <= now() + 7 * 86400 and (issuer["expires_at"] is None or expiry <= issuer["expires_at"]),
                    "invalid_expiry", "Invitations expire within 7 days and cannot outlive their issuer.")
            existing = conn.execute("SELECT a.*,p.org_admin FROM user_accounts a JOIN principals p ON p.id=a.principal_id WHERE a.org_id=? AND a.username=?",
                                    (actor.org_id, login)).fetchone()
            target = conn.execute("SELECT * FROM principals WHERE id=? AND org_id=? AND org_admin=0 AND kind='human'", (reset_principal, actor.org_id)).fetchone() if reset_principal else None
            old_account = conn.execute("SELECT username FROM user_accounts WHERE principal_id=?", (reset_principal,)).fetchone() if target else None
            require((existing is None and reset_principal is None) or
                    (target and (existing is None or existing["principal_id"] == reset_principal)
                     and (old_account is None or old_account[0] == login)),
                    "account_exists", "Use an explicit reset invitation for an existing non-admin account.", 409)
            conn.execute("UPDATE company_invites SET state='revoked' WHERE org_id=? AND username=? AND state='pending'", (actor.org_id, login))
            revision = conn.execute("SELECT revision FROM member_versions WHERE principal_id=?", (reset_principal,)).fetchone() if reset_principal else None
            conn.execute("INSERT INTO company_invites VALUES(?,?,?,?,?,?,?,?,?,'pending',?,?,?)",
                         (ident, actor.org_id, login, name, sha(secret), dumps(selected), actor.principal_id,
                          actor.credential_id, expiry, reset_principal, revision[0] if revision else 0, now()))
            audit(conn, actor, "invite.create", ident, details={"reset": reset_principal is not None})
            organization = conn.execute("SELECT slug FROM organizations WHERE id=?", (actor.org_id,)).fetchone()[0]
        return {"id": ident, "secret": secret, "organization_id": actor.org_id, "company": organization,
                "username": login, "expires_at": expiry, "access": selected, "single_use": True}

    def list_invites(self, actor):
        with self.store.transaction() as conn:
            organization_admin(conn, actor)
            return [dict(row) for row in conn.execute("SELECT id,username,display_name,expires_at,state FROM company_invites WHERE org_id=? ORDER BY created_at DESC LIMIT 100", (actor.org_id,))]

    def revoke_invite(self, actor, invite_id):
        with self.store.transaction(write=True) as conn:
            organization_admin(conn, actor)
            row = conn.execute("SELECT id FROM company_invites WHERE id=? AND org_id=?", (invite_id, actor.org_id)).fetchone()
            require(row, "not_found", "Invitation not found.", 404)
            conn.execute("UPDATE company_invites SET state='revoked' WHERE id=? AND state='pending'", (invite_id,))
            recovery_event(conn, "invite.revoke", invite_id)
            audit(conn, actor, "invite.revoke", invite_id)
        self.flush_recovery_journal()
        return {"status": "revoked"}

    def accept_invite(self, organization, invite_id, secret, password):
        require(isinstance(secret, str) and 20 <= len(secret) <= 100 and isinstance(invite_id, str)
                and isinstance(organization, str), "invalid_invite", "Invalid or expired invitation.", 401)
        with self.store.transaction() as conn:
            row = conn.execute("SELECT * FROM company_invites WHERE id=? AND org_id=?", (invite_id, organization)).fetchone()
            require(row and row["state"] == "pending" and row["expires_at"] > now()
                    and hmac.compare_digest(row["secret_hash"], sha(secret)), "invalid_invite", "Invalid or expired invitation.", 401)
            login = row["username"]
        encoded = hash_password(password, login)
        with self.store.transaction(write=True) as conn:
            row = conn.execute("SELECT * FROM company_invites WHERE id=? AND org_id=?", (invite_id, organization)).fetchone()
            require(row and row["state"] == "pending" and row["expires_at"] > now()
                    and hmac.compare_digest(row["secret_hash"], sha(secret)), "invalid_invite", "Invalid or expired invitation.", 401)
            issuer = Actor(row["issuer_id"], row["org_id"], row["issuer_credential"])
            organization_admin(conn, issuer)
            access = access_spec(conn, issuer, loads(row["access"]))
            if row["reset_principal"]:
                principal_id = row["reset_principal"]
                revision = conn.execute("SELECT revision FROM member_versions WHERE principal_id=?", (principal_id,)).fetchone()
                require((revision[0] if revision else 0) == row["reset_revision"], "invalid_invite",
                        "Membership changed since this reset invitation. Ask for a new invitation.", 409)
                require(conn.execute("SELECT 1 FROM principals WHERE id=? AND org_id=? AND org_admin=0", (principal_id, organization)).fetchone(),
                        "invalid_invite", "Invalid or expired invitation.", 401)
                conn.execute("INSERT INTO user_accounts VALUES(?,?,?,?,1,?) ON CONFLICT(principal_id) DO UPDATE SET password_hash=excluded.password_hash,enabled=1",
                             (principal_id, login, organization, encoded, now()))
                conn.execute("UPDATE principals SET active=1 WHERE id=?", (principal_id,))
            else:
                require(not conn.execute("SELECT 1 FROM user_accounts WHERE org_id=? AND username=?", (organization, login)).fetchone(),
                        "invalid_invite", "Invalid or expired invitation.", 401)
                principal_id = uid("principal")
                conn.execute("INSERT INTO principals VALUES(?,?,?,?,0,1,?)", (principal_id, organization, row["display_name"], "human", now()))
                conn.execute("INSERT INTO user_accounts VALUES(?,?,?,?,1,?)", (principal_id, login, organization, encoded, now()))
            replace_access(conn, issuer, principal_id, access)
            conn.execute("UPDATE company_invites SET state='accepted' WHERE id=?", (invite_id,))
            audit(conn, issuer, "invite.accept", invite_id, details={"principal_id": principal_id})
            result = session(conn, conn.execute("SELECT * FROM principals WHERE id=?", (principal_id,)).fetchone())
        self.flush_recovery_journal()
        return result

    def login(self, organization, username_value, password):
        require(isinstance(organization, str) and 0 < len(organization) <= 120, "invalid_login", "Invalid company, username or password.", 401)
        try:
            login = username(username_value)
        except BrainError:
            login = "invalid-login"
        with self.store.transaction(write=True) as conn:
            require(conn.execute("SELECT value FROM meta WHERE key='recovery_mode'").fetchone()[0] == "0",
                    "unavailable", "Sign-in is unavailable during recovery.", 503)
            company = conn.execute("SELECT id FROM organizations WHERE id=? OR slug=?", (organization, organization)).fetchone()
            key = sha("login:" + (company[0] if company else organization) + ":" + login)
            reserve_attempt(conn, key)
            row = conn.execute("SELECT a.*,p.active FROM user_accounts a JOIN principals p ON p.id=a.principal_id JOIN organizations o ON o.id=a.org_id WHERE (o.id=? OR o.slug=?) AND a.username=?", (organization, organization, login)).fetchone()
            encoded = row["password_hash"] if row else ""
        valid = verify_password(password, encoded)
        require(valid and row and row["enabled"] and row["active"], "invalid_login", "Invalid company, username or password.", 401)
        with self.store.transaction(write=True) as conn:
            current = conn.execute("SELECT a.*,p.active FROM user_accounts a JOIN principals p ON p.id=a.principal_id WHERE a.principal_id=?", (row["principal_id"],)).fetchone()
            require(current and current["enabled"] and current["active"] and current["password_hash"] == encoded,
                    "invalid_login", "Invalid company, username or password.", 401)
            conn.execute("DELETE FROM auth_attempts WHERE attempt_key=?", (key,))
            return session(conn, conn.execute("SELECT * FROM principals WHERE id=?", (row["principal_id"],)).fetchone())

    def list_members(self, actor):
        with self.store.transaction() as conn:
            organization_admin(conn, actor)
            result = []
            for row in conn.execute("SELECT p.id,p.name,p.kind,p.org_admin,p.active,a.username,a.enabled,COALESCE(v.revision,0) AS revision FROM principals p LEFT JOIN user_accounts a ON a.principal_id=p.id LEFT JOIN member_versions v ON v.principal_id=p.id WHERE p.org_id=? ORDER BY p.name", (actor.org_id,)):
                item = dict(row)
                item["access"] = current_access(conn, row["id"])
                item["groups"] = [dict(g) for g in conn.execute("SELECT g.id,g.name FROM groups g JOIN group_members m ON m.group_id=g.id WHERE m.principal_id=? AND g.org_id=? ORDER BY g.name", (row["id"], actor.org_id))]
                result.append(item)
            return result

    def set_member_access(self, actor, principal_id, access, expected_revision):
        require(type(expected_revision) is int and expected_revision >= 0, "invalid_revision", "Provide the current membership revision.")
        with self.store.transaction(write=True) as conn:
            organization_admin(conn, actor)
            principal = conn.execute("SELECT * FROM principals WHERE id=? AND org_id=? AND org_admin=0", (principal_id, actor.org_id)).fetchone()
            require(principal, "forbidden", "Select a non-admin employee/service. Owner access is managed separately.", 403)
            for current in current_access(conn, principal_id):
                authorize(conn, actor, current["space_id"], "manage")
                for op in current["operations"]:
                    authorize(conn, actor, current["space_id"], op)
            selected = access_spec(conn, actor, access, allow_empty=True)
            revision = conn.execute("SELECT revision FROM member_versions WHERE principal_id=?", (principal_id,)).fetchone()
            require((revision[0] if revision else 0) == expected_revision, "revision_conflict", "Membership changed. Reload and review it again.", 409)
            replace_access(conn, actor, principal_id, selected)
        self.flush_recovery_journal()
        return {"principal_id": principal_id, "revision": expected_revision + 1, "access": selected,
                "sessions_revoked": True, "next": "Employee must sign in again. Service credentials must be reissued deliberately."}

    def disable_member(self, actor, principal_id):
        with self.store.transaction(write=True) as conn:
            organization_admin(conn, actor)
            require(conn.execute("SELECT 1 FROM principals WHERE id=? AND org_id=? AND org_admin=0", (principal_id, actor.org_id)).fetchone(),
                    "forbidden", "Select a non-admin member.", 403)
            conn.execute("UPDATE principals SET active=0 WHERE id=?", (principal_id,))
            conn.execute("UPDATE user_accounts SET enabled=0,password_hash='' WHERE principal_id=?", (principal_id,))
            for row in conn.execute("SELECT group_id FROM group_members WHERE principal_id=?", (principal_id,)).fetchall():
                recovery_event(conn, "group.remove", row["group_id"], {"principal_id": principal_id})
            conn.execute("DELETE FROM group_members WHERE principal_id=?", (principal_id,))
            revoke_all(conn, principal_id)
            conn.execute("UPDATE company_invites SET state='revoked' WHERE reset_principal=? AND state='pending'", (principal_id,))
            conn.execute("INSERT INTO member_versions VALUES(?,1) ON CONFLICT(principal_id) DO UPDATE SET revision=revision+1", (principal_id,))
            recovery_event(conn, "account.disable", principal_id)
            audit(conn, actor, "account.disable", principal_id)
        self.flush_recovery_journal()
        return {"status": "disabled", "principal_id": principal_id}

    def change_password(self, actor, old_password, new_password):
        key = sha("password-change:" + actor.principal_id)
        with self.store.transaction(write=True) as conn:
            live_principal(conn, actor)
            reserve_attempt(conn, key)
            row = conn.execute("SELECT * FROM user_accounts WHERE principal_id=? AND enabled=1", (actor.principal_id,)).fetchone()
        require(row and verify_password(old_password, row["password_hash"]), "invalid_login", "Current password did not verify.", 401)
        encoded = hash_password(new_password, row["username"])
        with self.store.transaction(write=True) as conn:
            live_principal(conn, actor)
            require(conn.execute("SELECT 1 FROM user_accounts WHERE principal_id=? AND enabled=1 AND password_hash=?", (actor.principal_id, row["password_hash"])).fetchone(),
                    "invalid_login", "Account changed. Sign in again.", 401)
            conn.execute("UPDATE user_accounts SET password_hash=? WHERE principal_id=?", (encoded, actor.principal_id))
            conn.execute("DELETE FROM auth_attempts WHERE attempt_key=?", (key,))
            revoke_all(conn, actor.principal_id)
            result = session(conn, conn.execute("SELECT * FROM principals WHERE id=?", (actor.principal_id,)).fetchone())
        self.flush_recovery_journal()
        return result
