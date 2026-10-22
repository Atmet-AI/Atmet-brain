# Implementation status

This repository is a working local/private-pilot alpha of Atmet Brain, version 0.2.3 (npm-only publication prepared). The 0.2.0 feature release added terminal setup/presentation, private remote CLI connections, an MCP bridge, atomic scoped team provisioning and per-user service management. The canonical database schema remains version 1. The broader product design also includes managed hosting, richer interfaces and additional providers. Those are separate development tracks.

| Capability | Evidence and scope |
| --- | --- |
| Organizations/spaces | Local provisioning, stable IDs and tested company/space isolation |
| Users and services | Scoped bearer credentials, lineage, expiry, revocation, groups and operation grants; atomic team-add with selected spaces and default 30-day expiry |
| Registry distribution | npm launcher includes the matching checksum-verified core wheel and private runtime bootstrap; npm-only OIDC build/publish workflow prepared. First npm login/upload and public install validation remain pending. No Atmet PyPI release needed. |
| Terminal setup | Guided create/connect choices, company/department setup, human TTY output and JSON for scripts; no AI onboarding interview |
| Background services | Explicit per-user launchd/systemd API and worker definitions plus controls; templates/dispatch tested, actual OS-manager lifecycle needs deployment validation |
| Source ingestion | Working UTF-8 text/Markdown/CSV/JSON capture with revisions and current audience |
| Memory learning | Working local line extractor, explicit authoritative-fact activation, observations, reviewable inference/conflict |
| Model extraction | Opt-in compatible HTTP adapter with evidence/response validation; fixture validation, no live provider benchmark |
| Policy/workflow/skill lifecycle | Working proposal/publication, optimistic revisions, schedules, retirement and rollback |
| Skills | Working text package/resource import and approved dependency-aware retrieval; no script execution |
| Search | Working permission-first lexical ranking; no semantic/vector index in this release |
| Context | Working bounded approved/reference separation and source/artifact manifest |
| History | Working artifact effective/known time lookup and retained source versions; no universal historical state replay |
| REST and remote CLI | Local HTTP adapter; named HTTPS/SSH-loopback client connections with identity pinning, private credential files, CA validation and no redirects; real loopback HTTP/TLS tests; no production gateway or SSO |
| MCP | Local stdio and stdio-to-REST remote bridge with subprocess/revocation tests; generated client configuration; no remote MCP HTTP/OAuth transport or named-client certification |
| File connector | Working bounded POSIX selected-directory sync, changes, omissions and tombstones |
| Gmail | Read-only selected-label adapter with fixture tests; no live account validation or token refresh |
| Discovery | Working sequence drafts from explicit case-linked events; no general semantic process mining |
| Repeated-task scripts | Working observed-run grouping, template inference, pending Python recipes, reviewed publication and current-permission/version routing for record normalization and grouped decimal totals; no arbitrary code generation/runtime or scheduler |
| Graph | Permissioned JSON nodes/edges; no graphical editor |
| Backups | Working encrypted bounded snapshots, integrity checks, journal replay and quarantined restore tests |
| Hosted platform | Separate future application |
| Playground | Separate future coding-agent application |
| Recording ingestion | Text transcripts can be sources; video/audio transcription is not implemented |

## Release evidence

See [validation](validation.md) for commands and the exact locally validated scope. CI configuration is included, but a local pass does not mean a remote GitHub Actions run has occurred. Provider adapters use fixtures in tests and do not contact paid APIs or real mailboxes.

The project contains runnable implementation and a larger documented target. Read the table before depending on a feature. Tagged source releases are published in the repository; package-index distribution and hosted service availability are separate.
