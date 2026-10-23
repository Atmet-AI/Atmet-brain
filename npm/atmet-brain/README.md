# Atmet Brain launcher

The terminal entry point for the open-source Atmet Brain Python engine. The matching core wheel is included in this npm package. No Atmet PyPI release or account is needed.

With Node.js 22.14 or newer and npm installed:

```bash
npx atmet-brain@latest setup
```

Or install the command for regular use:

```bash
npm install --global atmet-brain
atmet-brain setup
atmet-brain status
```

The interactive welcome and setup use a large orange wordmark with compact layouts on narrow terminals. Use `--plain` or `NO_COLOR=1` to disable styling; redirected JSON and MCP remain free of display decoration.

## What happens

On first execution, the launcher downloads the pinned official uv runtime, verifies its archive SHA-256, then verifies and installs the exact matching `atmet-brain` wheel included in this npm archive in an isolated Python 3.12 tool environment. uv can obtain Python when needed. No manual Python/uv install, repository clone, sudo or shell startup-file changes are required. macOS/Linux need the standard `tar` utility for automatic uv extraction. The npm package has no JavaScript dependencies or postinstall hooks. The Python core declares dependencies such as `cryptography`, downloaded from the public Python index when needed. No Atmet PyPI release/account is required; this is not a fully offline installer.

Subsequent launches reuse that version's runtime. The launcher does not supply a second memory engine or fall back to downloading Atmet wheels from GitHub. The uv/Python runtime bootstrap uses upstream distribution infrastructure; package installation needs network access. Brain processing/provider data flows are configured separately.

## Runtime and company data

- macOS runtime: `~/Library/Application Support/atmet-brain/runtime`.
- Linux runtime: `$XDG_DATA_HOME/atmet-brain/runtime`, or `~/.local/share/atmet-brain/runtime`.
- Company data: the core's separate `~/.atmet-brain` home, or an explicit `--home` / `ATMET_HOME`.
- `ATMET_LAUNCHER_HOME`: an absolute directory overriding managed runtime storage.
- `ATMET_UV_BIN`: optional absolute path to an administrator-selected trusted uv executable. This is local operator configuration, not a model argument.

Keep the runtime directory available while its background services or saved MCP configurations use its Python executable. Removing/upgrading the npm launcher does not delete company data. Different launcher versions keep separate tool environments and share the explicitly selected company data; read schema/recovery notes before changing engine versions.

The launcher ignores ambient uv/pip project/index configuration for its engine install and uses the official PyPI index for third-party Python dependencies only. Its core is always the checksum-verified wheel included in the npm archive. Brain credentials/provider settings still reach the core through its normal environment. Managed runtime files are protected by user filesystem permissions; this is not protection from a compromised host administrator.

## Agents and remote teams

All core arguments are forwarded literally. Bootstrap messages go to stderr; MCP stdout remains protocol-only.

```bash
npx atmet-brain --connection company mcp
```

On the company device run `npx atmet-brain@latest host`. It creates or reuses the Brain and prepares a private scoped connection file for each teammate. On their device run `npx atmet-brain@latest join` and choose that file. Join checks the real server identity and lists allowed workspaces. Treat the invitation as private, expiring enrollment material. Explicit legacy bearer connection files remain supported and reusable.

SSH connections manage their own forwarding per request after an administrator configures the forwarding-only account, SSH keys and trusted host key. HTTPS uses existing company ingress. The wizard does not configure OS accounts, firewall rules or certificates. The manual `connect` command remains available. Each user/agent needs individual scoped access. No company data is uploaded by merely installing this launcher. [Host and Join](https://github.com/Atmet-AI/Atmet-brain/blob/main/docs/team-server.md).

Automatic bootstrap targets macOS and glibc Linux, x64/arm64. Runtime tests have local macOS arm64 and Linux CI coverage; the other archive targets need deployment checks. Windows is not validated. On other Linux libc variants, an administrator can select a compatible uv with `ATMET_UV_BIN`; core support still needs evaluation.

[Usage and installation](https://github.com/Atmet-AI/Atmet-brain/blob/main/docs/install.md) | [Account publication setup](https://github.com/Atmet-AI/Atmet-brain/blob/main/docs/package-publishing.md) | [Apache 2.0](LICENSE)

## Task outcomes and reusable skills

Use task-report to save selected outcomes with original source evidence, task-history/task-get to inspect permitted history and task-learn to create a pending skill from reported steps/corrections. History requires explicit grants; reports default private and never become approved company rules automatically. [Complete walkthrough](https://github.com/Atmet-AI/Atmet-brain/blob/main/docs/task-history-and-learning.md).

Current engine 0.10.0 upgrades supported schema-1/2/3 data transactionally to schema 4. Use the guided update below before opening existing data; its manual fallback uses the old compatible engine for backup. Older engines cannot open schema 4. [Upgrade and recovery](https://github.com/Atmet-AI/Atmet-brain/blob/main/docs/versioning.md#schema-4-upgrade).

## Automatic agent feedback

Configure `mcp-config --task-feedback` with a scoped reporter credential, or send selected completion JSON through `task-complete - --space SPACE_ID` from your agent application's lifecycle hook. Eligible results create pending skill candidates; a publisher approves the exact revision. MCP completion instructions require client cooperation and do not monitor unrelated agents. [One-time setup and Python/REST hooks](https://github.com/Atmet-AI/Atmet-brain/blob/main/docs/automatic-task-feedback.md).

## Guided agent connection

Run `npx atmet-brain@latest agent`. Choose the Brain, connection method, workspace names and read-only or learning access. The wizard creates/verifies scoped access, displays a copyable MCP entry and saves private next-step files. Add that configuration to the app and test it there; no application settings, API services or host task hooks are installed automatically. [Agent setup](https://github.com/Atmet-AI/Atmet-brain/blob/main/docs/agent-setup.md).

## Employee logins and several companies

Use brains create COMPANY for independent company data homes, then --brain COMPANY account setup, login, host and team. The terminal team editor selects each employee's workspaces and a role in each; omitted payroll access stays denied. Employees consume a private invitation with join, choose a password privately and use their named connection with login, logout or agent. Passwords are never saved by the client. Sessions expire and permission changes require a new sign-in. Invalid wizard fields retry in place; /cancel cancels the current operation.

This adds local password accounts and single-use invitations, not SSO/MFA, email verification or a global company-number resolver. Each company needs its own backup and server port. [Complete walkthrough](https://github.com/Atmet-AI/Atmet-brain/blob/main/docs/employee-accounts.md).

## Manage company changes through your agent

Run npx atmet-brain@latest --brain COMPANY admin agent --name company-assistant to prepare an administration MCP entry. Your external agent translates requests into pending changes; you use admin review CHANGE_ID in your human session and enter the password privately. New/changed documents stay in restricted intake until an approved explicit rule or human classification releases them. admin classify SOURCE_ID guides manual onboarding. Reader/User/Editor are everyday presets; company administration stays separate. [Full guide](https://github.com/Atmet-AI/Atmet-brain/blob/main/docs/conversational-administration.md).

## Update an existing company Brain

```bash
npx atmet-brain@latest update
```

On the Brain host, choose your existing company, close its agents/external processes and approve the plan. The wizard saves and verifies an encrypted pre-migration backup plus journal with a separate key, opens the same data home, verifies retained records/permissions and refreshes unchanged Atmet-managed services. Reconnect saved MCP entries afterward. Multiple companies update separately; remote employees update their launcher separately. A global shortcut still needs npm install --global atmet-brain@latest. [Prompts, backups and failure recovery](https://github.com/Atmet-AI/Atmet-brain/blob/main/docs/upgrading.md).
