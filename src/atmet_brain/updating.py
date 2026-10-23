"""Local operator update wizard. Never initialize a guessed home or restore over it."""

from collections import Counter
from dataclasses import asdict
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from urllib.request import urlopen
import zipfile

from ._version import __version__
from .backups import MAGIC, MAX_BACKUP_BYTES, generate_backup_key, load_key
from .config import Settings
from .db import SCHEMA_VERSION
from .errors import BrainError, require
from .maintenance import maintenance
from .services import manage_service, update_services
from .terminal import Console, prompt
from .util import dumps, now, private_write, sha, uid


def version_tuple(value):
    require(isinstance(value, str) and re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", value), "invalid_version", "Choose a stable numeric version, for example 0.9.0.")
    return tuple(map(int, value.split(".")))


def latest_version():
    try:
        with urlopen("https://registry.npmjs.org/atmet-brain/latest", timeout=15) as response:
            require(response.url.startswith("https://registry.npmjs.org/"), "update_registry", "Unexpected package registry redirect.")
            data = response.read(100_001)
        require(len(data) <= 100_000, "update_registry", "Package metadata is too large.")
        value = json.loads(data)["version"]
        version_tuple(value)
        return value
    except (OSError, ValueError, KeyError):
        raise BrainError("update_registry", "Cannot check npm. Check connectivity, or use update --to VERSION after reviewing that release.") from None


class ReadConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def readonly(path):
    conn = sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True, timeout=5, factory=ReadConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def inspect_home(home):
    try:
        return _inspect_home(home)
    except sqlite3.Error:
        raise BrainError("invalid_database", "Cannot inspect this company database safely. Keep it stopped and check its path or recovery status.") from None


def _inspect_home(home):
    home = Path(home).expanduser()
    require(not home.is_symlink() and not (home / "brain.sqlite3").is_symlink(), "unsafe_update_path", "Use the actual company folder and a regular database, not links.")
    home = home.resolve()
    require(home.is_dir() and (home / "brain.sqlite3").is_file(), "brain_missing", "Select an existing company Brain with --brain NAME or --home PATH. Update never creates a company.")
    require(home.stat().st_uid == os.getuid() and (home / "brain.sqlite3").stat().st_uid == os.getuid(),
            "unsafe_update_path", "Run the update as the device user who owns this Brain.")
    with readonly(home / "brain.sqlite3") as conn:
        meta = dict(conn.execute("SELECT key,value FROM meta"))
        require(meta.get("schema_version") in {"1", "2", "3", str(SCHEMA_VERSION)}, "schema_version", "Unsupported schema. Keep this home stopped and use its compatible release.")
        require(meta.get("recovery_mode") == "0", "brain_recovering", "Finish recovery before updating this Brain.")
        require(meta.get("instance_id"), "brain_missing", "This database has no Brain identity.")
        require(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "backup_integrity", "The existing database failed its integrity check. Use the recovery guide.")
        companies = [dict(v) for v in conn.execute("SELECT id,slug FROM organizations ORDER BY id")]
        spaces = [dict(v) for v in conn.execute("SELECT id,org_id,slug FROM spaces ORDER BY id")]
        require(len(companies) == 1, "brain_missing", "Select an initialized company Brain. Update cannot initialize a company.")
    return {"home": str(home), "instance_id": meta["instance_id"], "schema": int(meta["schema_version"]), "companies": companies, "workspaces": spaces}


def quote_identifier(value):
    return '"' + value.replace('"', '""') + '"'


def records(conn, table, columns):
    query = "SELECT " + ",".join(map(quote_identifier, columns)) + " FROM " + quote_identifier(table)
    return Counter(sha(repr(tuple(row))) for row in conn.execute(query)
                   if table != "meta" or row[0] != "schema_version")


def inventory(path):
    with readonly(path) as conn:
        result = {}
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            table = row[0]
            columns = [v[1] for v in conn.execute("PRAGMA table_info(" + quote_identifier(table) + ")")]
            result[table] = (columns, records(conn, table, columns))
        return result


def verify_records(path, before):
    with readonly(path) as conn:
        require(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "update_verification", "Updated database failed integrity verification.")
        for table, (columns, expected) in before.items():
            actual = records(conn, table, columns)
            # A migration may add metadata keys, but cannot change an existing one.
            require((not expected - actual) if table == "meta" else actual == expected,
                    "update_verification", "Existing company records changed unexpectedly. Keep the Brain stopped and inspect the update report.")


def files(home):
    result = {}
    for directory, names, filenames in os.walk(home, followlinks=False):
        for name in names:
            path = Path(directory) / name
            if path.is_symlink():
                result[str(path.relative_to(home))] = "link:" + os.readlink(path)
        names[:] = [v for v in names if v not in {"services", "service-logs"} and not (Path(directory) / v).is_symlink()]
        for name in filenames:
            path = Path(directory) / name
            relative = str(path.relative_to(home))
            if relative in {"brain.sqlite3", "brain.sqlite3-wal", "brain.sqlite3-shm", ".maintenance.lock"}:
                continue
            result[relative] = "link:" + os.readlink(path) if path.is_symlink() else sha(path.read_bytes())
    return result


def running_processes(home):
    home = Path(home).resolve()
    try:
        result = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True, timeout=10, check=True)
    except (OSError, subprocess.SubprocessError):
        raise BrainError("update_process_check", "Cannot inspect running processes. Stop the host services and use the manual upgrade guide.") from None
    found = []
    for line in result.stdout.splitlines():
        try:
            pid, command = line.strip().split(None, 1)
            args = shlex.split(command)
            if int(pid) == os.getpid() or not any("atmet-brain" in a or a == "atmet_brain" for a in args):
                continue
            if not any(a in {"serve", "mcp"} or (a == "worker" and "--loop" in args) for a in args):
                continue
            process_home = Path(args[args.index("--home") + 1]).expanduser().resolve() if "--home" in args else None
            if process_home and "--brain" in args:
                from .companies import select
                try:
                    process_home = select(process_home, args[args.index("--brain") + 1])
                except (BrainError, OSError, ValueError):
                    process_home = None
            if process_home is None or process_home == home:
                found.append(int(pid))
        except (ValueError, IndexError):
            continue
    return sorted(set(found))


def snapshot(home, destination, key_file, journal):
    """Snapshot the old schema without constructing Brain/Store or running migrations."""
    cipher = load_key(key_file)
    with tempfile.TemporaryDirectory(prefix="atmet-update-") as temporary:
        path = Path(temporary) / "brain.sqlite3"
        source, target = readonly(home / "brain.sqlite3"), sqlite3.connect(path)
        try:
            require(source.execute("PRAGMA page_count").fetchone()[0] * source.execute("PRAGMA page_size").fetchone()[0] <= MAX_BACKUP_BYTES,
                    "backup_size", "Guided snapshots support databases up to 256 MiB. Use your reviewed large-database backup procedure.")
            source.backup(target)
            require(target.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "backup_integrity", "Backup integrity verification failed.")
            meta = dict(target.execute("SELECT key,value FROM meta"))
            cursor = target.execute("SELECT * FROM recovery_events ORDER BY sequence")
            columns = [v[0] for v in cursor.description]
            events = [dict(zip(columns, row)) for row in cursor]
        finally:
            source.close()
            target.close()
        data = path.read_bytes()
        manifest = {"format": "atmet-brain-backup-v1", "engine_version": __version__, "schema_version": int(meta["schema_version"]),
                    "created_at": now(), "instance_id": meta["instance_id"], "recovery_sequence": events[-1]["sequence"] if events else 0,
                    "database_sha256": sha(data), "database_bytes": len(data), "deployment_settings": asdict(Settings.load(home))}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", dumps(manifest))
            archive.writestr("brain.sqlite3", data)
        private_write(destination, MAGIC + cipher.encrypt(buffer.getvalue()), overwrite=False)
        # Independently read/authenticate the saved envelope, then verify its actual SQLite payload.
        saved = Path(destination).read_bytes()
        require(saved.startswith(MAGIC), "backup_integrity", "Saved backup envelope is invalid.")
        with zipfile.ZipFile(io.BytesIO(cipher.decrypt(saved[len(MAGIC):]))) as archive:
            require(json.loads(archive.read("manifest.json")) == manifest and sha(archive.read("brain.sqlite3")) == manifest["database_sha256"],
                    "backup_integrity", "Saved backup verification failed.")
        baseline = inventory(path)
        value = {"format": "atmet-recovery-journal-v1", "instance_id": meta["instance_id"], "events": events,
                 "last_sequence": manifest["recovery_sequence"], "sha256": sha(dumps(events))}
        private_write(journal, dumps(value), overwrite=False)
        return manifest, baseline


def private_destination(path, home):
    path = Path(path).expanduser().absolute()
    require(not path.exists() and not path.is_symlink(), "already_exists", "Choose a new backup folder and key filename for each update.")
    require(not path.resolve().is_relative_to(home), "unsafe_update_path", "Save update backups and keys outside the company data home.")
    ancestor = path.parent
    while not ancestor.exists():
        ancestor = ancestor.parent
    require(not ancestor.is_symlink() and ancestor.stat().st_uid == os.getuid(), "unsafe_update_path", "Choose backup storage owned by your device user.")
    return path


def guided_update(args):
    require(not args.connection and not args.endpoint, "local_only", "Update must run on the device hosting the company Brain. Joined employees update their launcher separately.")
    interactive = sys.stdin.isatty() and not args.json and not args.yes
    console = Console(plain=args.plain)
    target = args.to or latest_version()
    require(version_tuple(target) >= version_tuple(__version__), "update_downgrade", "In-place downgrades are not supported. Use the recovery guide for an older snapshot.")
    if target != __version__:
        executable = shutil.which("npx")
        require(executable, "update_launcher", "Install Node.js/npm, then run npx atmet-brain@latest update. No company data was opened.")
        console.line("  Preparing Atmet Brain " + target + ". Company data will be backed up before migration.", accent=True)
        values = list(sys.argv[1:])
        try:
            result = subprocess.run([executable, "--yes", "--registry=https://registry.npmjs.org", "atmet-brain@" + target, *values], check=False)
        except OSError:
            raise BrainError("update_launcher", "Could not start the selected npm launcher. No company data was opened.") from None
        require(result.returncode == 0, "update_incomplete", "The selected updater did not finish. Read its error and any saved report before retrying.")
        return None
    from .companies import catalog
    home = Path(args.home).expanduser().resolve()
    if not args.brain:
        choices = {name: path for name, path in catalog(args.catalog_home).items()}
        if (home / "brain.sqlite3").is_file():
            choices = {"this-folder": str(home), **{k: v for k, v in choices.items() if Path(v).resolve() != home}}
        if choices:
            require(interactive or len(choices) == 1, "update_company_required", "Several companies are available. Select one with --brain NAME or its actual --home PATH.")
            if interactive:
                console.banner("Update an existing company Brain. Your workspaces stay in place.")
                for name, path in choices.items():
                    console.option(name, name, path)
                name = prompt("Company to update", next(iter(choices)) if len(choices) == 1 else None, list(choices), console=console)
            else:
                name = next(iter(choices))
            home = Path(choices[name]).expanduser().resolve()
    before = inspect_home(home)
    services = update_services(home)
    if services:
        from .services import run_control
        probe = run_control([sys.executable, "-I", "-c", "import atmet_brain; print(atmet_brain.__version__)"], check=False)
        require(probe.returncode == 0 and probe.stdout.strip() == target, "service_runtime_missing",
                "Managed services need the matching persistently installed runtime. Run npx atmet-brain@" + target + " update --to " + target + ". No data was changed.")
    label = uid("before-" + target)
    backup_dir = private_destination(args.backup_dir or Path.home() / "Atmet-backups" / label, home)
    key_file = private_destination(args.key_file or Path.home() / ".atmet-backup-keys" / (label + ".key"), home)
    require(not key_file.resolve().is_relative_to(backup_dir.resolve()) and not backup_dir.resolve().is_relative_to(key_file.resolve()),
            "unsafe_update_path", "Keep the decryption key outside the backup folder.")
    if interactive:
        console.line("\n  Target: " + target + " | Company: " + ", ".join(v["slug"] for v in before["companies"]), accent=True)
        console.line("  Existing workspaces: " + ", ".join(v["slug"] for v in before["workspaces"]))
        console.line("  Data: " + str(home))
        console.line("  Encrypted backup: " + str(backup_dir))
        console.line("  Separate key: " + str(key_file))
        console.line("  Managed services to preserve: " + str(len(services)))
        console.line("  Close this company's agent/MCP connections, foreground servers, workers and scheduled scripts.")
        console.line("  The updater stops and refreshes unchanged Atmet-managed services itself.")
        require(prompt("Have you stopped all other access? yes or no", "no", ["yes", "no"], console=console) == "yes", "update_cancelled", "Update cancelled before backup or migration.")
        require(prompt("Back up, verify and update this company? yes or no", "no", ["yes", "no"], console=console) == "yes", "update_cancelled", "Update cancelled before backup or migration.")
    else:
        require(args.yes and args.confirm_stopped, "update_answers_required", "Run update interactively, or explicitly supply --yes --confirm-stopped after closing all external access.")
    backup_dir.mkdir(parents=True, mode=0o700)
    report_path = backup_dir / "update-report.json"
    report = {"format": "atmet-update-v1", "target": target, "before": before, "backup": str(backup_dir / "brain.atmet"),
              "journal": str(backup_dir / "recovery-journal.json"), "key_file": str(key_file), "services": services,
              "phase": "preparing", "created_at": now()}
    def checkpoint(phase):
        report["phase"] = phase
        private_write(report_path, dumps(report))
        if interactive:
            console.line("  " + phase.replace("_", " "), accent=True)
    try:
        checkpoint("stopping_managed_services")
        for service in services:
            if service["running"]:
                manage_service("stop", service["old"])
        require(not running_processes(home), "brain_busy", "A foreground/old Brain process is still running. Close agent connections and servers, then retry. Managed services remain stopped.")
        with maintenance(home):
            require(inspect_home(home) == before, "update_changed", "The selected Brain changed before maintenance. Retry with a new backup.")
            preserved = files(home)
            catalog_file = Path(args.catalog_home) / "brains.json"
            catalog_hash = sha(catalog_file.read_bytes()) if catalog_file.exists() else None
            checkpoint("creating_backup")
            generate_backup_key(key_file)
            manifest, baseline = snapshot(home, report["backup"], key_file, report["journal"])
            report["backup_manifest"] = manifest
            checkpoint("backup_verified")
            verify_records(home / "brain.sqlite3", baseline)
            require(files(home) == preserved, "update_changed", "Company configuration changed during backup. Stop external access and retry.")
            checkpoint("opening_target_runtime")
            from .brain import Brain
            Brain(home)
            checkpoint("verifying_company_data")
            verify_records(home / "brain.sqlite3", baseline)
            after = inspect_home(home)
            require(all(before[k] == after[k] for k in ("home", "instance_id", "companies", "workspaces")) and after["schema"] == SCHEMA_VERSION
                    and files(home) == preserved and (sha(catalog_file.read_bytes()) if catalog_file.exists() else None) == catalog_hash,
                    "update_verification", "Company identity, configuration or credentials changed. Keep access stopped and inspect the update report.")
            report["after"] = after
            checkpoint("company_verified")
            for service in services:
                manage_service("replace", service["new"])
            checkpoint("services_refreshed")
        for service in services:
            if service["running"]:
                manage_service("start", service["new"])
                require(manage_service("status", service["new"])["state"] in {"active", "loaded"}, "service_control_failed", "A refreshed service did not start. Inspect its private logs and update report.")
        checkpoint("complete")
    except BaseException as error:
        report["failed_phase"] = report["phase"]
        report["error_code"] = error.code if isinstance(error, BrainError) else "update_interrupted" if isinstance(error, KeyboardInterrupt) else "update_failed"
        checkpoint("needs_attention")
        # Never restart an old runtime after a possibly successful migration.
        for service in services:
            try:
                manage_service("stop", service["new"])
            except (BrainError, OSError, ValueError, KeyError):
                pass
        raise BrainError(report["error_code"], "Update stopped. Company data was kept; no automatic rollback was attempted. Keep access stopped. Private report: " + str(report_path)) from None
    return {"status": "updated", "version": target, "home": str(home), "workspaces": before["workspaces"], "schema": SCHEMA_VERSION,
            "backup": report["backup"], "key_file": str(key_file), "journal": report["journal"], "report": str(report_path),
            "next": ["Reconnect agent/MCP entries with this runtime and their existing scoped credential files.",
                     "Use npx atmet-brain@" + target + " for future commands. To update a global shortcut: npm install --global atmet-brain@" + target,
                     "Keep the backup and key separately protected. Copy the backup and journal to independent storage for disk-loss protection."],
            "mcp_runtime": str(Path(sys.executable).absolute())}
