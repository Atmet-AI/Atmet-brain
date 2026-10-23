# Validation and support evidence

Use this page to judge what has been checked. For installation and daily operation, start with the [quickstart](quickstart.md). For the commands contributors run, use [testing](testing.md).

## Current engine verification

Atmet Brain 0.7.0 uses schema 3. The suite passed 292 Python tests and 8 launcher tests. Its 57 account/UI/company regressions cover one-time enrollment and concurrency, username/company isolation, password verifiers, persisted attempt limits, session expiry/logout, per-space role isolation, payroll audiences, exact membership reviews, password change/reset/disable, group removal, local owner recovery and schema/backup quarantine. Actual loopback HTTP/TLS and CLI subprocesses exercise the interfaces; redirects cannot forward passwords and forged caller/role fields cannot grant access.

Interactive tests check invalid SSH/slug/workspace input recovery, team-menu cancellation, private password/session state and explicit independent company homes. Existing memory/source/workflow/automation/reporting/skill/recovery/MCP checks remain in the suite. A fresh packed npm installation and actual installed pseudo-terminal/TLS walkthrough verified owner login, single-use employee enrollment, per-workspace review, general-finance access with payroll denied, revocation of an already initialized MCP child, fresh sign-in, separate skill approval and two company homes. Installed 0.6.1 schema-2 data and encrypted backup upgraded to schema 3; restored sources stayed quarantined and old credentials remained revoked. The old engine rejected schema 3. All 27 diagrams rendered. Public distribution is verified independently by the release workflow. No external identity provider, paid account, customer deployment or production security audit is implied.

## Documentation checks

The from-scratch README walkthrough was exercised against the public installed 0.5.0 engine outside the source checkout: 17 Bash blocks cover first-company source/workflow setup, existing-project reference import, scoped identities, actual generated MCP feedback, separate publication, selected-directory updates, history and encrypted backup/journal. The original project memory stayed unchanged and Brain/credential files stayed outside it. Its 24 repository Mermaid diagrams rendered; README fragment links were checked. Named-client UI and real company deployments are separate checks.

The project checker checks portable links, syntax/JSON, package/runtime/changelog parity, generated OpenAPI/diagram parity and common private-data mistakes. Changed command examples are also exercised with fictional data and an installed engine; a passing link check alone does not establish that a guide works.

The setup-to-use documentation audit passed 117 CLI invocations against the installed 0.2.6 wheel outside the source checkout, plus the two fictional repository demos. It covers local setup, source ingestion and updates, workflow publication, portable skill creation, configuration, scoped credentials, file sync, history, MCP and encrypted recovery. See [testing](testing.md) for the repeatable core checks and [documentation maintenance](documentation.md) for the review procedure.

## Boundaries

Local tests and the reference API do not establish production hardening or an uptime target. Actual launchd/systemd lifecycle and before-login operation, Docker runtime, customer SSH/VPN/HTTPS ingress, live Gmail/model accounts, external named MCP clients, large-scale load and penetration testing need separate deployment validation. No real company information or paid provider was needed for the ordinary suite.

For dated earlier evidence and preparation checkpoints, see [historical release validation](release-validation.md). Keep version-by-version changes in the [changelog](../CHANGELOG.md), rather than appending release narratives to usage guides.
