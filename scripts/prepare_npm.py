"""Bundle a reviewed universal core wheel inside the npm package before packing."""

import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import shutil
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def validate_wheel(data, version):
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as wheel:
        prefix = f"atmet_brain-{version}.dist-info/"
        metadata = BytesParser().parsebytes(wheel.read(prefix + "METADATA"))
        if metadata["Name"] != "atmet-brain" or metadata["Version"] != version:
            raise ValueError("Wheel metadata must match the launcher and core version.")
        entry = wheel.read(prefix + "entry_points.txt").decode()
        if "atmet-brain = atmet_brain.cli:main" not in entry:
            raise ValueError("Wheel is missing the core CLI entry point.")
        wheel.read("atmet_brain/schema.sql")
        for name in ("LICENSE", "NOTICE"):
            if wheel.read(prefix + "licenses/" + name) != (ROOT / name).read_bytes():
                raise ValueError("Bundled core license/notice differs from the source.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, type=Path)
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    package = ROOT / "npm/atmet-brain"
    metadata = json.loads((package / "package.json").read_text())
    if metadata["version"] != version or metadata["atmetBrain"]["engineVersion"] != version:
        parser.error("Engine and npm package versions differ.")
    filename = f"atmet_brain-{version}-py3-none-any.whl"
    if args.wheel.name != filename:
        parser.error("Expected the matching universal wheel: " + filename)
    data = args.wheel.read_bytes()
    validate_wheel(data, version)
    destination = package / "vendor"
    # Generated distribution material only; never store company state here.
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir()
    (destination / filename).write_bytes(data)
    manifest = {"schemaVersion": 1, "version": version, "file": filename,
                "sha256": hashlib.sha256(data).hexdigest()}
    (destination / "engine.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("PASS: bundled matching core wheel for npm " + version)


if __name__ == "__main__":
    main()
