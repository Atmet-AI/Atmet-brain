# Terminal guide

Open `atmet-brain` for a welcome screen, then run `atmet-brain setup`. On a supported color terminal, welcome and interactive setup show a large orange pixel wordmark, clear setup choices and spaced next steps. Other commands use a compact orange header and wrapped results. Narrow terminals, plain mode, unsupported encodings and terminals without color use a compact title. Redirected output remains JSON. Use `--json` to request JSON in a terminal, or `--plain` / `NO_COLOR=1` to disable styling. Imported text cannot emit terminal control characters through the human renderer. This is a command-line interface, not an AI chat application.

For unstyled output, use `atmet-brain --plain status`. For machine-readable output, use `atmet-brain --json status`. Setup prompts go to stderr so redirected stdout remains JSON.

Global options go before the command. No model key is needed for setup or the local line extractor. Setting up a remote connection does not enable model-based extraction or send company data to a model.

## Company chooser, login and employees

Run brains for a guided company chooser; brains create NAME creates an independent data home, and brains add NAME --path HOME registers existing data. Use --brain NAME explicitly before other commands. Each company has separate accounts, data and backups; concurrent servers need different ports. Run account setup once for the owner, login to sign in, and team for employee invitations and per-workspace access. Employee enrollment happens through join with a private single-use invitation. [Full account walkthrough](employee-accounts.md).

Recoverable input errors re-prompt the relevant field. Type /cancel to cancel the current operation. The interactive team menu can continue after a cancelled/failed action without automatically resubmitting it. Invalid login passwords can be retried without re-entering company details. EOF/Ctrl+C and deliberate completion return to the shell; the Terminal app stays open. Security failures, uncertain remote writes and partial saves are reported rather than replayed automatically.

## Connect an agent

Run `atmet-brain agent` after setup, or choose Join within it for a company Brain. The guided flow offers method, permitted workspace names, read/learning access and a separate or narrowed identity. It shows a review, verifies the new credential and presents copyable MCP configuration or method-specific commands. The bundle stays private; existing files are not overwritten. Use `--json agent` with explicit flags for automation. [Full wizard guide](agent-setup.md).

## First visit

```bash
atmet-brain setup
```

The wizard offers local, Host and Join. Local creates a fresh private Brain. Host creates or reuses a company Brain, selects a secure route and prepares scoped teammate access. Join consumes a password invitation and verifies the account, or imports an explicitly legacy credential file. If Local finds an existing Brain, it offers reuse, a separate new data folder, or cancellation before company questions. Reuse keeps its company, owner, workspaces and data. Host reuses it without replacing its owner credential. Non-interactive Local without creation flags reuses the current Brain; creation flags against an existing Brain stop early with instructions.

To add a department to an existing Brain, use `atmet-brain space marketing`; company setup is not repeated. A separate company can use `atmet-brain --home /private/another-company setup`. Choose a fresh private home outside source control. Generated next commands include the selected home and installed Python runtime.

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

Run Host on the company device and Join on each teammate's device. Host lets you select workspace names, a role and a private invitation output file, then offers explicit background service installation. Join displays the file's destination, checks actual server identity and lists permitted spaces. Automatic SSH connections manage forwarding per request; HTTPS uses existing trusted ingress. The company administrator must prepare SSH accounts/keys/known hosts or HTTPS ingress first. Choose the Host route `later` to stop before networking/member setup.

For scripts use `host --transport https --endpoint https://brain.example.com --member "Sales employee" --member-spaces sales --output /private/sales.atmet-join.json`, then `join --file /private/sales.atmet-join.json` on the teammate's device. Add organization/spaces flags only for a new Brain. Private invitation files contain single-use enrollment secrets; legacy credential files remain reusable. Transfer either privately. See the [full Host/Join guide](team-server.md#guided-host-and-join).

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

Supported remote commands: `status`, `space`, `principal`, `grant`, `token`, `team-add`, `ingest`, `search`, `context`, `propose`, `review`, `sync`, `task-report`, `task-complete`, `task-history`, `task-get`, `task-learn`, `task-erase`, `rpc` and `mcp`. File ingestion uploads the explicitly selected local text file to the server. Installation-owner operations, skill-directory import, connector registration, services, backups, recovery and workers remain local. Unsupported remote commands fail instead of opening a local database.

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

## Task reports and skill learning

Use task-report FILE --space SPACE_ID to submit a selected outcome, task-history QUERY --space SPACE_ID to search permitted reports, task-get REPORT_ID to inspect one and task-learn to create a pending skill. task-erase requires separate erase/history access. These commands also work with --connection NAME. The [complete walkthrough](task-history-and-learning.md) explains report JSON, source evidence, permissions and separate publication.

MCP configuration accepts --allow-task-reports, --allow-proposals and --allow-automations to expose selected tool groups. Underlying grants remain required; reporting and learning expose no publication tool.

For agent completion hooks, use `task-complete FILE --space SPACE_ID` or `task-complete - --space SPACE_ID` with JSON on stdin. It saves the report and attempts an eligible skill draft, returning both statuses. `mcp-config --task-feedback` configures completion instructions/tool access. Both support named remote connections; neither publishes a skill. [Automatic setup and host integration](automatic-task-feedback.md).
