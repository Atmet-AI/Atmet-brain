"""Only a reviewed immutable version tag can feed the registry publishing job."""

import os
from pathlib import Path
import re
import subprocess
import tomllib

root = Path(__file__).resolve().parents[1]
tag = os.environ.get("RELEASE_TAG", "")
version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
if not re.fullmatch(r"v\d+\.\d+\.\d+", tag) or tag != "v" + version:
    raise SystemExit("Release tag must exactly match the package version.")
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
target = subprocess.check_output(["git", "rev-parse", "refs/tags/" + tag + "^{commit}"], cwd=root, text=True).strip()
if head != target:
    raise SystemExit("Checkout does not match the selected immutable release tag.")
print("PASS: release tag matches the package and checkout")
