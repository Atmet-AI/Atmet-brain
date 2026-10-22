# Atmet Brain launcher

The terminal entry point for the open-source Atmet Brain Python engine. This package is prepared for its first npm publication; the short commands are not available until this package is published by the maintainer. Only an npm account is needed for publication; the core wheel is included.

After official publication, with Node.js 22.14 or newer and npm installed:

```bash
npx atmet-brain setup
```

Or install the command for regular use:

```bash
npm install --global atmet-brain
atmet-brain setup
atmet-brain status
```

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

Save the company connection first using the core's `connect` command. Each user/agent needs individual scoped access. No company data is uploaded by merely installing this launcher.

Automatic bootstrap targets macOS and glibc Linux, x64/arm64. Runtime tests have local macOS arm64 and Linux CI coverage; the other archive targets need deployment checks. Windows is not validated. On other Linux libc variants, an administrator can select a compatible uv with `ATMET_UV_BIN`; core support still needs evaluation.

[Usage and installation](https://github.com/anashamad9/Atmet-brain/blob/main/docs/install.md) | [Account publication setup](https://github.com/anashamad9/Atmet-brain/blob/main/docs/package-publishing.md) | [Apache 2.0](LICENSE)
