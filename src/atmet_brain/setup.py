"""Guided first use. Setup records explicit answers, not inferred business policy."""

import sys
import shlex

from .errors import require
from .terminal import Console, prompt
from .util import slug, text


def guided_setup(args, initialize, connect_remote):
    interactive = sys.stdin.isatty() and not args.json
    console = Console(plain=args.plain)
    if interactive:
        console.banner("Let's connect your company's context.")
    mode = args.mode
    if not mode:
        require(interactive, "setup_answers_required", "Use setup --mode local|team|connect and the required flags when input is not interactive.")
        console.line("  local   Create a Brain for this device")
        console.line("  team    Create a company Brain with private team access guidance")
        console.line("  connect Connect this client to an existing Brain")
        mode = prompt("Choose a setup", "local", ["local", "team", "connect"])
    if mode == "connect":
        name = args.name or (prompt("Connection name", "company") if interactive else None)
        endpoint = args.endpoint or (prompt("Brain URL, HTTPS or SSH loopback") if interactive else None)
        token_file = args.token_file or (prompt("Path to your individual credential file") if interactive else None)
        require(name and endpoint and token_file, "setup_answers_required", "Connect setup needs --name, --endpoint and --token-file.")
        return connect_remote(name, endpoint, token_file, args.ca_file)
    organization = args.organization or (prompt("Company slug", "my-company") if interactive else None)
    require(organization, "setup_answers_required", "Local setup needs --organization.")
    organization = slug(organization)
    owner = args.owner or (prompt("Your name", "Company owner") if interactive else "Company owner")
    text(owner, maximum=120)
    spaces = args.spaces
    if spaces is None:
        spaces = prompt("Department spaces, separated by commas", "shared,sales") if interactive else "shared"
    spaces = [slug(value.strip()) for value in spaces.split(",") if value.strip()]
    require(0 < len(spaces) <= 30 and len(set(spaces)) == len(spaces), "invalid_spaces", "Choose 1 to 30 distinct space slugs.")
    # Collect and validate every answer before initializing the installation.
    result = initialize(organization, owner, spaces)
    result["access"] = "Loopback only. Team setup does not expose a network port."
    base = ["atmet-brain", "--home", str(args.home.expanduser().resolve())]
    result["next"] = [shlex.join(base + command) for command in [["serve"], ["status"], ["service", "install", "--start"]]]
    if mode == "team":
        result["team"] = ["Create an individual scoped credential with team-add.",
                          "Keep the server on loopback and use restricted SSH forwarding, or configure trusted private HTTPS ingress.",
                          "Each client runs connect, then uses --connection NAME for CLI or MCP.",
                          "The server device must remain awake and connected. Guide: https://github.com/anashamad9/Atmet-brain/blob/main/docs/team-server.md"]
    result["learning"] = "Add selected sources and reviewed workflows next. Setup does not infer or approve business rules."
    return result
