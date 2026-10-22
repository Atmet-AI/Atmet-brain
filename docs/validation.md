# Validation and support evidence

Use this page to judge what has been checked. For installation and daily operation, start with the [quickstart](quickstart.md). For the commands contributors run, use [testing](testing.md).

## Current published engine

Atmet Brain 0.2.6 has the following observed release evidence:

| Check | Result and scope |
| --- | --- |
| Core suite | 139 Python tests passed in the release workflow on Python 3.12 |
| npm launcher | 8 Node tests plus wheel/tarball identity, content and digest checks passed |
| Public distribution | GitHub OIDC upload, npm provenance metadata, exact public archive integrity and latest checks passed |
| Ubuntu install | Fresh public CLI installation passed in the release workflow |
| macOS arm64 install | Fresh anonymous pinned/unversioned setup, private credential output, MCP initialize/tools-list, runtime reuse and persistent service interpreter checks passed |
| API and MCP | Regression coverage includes real loopback HTTP/TLS and stdio subprocesses |
| Providers | Gmail/model request handling uses fixtures; no live provider certification |

[Release workflow](https://github.com/anashamad9/Atmet-brain/actions/runs/39830420887) and [versioned assets](https://github.com/anashamad9/Atmet-brain/releases/tag/v0.2.6) identify that release. Read the [support matrix](implementation-status.md) before relying on a capability.

## Documentation checks

The project checker checks portable links, syntax/JSON, package/runtime/changelog parity, generated OpenAPI/diagram parity and common private-data mistakes. Changed command examples are also exercised with fictional data and an installed engine; a passing link check alone does not establish that a guide works.

The setup-to-use documentation audit passed 117 CLI invocations against the installed 0.2.6 wheel outside the source checkout, plus the two fictional repository demos. It covers local setup, source ingestion and updates, workflow publication, portable skill creation, configuration, scoped credentials, file sync, history, MCP and encrypted recovery. See [testing](testing.md) for the repeatable core checks and [documentation maintenance](documentation.md) for the review procedure.

## Boundaries

Local tests and the reference API do not establish production hardening or an uptime target. Actual launchd/systemd lifecycle and before-login operation, Docker runtime, private SSH/VPN/HTTPS ingress, live Gmail/model accounts, external named MCP clients, large-scale load and penetration testing need separate deployment validation. No real company information or paid provider was needed for the ordinary suite.

For dated earlier evidence and preparation checkpoints, see [historical release validation](release-validation.md). Keep version-by-version changes in the [changelog](../CHANGELOG.md), rather than appending release narratives to usage guides.
