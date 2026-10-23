# Validation and support evidence

Use this page to judge what has been checked. For installation and daily operation, start with the [quickstart](quickstart.md). For the commands contributors run, use [testing](testing.md).

## Current engine verification

Atmet Brain 0.6.0 uses schema 2. The local suite passed 228 Python tests and 8 launcher tests. Its 26 agent-setup regressions cover actual core scope preflight, local/shared/Join routes, narrowed service/child identities, expiry and parent revocation, cancellation, private files, partial-failure revocation and explicit token-file precedence over ambient owner credentials. Existing source, skill, reporting, recovery, migration, SSH and Host/Join checks remain in the full suite.

A fresh anonymous macOS arm64 npm archive installation passed. Its installed engine exercised all four generated bundles, executed Python and MCP examples, retained Sales-only access under an ambient owner token, recorded a pending skill and required a separate publisher. The guided wizard ran through a real pseudo-terminal; all 25 diagrams rendered. External agent application settings and real business outcomes are separate acceptance checks. Public distribution is checked independently by the release workflow.

The existing Host/Join, automation, source, permissions, connector and recovery regressions remain required. Live customer applications, model quality and independently verified business outcomes are outside these tests. Read the [support matrix](implementation-status.md).

## Documentation checks

The from-scratch README walkthrough was exercised against the public installed 0.5.0 engine outside the source checkout: 17 Bash blocks cover first-company source/workflow setup, existing-project reference import, scoped identities, actual generated MCP feedback, separate publication, selected-directory updates, history and encrypted backup/journal. The original project memory stayed unchanged and Brain/credential files stayed outside it. Its 24 repository Mermaid diagrams rendered; README fragment links were checked. Named-client UI and real company deployments are separate checks.

The project checker checks portable links, syntax/JSON, package/runtime/changelog parity, generated OpenAPI/diagram parity and common private-data mistakes. Changed command examples are also exercised with fictional data and an installed engine; a passing link check alone does not establish that a guide works.

The setup-to-use documentation audit passed 117 CLI invocations against the installed 0.2.6 wheel outside the source checkout, plus the two fictional repository demos. It covers local setup, source ingestion and updates, workflow publication, portable skill creation, configuration, scoped credentials, file sync, history, MCP and encrypted recovery. See [testing](testing.md) for the repeatable core checks and [documentation maintenance](documentation.md) for the review procedure.

## Boundaries

Local tests and the reference API do not establish production hardening or an uptime target. Actual launchd/systemd lifecycle and before-login operation, Docker runtime, customer SSH/VPN/HTTPS ingress, live Gmail/model accounts, external named MCP clients, large-scale load and penetration testing need separate deployment validation. No real company information or paid provider was needed for the ordinary suite.

For dated earlier evidence and preparation checkpoints, see [historical release validation](release-validation.md). Keep version-by-version changes in the [changelog](../CHANGELOG.md), rather than appending release narratives to usage guides.
