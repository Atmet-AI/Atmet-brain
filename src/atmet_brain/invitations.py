"""Private one-time invitation files and verified password-session storage."""

import json
from pathlib import Path
import stat

from .client import Client
from .connections import profile_path
from .errors import BrainError, require
from .sharing import validate_route
from .util import now, private_write, slug

ANONYMOUS = "anonymous-account-request-no-bearer"


def read_private_json(path):
    import os
    path = Path(path).expanduser()
    require(path.is_file() and not path.is_symlink(), "invalid_invite_file", "Choose the private invitation file supplied by your administrator.")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW), "rb") as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "invalid_invite_file", "Choose a regular invitation file.")
        data = stream.read(65537)
    require(len(data) <= 65536, "invalid_invite_file", "Invitation exceeds the supported size.")
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError, RecursionError):
        raise BrainError("invalid_invite_file", "Invitation is not valid JSON.") from None
    require(isinstance(value, dict), "invalid_invite_file", "Invalid invitation file.")
    return value


def read_invitation(path):
    record = read_private_json(path)
    fields = {"format", "endpoint", "ssh", "organization_id", "company", "username", "invite_id", "secret", "expires_at"}
    require(set(record) == fields and record["format"] == "atmet-invite-v1", "invalid_invite_file", "Use a current company invitation file.")
    validate_route(record["endpoint"], record["ssh"])
    require(type(record["expires_at"]) in {int, float} and now() < record["expires_at"] < now() + 8 * 86400,
            "invite_expired", "Invitation expired. Ask your administrator for a new one.")
    for key in ["organization_id", "company", "username", "invite_id", "secret"]:
        require(isinstance(record[key], str) and 0 < len(record[key]) <= 200, "invalid_invite_file", "Invalid invitation fields.")
    return record


def route_client(route, token=ANONYMOUS, ca_file=None):
    if route.get("ssh"):
        from .ssh import SSHClient
        require(not ca_file, "invalid_connection", "SSH connections do not use a CA file.")
        return SSHClient(route["ssh"], token)
    return Client(route["endpoint"], token, ca_file)


def save_invitation(client, output, *, username_value, name, access, route, reset_principal=None, expires_at=None):
    validate_route(route.get("endpoint"), route.get("ssh"))
    output = Path(output).expanduser()
    require(not output.is_symlink(), "already_exists", "Choose a new private file.")
    private_write(output, "", overwrite=False)
    created = None
    try:
        params = {"username_value": username_value, "name": name, "access": access}
        if reset_principal is not None:
            params["reset_principal"] = reset_principal
        if expires_at is not None:
            params["expires_at"] = expires_at
        created = client.call("invites.create", **params)
        record = {"format": "atmet-invite-v1", "endpoint": route.get("endpoint"), "ssh": route.get("ssh"),
                  "organization_id": created["organization_id"], "company": created["company"],
                  "username": created["username"], "invite_id": created["id"], "secret": created["secret"], "expires_at": created["expires_at"]}
        private_write(output, json.dumps(record, indent=2) + "\n")
    except (BrainError, OSError, ValueError):
        revoked = False
        if created:
            try:
                client.call("invites.revoke", invite_id=created["id"])
                revoked = True
            except (BrainError, OSError):
                pass
        output.unlink(missing_ok=True)
        if created:
            raise BrainError("invite_save_failed", "Invitation file could not be saved. " +
                             ("The invitation was revoked." if revoked else "Revoke invitation " + created["id"] + " before retrying."), 409) from None
        raise
    return {"invitation_id": created["id"], "username": created["username"], "company": created["company"],
            "expires_at": created["expires_at"], "single_use": True, "private_file": str(output.resolve()),
            "delivery": "Give this file privately to this employee. They run join and choose their own password. No email was sent."}


def save_session(home, name, route, issued, login, *, ca_file=None, local=False, replacing=False):
    """Validate remote identity before storing; never silently replace another identity."""
    home = Path(home).expanduser().resolve()
    if local:
        from .brain import Brain
        from .feedback import LocalClient
        client = LocalClient(Brain(home), issued["token"])
        token_path, profile = home / "session.token", home / "login.json"
    else:
        client = route_client(route, issued["token"], ca_file)
        token_path, profile = home / "client-tokens" / (slug(name) + ".token"), profile_path(home, name)
    try:
        identity = client.call("identity.me")
        require(all(identity[key] == issued[key] for key in ["organization_id", "principal_id", "credential_id"]),
                "identity_changed", "Sign-in identity does not match the server.", 409)
        require(identity.get("username") == login, "identity_changed", "The server returned another login identity.", 409)
        spaces = client.call("spaces.list")
        if profile.exists():
            require(replacing and not profile.is_symlink(), "already_exists", "Choose a new connection name.", 409)
            previous = read_private_json(profile)
            require(all(previous[key] == identity[key] for key in ["organization_id", "principal_id"]),
                    "identity_changed", "This connection belongs to another identity. Use a different name.", 409)
        else:
            require(not token_path.exists() and not token_path.is_symlink() and not profile.is_symlink(),
                    "already_exists", "Choose a new private connection.", 409)
        record = {"principal_id": identity["principal_id"], "organization_id": identity["organization_id"],
                  "username": login, "company": identity["company"], "credential_id": issued["credential_id"], "expires_at": issued["expires_at"]}
        if not local:
            record.update(endpoint=client.endpoint, token_file=str(token_path), ca_file=str(Path(ca_file).expanduser().resolve()) if ca_file else None)
            if route.get("ssh"):
                record["ssh"] = route["ssh"]
        private_write(token_path, issued["token"] + "\n")
        private_write(profile, json.dumps(record, indent=2) + "\n")
    except (BrainError, OSError, ValueError):
        try:
            client.call("credentials.revoke", credential_id=issued["credential_id"])
        except (BrainError, OSError):
            raise BrainError("session_save_failed", "Session was not safely saved. Ask an administrator to revoke credential " + issued["credential_id"] + ".", 409) from None
        raise
    return {"signed_in": True, "connection": None if local else name, "username": login, "identity": identity,
            "spaces": spaces, "expires_at": issued["expires_at"], "credential_file": str(token_path),
            "note": "Password was not saved. Current workspace and source permissions still apply."}
