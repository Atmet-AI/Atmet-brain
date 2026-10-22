# Terminal guide

Open `atmet-brain` for a welcome screen, then run `atmet-brain setup`. On a terminal, results use an indented monochrome view with optional bold emphasis and line wrapping. Redirected output remains JSON. Use `--json` to request JSON in a terminal, or `--plain` / `NO_COLOR=1` to disable styling. Imported text cannot emit terminal control characters through the human renderer. This is a command-line interface, not an AI chat application.

Global options go before the command. No model key is needed for setup or the local line extractor. Setting up a remote connection does not enable model-based extraction or send company data to a model.

## First visit

```bash
atmet-brain setup
```

The wizard asks whether to create a local Brain, prepare a company server or connect to an existing server. Creating a Brain collects a company slug, owner name and explicit department-space names. It validates the answers before provisioning. Repeating setup refuses an existing installation instead of replacing its owner credential.

For scripts:

```bash
atmet-brain --json setup --mode local --organization example-company --owner "Company owner" --spaces shared,sales
atmet-brain --json status
```

`--mode team` adds private-access instructions while keeping the server bound to loopback. Setup does not install a VPN, open firewall ports or infer/approve business procedures. Add sources and reviewed workflows through the [company walkthrough](use-for-your-company.md).

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

Connections are always selected explicitly with `--connection NAME`. A one-off `--endpoint URL --token-file FILE` is also available. There is no implicit active-company setting. Named profiles bind the verified organization/principal and store their credential privately in `~/.atmet-brain/client-tokens`. The client uses direct connections, refuses redirects and plaintext non-loopback HTTP, and bounds responses. Configure an HTTPS ingress or SSH tunnel rather than disabling these controls.

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
