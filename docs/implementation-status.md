# Implementation status

Atmet Brain 0.4.0 is a local/private-pilot alpha using database schema 2. Use this table to choose supported operations and identify features needing additional validation. Follow [installation](install.md) and the [company walkthrough](use-for-your-company.md) to use the core.

| Capability | Evidence and scope |
| --- | --- |
| Organizations/spaces | Local provisioning, stable IDs and tested company/space isolation |
| Users and services | Scoped bearer credentials, lineage, expiry, revocation, groups and operation grants; atomic team-add with selected spaces and default 30-day expiry |
| Registry distribution | npm includes the matching checksum-verified Python core and isolated runtime bootstrap; public Ubuntu CLI and anonymous macOS arm64 setup/MCP checks passed. See [installation](install.md) and [validation](validation.md). |
| Terminal setup | Guided Local/Host/Join, existing-Brain reuse, workspace-name member selection, private scoped connection files, server identity/scope verification and explicit service-start option; orange/plain/JSON presentation; no AI onboarding interview |
| Background services | Explicit per-user launchd/systemd API and worker definitions plus controls; templates/dispatch tested, actual OS-manager lifecycle needs deployment validation |
| Source ingestion | Working UTF-8 text/Markdown/CSV/JSON capture with revisions and current audience |
| Memory learning | Working local line extractor, explicit authoritative-fact activation, observations, reviewable inference/conflict |
| Model extraction | Opt-in compatible HTTP adapter with evidence/response validation; fixture validation, no live provider benchmark |
| Policy/workflow/skill lifecycle | Working proposal/publication, optimistic revisions, schedules, retirement and rollback |
| Skills | Text package/resource import, dependency-aware retrieval and explicit task-outcome skill drafts; exact-revision publication remains separate; no script execution |
| Task reports/history | Explicit authenticated reports, default-private audiences, permission-first lexical history, reported steps/corrections and separate skill drafts; no automatic external transcript capture or independent outcome verification |
| Schema upgrades | Transactional schema-1 to schema-2 migration and old-backup upgrade before quarantine; older engines cannot open schema 2 |
| Search | Working permission-first lexical ranking; no semantic/vector index in this release |
| Context | Working bounded approved/reference separation and source/artifact manifest |
| History | Working artifact effective/known time lookup and retained source versions; no universal historical state replay |
| REST and remote CLI | Local HTTP adapter; named HTTPS/manual SSH-loopback/automatic SSH client connections with identity pinning, private credential files, CA validation and no redirects; real loopback HTTP/TLS tests; no production gateway or SSO |
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
