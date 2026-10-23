# Validation and support evidence

Use this page to judge what has been checked. For installation and daily operation, start with the [quickstart](quickstart.md). For the commands contributors run, use [testing](testing.md).

## Current engine verification

Atmet Brain 0.5.0 uses schema 2. The local suite passed 202 Python tests and 8 launcher tests. Its 21 completion-feedback regressions cover automatic local/real remote Python hooks, CLI stdin/file delivery, MCP opt-in instructions, reporter identity, separate publisher authority, private/inherited/source audiences, partial failures, concurrent and ambiguous retries, revocation and erasure. Host task exceptions retain their original behavior while reports omit raw error details. Existing source/skill/backup/migration/SSH/Host/Join tests remain in the full suite.

The packed npm archive installed in a fresh anonymous macOS arm64 environment, reused its matching runtime, generated clean MCP protocol output and retained a valid service interpreter. The automatic-feedback guide's two Python examples, reporter provisioning, installed MCP config/subprocess, stdin callback and separate publisher approval passed with fictional data outside the source checkout. All 19 Mermaid diagrams rendered. Public registry publication is a separate check; this local evidence alone does not establish it.

The existing Host/Join, automation, source, permissions, connector and recovery regressions remain required. Live customer applications, model quality and independently verified business outcomes are outside these tests. Read the [support matrix](implementation-status.md).

## Documentation checks

The project checker checks portable links, syntax/JSON, package/runtime/changelog parity, generated OpenAPI/diagram parity and common private-data mistakes. Changed command examples are also exercised with fictional data and an installed engine; a passing link check alone does not establish that a guide works.

The setup-to-use documentation audit passed 117 CLI invocations against the installed 0.2.6 wheel outside the source checkout, plus the two fictional repository demos. It covers local setup, source ingestion and updates, workflow publication, portable skill creation, configuration, scoped credentials, file sync, history, MCP and encrypted recovery. See [testing](testing.md) for the repeatable core checks and [documentation maintenance](documentation.md) for the review procedure.

## Boundaries

Local tests and the reference API do not establish production hardening or an uptime target. Actual launchd/systemd lifecycle and before-login operation, Docker runtime, customer SSH/VPN/HTTPS ingress, live Gmail/model accounts, external named MCP clients, large-scale load and penetration testing need separate deployment validation. No real company information or paid provider was needed for the ordinary suite.

For dated earlier evidence and preparation checkpoints, see [historical release validation](release-validation.md). Keep version-by-version changes in the [changelog](../CHANGELOG.md), rather than appending release narratives to usage guides.
