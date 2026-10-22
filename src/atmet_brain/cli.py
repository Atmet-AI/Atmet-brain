"""Local operator commands and authenticated core calls."""

import argparse
import json
import os
from pathlib import Path
import shlex
import sys
import time

from .auth import ROLES
from .backups import generate_backup_key
from .brain import Brain
from ._version import __version__
from .client import Client
from .connections import connect, list_connections, load_connection, remove_connection
from .config import default_home
from .errors import BrainError, require
from .mcp import MCPServer
from .rpc import dispatch, openapi
from .server import make_server
from .skills import install_skill
from .util import private_write, uid
from .terminal import Console


def parser():
    root = argparse.ArgumentParser(prog="atmet-brain", description="Company memory, workflows and skills for AI agents.",
                                   epilog="First visit: atmet-brain setup | Team client: atmet-brain connect --help")
    root.add_argument("--version", action="version", version="Atmet Brain " + __version__)
    root.add_argument("--json", action="store_true", help="Machine-readable output, including in a terminal")
    root.add_argument("--plain", action="store_true", help="Disable terminal colors")
    root.add_argument("--connection", help="Use an explicitly saved remote connection")
    root.add_argument("--endpoint", help="One-off remote HTTPS endpoint or SSH loopback URL")
    root.add_argument("--ca-file", type=Path, help="CA certificate file for a private HTTPS server")
    root.add_argument("--home", type=Path, default=default_home(), help="Private data directory")
    root.add_argument("--token-file", type=Path, help="Scoped credential file; defaults to ATMET_TOKEN_FILE or home/owner.token")
    sub = root.add_subparsers(dest="command")
    sub.add_parser("status", help="Show current local or selected remote Brain status")
    mcp_config = sub.add_parser("mcp-config", help="Print a credential-file-based MCP client configuration")
    for flag in ("allow-proposals", "allow-automations", "allow-task-reports"):
        mcp_config.add_argument("--" + flag, action="store_true")
    setup = sub.add_parser("setup", help="Guided company initialization or connection")
    setup.add_argument("--mode", choices=["local", "host", "join", "team", "connect"])
    setup.add_argument("--organization")
    setup.add_argument("--owner")
    setup.add_argument("--spaces", help="Comma-separated department space slugs")
    setup.add_argument("--name", help="Connection name for connect mode")
    setup.add_argument("--endpoint", default=argparse.SUPPRESS)
    setup.add_argument("--token-file", type=Path, default=argparse.SUPPRESS)
    setup.add_argument("--ca-file", type=Path, default=argparse.SUPPRESS)
    setup.add_argument("--file", type=Path, help="Private team connection file for Join")
    setup.add_argument("--transport", choices=["ssh", "https", "later"], help="Host connection route")
    setup.add_argument("--ssh-destination", help="Administrator-configured forwarding-only user@host")
    setup.add_argument("--port", type=int, default=7310, help="Host loopback Brain port")
    setup.add_argument("--member", help="Teammate name to provision")
    setup.add_argument("--member-spaces", help="Allowed workspace names, separated by commas")
    setup.add_argument("--role", choices=sorted(set(ROLES) - {"owner"}))
    setup.add_argument("--output", type=Path, help="New private member connection file")
    setup.add_argument("--start-service", action="store_true", help="Install and start the per-user API service")
    # Reuse the same flags and validation for the short, discoverable entry points.
    for name, mode in [("host", "host"), ("join", "join")]:
        command = sub.add_parser(name, parents=[setup], add_help=False, help="Guided " + name + " setup")
        command.set_defaults(setup_entry=mode)
    connection = sub.add_parser("connect", help="Verify and save a remote connection without copying its database")
    connection.add_argument("name")
    connection.add_argument("--endpoint", required=True, dest="connect_endpoint")
    connection.add_argument("--token-file", type=Path, required=True, dest="connect_token_file")
    connection.add_argument("--ca-file", type=Path, dest="connect_ca_file")
    connections = sub.add_parser("connections", help="List or remove saved connections")
    connections.add_argument("action", choices=["list", "remove"], default="list", nargs="?")
    connections.add_argument("name", nargs="?")
    team = sub.add_parser("team-add", help="Create a member, scoped grants and an expiring credential")
    team.add_argument("name")
    team.add_argument("--space", action="append", required=True)
    team.add_argument("--role", choices=sorted(set(ROLES) - {"owner"}), default="reader")
    team.add_argument("--kind", choices=["human", "service"], default="human")
    team.add_argument("--expires-at", help="Defaults to 30 days; cannot outlive the issuer")
    team.add_argument("--output", type=Path, required=True)
    service = sub.add_parser("service", help="Render or manage an explicit per-user background service")
    service.add_argument("action", choices=["render", "install", "start", "stop", "status", "remove"])
    service.add_argument("--kind", choices=["api", "worker"], default="api")
    service.add_argument("--space")
    service.add_argument("--port", type=int, default=7310)
    service.add_argument("--platform", choices=["darwin", "linux"], help="For render only")
    service.add_argument("--start", action="store_true", help="Start after install")
    init = sub.add_parser("init", help="Initialize a fresh installation")
    init.add_argument("--organization", default="example")
    init.add_argument("--owner", default="Owner")
    org = sub.add_parser("organization-add", help="Locally provision another isolated company")
    org.add_argument("name")
    org.add_argument("--owner", default="Owner")
    space = sub.add_parser("space", help="Create or list spaces")
    space.add_argument("name", nargs="?")
    member = sub.add_parser("principal", help="Create an attributable principal")
    member.add_argument("name")
    member.add_argument("--kind", choices=["human", "service"], default="service")
    grant = sub.add_parser("grant", help="Grant operations in a space")
    grant.add_argument("--principal", required=True)
    grant.add_argument("--space", required=True)
    grant.add_argument("--role", choices=sorted(ROLES), required=True)
    key = sub.add_parser("token", help="Mint a scoped credential and save it privately")
    key.add_argument("--principal")
    key.add_argument("--space", action="append")
    key.add_argument("--operation", action="append")
    key.add_argument("--expires-at")
    key.add_argument("--output", type=Path, required=True)
    source = sub.add_parser("ingest", help="Capture a UTF-8 source revision")
    source.add_argument("file", type=Path)
    source.add_argument("--space", required=True)
    source.add_argument("--external-id")
    source.add_argument("--title")
    source.add_argument("--authority", choices=["observation", "reference", "authoritative"], default="observation")
    source.add_argument("--audience", action="append")
    source.add_argument("--expected-revision", type=int)
    report = sub.add_parser("task-report", help="Record an explicit task outcome from a JSON file")
    report.add_argument("file", type=Path)
    report.add_argument("--space", required=True)
    history = sub.add_parser("task-history", help="Search permissioned task history; requires history access")
    history.add_argument("query", nargs="?", default="")
    history.add_argument("--space", required=True)
    history.add_argument("--task-key")
    history.add_argument("--limit", type=int, default=10)
    for name in ("task-get", "task-erase"):
        command = sub.add_parser(name, help="Read or erase a task report with current permissions")
        command.add_argument("report_id")
    learn = sub.add_parser("task-learn", help="Propose a skill from reported outcomes; never publish")
    learn.add_argument("--space", required=True)
    learn.add_argument("--report", action="append", required=True)
    learn.add_argument("--name", required=True)
    learn.add_argument("--idempotency-key", required=True)
    learn.add_argument("--artifact-id")
    learn.add_argument("--expected-revision", type=int, default=0)
    learn.add_argument("--task-path", default="shared")
    for name in ["search", "context"]:
        command = sub.add_parser(name)
        command.add_argument("query")
        command.add_argument("--space", required=True)
        if name == "context":
            command.add_argument("--artifact", action="append")
            command.add_argument("--task-path", default="shared")
            command.add_argument("--max-chars", type=int)
    propose = sub.add_parser("propose", help="Submit an artifact request from a JSON specification")
    propose.add_argument("specification", type=Path)
    review = sub.add_parser("review", help="Publish or reject the current artifact draft")
    review.add_argument("artifact_id")
    review.add_argument("--revision", required=True, type=int)
    decision = review.add_mutually_exclusive_group(required=True)
    decision.add_argument("--approve", action="store_true")
    decision.add_argument("--reject", action="store_true")
    review.add_argument("--reason", required=True)
    skill = sub.add_parser("skill-install", help="Import a portable skill as a pending version")
    skill.add_argument("package", type=Path)
    skill.add_argument("--space", required=True)
    skill.add_argument("--artifact-id")
    skill.add_argument("--expected-revision", type=int, default=0)
    worker = sub.add_parser("worker", help="Drain learning jobs once or continuously")
    worker.add_argument("--space", required=True)
    worker.add_argument("--loop", action="store_true")
    worker.add_argument("--interval", type=float, default=5)
    worker.add_argument("--max-jobs", type=int, default=20)
    connector = sub.add_parser("connector-add", help="Register an operator-selected connector")
    connector.add_argument("--space", required=True)
    connector.add_argument("--kind", choices=["files", "gmail"], required=True)
    connector.add_argument("--config", type=Path, required=True)
    connector.add_argument("--audience", action="append")
    connector.add_argument("--authority", choices=["observation", "reference", "authoritative"], default="observation")
    sync = sub.add_parser("sync", help="Reconcile a connector")
    sync.add_argument("connector_id")
    serve = sub.add_parser("serve", help="Run the local REST adapter")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=7310)
    serve.add_argument("--allow-network", action="store_true")
    mcp = sub.add_parser("mcp", help="Run MCP over stdio")
    mcp.add_argument("--allow-proposals", action="store_true")
    mcp.add_argument("--allow-automations", action="store_true", help="Expose observed-run recording and bounded pure recipe execution tools")
    mcp.add_argument("--allow-task-reports", action="store_true", help="Expose explicit task reporting; grants still apply")
    rpc = sub.add_parser("rpc", help="Call any registered operation")
    rpc.add_argument("method")
    rpc.add_argument("--params", default="{}", help="JSON object, or @path/to/request.json")
    sub.add_parser("openapi", help="Print the REST OpenAPI document")
    sub.add_parser("doctor", help="Check local database integrity and installation state")
    keygen = sub.add_parser("backup-key")
    keygen.add_argument("--output", type=Path, required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("--output", type=Path, required=True)
    backup.add_argument("--key-file", type=Path, required=True)
    restore = sub.add_parser("restore")
    restore.add_argument("--input", type=Path, required=True)
    restore.add_argument("--destination", type=Path, required=True)
    restore.add_argument("--key-file", type=Path, required=True)
    journal = sub.add_parser("journal")
    journal.add_argument("--output", type=Path, required=True)
    recover = sub.add_parser("recover")
    recover.add_argument("--journal", type=Path, required=True)
    recover.add_argument("--owner", default="Recovery owner")
    recover.add_argument("--confirm-journal-complete", action="store_true")
    return root


def read_token(args):
    if os.environ.get("ATMET_TOKEN"):
        return os.environ["ATMET_TOKEN"].strip()
    path = args.token_file or Path(os.environ.get("ATMET_TOKEN_FILE", args.home / "owner.token"))
    return path.read_text().strip()


def save_credential(path, create):
    """Reserve a private destination before minting a once-returned credential."""
    path = path.expanduser()
    private_write(path, "", overwrite=False)
    try:
        result = create()
        private_write(path, result.pop("token") + "\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return {**result, "token_file": str(path.resolve())}


def remote_execute(args, client):
    command = args.command
    if command == "mcp":
        MCPServer(None, None, args.allow_proposals, args.allow_automations, client=client, allow_task_reports=args.allow_task_reports).serve()
        return None
    if command == "status":
        return {"mode": "remote", "endpoint": client.endpoint, "identity": client.call("identity.me"),
                "spaces": client.call("spaces.list")}
    if command == "rpc":
        params = json.loads(Path(args.params[1:]).read_text() if args.params.startswith("@") else args.params)
        require(isinstance(params, dict), "invalid_params", "params must be an object.")
        return client.call(args.method, **params)
    if command == "space":
        return client.call("spaces.create", name=args.name) if args.name else client.call("spaces.list")
    if command == "principal":
        return client.call("principals.create", name=args.name, kind=args.kind)
    if command == "grant":
        return client.call("grants.create", principal_id=args.principal, space_id=args.space, operations=ROLES[args.role])
    if command == "token":
        return save_credential(args.output, lambda: client.call("credentials.create", principal_id=args.principal,
                                                               operations=args.operation, space_ids=args.space, expires_at=args.expires_at))
    if command == "team-add":
        return save_credential(args.output, lambda: client.call("team.add", name=args.name, space_ids=args.space,
                                                               role=args.role, kind=args.kind, expires_at=args.expires_at))
    if command in {"task-report", "task-history", "task-get", "task-learn", "task-erase"}:
        method, params = task_request(args)
        return client.call(method, **params)
    if command == "search":
        return client.call("search", space_id=args.space, query=args.query)
    if command == "context":
        return client.call("context.get", space_id=args.space, query=args.query, artifact_ids=args.artifact,
                           task_path=args.task_path, max_chars=args.max_chars)
    if command == "ingest":
        from .connectors.files import MIMES
        mime = MIMES.get(args.file.suffix.lower())
        require(mime, "unsupported_format", "Use .txt, .md, .json or .csv.")
        return client.call("sources.put", space_id=args.space, external_id=args.external_id or args.file.name,
                           title=args.title or args.file.name, content=args.file.read_text(encoding="utf-8"), mime=mime,
                           audience=args.audience, authority=args.authority, expected_revision=args.expected_revision)
    if command == "propose":
        params = json.loads(args.specification.read_text())
        params.setdefault("idempotency_key", uid("request"))
        return client.call("artifacts.propose", **params)
    if command == "review":
        return client.call("artifacts.review", artifact_id=args.artifact_id, expected_revision=args.revision,
                           approve=args.approve, reason=args.reason)
    if command == "sync":
        return client.call("connectors.sync", connector_id=args.connector_id)
    raise BrainError("local_only", "This command requires the server's local installation. Remote mode never falls back to a local Brain.")


def task_request(args):
    if args.command == "task-report":
        require(args.file.stat().st_size <= 200000, "invalid_report", "Task report file is too large.")
        params = json.loads(args.file.read_text())
        require(isinstance(params, dict) and "space_id" not in params, "invalid_report", "Use report parameters without space_id; select it with --space.")
        return "reports.record", {**params, "space_id": args.space}
    if args.command == "task-history":
        return "reports.search", {"space_id": args.space, "query": args.query, "task_key": args.task_key, "limit": args.limit}
    if args.command in {"task-get", "task-erase"}:
        return ("reports.get" if args.command == "task-get" else "reports.erase"), {"report_id": args.report_id}
    return "skills.learn", {"space_id": args.space, "report_ids": args.report, "name": args.name,
                            "idempotency_key": args.idempotency_key, "artifact_id": args.artifact_id,
                            "expected_revision": args.expected_revision, "instruction_path": args.task_path}


def execute(args):
    require(not (args.connection and args.endpoint), "invalid_connection", "Choose --connection or --endpoint.")
    if args.command is None and (args.connection or args.endpoint):
        args.command = "status"
    if args.command is None:
        base = ["atmet-brain", "--home", str(args.home.expanduser().resolve())]
        return {"version": __version__, "initialized": (args.home / "brain.sqlite3").exists(),
                "home": str(args.home), "start": shlex.join(base + ["setup"]), "inspect": shlex.join(base + ["status"]),
                "host": shlex.join(base + ["host"]), "join": shlex.join(base + ["join"]),
                "help": "atmet-brain --help", "connections": list_connections(args.home)}
    if args.command == "connect":
        require(not args.connection and not args.endpoint, "invalid_connection", "Use connect's own endpoint and token-file arguments.")
        return connect(args.home, args.name, args.connect_endpoint, args.connect_token_file, args.connect_ca_file)
    if args.command == "connections":
        require(not args.connection and not args.endpoint, "local_only", "Connection management is local.")
        if args.action == "list":
            return list_connections(args.home)
        require(args.name, "connection_missing", "Choose a connection name to remove.")
        return remove_connection(args.home, args.name)
    if args.command in {"setup", "host", "join"}:
        require(not args.connection, "invalid_connection", "Host and Join configure connections; omit --connection.")
        require(type(args.port) is int and 1 <= args.port <= 65535, "invalid_port", "Choose a port between 1 and 65535.")
        from .setup import guided_setup
        from .sharing import create_share, join_share
        def initialize(organization, owner, spaces):
            initialized = execute(argparse.Namespace(**{**vars(args), "command": "init", "endpoint": None, "organization": organization, "owner": owner}))
            local = Brain(args.home)
            actor = local.authenticate(Path(initialized["token_file"]).read_text().strip())
            initialized["spaces"] = [local.create_space(actor, name) for name in spaces]
            return initialized
        def local_status():
            return execute(argparse.Namespace(**{**vars(args), "command": "status", "endpoint": None}))
        def share_member(*values, **options):
            local = Brain(args.home)
            actor = local.authenticate(read_token(args))
            return create_share(local, actor, *values, **options)
        def start_api(port):
            from .services import manage_service, service_spec
            return manage_service("install", service_spec(args.home, "api", None, None, port), True)
        return guided_setup(args, initialize, lambda name, endpoint, token, ca: connect(args.home, name, endpoint, token, ca),
                            inspect_local=local_status, share=share_member,
                            join=lambda path, name, ca, record: join_share(args.home, path, name, ca, record), start_service=start_api)
    if args.command == "mcp-config":
        require(not args.endpoint, "invalid_connection", "Save a named connection first, or use a dedicated local token file.")
        command = ["-m", "atmet_brain", "--home", str(args.home.expanduser().resolve())]
        if args.connection:
            require(not args.token_file, "invalid_connection", "A named connection uses its own credential.")
            load_connection(args.home, args.connection)
            command += ["--connection", args.connection]
        else:
            require(args.token_file and args.token_file.is_file(), "credential_missing", "Use --token-file with a dedicated scoped agent credential.")
            command += ["--token-file", str(args.token_file.expanduser().resolve())]
        switches = ["--" + flag.replace("_", "-") for flag in ("allow_proposals", "allow_automations", "allow_task_reports") if getattr(args, flag)]
        return {"mcpServers": {"atmet-brain": {"command": str(Path(sys.executable).absolute()), "args": command + ["mcp", *switches]}}}
    if args.connection or args.endpoint:
        require(not args.connection or not args.token_file, "invalid_connection", "A saved connection uses its own credential. Reconnect to change it.")
        client = load_connection(args.home, args.connection)[0] if args.connection else Client(args.endpoint, read_token(args), args.ca_file)
        return remote_execute(args, client)
    if args.command == "service":
        from .services import manage_service, service_spec
        require(not args.platform or args.action == "render", "invalid_service", "--platform is for render only.")
        require(not args.start or args.action == "install", "invalid_service", "--start is for install only.")
        spec = service_spec(args.home, args.kind, args.space, args.token_file, args.port, args.platform)
        return manage_service(args.action, spec, args.start)
    if args.command == "status":
        if not (args.home / "brain.sqlite3").is_file():
            return {"mode": "local", "state": "not_initialized", "next": shlex.join(["atmet-brain", "--home", str(args.home.expanduser().resolve()), "setup"])}
        local = Brain(args.home)
        actor = local.authenticate(read_token(args))
        return {"version": __version__, "mode": "local", "home": str(local.store.home),
                "identity": local.whoami(actor), "spaces": local.list_spaces(actor),
                "next": shlex.join(["atmet-brain", "--home", str(local.store.home), "serve"])}
    if args.command == "backup-key":
        return generate_backup_key(args.output)
    if args.command == "restore":
        return Brain.restore_backup(args.input, args.destination, args.key_file)
    brain = Brain(args.home)
    if args.command == "organization-add":
        result = brain.provision_organization(args.name, args.owner)
        path = args.home / (args.name + "-owner.token")
        private_write(path, result.pop("token") + "\n", overwrite=False)
        return {**result, "token_file": str(path)}
    if args.command == "init":
        result = brain.bootstrap(args.organization, args.owner)
        token = result.pop("token")
        path = args.home / "owner.token"
        private_write(path, token + "\n", overwrite=False)
        private_write(args.home / "config.toml", "[brain]\nmax_context_chars = 16000\nmax_results = 12\nallow_remote_processing = false\n", overwrite=False)
        return {**result, "token_file": str(path), "home": str(args.home)}
    if args.command == "doctor":
        from .db import SCHEMA_VERSION
        with brain.store.transaction() as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            recovering = conn.execute("SELECT value FROM meta WHERE key='recovery_mode'").fetchone()[0]
            return {"integrity": integrity, "schema": SCHEMA_VERSION, "recovery_mode": recovering == "1", "home": str(brain.store.home)}
    if args.command == "backup":
        return brain.create_backup(args.output, args.key_file)
    if args.command == "journal":
        return brain.flush_recovery_journal(args.output)
    if args.command == "recover":
        result = brain.finish_recovery(args.journal, args.owner, args.confirm_journal_complete)
        for owner in result["owners"]:
            path = args.home / (owner["organization"] + "-recovery.token")
            private_write(path, owner.pop("token") + "\n", overwrite=False)
            owner["token_file"] = str(path)
        return result
    if args.command == "openapi":
        return openapi(brain)
    if args.command == "serve":
        server = make_server(brain, args.host, args.port, args.allow_network)
        console = Console(plain=args.plain)
        if sys.stderr.isatty():
            console.banner("Your company Brain is listening.")
        console.result({"url": f"http://{args.host}:{server.server_port}", "storage": str(brain.store.home),
                        "access": "Scoped credentials required. Use private ingress for remote access.",
                        "stop": "Ctrl+C stops this foreground server. Use service for background operation."})
        try:
            server.serve_forever()
        finally:
            server.server_close()
        return None
    token = read_token(args)
    actor = brain.authenticate(token)
    if args.command in {"task-report", "task-history", "task-get", "task-learn", "task-erase"}:
        method, params = task_request(args)
        return dispatch(brain, actor, method, params)
    if args.command == "mcp":
        MCPServer(brain, token, args.allow_proposals, args.allow_automations, allow_task_reports=args.allow_task_reports).serve()
        return None
    if args.command == "space":
        return brain.create_space(actor, args.name) if args.name else brain.list_spaces(actor)
    if args.command == "principal":
        return brain.create_principal(actor, args.name, args.kind)
    if args.command == "grant":
        return brain.grant(actor, args.principal, args.space, ROLES[args.role])
    if args.command == "token":
        return save_credential(args.output, lambda: brain.create_credential(actor, args.principal, args.operation, args.space, args.expires_at))
    if args.command == "team-add":
        return save_credential(args.output, lambda: brain.add_team_member(actor, args.name, args.space, args.role, args.kind, args.expires_at))
    if args.command == "ingest":
        from .connectors.files import MIMES
        mime = MIMES.get(args.file.suffix.lower())
        if not mime:
            raise BrainError("unsupported_format", "Use .txt, .md, .json or .csv.")
        return brain.put_source(actor, args.space, args.external_id or args.file.name, args.title or args.file.name,
                                args.file.read_text(encoding="utf-8"), mime, args.audience, args.authority, args.expected_revision)
    if args.command == "search":
        return brain.search(actor, args.space, args.query)
    if args.command == "context":
        return brain.get_context(actor, args.space, args.query, args.artifact, args.task_path, args.max_chars)
    if args.command == "propose":
        params = json.loads(args.specification.read_text())
        params.setdefault("idempotency_key", uid("request"))
        return dispatch(brain, actor, "artifacts.propose", params)
    if args.command == "review":
        return brain.review_artifact(actor, args.artifact_id, args.revision, args.approve, args.reason)
    if args.command == "skill-install":
        return install_skill(brain, actor, args.space, args.package, args.artifact_id, args.expected_revision)
    if args.command == "connector-add":
        return brain.register_connector(actor, args.space, args.kind, json.loads(args.config.read_text()), args.audience, args.authority)
    if args.command == "sync":
        return brain.sync_connector(actor, args.connector_id)
    if args.command == "worker":
        while True:
            result = brain.run_jobs(actor, args.space, args.max_jobs)
            if not args.loop:
                return result
            print(json.dumps(result), flush=True)
            time.sleep(max(1, args.interval))
    if args.command == "rpc":
        params = json.loads(Path(args.params[1:]).read_text() if args.params.startswith("@") else args.params)
        return dispatch(brain, actor, args.method, params)
    raise BrainError("unknown_command", "Unknown command.")


def main():
    args = parser().parse_args()
    human = sys.stdout.isatty() and not args.json and args.command not in {"mcp-config", "openapi"}
    try:
        result = execute(args)
        if result is not None:
            if human:
                console = Console(sys.stdout, args.plain)
                if args.command is None:
                    console.welcome(result)
                else:
                    if args.command in {"setup", "host", "join"} and sys.stdin.isatty():
                        console.line("\n  Setup complete", accent=True)
                    else:
                        console.banner(compact=True)
                    console.result(result)
            else:
                print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except BrainError as error:
        if human:
            Console(plain=args.plain).line(f"  {error.code}: {error.message}", accent=True)
        else:
            print(json.dumps({"error": error.as_dict()}), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError):
        print(json.dumps({"error": {"code": "local_input_error", "message": "Check the input file, credential, format and destination."}}), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
