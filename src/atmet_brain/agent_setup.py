"""Guided connection bundles. No client settings edits or privilege escalation."""

from functools import partial
import json
from pathlib import Path
import shlex
import sys

from .auth import ROLES
from .brain import Brain
from .client import Client
from .connections import connect, list_connections, load_connection, profile_path
from .errors import BrainError, require
from .feedback import LocalClient
from .terminal import Console, prompt
from .util import now, private_write, slug


def pick_spaces(value, available):
    aliases = {key: item for item in available for key in (item["slug"], item["id"])}
    for index, item in enumerate(available, 1):
        aliases["#" + str(index)] = item
        aliases.setdefault(str(index), item)
    names = [name.strip() for name in value.split(",") if name.strip()]
    require(0 < len(names) <= 30 and all(name in aliases for name in names),
            "invalid_spaces", "Choose workspace numbers/names from the list.")
    selected = [aliases[name] for name in names]
    require(len({item["id"] for item in selected}) == len(selected), "invalid_spaces", "Choose each workspace once.")
    return selected


def guided_agent(args, read_token, join_team):
    home = args.home.expanduser().resolve()
    interactive = sys.stdin.isatty() and not args.json
    console = Console(plain=args.plain)
    ask = partial(prompt, console=console)
    if interactive:
        console.banner("Connect your agent. Choose access, then add the ready configuration.")
    source = args.connection
    route = None
    if not source and not args.endpoint and interactive:
        saved = list_connections(home)
        console.option("local", "Brain on this device", "Use an existing local company Brain.")
        for connection in saved:
            console.option("remote:" + connection["name"], connection["name"], connection["endpoint"])
        console.option("join", "Join a company Brain first", "Verify your administrator's private connection file.")
        chosen = ask("Where is the Brain", "local", ["local", "join", *["remote:" + item["name"] for item in saved]])
        if chosen == "join":
            source = join_team()["connection"]
        elif chosen.startswith("remote:"):
            source = chosen[7:]
    if source:
        require(not args.token_file, "invalid_connection", "A saved connection uses its own credential.")
        client, _ = load_connection(home, source)
        route = json.loads(profile_path(home, source).read_text())
    elif args.endpoint:
        client = Client(args.endpoint, read_token(args), args.ca_file)
        route = {"endpoint": args.endpoint, "ca_file": args.ca_file}
    else:
        require((home / "brain.sqlite3").is_file(), "brain_missing", "Create a Brain with setup first, or run agent and choose Join.")
        client = LocalClient(Brain(home), read_token(args))
    caller = client.call("identity.me")
    available = client.call("spaces.list")
    require(available, "no_spaces", "No permitted workspaces. Ask your administrator for access or create a space first.")
    methods = ["mcp", "terminal"] if route and route.get("ssh") else ["mcp", "terminal", "rest", "python"]
    if interactive:
        console.line("  1 / How will the agent connect?", accent=True)
        for key, title, description in [
            ("mcp", "Agent app with MCP", "Save an MCP entry to add in your app. Local stdio support is required."),
            ("terminal", "Coding agent with terminal tools", "Use ready context and completion commands."),
            ("rest", "My own app using HTTP", "Get an endpoint, request example and credential-file path."),
            ("python", "My trusted Python application", "Get a runnable context example with the installed interpreter."),
        ]:
            if key in methods:
                console.option(key, title, description)
        if "rest" not in methods:
            console.line("  This SSH profile supports MCP/terminal. Direct REST/Python needs HTTPS or a managed loopback endpoint.")
    method = args.method or (ask("Connection method", "mcp", methods) if interactive else None)
    require(method in methods, "agent_answers_required", "Choose --method mcp|terminal|rest|python; SSH profiles support mcp/terminal.")
    if interactive:
        console.line("  2 / Choose workspaces", accent=True)
        for index, item in enumerate(available, 1):
            console.line("  #" + str(index) + "  " + item["slug"])
    value = args.spaces or (ask("Workspace names or #numbers, separated by commas", "#1",
                               validate=lambda v: pick_spaces(v, available)) if interactive else None)
    require(value, "agent_answers_required", "Choose --spaces using permitted workspace names.")
    selected = pick_spaces(value, available)
    try:
        permissions = [client.call("access.check", space_id=item["id"]) for item in selected]
    except BrainError as error:
        if error.code == "unknown_method":
            raise BrainError("server_upgrade_required", "Guided agent setup requires engine 0.6.0 or newer on the Brain server. No credential was issued.", 409) from None
        raise
    allowed_access = ["read"]
    if all(set(ROLES["reporter"]) <= set(item["operations"]) for item in permissions):
        allowed_access.append("learn")
    if interactive:
        console.line("  3 / What may this agent do?", accent=True)
        console.option("read", "Read-only", "Retrieve permitted context. No reporting or proposal tools.")
        if "learn" in allowed_access:
            console.option("learn", "Report results and draft skills", "Read context, retain selected task outcomes and propose methods. Publication stays separate.")
        else:
            console.line("  Your current access permits read-only setup. Ask an administrator for reporting/learning access.")
    access = args.access or (ask("Agent access", "read", allowed_access) if interactive else None)
    require(access in {"read", "learn"}, "agent_answers_required", "Choose --access read or learn.")
    role = "reader" if access == "read" else "reporter"
    operations = set(ROLES[role])
    require(all(operations <= set(item["operations"]) for item in permissions),
            "forbidden", "Current access cannot provide this mode in every selected workspace. Choose read-only or ask an administrator.")
    can_create = all(item["can_add_members"] for item in permissions)
    if interactive:
        console.line("  4 / Agent identity", accent=True)
        if can_create:
            console.option("new", "Separate service identity", "Create attributable agent access, normally expiring in 30 days.")
        console.option("current", "Use my current identity", "Create a narrower child credential. Attribution and expiry follow this identity; revocation of its parent also blocks it.")
    identity_mode = args.identity or (ask("Identity", "new" if can_create else "current", ["new", "current"] if can_create else ["current"]) if interactive else None)
    require(identity_mode in {"new", "current"}, "agent_answers_required", "Choose --identity new or current.")
    require(identity_mode != "new" or can_create, "forbidden", "Only an authorized administrator can create a separate agent identity.")
    def available_name(value):
        slug(value)
        require(len(value) <= 60, "invalid_slug", "Keep the agent name within 60 characters.")
        destination = (args.output or home / "agents" / value).expanduser().absolute()
        require(not destination.exists() and not destination.is_symlink(), "already_exists", "That private setup folder exists. Choose a new name or /cancel.")
        if route:
            require(not profile_path(home, "agent-" + value).exists(), "already_exists", "That agent connection exists. Choose another name.")
    name = args.name or (ask("Agent slug", "project-assistant", validate=available_name) if interactive else None)
    require(name, "agent_answers_required", "Choose --name, for example project-assistant.")
    slug(name)
    require(len(name) <= 60, "invalid_slug", "Keep the agent slug within 60 characters.")
    directory = (args.output or home / "agents" / name).expanduser().absolute()
    require(not directory.exists() and not directory.is_symlink(), "already_exists", "Choose a new setup directory or agent name; existing setup is never overwritten.")
    connection_name = "agent-" + name
    if route:
        require(not profile_path(home, connection_name).exists()
                and not (home / "client-tokens" / (connection_name + ".token")).exists(),
                "already_exists", "That agent connection already exists. Choose another agent name.")
    if interactive:
        console.line("  5 / Review before creating access", accent=True)
        console.result({"agent": name, "method": method, "workspaces": [item["slug"] for item in selected],
                        "access": access, "identity": identity_mode, "private_folder": str(directory), "publication": "Not granted"})
        require(ask("Create this agent setup", "yes", ["yes", "no"]) == "yes", "setup_cancelled", "Agent setup cancelled before creating access.")
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    token_file = directory / "agent.token"
    credential = None
    try:
        private_write(token_file, "", overwrite=False)
        if identity_mode == "new":
            expiry = min(now() + 30 * 86400, caller["expires_at"]) if caller["expires_at"] is not None else now() + 30 * 86400
            credential = client.call("team.add", name=name, space_ids=[item["id"] for item in selected],
                                     role=role, kind="service", expires_at=expiry)
        else:
            credential = client.call("credentials.create", operations=sorted(operations), space_ids=[item["id"] for item in selected])
        private_write(token_file, credential["token"] + "\n")
        if route:
            connect(home, connection_name, route["endpoint"], token_file, route.get("ca_file"), ssh=route.get("ssh"))
            agent_client, agent_identity = load_connection(home, connection_name)
            base = [str(Path(sys.executable).absolute()), "-m", "atmet_brain", "--home", str(home), "--connection", connection_name]
            mcp_args = ["--home", str(home), "--connection", connection_name]
        else:
            agent_client = LocalClient(client.brain, credential["token"])
            agent_identity = agent_client.call("identity.me")
            base = [str(Path(sys.executable).absolute()), "-m", "atmet_brain", "--home", str(home), "--token-file", str(token_file)]
            mcp_args = base[3:]
        for item in selected:
            checked = agent_client.call("access.check", space_id=item["id"])
            require(operations <= set(checked["operations"]) and "publish" not in checked["operations"],
                    "forbidden", "The new credential did not verify with the requested access.")
        settings = {"mcpServers": {"atmet-brain": {"command": str(Path(sys.executable).absolute()),
                    "args": ["-m", "atmet_brain", *mcp_args, "mcp", *(["--allow-proposals", "--task-feedback"] if access == "learn" else [])]}}}
        private_write(directory / "mcp.json", json.dumps(settings, indent=2) + "\n", overwrite=False)
        context = shlex.join(base + ["--json", "context", "Describe the current project", "--space", selected[0]["id"]])
        complete = shlex.join(base + ["task-complete", "-", "--space", selected[0]["id"]])
        request = {"method": "context.get", "params": {"space_id": selected[0]["id"], "query": "Describe the current project"}}
        private_write(directory / "request.json", json.dumps(request, indent=2) + "\n", overwrite=False)
        endpoint = route["endpoint"].rstrip("/") if route else "http://127.0.0.1:7310"
        py = "from pathlib import Path\nfrom atmet_brain import " + ("Client" if route else "Brain, LocalClient") + "\n\ntoken = Path(" + repr(str(token_file)) + ").read_text().strip()\n"
        py += ("client = Client(" + repr(endpoint) + ", token, ca_file=" + repr(str(route["ca_file"]) if route.get("ca_file") else None) + ")\n" if route and not route.get("ssh")
               else "client = LocalClient(Brain(" + repr(str(home)) + "), token)\n" if not route else "# Use the generated CLI/MCP bridge for this SSH connection.\n")
        if not route or not route.get("ssh"):
            py += "context = client.call('context.get', **" + repr(request["params"]) + ")\nprint(context)\n"
            private_write(directory / "agent.py", py, overwrite=False)
        instructions = ("Use the selected Brain space IDs: " + ", ".join(item["id"] for item in selected) + ".\n"
            "Retrieve current context with matching source terms before acting. Keep approved instructions separate from reference data.\n"
            "External actions need separate host authorization. Never widen credentials or publish skills automatically.\n")
        if access == "learn":
            instructions += ("At task completion, report a safe result, actual steps/checks/corrections and all original source evidence.\n"
                "Reports default private. Share with a publisher only when authorized and all original evidence also permits review.\n"
                "Inspect separate report/skill statuses; retry the same payload after a delivery failure without repeating business actions.\n")
        private_write(directory / "agent-instructions.md", instructions, overwrite=False)
        next_steps = {
            "mcp": ["Open " + str(directory / "mcp.json") + " and add its server entry to your app's local MCP settings.",
                    "Restart/reconnect the agent app. It must support local MCP stdio.", "Ask it to list permitted spaces and cite a matching source from " + selected[0]["slug"] + "."],
            "terminal": ["Run this scoped context command: " + context, "Give your coding agent " + str(directory / "agent-instructions.md") + "."],
            "rest": ["Use endpoint " + endpoint + "/v1/rpc with Authorization: Bearer read from " + str(token_file) + ".",
                     "Send the JSON from " + str(directory / "request.json") + "."],
            "python": ["Run the example with the installed core: " + shlex.join([str(Path(sys.executable).absolute()), str(directory / "agent.py")]),
                       "Integrate its client.call pattern into your trusted application."],
        }[method]
        if method == "rest" and not route:
            next_steps.insert(0, "Start the local API separately: " + shlex.join([str(Path(sys.executable).absolute()), "-m", "atmet_brain", "--home", str(home), "serve"]))
        guide = "# Agent connection\n\n" + "\n".join(str(index) + ". " + step for index, step in enumerate(next_steps, 1))
        guide += ("\n\nContext command:\n\n```bash\n" + context + "\n```\n\n"
                  "Core identity/space permissions were verified. The external app, API listener and source relevance were not tested.\n"
                  "Read agent-instructions.md. A credential authorizes access, not external actions or skill publication.\n")
        if access == "learn":
            guide += ("\nCompletion hook command (host supplies safe report JSON on stdin):\n\n```bash\n" + complete + "\n```\n"
                "\nMCP completion instructions require agent cooperation. Python hosts can use client.task_feedback(...).\n"
                "No existing application hooks were installed. New skills require publisher review; private reports need deliberate sharing for review.\n")
        private_write(directory / "CONNECT.md", guide, overwrite=False)
        result = {"directory": str(directory), "method": method, "workspaces": [item["slug"] for item in selected],
                  "space_ids": [item["id"] for item in selected], "access": access,
                  "access_description": "Read-only" if access == "read" else "Reports and pending skill drafts; publication not granted",
                  "identity": agent_identity, "identity_mode": identity_mode, "token_file": str(token_file),
                  "mcp_config": str(directory / "mcp.json"), "guide": str(directory / "CONNECT.md"),
                  "mcp_entry": settings,
                  "connection": connection_name if route else None, "verified": "core identity and selected-space permissions",
                  "external_agent_verified": False, "publication_authorized": False, "next": next_steps}
        private_write(directory / "receipt.json", json.dumps(result, indent=2) + "\n", overwrite=False)
        return result
    except (BrainError, OSError, ValueError):
        revoked = False
        if credential:
            try:
                client.call("credentials.revoke", credential_id=credential["credential_id"])
                revoked = True
            except (BrainError, OSError):
                pass
        if revoked:
            token_file.unlink(missing_ok=True)
        message = ("Setup stopped. " + ("The new credential was revoked. " if revoked else
                   "Check/revoke new credential " + credential["credential_id"] + " before reuse. " if credential else "No credential was issued. ") +
                   "Inspect the private folder " + str(directory) + "; choose a new name/directory for a retry.")
        raise BrainError("agent_setup_incomplete", message, 409) from None
