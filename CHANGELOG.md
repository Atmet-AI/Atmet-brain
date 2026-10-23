# Changelog

## Unreleased

## 0.9.0 - guided backup-first company updates, 2026-10-23

### Added

- Guided local update with company selection, exact npm target handoff, review/maintenance confirmation, encrypted read-only pre-migration snapshots and matching recovery journals with separate keys.
- Retained table/record, identity, workspace, credential/configuration and catalog verification; private phase reports on success/failure without automatic database rollback.
- Cooperative maintenance leases and unchanged managed-service refresh preserving API port, worker scope and prior running/inactive state.

### Scope

- Schema 4 is unchanged. Older supported schemas migrate only after backup verification. Close old/custom processes and reconnect saved MCP entries manually. The updater is local-only, bounded to 256 MiB snapshots and does not change global npm installations, provision networking, provide remote backup storage or run through agent RPC.


### Documentation

- Add a safe software-update walkthrough covering old-version backups, retained company homes/workspace IDs, schema migration, multiple companies, remote clients and refreshed MCP/service runtime paths.

## 0.8.1 - organization publishing and project identity, 2026-10-23

### Documentation and maintenance

- Add the Atmet Brain logo, product summary and live package-version badge to the README, with light and dark logo variants.
- Move the existing repository to Atmet-AI/Atmet-brain and update active project links, package metadata and release configuration. Earlier published versions and historical tags remain unchanged.
- Configure the organization trusted publisher for automatic npm releases.

### Compatibility

- Brain behavior and schema 4 are unchanged. This patch requires no data migration from 0.8.0. Older schema upgrades still follow the existing backup and restart procedure.

## 0.8.0 - approved agent administration and restricted document intake, 2026-10-23

### Added

- Administration MCP tools prepare exact workspace, employee, group, access-rule, classification and source/connector proposals. A separate private human password review applies each change once after rechecking current authority, revisions and digest. Agents cannot approve themselves.
- Guided admin agent, overview, queue, classify and review commands, with private scoped control bundles and sanitized configured SSH/HTTPS metadata.
- New/changed documents default to restricted intake. Approved explicit term/connector rules classify matching documents; unmatched/held sources require human-reviewed release. Every matching audience intersects. Workspace-wide automatic release requires a trusted connector binding.
- Reader, User and Editor everyday labels alongside existing specialist roles; company administration remains separate.
- Rule/approval history, stale classification checks, retained restrictive source-history audiences and erasure/recovery handling.

### Changed

- Schema 4 upgrades supported schemas 1/2/3 transactionally. Back up with the old compatible engine and stop old processes before the first new database open. Restart all services/MCP with the new engine; no mixed-engine use or in-place downgrade.
- Existing active sources retain their current access until updated or policy changes require reclassification. Restores reject pending changes, revoke controls, disable rules and require fresh classification.
- Release verification handles bounded npm metadata propagation and can verify accepted releases independently without uploading again.

### Scope

- Your configured external agent interprets natural language. The core enforces explicit approved structured actions. This is not perfect semantic classification, universal DLP, automatic salary redaction, OS/SSH provisioning, SSO or MFA.

## 0.7.0 - employee accounts, invitations and company selection, 2026-10-23

### Added

- Company-local username/password accounts with salted scrypt verifiers, bounded persistent sign-in attempts and 12-hour opaque sessions. Passwords are prompted privately and never saved by the client.
- Single-use, expiring employee invitations and explicit reset/enrollment of existing employees. Administrators choose a separate role for each workspace. Password change, logout, disabling and access changes revoke the relevant credentials and descendants.
- Guided team menu for employee lists, invitations, per-workspace access reviews, disabling, password reset and new workspaces. Interactive Host defaults to password enrollment invitations; explicit legacy bearer sharing remains available.
- Device-local company catalog with brains create/add/list/open and explicit --brain selection. Independent company data homes retain separate sources, users, permissions and backups. Multiple company servers need distinct local ports.
- Local filesystem-owner account recovery with explicit confirmation, a privately saved operator key and no public recovery endpoint.

### Fixed

- Recoverable SSH/HTTPS, company, workspace and agent-name input errors re-prompt the relevant field. /cancel stops the current operation; the interactive team menu can continue without replaying completed operations.
- Signed-out local sessions cannot silently fall back to the owner credential. Saved remote logins retain their verified route for explicit sign-in after expiry or permission changes.

### Upgrade

- Schema 3 adds account, invitation, membership-review and sign-in-attempt records. Back up using the existing engine before the first new open; stop old processes and restart services with 0.7.0. Supported schemas 1/2 upgrade transactionally. There is no in-place downgrade or rolling mixed-engine deployment.
- Restored accounts lose password verifiers and remain disabled; old invitations and sessions are revoked. Journal recovery and deliberate identity/source revalidation remain required.
- Local password login is implemented. SSO, MFA, email verification/delivery, a browser login UI and global numeric company discovery are not part of this release.

## 0.6.1 - existing Brain setup recovery, 2026-10-23

### Fixed

- Local setup detects an existing Brain before company questions and offers Open existing, Create separate or Cancel. Reuse preserves the owner, workspaces and records; a separate Brain requires a new private directory.
- Explicit creation flags against an existing home fail before the interview with recovery instructions. Non-interactive local setup without creation flags opens the existing Brain.
- Setup/Host/Join next commands use the installed interpreter so npm-only users do not need a global CLI executable.

### Documentation

- Explain explicit workspace access, remote network reachability, reusable bearer authentication, restricted payroll sources and the distinction between company discovery IDs and login.

### Compatibility

- Schema remains 2. No migration from 0.6.0. No existing Brain is reset or renamed. Login/SSO and numeric company discovery are not added by this patch.

## 0.6.0 - guided agent connection, 2026-10-23

### Added

- Interactive agent command for local, saved remote or Join access; MCP/terminal/REST/Python choices, workspace names, reader/reporter scope, reviewed identity creation and private configuration bundles.
- Core access.check preflight and credential expiry metadata, with new/current identity choices bounded by existing grants and lineage.
- Copyable MCP entry, installed Python example, HTTP request, context/completion commands and app-specific next-step guidance without automatic client settings edits.

### Fixed

- Explicit --token-file now takes precedence over an ambient ATMET_TOKEN so a configured scoped agent cannot accidentally run with a shell's broader credential.
- Failed bundle creation attempts credential revocation; existing outputs are never overwritten and cancellation stops before issuance.

### Compatibility

- Database schema remains 2. Existing 0.5.0 data needs no migration. Guided remote setup requires engine 0.6.0+ on the server for access preflight; existing manual interfaces remain available.
- Configuration generation verifies core scope, not the external app, source relevance or an API listener. Host callbacks and skill publication remain separate.

### Documentation

- Expand the README into a from-scratch lifecycle, memory-type reference, reviewed first workflow and existing-project setup with scoped agents, selected imports, history/recovery and explanatory charts.

- Record the verified 0.5.0 public npm release workflow in the validation reference.

## 0.5.0 - automatic task completion feedback, 2026-10-23

### Added

- reports.complete saves a safe task result and attempts an eligible skill draft with separate statuses. Exact retries reuse the report/candidate without repeating business actions or revising approved methods.
- Token-bound Python LocalClient/Client task_feedback lifecycle wrappers, automatic failure reporting without raw exception text and in-memory frozen-payload retries.
- task-complete FILE or stdin completion hook, local/remote MCP --task-feedback tool/instructions, and a scoped reporter role without publish authority.
- One-time integration guide covering source provenance, default-private/shared audiences, host callbacks, partial delivery, exact-revision human approval and operational limits.

### Compatibility

- Schema remains 2. Existing 0.4.0 data is reused without a migration; schema-1 installations still require the documented backup/upgrade procedure.
- Automatic delivery requires a configured host hook. MCP instructions alone cannot guarantee that an unrelated agent reports a result. No background transcript watcher, durable retry queue, new model learner or auto-publication is added.

### Documentation

- Clarify that pre-upgrade backups use the existing schema-1 engine before opening the Brain with 0.4.0.
- Clarify that task-report integrations must provide complete provenance; reference validation does not attest undisclosed data sources or business success.

## 0.4.0 - task history and reviewed skill learning, 2026-10-23

### Added

- Explicit task reports with authenticated attribution, bounded outcomes/steps/corrections/checks, original source evidence, private-by-default audiences and idempotent reporting.
- Permissioned lexical task-history search and report inspection through Python, CLI, REST and MCP. Raw reports remain outside ordinary company search/context/source listings and portable space exports.
- Deterministic skill drafts from selected reported methods and corrections. Drafts retain report/original-source evidence, remain pending and require the normal exact-revision publisher approval. Reported success remains unverified; no scripts are executed.
- CLI task-report, task-history, task-get, task-learn and task-erase commands, including remote connections. Explicit MCP task-reporting/proposal switches and matching configuration generation.
- Report erasure through the existing source journal, including dependent method retraction and recovery replay. Tests cover identity, grants, audiences, stale evidence, concurrency, migration and local/remote interfaces.

### Upgrade

- Schema 2 adds task-report metadata and separate operational source classification/state. Schema-1 installations upgrade transactionally; back up first, stop old local processes and restart services with the compatible engine. Older engines cannot open schema 2; there is no in-place downgrade.
- Restore supported schema-1 snapshots into a fresh home, upgrade before quarantine and replay the latest recovery journal. Existing identities, sources and artifact versions remain.
- Operational report sources never enter the legacy active-document state, preventing older ordinary-source queries from exposing raw report bodies.

### Documentation

- Add a complete reporting/history/learning walkthrough, permission requirements, agent tool setup, erasure/recovery and migration instructions. Update architecture, README, support matrix and MVP/Harness records.

## 0.3.1 - SSH forwarding ownership, 2026-10-23

- Require OpenSSH's successful loopback bind/listen diagnostic before sending a Brain credential. A reachable local port alone is not accepted as SSH readiness.
- Keep startup diagnostics in a private temporary directory, cap reads, and remove the directory when forwarding ends. Preserve strict host checks, bounded startup and process cleanup.
- Add a regression proving that an unrelated open port receives no probe or Brain credential without SSH's positive bind confirmation.

- Clarify Host/Join credential and SSH boundaries in security, API, permissions and navigation references.

## 0.3.0 - guided team sharing, 2026-10-23

### Added

- Guided Host and Join entry points, available from setup and the terminal welcome. Host reuses an existing Brain, selects workspaces by name and provisions one scoped member connection file at a time.
- Join previews the server/access details, validates the real organization/principal/credential identity and lists permitted workspaces before saving a private connection. Expired, changed, revoked and mismatched files are rejected.
- Automatic SSH forwarding for named CLI/MCP connections, with strict known-host/key authentication, bounded startup and per-request process cleanup. No separate tunnel terminal is required after administrator SSH setup.
- Explicit Host option to install/start the existing per-user API service. HTTPS/manual connection profiles remain supported. The API stays on loopback; no SSH accounts, firewall rules, VPN or certificates are installed.
- Regression coverage for guided flows, connection-file handling, access boundaries and SSH failure/cleanup. Schema remains 1; existing company data is reused.

### Documentation

- Explain Host and Join by device, how to transfer/revoke private connection files, SSH prerequisites and troubleshooting. Keep advanced manual commands available.

- A task-based documentation index and troubleshooting guide for setup, retrieval, agents, access, synchronization and upgrades.
- Installed-CLI walkthroughs for memory updates, workflow publication, portable skills, scoped access and task configuration; historical validation has its own archive page.

- Refocus the root README and user guides on architecture, setup and usage. Keep release history and publishing procedures in their dedicated guides.
- Correct old installation pins, require an explicit version for the legacy GitHub installer, and clarify npx versus global CLI commands, source-only examples and existing-data upgrades.
- Require affected guides and examples to stay accurate when versions change, with user-visible release entries maintained here.

## 0.2.6 - registry propagation handling, 2026-10-22

- Wait up to ten minutes for an accepted npm upload to appear in public metadata and latest. Retry visibility checks without uploading the version again.
- Fail immediately for mismatched package identity or archive integrity. Bound the publishing job to fifteen minutes and test delayed metadata/latest responses.
- This fixes the first OIDC upload's premature post-publication timeout. Core runtime, API and schema are unchanged.

## 0.2.5 - automated npm releases, 2026-10-22

- Annotated version tags automatically build, test and publish through GitHub OIDC after one-time trusted-publisher activation. No stored npm publishing token or per-release browser approval is needed for that route.
- Reject mismatched tags, commits outside main, duplicate npm versions and latest downgrades. Verify public archive integrity and run a fresh public CLI install after publishing.
- Keep build-only dispatch and a repository activation switch for initial setup/recovery. Update maintainer instructions and record verified 0.2.4 availability. Core API and schema are unchanged.

## 0.2.4 - orange terminal refresh, 2026-10-22

- Large orange pixel wordmark for the welcome and interactive setup, with clearer mode choices and next steps. Compact headers keep ordinary commands short.
- Responsive/plain/no-color/encoding fallbacks; prompts go to stderr to preserve redirected JSON. Core API, permissions and schema remain unchanged.

## 0.2.3 - first npm release, 2026-10-22

- Published the first public npm package with the included core and normal user commands. Fresh anonymous public install/setup/MCP and the unversioned npx command were verified on macOS arm64.
- Preserve the v0.2.2 preparation tag; the npm launcher and Python core use the same new version. Runtime behavior and schema are unchanged.

## 0.2.2 - npm-only publication prepared, 2026-10-22

- Include the exact matching universal core wheel and SHA-256 manifest inside the npm package; verify both before execution. No Atmet PyPI release or PyPI account is required.
- Build and inspect the full npm archive in CI, including wheel metadata, licenses and the public file allowlist.
- Remove the PyPI publication dependency from the npm workflow; update installation/account docs for npm-only publishing.
- Core API and schema remain unchanged. Python/runtime and third-party dependency downloads may still be needed on first use. Actual npm upload/public install verification remain pending owner login.

## 0.2.1 - registry publication prepared, 2026-10-22

- Added a copy-and-follow history walkthrough for creating, comparing, publishing and restoring workflow revisions, context manifests, source reads, audit records and common errors.
- Linked practical history usage from the README/docs index, clarified whole-agent snapshot limits, and distinguished guided setup from manual initialization to prevent repeated init.
- PyPI-ready build/validation and manually dispatched OIDC publishing workflow; first registry account configuration/publication is still pending.
- Version-matched npm launcher with verified uv bootstrap, isolated persistent runtime, literal command forwarding and clean MCP stdout.
- npm archive checks and launcher CI; maintainer account checklist and registry-first README/install instructions.
- Core API, schema and prior release assets remain unchanged; software versions are synchronized for the first registry release.

## 0.2.0 - 2026-10-22

Terminal experience and private team access feature release. Canonical schema version 1 is unchanged.

- Guided local/team/connect setup, welcome/status screens, readable TTY results, plain output and explicit JSON mode.
- Versioned release installer with wheel checksum verification and isolated per-user uv installation.
- Explicit remote CLI profiles using HTTPS or SSH-loopback HTTP, private copied credentials, identity binding, optional trusted CA, no redirects and no plaintext LAN fallback.
- Local stdio-to-REST MCP bridge and generated client configuration, with current authorization and clean protocol stdout.
- Atomic team provisioning with non-admin identities, selected-space roles, expiring grants/credentials and private CLI token output.
- Explicit launchd/systemd user-session API/worker service rendering, installation, controls and modified-file protection. Actual OS-manager lifecycle remains deployment-specific validation.
- Terminal/team-server documentation and diagrams. No VPN/SSO/public ingress, remote HTTP MCP transport, AI onboarding interview or agent profile/release bundles are introduced.

## 0.1.1 - 2026-10-22

Documentation and release-maintenance update. Core behavior and public API are unchanged.

- Six README diagrams explain company spaces, the shared core, learning/review, agent tasks, pure Python reuse and change handling.
- Rebuilt architecture guide with current module responsibilities, task/recipe paths, data relationships and runtime boundaries.
- Added an installation guide and company walkthrough; the quickstart works without repository example files.
- Added a documentation-impact requirement to project instructions, contribution guidance and the pull request template.
- The project checker now rejects missing, stale and obsolete generated Mermaid diagrams; diagram generation has a read-only check mode.

## 0.1.0 - 2026-10-22

Initial local alpha.

- Organization/space identity, scoped credentials, groups and operation grants.
- Source revisions, evidence access, learning jobs and current-permission invalidation.
- Local extraction and opt-in compatible model adapter.
- Reviewed policy, workflow, instruction, configuration and skill artifacts.
- Optimistic updates, schedules, dependency checks, history and controlled rollback.
- Permission-first lexical retrieval, context envelopes, manifests and JSON graph.
- Python, CLI, REST and MCP stdio interfaces.
- Selected-directory and bounded read-only Gmail adapters.
- Evidence-linked case-event workflow drafts.
- Repeated task observations, inferred bounded Python recipes, reviewed publication, permission/version-aware routing, regression pauses and execution records.
- Encrypted snapshots, journal reconciliation and quarantined recovery.
- Runnable examples, tests, diagrams and public development documentation.

See the support matrix for fixture-only and planned capabilities.
