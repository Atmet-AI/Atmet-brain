"""Private member connection files. They contain a credential, never owner access."""

import json
import math
import os
from pathlib import Path
import stat
from urllib.parse import urlparse

from .client import Client
from .auth import ROLES
from .connections import connect
from .errors import require
from .ssh import validate_ssh
from .util import now, private_write, slug, text


def validate_route(endpoint=None, ssh=None):
    require((endpoint is None) != (ssh is None), "invalid_route", "Choose HTTPS or automatic SSH forwarding.")
    if ssh is not None:
        validate_ssh(ssh)
    else:
        Client(endpoint, "route-validation-credential")
        require(urlparse(endpoint).scheme == "https", "insecure_endpoint", "Team connection files require HTTPS, or choose SSH.")


def create_share(brain, actor, name, space_names, role, output, *, endpoint=None, ssh=None, expires_at=None):
    validate_route(endpoint, ssh)
    available = {space["slug"]: space["id"] for space in brain.list_spaces(actor)}
    require(isinstance(space_names, list) and space_names and len(space_names) == len(set(space_names))
            and all(value in available for value in space_names), "invalid_spaces", "Select distinct workspace names from this company.")
    output = Path(output).expanduser()
    # Reserve before provisioning so a path error cannot strand a new credential.
    private_write(output, "", overwrite=False)
    member = None
    try:
        member = brain.add_team_member(actor, name, [available[value] for value in space_names], role, expires_at=expires_at)
        record = {"format": "atmet-join-v1", "name": "company",
                  "endpoint": endpoint, "ssh": ssh,
                  "identity": {"principal_id": member["principal_id"], "organization_id": actor.org_id,
                               "credential_id": member["credential_id"]},
                  "expires_at": member["expires_at"], "token": member["token"],
                  "workspaces": space_names, "role": role}
        private_write(output, json.dumps(record, indent=2) + "\n")
    except BaseException:
        if member is not None:
            brain.revoke_credential(actor, member["credential_id"])
        output.unlink(missing_ok=True)
        raise
    return {"member": name, "workspaces": space_names, "role": role, "expires_at": member["expires_at"],
            "credential_id": member["credential_id"], "connection_file": str(output.resolve()),
            "delivery": "Give this private file only to its intended teammate. It contains their access credential.",
            "join": "On their device: npx atmet-brain@latest join"}


def read_share(path):
    path = Path(path).expanduser()
    require(path.is_file() and not path.is_symlink(), "invalid_join_file", "Choose a regular private connection file.")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), "rb") as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "invalid_join_file", "Choose a regular connection file.")
        body = stream.read(65537)
    require(len(body) <= 65536, "invalid_join_file", "Connection file is too large.")
    try:
        record = json.loads(body)
    except (ValueError, UnicodeError):
        record = None
    fields = {"format", "name", "endpoint", "ssh", "identity", "expires_at", "token", "workspaces", "role"}
    require(isinstance(record, dict) and set(record) == fields and record["format"] == "atmet-join-v1",
            "invalid_join_file", "Use an Atmet connection file supplied by your administrator.")
    slug(record["name"])
    validate_route(record["endpoint"], record["ssh"])
    Client("http://127.0.0.1", record["token"])
    identity = record["identity"]
    require(isinstance(identity, dict) and set(identity) == {"principal_id", "organization_id", "credential_id"}
            and all(isinstance(value, str) and 0 < len(value) <= 200 for value in identity.values()),
            "invalid_join_file", "Connection identity is invalid.")
    expiry = record["expires_at"]
    require(type(expiry) in {int, float} and math.isfinite(expiry) and expiry > now(),
            "join_expired", "This connection file has expired. Ask your administrator for current access.")
    require(isinstance(record["workspaces"], list) and 0 < len(record["workspaces"]) <= 30
            and all(isinstance(value, str) for value in record["workspaces"]), "invalid_join_file", "Invalid workspaces.")
    for value in record["workspaces"]:
        slug(value)
    text(record["role"], maximum=80)
    require(record["role"] in ROLES and record["role"] != "owner", "invalid_join_file", "Invalid member role.")
    return record


def join_share(home, path, name="company", ca_file=None, expected_record=None):
    record = read_share(path)
    require(expected_record is None or record == expected_record, "join_file_changed",
            "The connection file changed after review. Run Join again and review the new file.")
    # Never persist a token until the server confirms the pinned identity and scope.
    # connect accepts a credential path; a private temporary file is always removed.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="atmet-join-") as directory:
        token_file = Path(directory) / "member.token"
        private_write(token_file, record["token"])
        return connect(home, name, record["endpoint"], token_file, ca_file, ssh=record["ssh"],
                       expected_identity=record["identity"])
