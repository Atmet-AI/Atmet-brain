"""Private, explicit remote connection profiles. No local database access."""

import json
import shlex
from pathlib import Path

from .client import Client
from .errors import require
from .util import private_write, slug


def profile_path(home, name):
    return Path(home) / "connections" / (slug(name) + ".json")


def load_connection(home, name):
    path = profile_path(home, name)
    require(path.is_file() and not path.is_symlink(), "connection_missing", "Connection not found. Run connect first.")
    record = json.loads(path.read_text())
    require(isinstance(record, dict) and set(record) == {"endpoint", "token_file", "ca_file", "principal_id", "organization_id"},
            "invalid_connection", "Connection file is invalid. Reconnect with a current credential.")
    client = Client(record["endpoint"], Path(record["token_file"]).read_text().strip(), ca_file=record["ca_file"])
    actor = client.call("identity.me")
    require(all(actor.get(key) == record[key] for key in ("principal_id", "organization_id")),
            "identity_changed", "Connection identity changed. Reconnect explicitly.")
    return client, actor


def connect(home, name, endpoint, token_file, ca_file=None):
    path = profile_path(home, name)
    require(not path.exists(), "already_exists", "Connection exists. Remove it explicitly before reconnecting.", 409)
    token = Path(token_file).expanduser().read_text().strip()
    ca_file = str(Path(ca_file).expanduser().resolve()) if ca_file else None
    client = Client(endpoint, token, ca_file=ca_file)
    actor = client.call("identity.me")  # Validate before writing any connection state.
    secret = Path(home).resolve() / "client-tokens" / (slug(name) + ".token")
    require(not secret.exists(), "already_exists", "A connection token file already exists.", 409)
    private_write(secret, token + "\n", overwrite=False)
    record = {"endpoint": client.endpoint, "token_file": str(secret), "ca_file": ca_file,
              "principal_id": actor["principal_id"], "organization_id": actor["organization_id"]}
    try:
        private_write(path, json.dumps(record, indent=2) + "\n", overwrite=False)
    except BaseException:
        secret.unlink()
        raise
    return {"connection": name, "endpoint": client.endpoint, "identity": actor,
            "next": shlex.join(["atmet-brain", "--home", str(Path(home).expanduser().resolve()), "--connection", name, "space"])}


def list_connections(home):
    result = []
    for path in sorted((Path(home) / "connections").glob("*.json")):
        if path.is_symlink():
            continue
        data = json.loads(path.read_text())
        result.append({"name": path.stem, "endpoint": data["endpoint"], "principal_id": data["principal_id"]})
    return result


def remove_connection(home, name):
    path = profile_path(home, name)
    require(path.is_file() and not path.is_symlink(), "connection_missing", "Connection not found.")
    path.unlink()
    secret = Path(home) / "client-tokens" / (slug(name) + ".token")
    if secret.exists() or secret.is_symlink():
        secret.unlink()
    return {"removed": name, "note": "Local connection removed. Revoke the credential on the server to remove its authority."}
