# Validation and support evidence

Use this page to judge what has been checked. For installation and daily operation, start with the [quickstart](quickstart.md). For the commands contributors run, use [testing](testing.md).

## Current engine verification

Atmet Brain 0.3.1 uses schema 1. The local release checks cover 155 Python regressions and 8 Node launcher tests. The Host/Join tests exercise real loopback HTTPS, private connection files, scope/identity checks, expiry/revocation, malformed inputs and SSH failure/cleanup, including rejection of port readiness without an SSH-owned listener. The version-tag release workflow also passed build/archive checks, GitHub OIDC publication, exact public npm integrity/latest verification and a fresh Ubuntu CLI installation. [Verified workflow](https://github.com/anashamad9/Atmet-brain/actions/runs/39859008158) identifies this release.

A disposable macOS arm64 integration exercised real OpenSSH forwarding with temporary host/member keys and a loopback-only SSH daemon, joining Sales, denying Finance, rejecting an unknown host key and enforcing revocation. No system SSH configuration was changed. This is an isolated integration check, not a customer-network deployment assessment.

Read the [support matrix](implementation-status.md) before relying on a capability. Older release evidence is preserved in [historical validation](release-validation.md).

## Documentation checks

The project checker checks portable links, syntax/JSON, package/runtime/changelog parity, generated OpenAPI/diagram parity and common private-data mistakes. Changed command examples are also exercised with fictional data and an installed engine; a passing link check alone does not establish that a guide works.

The setup-to-use documentation audit passed 117 CLI invocations against the installed 0.2.6 wheel outside the source checkout, plus the two fictional repository demos. It covers local setup, source ingestion and updates, workflow publication, portable skill creation, configuration, scoped credentials, file sync, history, MCP and encrypted recovery. See [testing](testing.md) for the repeatable core checks and [documentation maintenance](documentation.md) for the review procedure.

## Boundaries

Local tests and the reference API do not establish production hardening or an uptime target. Actual launchd/systemd lifecycle and before-login operation, Docker runtime, customer SSH/VPN/HTTPS ingress, live Gmail/model accounts, external named MCP clients, large-scale load and penetration testing need separate deployment validation. No real company information or paid provider was needed for the ordinary suite.

For dated earlier evidence and preparation checkpoints, see [historical release validation](release-validation.md). Keep version-by-version changes in the [changelog](../CHANGELOG.md), rather than appending release narratives to usage guides.
