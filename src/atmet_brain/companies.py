"""Device-local catalog of independent company data homes. No implicit active company."""

import json
import os
from pathlib import Path
import shlex
import sys

from .errors import BrainError, require
from .terminal import Console, prompt
from .util import private_write, slug


def catalog(home):
    path = Path(home).expanduser().resolve() / "brains.json"
    if not path.exists():
        return {}
    require(path.is_file() and not path.is_symlink(), "invalid_catalog", "Use a regular private company catalog.")
    value = json.loads(path.read_text())
    require(isinstance(value, dict) and len(value) <= 100 and all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()),
            "invalid_catalog", "Invalid company catalog.")
    for name, destination in value.items():
        slug(name)
        require(Path(destination).is_absolute(), "invalid_catalog", "Company paths must be absolute.")
    return value


def remember(home, name, destination):
    try:
        import fcntl
    except ImportError:
        raise BrainError("unsupported_platform", "The local company catalog currently requires POSIX file locking.") from None
    home = Path(home).expanduser().resolve()
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(home / ".brains.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600), "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _remember(home, name, destination)


def _remember(home, name, destination):
    name = slug(name)
    destination = Path(destination).expanduser().resolve()
    require((destination / "brain.sqlite3").is_file(), "brain_missing", "Set up this company Brain first.")
    records = catalog(home)
    require(name not in records or records[name] == str(destination), "already_exists", "This company label already points to another Brain.")
    require(len(records) < 100 or name in records, "catalog_full", "This catalog supports up to 100 companies.")
    records[name] = str(destination)
    private_write(Path(home) / "brains.json", json.dumps(records, indent=2) + "\n")
    return {"brain": name, "home": str(destination)}


def select(home, name):
    records = catalog(home)
    require(name in records, "brain_missing", "Company not found in this catalog. Run brains to add or create it.")
    destination = Path(records[name]).expanduser().resolve()
    require((destination / "brain.sqlite3").is_file(), "brain_missing", "This company's data home is unavailable. Check the device/path.")
    return destination


def guided_companies(args):
    from .cli import execute, parser
    interactive = sys.stdin.isatty() and not args.json
    console = Console(plain=args.plain)
    home = args.catalog_home
    records = catalog(home)
    action, name = args.action, args.name
    if not action:
        if not interactive:
            return [{"brain": k, "home": v} for k, v in sorted(records.items())]
        console.banner("Your companies. Each Brain has its own data, people and permissions.")
        for label, path in sorted(records.items()):
            console.option(label, label, path)
        action = prompt("Choose list, open, create or add", "open" if records else "create", ["list", "open", "create", "add"], console=console)
    if action == "list":
        return [{"brain": k, "home": v} for k, v in sorted(records.items())]
    if not name and interactive:
        name = prompt("Company label", next(iter(records)) if action == "open" and records else None, console=console, validate=slug)
    require(name, "company_answers_required", "Choose a company label, for example brains create acme.")
    slug(name)
    if action == "create":
        destination = Path(home) / "companies" / name
        require(not destination.exists() and not destination.is_symlink() and name not in records,
                "already_exists", "Choose a new company label. Existing data is never replaced.")
        values = ["--home", str(destination), *(["--plain"] if args.plain else []), *(["--json"] if args.json else []), "setup", "--mode", "local", "--organization", name]
        if args.owner:
            values.extend(["--owner", args.owner])
        if args.spaces:
            values.extend(["--spaces", args.spaces])
        result = execute(parser().parse_args(values))
        remember(home, name, destination)
    elif action == "add":
        value = args.path or (prompt("Existing private Brain data folder", console=console,
                                    validate=lambda p: require((Path(p).expanduser() / "brain.sqlite3").is_file(), "brain_missing", "Choose an existing Brain data folder.")) if interactive else None)
        require(value, "company_answers_required", "Use --path for an existing Brain data home.")
        result = remember(home, name, value)
        destination = Path(result["home"])
    else:
        destination = select(home, name)
        result = {"brain": name, "home": str(destination)}
    base = [str(Path(sys.executable).absolute()), "-m", "atmet_brain", "--home", str(Path(home).resolve()), "--brain", name]
    result["brain"] = name
    result["next"] = [shlex.join(base + [command]) for command in ["status", "host", "team", "agent"]]
    result["selection"] = "Use --brain " + name + " explicitly. Choosing a company does not silently switch other agents or shells."
    return result
