# Validation and support evidence

Use this page to judge what has been checked. For installation and daily operation, start with the [quickstart](quickstart.md). For the commands contributors run, use [testing](testing.md).

## Current engine verification

Atmet Brain 0.4.0 uses schema 2. The local suite passed 181 Python tests and 8 launcher tests; the seven-block reporting walkthrough ran with the installed engine, and all 18 Mermaid diagrams rendered. Task-report checks cover actual caller attribution, read/observe/contribute/history/publish separation, private/source audience intersections, immutable replay, stale evidence and reviews, report/source erasure, encrypted recovery replay, old-schema/backup migration and rollback on a failed migration. CLI and real local REST/MCP fixtures exercise reporting, search and skill drafts through the same core. The [tag-push release workflow](https://github.com/anashamad9/Atmet-brain/actions/runs/39867328965) passed build/archive checks, OIDC upload, public npm integrity/latest and a fresh Ubuntu install. Independent anonymous macOS arm64 pinned/unversioned installs verified task commands, schema 2, MCP and persistent runtime reuse.

The existing Host/Join, automation, source, permissions, connector and recovery regressions remain required. Live customer applications, model quality and independently verified business outcomes are outside these tests. Read the [support matrix](implementation-status.md).

## Documentation checks

The project checker checks portable links, syntax/JSON, package/runtime/changelog parity, generated OpenAPI/diagram parity and common private-data mistakes. Changed command examples are also exercised with fictional data and an installed engine; a passing link check alone does not establish that a guide works.

The setup-to-use documentation audit passed 117 CLI invocations against the installed 0.2.6 wheel outside the source checkout, plus the two fictional repository demos. It covers local setup, source ingestion and updates, workflow publication, portable skill creation, configuration, scoped credentials, file sync, history, MCP and encrypted recovery. See [testing](testing.md) for the repeatable core checks and [documentation maintenance](documentation.md) for the review procedure.

## Boundaries

Local tests and the reference API do not establish production hardening or an uptime target. Actual launchd/systemd lifecycle and before-login operation, Docker runtime, customer SSH/VPN/HTTPS ingress, live Gmail/model accounts, external named MCP clients, large-scale load and penetration testing need separate deployment validation. No real company information or paid provider was needed for the ordinary suite.

For dated earlier evidence and preparation checkpoints, see [historical release validation](release-validation.md). Keep version-by-version changes in the [changelog](../CHANGELOG.md), rather than appending release narratives to usage guides.
