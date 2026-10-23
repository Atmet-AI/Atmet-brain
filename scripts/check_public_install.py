"""Check the anonymous public launcher, allowing bounded npm metadata propagation."""

import argparse
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile
import time


def check(version):
    if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", version):
        raise ValueError("Choose an exact stable release version.")
    with tempfile.TemporaryDirectory(prefix="atmet-public-install-") as temporary:
        home = Path(temporary)
        (home / "user.npmrc").write_text("registry=https://registry.npmjs.org/\n")
        (home / "global.npmrc").write_text("")
        env = {k: v for k, v in os.environ.items() if not k.startswith("ATMET_")
               and k not in {"NODE_AUTH_TOKEN", "NPM_TOKEN", "PYTHONPATH"}}
        env.update(ATMET_LAUNCHER_HOME=str(home / "runtime"), NPM_CONFIG_USERCONFIG=str(home / "user.npmrc"),
                   NPM_CONFIG_GLOBALCONFIG=str(home / "global.npmrc"))
        for attempt in range(1, 14):
            env["NPM_CONFIG_CACHE"] = str(home / ("cache-" + str(attempt)))
            result = subprocess.run(["npx", "--yes", "--prefer-online", "--package=atmet-brain@" + version,
                                     "atmet-brain", "--version"], capture_output=True, text=True, env=env, timeout=180)
            if result.returncode == 0:
                if result.stdout.strip() != "Atmet Brain " + version:
                    raise ValueError("The public launcher ran an unexpected engine.")
                return {"version": version, "anonymous_public_install": True, "attempts": attempt,
                        "platform": platform.system(), "machine": platform.machine()}
            if not re.search(r"npm (?:ERR!|error) code (?:ETARGET|E404)\b", result.stderr) or attempt == 13:
                raise ValueError("Public install failed:\n" + result.stderr[-6000:])
            print("npm package metadata is still propagating; retrying with a fresh cache.", flush=True)
            time.sleep(10)
    raise AssertionError("Unreachable")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        report = check(args.version)
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        raise SystemExit(str(error)) from error
    if args.receipt:
        args.receipt.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
