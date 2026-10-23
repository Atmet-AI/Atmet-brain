# Implementation status

Atmet Brain 0.9.0 is a local/private-pilot alpha using database schema 4. Use this table to choose supported operations and identify features needing additional validation. Follow [installation](install.md) and the [company walkthrough](use-for-your-company.md) to use the core.

| Capability | Evidence and scope |
| --- | --- |
| Organizations/spaces | Local provisioning, stable IDs and tested company/space isolation |
| Employee login and invitations | Company-local password accounts, single-use expiring private enrollment, bounded scrypt work/attempts, 12-hour sessions, password change/reset, logout/disable and reviewed workspace roles; no SSO/MFA, verified email or browser UI |
| Multiple company Brains | Device-local catalog, separate data homes and explicit --brain selection; no global discovery service. Backups/ports are per Brain |
| Users and services | Scoped bearer credentials, lineage, expiry, revocation, groups and operation grants; atomic team-add with selected spaces and default 30-day expiry |
| Registry distribution | npm includes the matching checksum-verified Python core and isolated runtime bootstrap; public Ubuntu CLI and anonymous macOS arm64 setup/MCP checks passed. See [installation](install.md) and [validation](validation.md). |
| Terminal setup | Guided Local/Host/Join, existing-Brain Local reuse/separate-home choice and Host reuse, workspace-name member selection, private scoped connection files, server identity/scope verification and explicit service-start option; orange/plain/JSON presentation; no AI onboarding interview |
| Agent connection wizard | Guided local/saved-team/Join selection, workspace names, MCP/terminal/REST/Python bundles, verified reader/reporter child or service credentials, private files and copyable configuration; external app hookup remains manual |
| Background services | Explicit per-user launchd/systemd API and worker definitions plus controls; templates/dispatch tested, actual OS-manager lifecycle needs deployment validation |
| Source ingestion | Working UTF-8 text/Markdown/CSV/JSON capture with revisions and current audience |
| Memory learning | Working local line extractor, explicit authoritative-fact activation, observations, reviewable inference/conflict |
| Model extraction | Opt-in compatible HTTP adapter with evidence/response validation; fixture validation, no live provider benchmark |
| Policy/workflow/skill lifecycle | Working proposal/publication, optimistic revisions, schedules, retirement and rollback |
| Skills | Text package/resource import, dependency-aware retrieval and explicit task-outcome skill drafts; exact-revision publication remains separate; no script execution |
| Task reports/history | Authenticated reports, default-private audiences, permission-first lexical history and explicit steps/corrections. Opt-in Python/host completion hooks automatically submit and attempt pending skill candidates; MCP completion instructions depend on the agent. No automatic external transcript capture or independent outcome verification |
| Guided update | Local macOS/Linux operator wizard, npm target handoff, read-only encrypted pre-migration snapshot/journal, retained record/file checks and canonical service refresh; cooperative maintenance lock. Stop old/custom processes, reconnect external MCP manually. OS service lifecycle still needs host validation |
| Schema upgrades | Transactional schema-1/2/3 to schema-4 migration and old-backup upgrade before quarantine; old accounts/invites/sessions disabled on restore; stop old engines and back up before upgrading |
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

## Agent administration and restricted intake

[Conversational administration](conversational-administration.md) is implemented as explicit structured proposals from your external agent, with a separate exact human password review. Supported controls cover workspaces, non-admin memberships, groups, rules, source classification/authority/access/erasure and connector disable. New/changed documents default to restricted intake; approved explicit rules or human classification release them. Retained restrictions and current audiences apply to history/derived data. Model suggestions alone do not release documents. OS/SSH provisioning, universal semantic/DLP classification, arbitrary file parsing, large-queue pagination and independent production security evaluation remain outside this subset.
