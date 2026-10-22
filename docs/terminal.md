# Terminal guide

Open `atmet-brain` for a welcome screen, then run `atmet-brain setup`. On a supported color terminal, welcome and interactive setup show a large orange pixel wordmark, clear setup choices and spaced next steps. Other commands use a compact orange header and wrapped results. Narrow terminals, plain mode, unsupported encodings and terminals without color use a compact title. Redirected output remains JSON. Use `--json` to request JSON in a terminal, or `--plain` / `NO_COLOR=1` to disable styling. Imported text cannot emit terminal control characters through the human renderer. This is a command-line interface, not an AI chat application.

For unstyled output, use `atmet-brain --plain status`. For machine-readable output, use `atmet-brain --json status`. Setup prompts go to stderr so redirected stdout remains JSON.

Global options go before the command. No model key is needed for setup or the local line extractor. Setting up a remote connection does not enable model-based extraction or send company data to a model.

## First visit

```bash
atmet-brain setup
```

The wizard offers local, Host and Join. Local creates a fresh private Brain. Host creates or reuses a company Brain, selects a secure route and prepares scoped teammate access. Join imports a private connection file and verifies it against the server. Local initialization still refuses an existing installation; Host reuses it without replacing its owner credential.

For scripts:

```bash
atmet-brain --json setup --mode local --organization example-company --owner "Company owner" --spaces shared,sales
atmet-brain --json status
```

## Host and Join a team

```bash
atmet-brain host
atmet-brain join
```

Run Host on the company device and Join on each teammate's device. Host lets you select workspace names, role and a private output file, then offers explicit background service installation. Join displays the file's destination, checks actual server identity and lists permitted spaces. Automatic SSH connections manage forwarding per request; HTTPS uses existing trusted ingress. The company administrator must prepare SSH accounts/keys/known hosts or HTTPS ingress first. Choose the Host route `later` to stop before networking/member setup.

For scripts use `host --transport https --endpoint https://brain.example.com --member "Sales employee" --member-spaces sales --output /private/sales.atmet-join.json`, then `join --file /private/sales.atmet-join.json` on the teammate's device. Add organization/spaces flags only for a new Brain. Connection files contain scoped credentials and must be transferred privately. See the [full Host/Join guide](team-server.md#guided-host-and-join).

`setup --mode host|join` supports the same flows; `--mode team` aliases Host. Setup does not install a VPN, open firewall ports or infer/approve business procedures. Add sources and reviewed workflows through the [company walkthrough](use-for-your-company.md).

## Common tasks

```bash
atmet-brain space
atmet-brain space finance
atmet-brain ingest company.md --space SPACE_ID
atmet-brain worker --space SPACE_ID
atmet-brain context "Prepare a quotation" --space SPACE_ID
atmet-brain serve
```

`serve` stays in the foreground. Ctrl+C stops it. `worker` drains pending jobs once unless `--loop` is selected. Connector synchronization is a separate explicit command; a server process alone does not continuously sync every app.

## Remote client

Obtain an individual credential through your administrator and protect its file:

```bash
atmet-brain connect company --endpoint https://brain.example.com --token-file /private/employee.token
atmet-brain --connection company status
atmet-brain --connection company space
atmet-brain --connection company context "Prepare a quotation" --space SPACE_ID
atmet-brain connections list
```

Alternatively, `atmet-brain setup --mode connect` guides those choices. Non-interactive connect setup accepts `--name`, `--endpoint` and `--token-file` after `setup`. An explicitly trusted private CA can be supplied with `--ca-file`. Certificate/hostname validation cannot be disabled.

Supported remote commands: `status`, `space`, `principal`, `grant`, `token`, `team-add`, `ingest`, `search`, `context`, `propose`, `review`, `sync`, `rpc` and `mcp`. File ingestion uploads the explicitly selected local text file to the server. Installation-owner operations, skill-directory import, connector registration, services, backups, recovery and workers remain local. Unsupported remote commands fail instead of opening a local database.

Connections are always selected explicitly with `--connection NAME`. A one-off `--endpoint URL --token-file FILE` is also available. There is no implicit active-company setting. Named profiles bind the verified organization/principal and store their credential privately in `~/.atmet-brain/client-tokens`. The client uses direct connections, refuses redirects and plaintext non-loopback HTTP, and bounds responses. Use Join with an automatic SSH connection file or configure trusted HTTPS ingress. Legacy loopback profiles can still use a manually managed SSH tunnel. Keep verification enabled.

```bash
atmet-brain connections remove company
```

Removal deletes the local saved profile and copied token. It does not revoke the server credential; an administrator must revoke it separately. Connection profiles and their raw token files are device-specific and outside the canonical database backup. New recovery credentials must be distributed and connected again after restoration.

## Connect your agent

```bash
atmet-brain --json --connection company mcp-config
atmet-brain --connection company mcp
```

`mcp-config` prints an MCP client configuration using the current Python executable, absolute data home and connection name. For local use, supply a dedicated scoped `--token-file`. Adapt the JSON to your client's configuration format. A persistent installation is preferable to a temporary uvx environment for saved service/client commands.

MCP stdout contains only protocol messages, even in a terminal. The remote bridge runs locally and forwards operations to the authenticated REST service; it does not implement a remote MCP HTTP/OAuth endpoint. [MCP details](mcp.md).
