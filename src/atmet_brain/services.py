"""Per-user launchd/systemd service management. No root or shell execution."""

import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

from .errors import BrainError, require
from .util import private_write


def service_spec(home, kind="api", space=None, token_file=None, port=7310, platform=None):
    platform = platform or sys.platform
    require(platform in {"darwin", "linux"}, "unsupported_platform", "Services support macOS launchd and Linux systemd user sessions.")
    home = Path(home).expanduser().resolve()
    require(kind in {"api", "worker"}, "invalid_service", "Choose api or worker.")
    require(1 <= port <= 65535, "invalid_port", "Choose a port from 1 to 65535.")
    require(kind != "worker" or (space and token_file), "invalid_service", "Worker services need --space and --token-file.")
    identity = hashlib.sha256((str(home) + ":" + (space or "")).encode()).hexdigest()[:12]
    label = f"pro.atmet.brain.{identity}.{kind}"
    # Preserve a virtual environment's executable symlink and its environment.
    command = [str(Path(sys.executable).absolute()), "-m", "atmet_brain", "--plain", "--home", str(home)]
    if kind == "api":
        command += ["serve", "--host", "127.0.0.1", "--port", str(port)]
    else:
        command += ["--token-file", str(Path(token_file).expanduser().resolve()), "worker", "--space", space, "--loop"]
    require(all(not any(ord(c) < 32 for c in arg) for arg in command), "invalid_service", "Service arguments cannot contain control characters.")
    logs = home / "service-logs"
    if platform == "darwin":
        destination = Path.home() / "Library/LaunchAgents" / (label + ".plist")
        body = plistlib.dumps({"Label": label, "ProgramArguments": command, "RunAtLoad": True,
                              "KeepAlive": True, "ThrottleInterval": 10, "WorkingDirectory": str(home),
                              "Umask": 0o077, "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
                              "StandardOutPath": str(logs / (label + ".out.log")),
                              "StandardErrorPath": str(logs / (label + ".err.log"))}).decode()
    else:
        destination = Path.home() / ".config/systemd/user" / (label + ".service")
        def quote(value):
            return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$") + '"'
        body = ("[Unit]\nDescription=Atmet Brain " + kind + "\n\n[Service]\nType=simple\nExecStart="
                + " ".join(quote(v) for v in command) + "\nRestart=on-failure\nRestartSec=5\nUMask=0077\n"
                "NoNewPrivileges=true\nEnvironment=PYTHONUNBUFFERED=1\n\n[Install]\nWantedBy=default.target\n")
    return {"label": label, "platform": platform, "path": str(destination), "content": body, "command": command,
            "kind": kind, "home": str(home), "logs": str(logs)}


def run_control(command, check=True):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        raise BrainError("service_manager_unavailable", "The user service manager is unavailable in this session.") from None
    if check and result.returncode:
        raise BrainError("service_control_failed", "Service control failed. Inspect the user service manager and private service logs.")
    return result


def manage_service(action, spec, start=False):
    path = Path(spec["path"])
    home = Path(spec["home"])
    record_path = home / "services" / (spec["label"] + ".json")
    require(not path.is_symlink() and not record_path.is_symlink(), "unsafe_service_path", "Service files cannot be symbolic links.")
    uid = str(os.getuid())
    target = "gui/" + uid + "/" + spec["label"]
    unit = path.name
    if action == "render":
        return spec
    if action == "install":
        require((home / "brain.sqlite3").is_file(), "not_initialized", "Run setup before installing a service.")
        require(not path.exists() and not record_path.exists(), "already_exists", "This service is already installed. Remove it before changing its definition.", 409)
        # A temporary uvx/source interpreter may not import the installed package without PYTHONPATH.
        probe = run_control([spec["command"][0], "-I", "-c", "import atmet_brain"], check=False)
        require(probe.returncode == 0, "service_runtime_missing", "Install the CLI persistently before installing a service.")
        if spec["kind"] == "worker":
            credential = Path(spec["command"][spec["command"].index("--token-file") + 1])
            require(credential.is_file(),
                    "credential_missing", "Worker credential file is missing.")
            from .auth import authorize
            from .brain import Brain
            brain = Brain(home)
            actor = brain.authenticate(credential.read_text().strip())
            with brain.store.transaction() as conn:
                authorize(conn, actor, spec["command"][spec["command"].index("--space") + 1], "process")
        Path(spec["logs"]).mkdir(mode=0o700, parents=True, exist_ok=True)
        private_write(path, spec["content"], overwrite=False)
        try:
            private_write(record_path, json.dumps({"content_hash": hashlib.sha256(spec["content"].encode()).hexdigest()}), overwrite=False)
        except BaseException:
            path.unlink()
            raise
        if spec["platform"] == "linux":
            run_control(["systemctl", "--user", "daemon-reload"])
        if start:
            return manage_service("start", spec)
        return {"installed": str(path), "label": spec["label"], "state": "installed", "next": "Run service start with the same --kind/--space selection."}
    if action == "status" and not path.exists():
        return {"label": spec["label"], "state": "not_installed"}
    require(path.is_file() and record_path.is_file(), "service_missing", "This service is not installed by Atmet Brain.")
    record = json.loads(record_path.read_text())
    require(hashlib.sha256(path.read_bytes()).hexdigest() == record["content_hash"],
            "service_modified", "The managed service file changed. Review it before managing it outside Atmet.")
    if action == "status":
        command = ["launchctl", "print", target] if spec["platform"] == "darwin" else ["systemctl", "--user", "is-active", unit]
        result = run_control(command, check=False)
        state = ("loaded" if spec["platform"] == "darwin" else "active") if result.returncode == 0 else "inactive"
        return {"label": spec["label"], "state": state, "path": str(path)}
    if spec["platform"] == "darwin":
        if action == "start":
            loaded = run_control(["launchctl", "print", target], check=False)
            if loaded.returncode:
                run_control(["launchctl", "bootstrap", "gui/" + uid, str(path)])
            else:
                run_control(["launchctl", "kickstart", target])
        elif action in {"stop", "remove"}:
            loaded = run_control(["launchctl", "print", target], check=False)
            if not loaded.returncode:
                run_control(["launchctl", "bootout", target])
    else:
        verbs = {"start": ["enable", "--now"], "stop": ["stop"], "remove": ["disable", "--now"]}
        run_control(["systemctl", "--user", *verbs[action], unit])
    if action == "remove":
        path.unlink()
        record_path.unlink()
        if spec["platform"] == "linux":
            run_control(["systemctl", "--user", "daemon-reload"])
    return {"label": spec["label"], "action": action, "note": "User-session service. No company data was removed."}
