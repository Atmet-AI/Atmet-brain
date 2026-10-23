"""Guided local, Host and Join setup with core-enforced permissions."""

import sys
import shlex
from functools import partial

from .auth import ROLES
from .errors import require
from .sharing import read_share, validate_route
from .terminal import Console, prompt
from .util import slug, text, uid


def guided_setup(args, initialize, connect_remote, *, inspect_local=None, share=None, join=None, start_service=None):
    args.home = args.home.expanduser().resolve()
    interactive = sys.stdin.isatty() and not args.json
    console = Console(plain=args.plain)
    ask = partial(prompt, console=console)
    if interactive:
        console.banner("Your company Brain. Host here, or join your team.")
    mode = args.mode or getattr(args, "setup_entry", None)
    if not mode:
        require(interactive, "setup_answers_required", "Choose setup --mode local|host|join, or run host / join.")
        console.option("local", "Just me", "Create a private Brain on this device.")
        console.option("host", "Host a team Brain", "Use a new or existing Brain and prepare teammate access.")
        console.option("join", "Join my team", "Open the private connection file from your administrator.")
        mode = ask("Choose a setup", "local", ["local", "host", "join", "team", "connect"])
    mode = {"team": "host"}.get(mode, mode)
    base = ["atmet-brain", "--home", str(args.home.expanduser().resolve())]
    if mode == "join" or (mode == "connect" and args.file):
        path = args.file or (ask("Private team connection file") if interactive else None)
        require(path, "setup_answers_required", "Use join --file PATH, or run join interactively.")
        record = read_share(path)
        name = args.name or (ask("Save this connection as", "company") if interactive else "company")
        slug(name)
        if interactive:
            console.line("  Review the connection supplied by your administrator", accent=True)
            console.result({"server": record["endpoint"] or "ssh://" + record["ssh"]["destination"],
                            "requested_workspaces": record["workspaces"], "role": record["role"]})
            console.line("  Continue only if this file and server came from your administrator.")
            require(ask("Verify and join", "yes", ["yes", "no"]) == "yes", "setup_cancelled", "Join cancelled. No connection saved.")
        result = join(path, name, args.ca_file, record)
        result["next"] = [shlex.join(base + ["--connection", name, "status"]),
                          shlex.join(base + ["--connection", name, "space"]),
                          shlex.join(base + ["--connection", name, "agent"]),
                          shlex.join(base + ["--connection", name, "mcp-config"])]
        result["note"] = "Only server-confirmed workspaces are listed. Keep the original connection file private; revocation is controlled by your administrator."
        return result
    if mode == "connect":
        name = args.name or (ask("Connection name", "company") if interactive else None)
        endpoint = args.endpoint or (ask("Brain URL, HTTPS or SSH loopback") if interactive else None)
        token_file = args.token_file or (ask("Path to your individual credential file") if interactive else None)
        require(name and endpoint and token_file, "setup_answers_required", "Connect setup needs --name, --endpoint and --token-file.")
        return connect_remote(name, endpoint, token_file, args.ca_file)

    existing = mode == "host" and (args.home / "brain.sqlite3").is_file()
    if existing:
        require(not args.organization and not args.spaces and not args.owner, "existing_brain",
                "Host reuses this Brain. Omit organization/owner/spaces flags; use space to add a department first.")
        result = inspect_local()
        spaces = [space["slug"] for space in result["spaces"]]
        require(spaces, "no_spaces", "Create a workspace with: atmet-brain space WORKSPACE_NAME, then run host.")
        if interactive:
            console.line("  1 / Reuse your existing Brain", accent=True)
            console.result({"home": result["home"], "signed_in_as": result["identity"]["name"], "workspaces": spaces})
    else:
        organization = args.organization or (ask("Company slug", "my-company") if interactive else None)
        require(organization, "setup_answers_required", "New Brain setup needs --organization.")
        organization = slug(organization)
        owner = args.owner or (ask("Your name", "Company owner") if interactive else "Company owner")
        text(owner, maximum=120)
        spaces_value = args.spaces
        if spaces_value is None:
            spaces_value = ask("Department workspaces, separated by commas", "shared,sales") if interactive else "shared"
        spaces = [slug(value.strip()) for value in spaces_value.split(",") if value.strip()]
        require(0 < len(spaces) <= 30 and len(set(spaces)) == len(spaces), "invalid_spaces", "Choose 1 to 30 distinct workspace slugs.")

    member, route, output, selected = args.member, args.transport, args.output, None
    if mode == "host":
        if interactive:
            console.line("  2 / How teammates reach this device", accent=True)
            console.option("ssh", "Automatic SSH forwarding", "Use administrator-configured SSH keys and a trusted host. Atmet opens and closes the tunnel for each request.")
            console.option("https", "Existing HTTPS address", "Use your company's already configured secure Brain address.")
            console.option("later", "Prepare the Brain first", "Keep access local. Run host again after network access is ready.")
        route = route or (ask("Connection route", "ssh", ["ssh", "https", "later"]) if interactive else "later")
        require(not args.endpoint or route == "https", "invalid_route", "Use --transport https with --endpoint.")
        require(not args.ssh_destination or route == "ssh", "invalid_route", "Use --transport ssh with --ssh-destination.")
        if route == "ssh":
            destination = args.ssh_destination or (ask("Forwarding-only SSH user@host") if interactive else None)
            ssh, endpoint = {"destination": destination, "port": args.port}, None
            validate_route(ssh=ssh)
        elif route == "https":
            endpoint = args.endpoint or (ask("Company Brain HTTPS address") if interactive else None)
            ssh = None
            validate_route(endpoint=endpoint)
        else:
            require(not member, "route_required", "Choose --transport https or ssh before creating member access.")
        if route != "later":
            if interactive:
                console.line("  3 / Give one teammate access", accent=True)
            if not member and interactive and ask("Create a private connection file", "yes", ["yes", "no"]) == "yes":
                member = ask("Teammate name")
            if member:
                text(member, maximum=120)
                if interactive:
                    console.line("  Available workspaces: " + ", ".join(spaces))
                selection = args.member_spaces or (ask("Allowed workspaces, separated by commas", spaces[0]) if interactive else None)
                require(selection, "setup_answers_required", "Choose --member-spaces using workspace names.")
                selected = [value.strip() for value in selection.split(",") if value.strip()]
                require(selected and len(selected) <= 30 and len(set(selected)) == len(selected) and all(value in spaces for value in selected),
                        "invalid_spaces", "Select distinct names from the listed workspaces.")
                role = args.role or (ask("Role", "reader", sorted(set(ROLES) - {"owner"})) if interactive else "reader")
                output = output or (args.home / "team-access" / (uid("member") + ".atmet-join.json"))
                require(not output.expanduser().exists() and not output.expanduser().is_symlink(),
                        "already_exists", "Choose a new private connection file; existing files are never overwritten.")
                if interactive:
                    console.result({"member": member, "workspaces": selected, "role": role, "private_file": str(output)})
                    require(ask("Create this member access", "yes", ["yes", "no"]) == "yes", "setup_cancelled", "Host setup cancelled before provisioning.")
    require(mode == "host" or not args.start_service, "invalid_setup", "Use Host to install a team API service.")
    keep_running = args.start_service
    if mode == "host" and interactive and not keep_running:
        keep_running = ask("Install and start the local background API service", "no", ["yes", "no"]) == "yes"
    if not existing:
        result = initialize(organization, owner, spaces)
    result["reused"] = existing
    result["access"] = "The API stays on loopback. SSH accounts and HTTPS ingress are configured by your administrator."
    result["next"] = [shlex.join(base + ["serve"]), shlex.join(base + ["status"])]
    if mode == "host":
        if member:
            result["team"] = share(member, selected, role, output, endpoint=endpoint, ssh=ssh)
            if interactive:
                console.line("  Member access saved: " + result["team"]["connection_file"], accent=True)
        result["server"] = {"port": args.port, "network_verified": False,
                            "next": shlex.join(base + ["serve", "--port", str(args.port)])}
        result["next"] = [result["server"]["next"], shlex.join(base + ["status"])]
        if keep_running:
            result["service"] = start_service(args.port)
            result["next"] = [shlex.join(base + ["service", "status"]), shlex.join(base + ["status"])]
            result["server"]["next"] = result["next"][0]
        result["team_note"] = ("Send the connection file privately, then your teammate runs join. Join verifies the real server and permissions."
                               if member else "No teammate access created. Run host again to add a teammate when your secure route is ready.")
        result["host_requirement"] = "Keep this device awake and connected. Services depend on your OS user session."
    result["learning"] = "Add selected sources and reviewed workflows next. Setup does not infer or approve business rules."
    result["next"].append(shlex.join(base + ["agent"]))
    return result
