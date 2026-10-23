"""Guided local, Host and Join setup with core-enforced permissions."""

import sys
import shlex
from functools import partial
from pathlib import Path

from .auth import ROLES
from .errors import require
from .sharing import read_share, validate_route
from .terminal import Console, prompt
from .util import slug, text, uid


def guided_setup(args, initialize, connect_remote, *, inspect_local=None, share=None, join=None, start_service=None, invite_member=None):
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
    base = [str(Path(sys.executable).absolute()), "-m", "atmet_brain", "--home", str(args.home)]
    if mode == "join" or (mode == "connect" and args.file):
        def validate_file(value):
            from .invitations import read_private_json, read_invitation
            return read_invitation(value) if read_private_json(value).get("format") == "atmet-invite-v1" else read_share(value)
        path = args.file or (ask("Private invitation or team connection file", validate=validate_file) if interactive else None)
        require(path, "setup_answers_required", "Use join --file PATH, or run join interactively.")
        from .invitations import read_private_json
        if read_private_json(path).get("format") == "atmet-invite-v1":
            from .account_cli import join_invitation
            return join_invitation(args, path)
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

    existing = (args.home / "brain.sqlite3").is_file()
    if existing and mode == "local":
        require(not args.organization and not args.spaces and not args.owner, "already_initialized",
                "A Brain already exists at " + str(args.home) + ". Run setup without creation flags to open it, use space NAME to add a department, or choose a different --home for a separate Brain.")
        if interactive:
            console.line("  A Brain already exists on this device.", accent=True)
            console.wrapped("Data home: " + str(args.home), "  ")
            console.option("reuse", "Open the existing Brain", "Keep its company, owner, workspaces and data.")
            console.option("new", "Create a separate Brain", "Choose a new data folder. The existing Brain stays intact.")
            console.option("cancel", "Leave setup", "Make no setup changes.")
            choice = ask("Existing Brain", "reuse", ["reuse", "new", "cancel"])
            require(choice != "cancel", "setup_cancelled", "Setup cancelled. Existing Brain kept.")
            if choice == "new":
                def new_folder(value):
                    chosen = Path(value).expanduser()
                    require(not chosen.exists() and not chosen.is_symlink(), "already_exists", "Choose a new private folder that does not exist.")
                target = Path(ask("New private data folder", str(args.home.with_name(args.home.name + "-other")), validate=new_folder)).expanduser()
                require(not target.exists() and not target.is_symlink(), "already_exists",
                        "Choose a new folder that does not exist. Existing folders are never overwritten.")
                args.home = target.resolve()
                base = [str(Path(sys.executable).absolute()), "-m", "atmet_brain", "--home", str(args.home)]
                existing = False
    if existing:
        if mode == "host":
            require(not args.organization and not args.spaces and not args.owner, "existing_brain",
                    "Host reuses this Brain. Omit organization/owner/spaces flags; use space to add a department first.")
        result = inspect_local()
        spaces = [space["slug"] for space in result["spaces"]]
        if mode == "host":
            require(spaces, "no_spaces", "Create a workspace with: atmet-brain space WORKSPACE_NAME, then run host.")
        if interactive:
            console.line("  1 / Reuse your existing Brain", accent=True)
            console.result({"home": result["home"], "signed_in_as": result["identity"]["name"], "workspaces": spaces})
    else:
        organization = args.organization or (ask("Company slug", "my-company", validate=slug) if interactive else None)
        require(organization, "setup_answers_required", "New Brain setup needs --organization.")
        organization = slug(organization)
        owner = args.owner or (ask("Your name", "Company owner", validate=lambda v: text(v, maximum=120)) if interactive else "Company owner")
        text(owner, maximum=120)
        spaces_value = args.spaces
        if spaces_value is None:
            def workspace_names(value):
                names = [slug(item.strip()) for item in value.split(",") if item.strip()]
                require(0 < len(names) <= 30 and len(set(names)) == len(names), "invalid_spaces", "Choose 1 to 30 distinct workspace names.")
            spaces_value = ask("Department workspaces, separated by commas", "shared,sales", validate=workspace_names) if interactive else "shared"
        spaces = [slug(value.strip()) for value in spaces_value.split(",") if value.strip()]
        require(0 < len(spaces) <= 30 and len(set(spaces)) == len(spaces), "invalid_spaces", "Choose 1 to 30 distinct workspace slugs.")

    member, route, output, selected = args.member, args.transport, args.output, None
    member_username = getattr(args, "member_username", None)
    require(not member_username or member, "setup_answers_required", "Use --member NAME with --member-username LOGIN.")
    if mode == "host":
        if interactive and args.port == 7310:
            from .companies import catalog
            records = catalog(getattr(args, "catalog_home", args.home))
            if len(records) > 1:
                def valid_port(value):
                    require(value.isdigit() and 1 <= int(value) <= 65535, "invalid_port", "Choose a port between 1 and 65535.")
                from .invitations import read_private_json
                settings = read_private_json(args.home / "hosting.json") if (args.home / "hosting.json").exists() else {}
                default_port = settings.get("port", (settings.get("ssh") or {}).get("port", 7310 + len(records) - 1))
                console.line("  Each company server running on this device needs a different local port.")
                args.port = int(ask("This company's Brain port", str(default_port), validate=valid_port))
        if interactive:
            console.line("  2 / How teammates reach this device", accent=True)
            console.option("ssh", "Automatic SSH forwarding", "Use administrator-configured SSH keys and a trusted host. Atmet opens and closes the tunnel for each request.")
            console.option("https", "Existing HTTPS address", "Use your company's already configured secure Brain address.")
            console.option("later", "Prepare the Brain first", "Keep access local. Run host again after network access is ready.")
        route = route or (ask("Connection route", "ssh", ["ssh", "https", "later"]) if interactive else "later")
        require(not args.endpoint or route == "https", "invalid_route", "Use --transport https with --endpoint.")
        require(not args.ssh_destination or route == "ssh", "invalid_route", "Use --transport ssh with --ssh-destination.")
        if route == "ssh":
            destination = args.ssh_destination or (ask("Forwarding-only SSH user@host, for example forward@brain.example.com",
                validate=lambda value: validate_route(ssh={"destination": value, "port": args.port})) if interactive else None)
            ssh, endpoint = {"destination": destination, "port": args.port}, None
            validate_route(ssh=ssh)
        elif route == "https":
            endpoint = args.endpoint or (ask("Company Brain HTTPS address", validate=lambda value: validate_route(endpoint=value)) if interactive else None)
            ssh = None
            validate_route(endpoint=endpoint)
        else:
            require(not member, "route_required", "Choose --transport https or ssh before creating member access.")
        if route != "later":
            if interactive:
                console.line("  3 / Give one teammate access", accent=True)
            if not member and interactive and ask("Create a single-use employee invitation", "yes", ["yes", "no"]) == "yes":
                from .accounts import username
                member = ask("Employee display name", validate=lambda v: text(v, maximum=120))
                member_username = ask("Employee work username or email", validate=username)
            if member:
                text(member, maximum=120)
                if interactive:
                    console.line("  Available workspaces: " + ", ".join(spaces))
                def permitted_names(value):
                    names = [v.strip() for v in value.split(",") if v.strip()]
                    require(names and len(names) <= 30 and len(set(names)) == len(names) and all(v in spaces for v in names),
                            "invalid_spaces", "Choose distinct workspace names from the list.")
                selection = args.member_spaces or (ask("Allowed workspaces, separated by commas", spaces[0], validate=permitted_names) if interactive else None)
                require(selection, "setup_answers_required", "Choose --member-spaces using workspace names.")
                selected = [value.strip() for value in selection.split(",") if value.strip()]
                require(selected and len(selected) <= 30 and len(set(selected)) == len(selected) and all(value in spaces for value in selected),
                        "invalid_spaces", "Select distinct names from the listed workspaces.")
                role = args.role or (ask("Role", "reader", sorted(set(ROLES) - {"owner"})) if interactive else "reader")
                output = output or (args.home / "team-access" / (uid("member") + (".atmet-invite.json" if member_username else ".atmet-join.json")))
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
        result["company"] = organization
    result["reused"] = existing
    result["access"] = "The API stays on loopback. SSH accounts and HTTPS ingress are configured by your administrator."
    result["next"] = [shlex.join(base + ["status"]), shlex.join(base + ["space"])]
    result["departments"] = "Add a department without repeating company setup: " + shlex.join(base + ["space", "DEPARTMENT_NAME"])
    if mode == "host":
        if member:
            result["team"] = (invite_member(member_username, member, selected, role, output, {"endpoint": endpoint, "ssh": ssh})
                              if member_username else share(member, selected, role, output, endpoint=endpoint, ssh=ssh))
            if interactive:
                console.line("  Member access saved: " + (result["team"].get("private_file") or result["team"]["connection_file"]), accent=True)
        result["server"] = {"port": args.port, "network_verified": False,
                            "next": shlex.join(base + ["serve", "--port", str(args.port)])}
        if route != "later":
            from .util import private_write, dumps
            private_write(args.home / "hosting.json", dumps({"endpoint": endpoint, "ssh": ssh, "port": args.port}) + "\n")
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
