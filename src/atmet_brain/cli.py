"""Local operator commands and authenticated core calls."""

import argparse
import json
import os
from pathlib import Path
import sys
import time

from .auth import ROLES
from .backups import generate_backup_key
from .brain import Brain
from .config import default_home
from .errors import BrainError
from .mcp import MCPServer
from .rpc import dispatch, openapi
from .server import make_server
from .skills import install_skill
from .util import private_write, uid


def parser():
    root = argparse.ArgumentParser(prog="atmet-brain", description="Company memory, workflows and skills for AI agents.")
    root.add_argument("--home", type=Path, default=default_home(), help="Private data directory")
    root.add_argument("--token-file", type=Path, help="Scoped credential file; defaults to ATMET_TOKEN_FILE or home/owner.token")
    sub = root.add_subparsers(dest="command", required=True)
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


def execute(args):
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
        with brain.store.transaction() as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            recovering = conn.execute("SELECT value FROM meta WHERE key='recovery_mode'").fetchone()[0]
            return {"integrity": integrity, "schema": 1, "recovery_mode": recovering == "1", "home": str(brain.store.home)}
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
        print(f"Atmet Brain listening on {args.host}:{server.server_port}", file=sys.stderr)
        try:
            server.serve_forever()
        finally:
            server.server_close()
        return None
    token = read_token(args)
    actor = brain.authenticate(token)
    if args.command == "mcp":
        MCPServer(brain, token, args.allow_proposals, args.allow_automations).serve()
        return None
    if args.command == "space":
        return brain.create_space(actor, args.name) if args.name else brain.list_spaces(actor)
    if args.command == "principal":
        return brain.create_principal(actor, args.name, args.kind)
    if args.command == "grant":
        return brain.grant(actor, args.principal, args.space, ROLES[args.role])
    if args.command == "token":
        result = brain.create_credential(actor, args.principal, args.operation, args.space, args.expires_at)
        private_write(args.output, result.pop("token") + "\n", overwrite=False)
        return {**result, "token_file": str(args.output)}
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
    try:
        result = execute(args)
        if result is not None:
            print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except BrainError as error:
        print(json.dumps({"error": error.as_dict()}), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError):
        print(json.dumps({"error": {"code": "local_input_error", "message": "Check the input file, credential, format and destination."}}), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
