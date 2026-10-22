"""Inspect the exact npm tarball, including its matching core wheel and digest."""

import argparse
import hashlib
import json
from pathlib import Path
import tarfile

from prepare_npm import validate_wheel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    with tarfile.open(args.archive, "r:gz") as archive:
        entries = archive.getmembers()
        if any(not member.isfile() for member in entries):
            parser.error("npm archive must contain regular files only.")
        names = [member.name for member in entries]
        if len(names) != len(set(names)):
            parser.error("Duplicate npm archive entries.")
        def read(name):
            return archive.extractfile("package/" + name).read()
        package = json.loads(read("package.json"))
        version = package["version"]
        if version != package["atmetBrain"]["engineVersion"]:
            parser.error("npm/core version mismatch.")
        filename = f"atmet_brain-{version}-py3-none-any.whl"
        expected = {"package/" + name for name in ["LICENSE", "NOTICE", "README.md", "package.json",
                    "bin/atmet-brain.mjs", "lib/bootstrap.mjs", "lib/launcher.mjs",
                    "vendor/engine.json", "vendor/" + filename]}
        if set(names) != expected:
            parser.error("npm archive does not match its exact public file allowlist.")
        manifest = json.loads(read("vendor/engine.json"))
        data = read("vendor/" + filename)
        if manifest != {"schemaVersion": 1, "version": version, "file": filename,
                        "sha256": hashlib.sha256(data).hexdigest()}:
            parser.error("Bundled engine manifest/digest mismatch.")
        validate_wheel(data, version)
    print("PASS: npm archive file allowlist, wheel identity, license and digest")


if __name__ == "__main__":
    main()
