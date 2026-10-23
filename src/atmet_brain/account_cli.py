"""Private password prompts and guided employee administration."""

import getpass
import json
from pathlib import Path
import shlex
import sys
import warnings

from .accounts import password_text, username
from .auth import ROLES
from .brain import Brain
from .connections import load_connection, profile_path
from .errors import BrainError, require
from .feedback import LocalClient
from .invitations import read_invitation, read_private_json, route_client, save_invitation, save_session
from .sharing import validate_route
from .terminal import Console, prompt
from .util import private_write, slug, uid


def interactive(args):
    return sys.stdin.isatty() and not args.json


def secret(args, label, *, new=False, login=None):
    if args.password_stdin:
        require(not sys.stdin.isatty(), "private_input_required", "Pipe private password input for --password-stdin, or omit that flag to use a hidden terminal prompt.")
        value = sys.stdin.readline(514)
        require(value and len(value) <= 513, "password_required", "Provide a bounded password line on stdin.")
        value = value.removesuffix("\n").removesuffix("\r")
        return password_text(value, login) if new else value
    require(interactive(args), "password_required", "Use an interactive terminal, or --password-stdin for private automation. Password arguments are not accepted.")
    console = Console(plain=args.plain)
    def hidden(message):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", getpass.GetPassWarning)
                return getpass.getpass(message)
        except getpass.GetPassWarning:
            raise BrainError("private_prompt_unavailable", "Cannot disable terminal echo. Use a real terminal or explicit private --password-stdin input.") from None
    while True:
        try:
            value = hidden(label + ": ")
            if value == "/cancel":
                raise BrainError("setup_cancelled", "Sign-in cancelled.")
            if new:
                password_text(value, login)
                require(value == hidden("Confirm password: "), "password_mismatch", "Passwords did not match.")
            return value
        except EOFError:
            raise BrainError("setup_interrupted", "Password entry interrupted. No password was saved.") from None
        except BrainError as error:
            if error.code not in {"invalid_password", "weak_password", "password_mismatch"}:
                raise
            console.line("  " + error.message + " Try again, or type /cancel.", accent=True)


def core_client(args, read_token):
    if args.connection:
        return load_connection(args.home, args.connection)[0]
    if args.endpoint:
        from .client import Client
        return Client(args.endpoint, read_token(args), args.ca_file)
    return LocalClient(Brain(args.home), read_token(args))


def role_choices(client, spaces):
    result = {}
    for space in spaces:
        allowed = set(client.call("access.check", space_id=space["id"])["operations"])
        result[space["id"]] = [name for name, operations in ROLES.items() if name != "owner" and set(operations) <= allowed]
    return result


def choose_access(args, client, current=None, *, allow_empty=False):
    console = Console(plain=args.plain)
    spaces = client.call("spaces.list")
    permissions = role_choices(client, spaces)
    existing = {entry["space_id"]: entry["role"] for entry in current or []}
    allowed = {space["slug"]: space for space in spaces}
    if interactive(args):
        for space in spaces:
            console.line("  " + space["slug"] + "  /  " + existing.get(space["id"], "no access"))
        console.line("  Include every allowed workspace. Leave payroll out for employees who must not see salaries.")
        def valid(value):
            names = [v.strip() for v in value.split(",") if v.strip()]
            require((allow_empty and value == "none") or
                    (names and len(names) == len(set(names)) and all(v in allowed for v in names)),
                    "invalid_spaces", "Choose distinct listed workspace names, or none when removing all access.")
        defaults = ",".join(space["slug"] for space in spaces if space["id"] in existing) or ("none" if allow_empty else None)
        value = prompt("Allowed workspaces, separated by commas", defaults, console=console, validate=valid)
        names = [] if value == "none" else [v.strip() for v in value.split(",") if v.strip()]
        selected = []
        for name in names:
            space = allowed[name]
            choices = permissions[space["id"]]
            require(choices, "forbidden", "You cannot delegate a role in " + name + ".", 403)
            default = {"reporter": "user", "publisher": "editor"}.get(existing.get(space["id"], "reader"), existing.get(space["id"], "reader"))
            if default not in choices:
                default = choices[0]
            console.line("  reader: read; user: work/report/draft; editor: edit/review/publish procedures.")
            console.line("  Company administration is separate. Legacy and specialist roles remain available.")
            simple = [role for role in ["reader", "user", "editor"] if role in choices]
            advanced = [role for role in choices if role not in {"reader", "user", "editor"}]
            menu = simple + (["advanced"] if advanced else [])
            selected_role = prompt("Access in " + name, default if default in simple else "advanced", menu, console=console)
            role = prompt("Advanced role in " + name, default if default in advanced else advanced[0], advanced, console=console) if selected_role == "advanced" else selected_role
            selected.append({"space_id": space["id"], "role": role})
        return selected
    require(args.access_file, "access_required", "Use --access-file containing explicit space_id/role entries, or run interactively.")
    return json.loads(args.access_file.expanduser().read_text())


def invitation_route(args):
    console = Console(plain=args.plain)
    if args.connection:
        record = read_private_json(profile_path(args.home, args.connection))
        if record.get("ssh"):
            return {"endpoint": None, "ssh": record["ssh"]}
        # A managed loopback connection is not a portable invitation address.
        if record["endpoint"].startswith("https://"):
            return {"endpoint": record["endpoint"], "ssh": None}
    if args.invite_endpoint:
        validate_route(endpoint=args.invite_endpoint)
        return {"endpoint": args.invite_endpoint, "ssh": None}
    if args.ssh_destination:
        value = {"destination": args.ssh_destination, "port": args.port}
        validate_route(ssh=value)
        return {"endpoint": None, "ssh": value}
    stored = Path(args.home) / "hosting.json"
    if stored.exists():
        value = read_private_json(stored)
        validate_route(value.get("endpoint"), value.get("ssh"))
        return {"endpoint": value.get("endpoint"), "ssh": value.get("ssh")}
    require(interactive(args), "route_required", "Provide --invite-endpoint HTTPS_URL or --ssh-destination user@host.")
    console.line("  This invitation needs the company address teammates can reach. Network administration remains separate.")
    kind = prompt("Company connection", "https", ["https", "ssh"], console=console)
    if kind == "https":
        endpoint = prompt("Company HTTPS address", console=console, validate=lambda value: validate_route(endpoint=value))
        return {"endpoint": endpoint, "ssh": None}
    destination = prompt("Forwarding-only SSH user@host", console=console,
                         validate=lambda value: validate_route(ssh={"destination": value, "port": args.port}))
    return {"endpoint": None, "ssh": {"destination": destination, "port": args.port}}


def invite_employee(args, client, member=None):
    console = Console(plain=args.plain)
    login = args.username or (member.get("username") if member else None) or (prompt("Employee work username or email", None,
                                    console=console, validate=username) if interactive(args) else None)
    require(login, "username_required", "Choose --username, or run invite interactively.")
    login = username(login)
    name = member["name"] if member else args.employee_name or (prompt("Employee display name", login, console=console) if interactive(args) else login)
    access = choose_access(args, client, member.get("access") if member else None)
    route = invitation_route(args)
    output = args.output or Path(args.home) / "invitations" / (uid("invite") + ".atmet-invite.json")
    if interactive(args):
        names = {s["id"]: s["slug"] for s in client.call("spaces.list")}
        console.result({"employee": login, "access": [{"workspace": names.get(x["space_id"], x["space_id"]), "role": x["role"]} for x in access],
                        "single_use": True, "reset_existing_login": bool(member), "private_file": str(output)})
        require(prompt("Create this invitation", "yes", ["yes", "no"], console=console) == "yes", "setup_cancelled", "Invitation cancelled before issuance.")
    return save_invitation(client, output, username_value=login, name=name, access=access, route=route,
                           reset_principal=member["id"] if member else args.reset_principal, expires_at=args.expires_at)


def join_invitation(args, path):
    console = Console(plain=args.plain)
    record = read_invitation(path)
    name = args.name or (prompt("Save company connection as", record["company"], console=console, validate=slug) if interactive(args) else record["company"])
    require(not profile_path(args.home, name).exists() and not (Path(args.home) / "client-tokens" / (name + ".token")).exists(),
            "already_exists", "This connection exists. Use login --connection NAME to sign in, or choose another connection name.", 409)
    if interactive(args):
        console.result({"company": record["company"], "username": record["username"], "server": record["endpoint"] or "ssh://" + record["ssh"]["destination"],
                        "invitation": "Single-use; your administrator sets workspace access"})
        require(prompt("Trust this invitation and enroll", "yes", ["yes", "no"], console=console) == "yes", "setup_cancelled", "Enrollment cancelled.")
    password = secret(args, "Choose your password", new=True, login=record["username"])
    route = {"endpoint": record["endpoint"], "ssh": record["ssh"]}
    client = route_client(route, ca_file=args.ca_file)
    try:
        issued = client.auth("accept", organization=record["organization_id"], invite_id=record["invite_id"], secret=record["secret"], password=password)
    except BrainError as error:
        if error.code == "connection_failed":
            raise BrainError(error.code, "Enrollment response was not received. If the invitation was accepted, use login with this company address and the password you just chose; do not request repeated account creation.", error.status) from None
        raise
    result = save_session(args.home, name, route, issued, record["username"], ca_file=args.ca_file)
    base = [str(Path(sys.executable).absolute()), "-m", "atmet_brain", "--home", str(Path(args.home).resolve()), "--connection", name]
    result["next"] = [shlex.join(base + ["status"]), shlex.join(base + ["agent"])]
    result["invitation_consumed"] = True
    return result


def login_employee(args):
    console = Console(plain=args.plain)
    route, local, previous = None, not (args.connection or args.endpoint or args.ssh_destination), None
    require(not args.ssh_destination or not (args.connection or args.endpoint), "invalid_connection", "Choose one saved connection, HTTPS endpoint or SSH destination.")
    if args.connection:
        previous = read_private_json(profile_path(args.home, args.connection))
        require(previous.get("username") and previous.get("credential_id"), "not_password_session",
                "This is a service/API-key connection. Use a new connection name for an employee login; scoped agent profiles are never upgraded silently.")
        route = {"endpoint": previous["endpoint"], "ssh": previous.get("ssh")}
        ca = args.ca_file or previous.get("ca_file")
        client = route_client(route, ca_file=ca)
        name = args.connection
    elif args.endpoint or args.ssh_destination:
        route, ca = {"endpoint": args.endpoint, "ssh": {"destination": args.ssh_destination, "port": args.port} if args.ssh_destination else None}, args.ca_file
        client, name = route_client(route, ca_file=ca), args.name or "company"
        require(not profile_path(args.home, name).exists(), "already_exists", "Use --connection NAME to refresh that saved login.")
    else:
        require((Path(args.home) / "brain.sqlite3").is_file(), "brain_missing", "Choose a company Brain or a remote connection first.")
        client, ca, name = Brain(args.home), None, None
        if (Path(args.home) / "login.json").exists():
            previous = read_private_json(Path(args.home) / "login.json")
    login = args.username or (previous.get("username") if previous else None) or (prompt("Username", console=console, validate=username) if interactive(args) else None)
    require(login, "username_required", "Choose --username, or run login interactively.")
    login = username(login)
    company = args.organization or (previous.get("organization_id") if previous else None)
    if not company and local:
        with client.store.transaction() as conn:
            rows = conn.execute("SELECT slug FROM organizations ORDER BY slug").fetchall()
        if len(rows) == 1:
            company = rows[0][0]
    company = company or (prompt("Company ID or slug", console=console) if interactive(args) else None)
    require(company, "company_required", "Choose --organization, or use your saved company connection.")
    while True:
        password = secret(args, "Password")
        try:
            issued = client.login(company, login, password) if local else client.auth("login", organization=company, username_value=login, password=password)
            break
        except BrainError as error:
            if not interactive(args) or error.code not in {"invalid_login", "connection_failed", "ssh_failed"}:
                raise
            console.line("  " + error.message, accent=True)
            require(prompt("Retry sign-in", "yes", ["yes", "no"], console=console) == "yes", "setup_cancelled", "Sign-in cancelled.")
    return save_session(args.home, name, route, issued, login, ca_file=ca, local=local, replacing=previous is not None)


def logout_employee(args):
    if args.connection:
        profile = read_private_json(profile_path(args.home, args.connection))
        require(profile.get("username"), "not_password_session", "This is a legacy service/key connection, not a password login.")
        token_path = Path(profile["token_file"])
        if not token_path.exists():
            return {"signed_out": True, "session_revoked": False, "note": "No local session remains. Sign in again with login."}
        client = route_client(profile, token_path.read_text().strip(), profile.get("ca_file"))
    else:
        require(not args.endpoint and not args.token_file, "invalid_logout", "Choose a saved login or local signed-in session.")
        profile = read_private_json(Path(args.home) / "login.json")
        token_path = Path(args.home) / "session.token"
        if not token_path.exists():
            return {"signed_out": True, "session_revoked": False, "note": "No local session remains. Sign in again with login."}
        client = LocalClient(Brain(args.home), token_path.read_text().strip())
    confirmed, note = False, None
    try:
        identity = client.call("identity.me")
        client.call("credentials.revoke", credential_id=identity["credential_id"])
        confirmed = True
    except BrainError as error:
        note = ("The session is already expired or revoked." if error.status == 401 else
                "Server revocation was not confirmed. Ask an administrator to revoke " + profile.get("credential_id", "this session") + ".")
    token_path.unlink(missing_ok=True)
    return {"signed_out": True, "session_revoked": confirmed, "username": profile["username"], "server_note": note,
            "note": "Connection address retained for login. Other device sessions are separate; password change revokes them all."}


def account_command(args, read_token):
    if args.action == "recover":
        from .accounts import recover_owner
        require(not args.connection and not args.endpoint and not args.token_file, "local_only", "Owner recovery requires the trusted local data-home operator.")
        require((Path(args.home) / "brain.sqlite3").is_file(), "brain_missing", "Choose the existing company data home.")
        console = Console(plain=args.plain)
        login = args.username or (prompt("Owner login to recover", console=console, validate=username) if interactive(args) else None)
        require(login, "username_required", "Choose --username.")
        confirmed = args.confirm_local_owner
        if interactive(args) and not confirmed:
            console.line("  Local filesystem-owner recovery resets this owner's password and revokes their existing credentials.")
            confirmed = prompt("Confirm you administer this private data home", "no", ["yes", "no"], console=console) == "yes"
        require(confirmed, "owner_confirmation_required", "Confirm the local operator action with --confirm-local-owner.")
        password = secret(args, "New owner password", new=True, login=login)
        output = args.output or Path(args.home) / "operator-access" / (uid("operator") + ".token")
        private_write(output, "", overwrite=False)
        issued = None
        try:
            brain = Brain(args.home)
            issued = recover_owner(brain, login, password, args.organization)
            private_write(output, issued.pop("token") + "\n")
        except (BrainError, OSError):
            output.unlink(missing_ok=True)
            if issued:
                raise BrainError("owner_save_failed", "Owner password changed but the operator key could not be saved. Sign in with the new password or repeat local recovery; revoke credential " + issued["credential_id"] + ".") from None
            raise
        return {**issued, "operator_file": str(Path(output).resolve()),
                "next": "Run login with the new password. Use the operator file explicitly for continuing local administration; do not share it."}
    if args.action == "password":
        require(not args.endpoint, "saved_login_required", "Password changes need a saved employee connection or local company session. Sign in and save a connection first.")
        if args.connection:
            require(read_private_json(profile_path(args.home, args.connection)).get("username"),
                    "not_password_session", "Choose a saved password login, not a service/API-key connection.")
    client = core_client(args, read_token)
    if args.action == "setup":
        client.call("members.list")
        require(not client.call("identity.me").get("username"), "already_exists", "This owner already has a login. Use login, account password or local account recover.")
        login = args.username or (prompt("Owner login username or email", console=Console(plain=args.plain), validate=username) if interactive(args) else None)
        require(login, "username_required", "Choose --username.")
        return client.call("accounts.setup", username_value=login, password=secret(args, "Choose your password", new=True, login=login))
    identity = client.call("identity.me")
    require(identity.get("username"), "account_missing", "Enroll the owner account or accept an employee invitation first.")
    old = secret(args, "Current password")
    new = secret(args, "New password", new=True)
    issued = client.call("accounts.password", old_password=old, new_password=new)
    if args.connection:
        profile = read_private_json(profile_path(args.home, args.connection))
        return save_session(args.home, args.connection, {"endpoint": profile["endpoint"], "ssh": profile.get("ssh")}, issued,
                            profile["username"], ca_file=profile.get("ca_file"), replacing=True)
    return save_session(args.home, None, None, issued, identity["username"], local=True,
                        replacing=(Path(args.home) / "login.json").exists())


def _team_command(args, read_token):
    console = Console(plain=args.plain)
    client = core_client(args, read_token)
    while True:
        members = client.call("members.list")
        action = args.action
        if not action:
            require(interactive(args), "team_action_required", "Choose team list or run team interactively.")
            console.banner("Team access. Select each employee's workspaces and access.", compact=True)
            action = prompt("Action", "list", ["list", "invite", "access", "reset", "disable", "workspace", "invites", "revoke", "done"], console=console)
        if action == "done":
            return {"done": True}
        if action == "list":
            result = members
            if interactive(args):
                names = {s["id"]: s["slug"] for s in client.call("spaces.list")}
                result = [{"employee": m["name"], "login": m["username"] or m["kind"], "active": bool(m["active"]),
                           "workspaces": [names.get(x["space_id"], "restricted workspace") + ": " + x["role"] for x in m["access"]],
                           "document_groups": [g["name"] for g in m["groups"]]}
                          for m in members]
        elif action == "invite":
            result = invite_employee(args, client)
        elif action == "workspace":
            require(interactive(args), "workspace_required", "Use space NAME for a scripted workspace.")
            name = prompt("New workspace slug, for example payroll", console=console, validate=slug)
            result = client.call("spaces.create", name=name)
            result["access"] = "Only its explicitly granted readers can read imported sources. Assign employees deliberately."
        elif action in {"invites", "revoke"}:
            invitations = client.call("invites.list")
            if action == "invites":
                result = invitations
            else:
                require(interactive(args) or args.invite_id, "invitation_required", "Choose --invite-id.")
                console.result(invitations)
                ident = args.invite_id or prompt("Invitation ID to revoke", console=console,
                    validate=lambda v: require(any(x["id"] == v for x in invitations), "not_found", "Choose a listed invitation ID."))
                result = client.call("invites.revoke", invite_id=ident)
        else:
            selectable = {str(i): member for i, member in enumerate(members, 1) if not member["org_admin"]}
            require(selectable, "no_members", "Invite an employee first.")
            if interactive(args):
                for key, member in selectable.items():
                    console.option(key, member["name"], (member["username"] or member["kind"]) + (" (disabled)" if not member["active"] else ""))
            target = next((m for m in members if m["id"] == args.principal), None) if args.principal else None
            if target is None and interactive(args):
                target = selectable[prompt("Employee number", choices=list(selectable), console=console)]
            require(target and not target["org_admin"], "member_required", "Choose a non-admin --principal or listed employee.")
            if action == "reset":
                require(target["kind"] == "human", "invalid_member", "Password invitations are for human employees.")
                result = invite_employee(args, client, target)
            elif action == "disable":
                if interactive(args):
                    require(prompt("Disable " + target["name"] + " and revoke their credentials", "no", ["yes", "no"], console=console) == "yes", "setup_cancelled", "No access changed.")
                result = client.call("members.disable", principal_id=target["id"])
                result["employee"] = target["name"]
            else:
                access = choose_access(args, client, target["access"], allow_empty=True)
                names = {s["id"]: s["slug"] for s in client.call("spaces.list")}
                if interactive(args):
                    console.result({"employee": target["name"], "new_access": [{"workspace": names.get(x["space_id"], x["space_id"]), "role": x["role"]} for x in access],
                                    "document_groups_unchanged": [g["name"] for g in target["groups"]],
                                    "existing_credentials": "Revoked; employee must sign in again"})
                    require(prompt("Apply these permissions", "no", ["yes", "no"], console=console) == "yes", "setup_cancelled", "No access changed.")
                result = client.call("members.access", principal_id=target["id"], access=access, expected_revision=target["revision"])
                result["employee"] = target["name"]
                result["workspace_access"] = [names.get(x["space_id"], "restricted workspace") + ": " + x["role"] for x in access]
        if args.action or not interactive(args):
            return result
        if isinstance(result, dict) and result.get("invitation_id"):
            console.invitation_ready(result)
        elif isinstance(result, dict) and result.get("employee"):
            console.employee_ready(result)
        else:
            console.result(result)


def team_command(args, read_token):
    while True:
        try:
            return _team_command(args, read_token)
        except BrainError as error:
            if args.action or not interactive(args):
                raise
            console = Console(plain=args.plain)
            console.line("  " + error.message, accent=True)
            console.line("  Completed operations are kept; nothing is automatically submitted again.")
            if prompt("Return to the team menu", "yes", ["yes", "no"], console=console) == "no":
                return {"done": True}
