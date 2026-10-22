# Changelog

## Unreleased

- Added a copy-and-follow history walkthrough for creating, comparing, publishing and restoring workflow revisions, context manifests, source reads, audit records and common errors.
- Linked practical history usage from the README/docs index, clarified whole-agent snapshot limits, and distinguished guided setup from manual initialization to prevent repeated init.
- Documentation only; engine behavior, schema and released v0.2.0 assets are unchanged.

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
