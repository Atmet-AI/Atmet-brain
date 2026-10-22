"""Refuse unsafe npm releases and verify the public archive after publishing."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import time
import tomllib
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REGISTRY = "https://registry.npmjs.org/atmet-brain/"


class RegistryPending(ValueError):
    """The accepted release has not propagated to public metadata yet."""


def version_parts(version):
    if not isinstance(version, str) or not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", version):
        raise ValueError("Automatic latest publication requires MAJOR.MINOR.PATCH.")
    return tuple(map(int, version.split(".")))


def fetch_metadata(selector):
    request = Request(REGISTRY + selector, headers={"Cache-Control": "no-cache", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=15) as response:
            data = response.read(2_000_001)
    except HTTPError as error:
        if error.code == 404:
            return None
        raise
    if len(data) > 2_000_000:
        raise ValueError("Unexpectedly large npm metadata response.")
    result = json.loads(data)
    if not isinstance(result, dict):
        raise ValueError("Unexpected npm metadata response.")
    return result


def before(version, fetch=fetch_metadata):
    target = version_parts(version)
    if fetch(version) is not None:
        raise ValueError("This npm version already exists. Never upload it again.")
    latest = fetch("latest")
    if latest is None:
        raise ValueError("Expected existing package/latest metadata; check the registry before publishing.")
    if target <= version_parts(latest.get("version")):
        raise ValueError("Release would downgrade npm latest. Use a newer version.")
    return {"version": version, "previous_latest": latest["version"], "available": True}


def after(version, archive, fetch=fetch_metadata):
    version_parts(version)
    metadata = fetch(version)
    latest = fetch("latest")
    if not metadata:
        raise RegistryPending("Published package identity is not visible yet.")
    if metadata.get("name") != "atmet-brain" or metadata.get("version") != version:
        raise ValueError("Unexpected public package identity.")
    expected = "sha512-" + base64.b64encode(hashlib.sha512(archive).digest()).decode("ascii")
    dist = metadata.get("dist", {})
    if dist.get("integrity") != expected or dist.get("shasum") != hashlib.sha1(archive).hexdigest():
        raise ValueError("Public npm archive does not match the reviewed build.")
    if not latest or latest.get("version") != version:
        raise RegistryPending("npm latest does not resolve to the published version.")
    return {"package": "atmet-brain", "version": version, "latest": version,
            "integrity": expected, "sha256": hashlib.sha256(archive).hexdigest(),
            "registry_verified": True, "provenance": dist.get("attestations")}


def wait_after(version, archive, fetch=fetch_metadata, attempts=121, interval=5):
    for attempt in range(attempts):
        try:
            return after(version, archive, fetch)
        except RegistryPending:
            if attempt == attempts - 1:
                raise
            time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["before", "after"])
    parser.add_argument("archive", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    archive = args.archive.read_bytes()
    # The workflow checks archive contents/version before reaching this guard.
    result = before(version) if args.phase == "before" else wait_after(version, archive)
    if args.receipt:
        args.receipt.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
