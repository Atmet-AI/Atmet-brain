"""Per-user launchd/systemd service management. No root or shell execution."""

import hashlib
import json
import os
from pathlib import Path
import plistlib
import shlex
import subprocess
import sys

from .errors import BrainError, require
from .util import private_write


def service_spec(home, kind="api", space=None, token_file=None, port=7310, platform=None, python=None):
    platform = platform or sys.platform
    require(platform in {"darwin", "linux"}, "unsupported_platform", "Services support macOS launchd and Linux systemd user sessions.")
    home = Path(home).expanduser().resolve()
    require(kind in {"api", "worker"}, "invalid_service", "Choose api or worker.")
    require(1 <= port <= 65535, "invalid_port", "Choose a port from 1 to 65535.")
    require(kind != "worker" or (space and token_file), "invalid_service", "Worker services need --space and --token-file.")
    identity = hashlib.sha256((str(home) + ":" + (space or "")).encode()).hexdigest()[:12]
    label = f"pro.atmet.brain.{identity}.{kind}"
    # Preserve a virtual environment's executable symlink and its environment.
    command = [str(Path(python or sys.executable).absolute()), "-m", "atmet_brain", "--plain", "--home", str(home)]
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
    if action in {"install", "replace"}:
        require((home / "brain.sqlite3").is_file(), "not_initialized", "Run setup before installing a service.")
        if action == "install":
            require(not path.exists() and not record_path.exists(), "already_exists", "This service is already installed. Remove it before changing its definition.", 409)
        else:
            require(path.is_file() and record_path.is_file()
                    and hashlib.sha256(path.read_bytes()).hexdigest() == json.loads(record_path.read_text())["content_hash"],
                    "service_modified", "The managed service changed. Keep it stopped and inspect the update report.")
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
        private_write(path, spec["content"], overwrite=action == "replace")
        try:
            private_write(record_path, json.dumps({"content_hash": hashlib.sha256(spec["content"].encode()).hexdigest()}), overwrite=action == "replace")
        except BaseException:
            if action == "install":
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


def update_services(home):
    """Discover only canonical, unchanged Atmet-managed definitions, including older records."""
    home = Path(home).resolve()
    directory = home / "services"
    require(not directory.is_symlink(), "unsafe_service_path", "The managed service directory cannot be a link.")
    result = []
    for record_path in sorted(directory.glob("*.json")):
        require(not record_path.is_symlink(), "unsafe_service_path", "Service records cannot be links.")
        label = record_path.stem
        suffix = ".plist" if sys.platform == "darwin" else ".service"
        base = Path.home() / ("Library/LaunchAgents" if sys.platform == "darwin" else ".config/systemd/user")
        path = base / (label + suffix)
        require(not path.is_symlink() and path.is_file(), "service_missing", "A managed service definition is missing. Resolve it before updating.")
        body = path.read_text()
        require(hashlib.sha256(body.encode()).hexdigest() == json.loads(record_path.read_text()).get("content_hash"),
                "service_modified", "A service definition changed outside Atmet. Review it before updating.")
        try:
            if sys.platform == "darwin":
                command = plistlib.loads(body.encode())["ProgramArguments"]
            else:
                lines = [v.removeprefix("ExecStart=") for v in body.splitlines() if v.startswith("ExecStart=")]
                require(len(lines) == 1, "service_modified", "Expected one managed ExecStart.")
                command = [v.replace("%%", "%").replace("$$", "$") for v in shlex.split(lines[0])]
            prefix = ["-m", "atmet_brain", "--plain", "--home", str(home)]
            require(command[1:6] == prefix and Path(command[0]).is_absolute(), "service_modified", "Unrecognized managed service command.")
            if command[6:9] == ["serve", "--host", "127.0.0.1"] and len(command) == 11 and command[9] == "--port":
                options = {"kind": "api", "port": int(command[10])}
            else:
                require(len(command) == 12 and command[6] == "--token-file"
                        and command[8:10] == ["worker", "--space"] and command[11] == "--loop",
                        "service_modified", "Unrecognized managed worker command.")
                options = {"kind": "worker", "token_file": command[7], "space": command[10]}
            old = service_spec(home, **options, python=command[0])
            require(old["label"] == label and old["content"] == body, "service_modified", "Only unchanged Atmet-managed services can update automatically.")
            state = manage_service("status", old)["state"]
            result.append({"old": old, "new": service_spec(home, **options), "running": state in {"active", "loaded"}})
        except (ValueError, KeyError, IndexError, TypeError, plistlib.InvalidFileException):
            raise BrainError("service_modified", "Cannot safely read a managed service. Inspect it before updating.") from None
    return result
