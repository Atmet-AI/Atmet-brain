"""Only an annotated release tag from main can feed the publishing job."""

import os
from pathlib import Path
import re
import subprocess
import tomllib


def check_release(root, tag):
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    if not re.fullmatch(r"v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", tag) or tag != "v" + version:
        raise ValueError("Release tag must exactly match the stable package version.")

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()

    if git("cat-file", "-t", "refs/tags/" + tag) != "tag":
        raise ValueError("Release tags must be annotated.")
    if git("rev-parse", "HEAD") != git("rev-parse", "refs/tags/" + tag + "^{commit}"):
        raise ValueError("Checkout does not match the selected immutable release tag.")
    if subprocess.run(["git", "merge-base", "--is-ancestor", "HEAD", "origin/main"], cwd=root).returncode:
        raise ValueError("Release commit must belong to origin/main.")


if __name__ == "__main__":
    try:
        check_release(Path(__file__).resolve().parents[1], os.environ.get("RELEASE_TAG", ""))
    except (ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
    print("PASS: annotated release tag matches the package, checkout and main history")
