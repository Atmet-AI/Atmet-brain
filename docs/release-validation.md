# Historical release validation

These dated records describe checks at each named release. Preparation-time statements such as pending account setup apply to that historical checkpoint, not current installation. Use [current validation](validation.md) and the [support matrix](implementation-status.md) for present scope. Release changes are in the [changelog](../CHANGELOG.md).

## Initial local validation record

Release preparation date: 22 October 2026.

This record describes local development validation of version 0.2.0, adding guided terminal setup, explicit remote clients, team provisioning and user-session service management. Canonical schema version 1 is unchanged. GitHub Actions results are tracked separately in the repository, and local checks do not establish a production assessment.

## Executed

- Python 3.12.14 and cryptography 50.0.2.
- `python -m unittest discover -s tests -v`: 130 tests passed, including real loopback HTTP requests and MCP subprocesses. The 32 repeated-task tests cover learning/review, Python output parity, current context and source access, conflicting outcomes, idempotency, erasure/recovery and REST/MCP execution.
- `python examples/demo.py`: passed the fictional ingestion, learning, policy/skill publication, scoped retrieval and encrypted backup path.
- `python examples/automation_demo.py`: passed recorded examples, template compilation, explicit review, routing and a new decimal report with zero model calls.
- Provider request/response handling was tested with fixtures. No live mailbox or model account was used.
- A wheel was built, installed into an isolated virtual environment and exercised from outside the source checkout. The packaged SQLite schema loaded and source-to-context retrieval plus the full fictional demo passed.
- All 17 current Mermaid diagrams rendered to SVG and PNG in a local headless browser. README and architecture layouts were inspected for readable labels and unclipped content.
- Diagram synchronization was checked with matching, missing, stale and obsolete generated files. The read-only check accepted matching source and rejected each drift case.
- The prior v0.1.1 wheel was installed with uv in temporary isolated tool/cache directories. Its CLI completed the checkout-independent company walkthrough: initialization, source ingestion/learning, context retrieval, the guide's exact workflow JSON, draft inspection/publication and scoped service setup.

- Twenty-one terminal/team regression tests cover no-write welcome/status, validated setup/reinitialization, a simulated interactive interview, private credential output, atomic team provisioning, remote CLI scope/revocation, no local fallback, actual loopback HTTPS trust/hostname checks, redirect refusal, MCP bridge subprocesses, identity-bound profiles, generated client config, service templates/control dispatch and installer checksum rejection.
- The v0.2.0 wheel was installed in an isolated uv tool environment outside the checkout. The installed CLI completed guided team setup, explicit individual credential creation, source learning, remote employee context, generated MCP subprocess calls and credential revocation. Its service definition retained the installed virtual-environment interpreter and that interpreter imported the package with isolated Python startup.
- A real terminal session exercised the wizard and readable status display. Machine-readable output and MCP protocol stdout remain separate from presentation.

## Release checks

The repository checker verifies Python syntax, JSON, portable local links, package/runtime/changelog consistency, generated OpenAPI/diagram consistency, forbidden punctuation and common credential patterns. Package build and isolated installation are recorded in the release validation report. Run these checks again for the actual public release you create.

## Limits

Runtime validation used Python 3.12 locally. CI targets additional Python versions; consult the repository's Actions runs for their results. Actual launchd/systemd start/stop and before-login behavior were not exercised on this workstation; service templates/dispatch use controlled fixtures. SSH, VPN and external HTTPS ingress were not deployed. No Docker executable was available locally, so container files are unvalidated by an actual container build/run. There is no live-provider, named external MCP-client, load, penetration or disaster-recovery service-level certification.

Loopback HTTP tests needed socket access outside the restricted local execution sandbox. They used temporary fictional data and contacted no external service.

## Registry packaging preparation, 0.2.1

The core API/schema are unchanged. The 130 Python tests pass with the synchronized version. Seven Node launcher tests cover exact engine pins, controlled package configuration, literal arguments, stderr-only bootstrap, protected MCP input/output, failure/exit codes and uv archive/cache integrity. The npm tarball allowlist contains only metadata, executable/library code, README and license/notice files.

A real macOS arm64 uv bootstrap download matched the pinned SHA-256 and its executable reported the expected version. Packed local-tarball npx setup was exercised using an explicit trusted local-wheel adapter because the registry engine does not exist yet. This is local packaging evidence, not a successful public npm/PyPI install. Automatic bootstrap targets other than local macOS arm64 and the CI fixture scope require deployment evaluation.

Actual registry uploads, trusted-publisher authentication, new-name ownership and fresh public npx/uvx resolution remain pending owner account configuration. The publisher checklist identifies the exact account fields.


## npm-only packaging, 0.2.2

The npm distribution now includes its matching universal core wheel and a SHA-256 manifest. Eight launcher tests cover local-wheel arguments, digest/metadata rejection before execution, runtime reuse, stderr-only bootstrap, protected MCP input/output and failure handling. Build checks inspect the exact tarball allowlist, wheel metadata, CLI/schema and license/notice contents. The shared core API/schema and 130-test Python suite are unchanged.

The actual packed npm archive is exercised with the included wheel and real uv, without the earlier unpublished-PyPI adapter. CI runs the archive on Ubuntu; local validation covers macOS arm64 setup, MCP output and persistent service interpreter. Public npm name ownership, upload/authentication and fresh public npm resolution remain separate pending steps. No Atmet PyPI release is required, although Python and third-party dependencies can be downloaded on first use.


## Public npm release, 0.2.3

The owner-authenticated upload completed as `anashamad0`. Public npm metadata matched the reviewed tarball integrity and version, and `latest` resolved to 0.2.3. A new npm cache/runtime with empty account configuration exercised version-pinned public setup, private owner credential creation, MCP initialize/tools-list exchange, runtime reuse and a service interpreter import. The unversioned public `npx atmet-brain` also returned 0.2.3. These checks used fictional temporary company data and the included core, with no Atmet PyPI release. No actual OS service was installed. Future npm OIDC/provenance configuration is separate from the first interactive upload.


## Orange terminal refresh, 0.2.4

The 132 Python tests and 8 launcher tests passed. Terminal checks cover orange wide-terminal rendering, compact narrow/plain/dumb fallbacks, control-character removal and stderr-only prompts. A real 88-column PTY captured the fictional welcome screen; its rendered SVG/PNG was visually inspected. The source preview is generated from actual CLI output, not a separate UI implementation. Existing transport tests retain JSON/MCP protocol checks. The color patch does not change the core API, authorization, schema or source learning.

## Public orange terminal release, 0.2.4

Public npm metadata matched the reviewed archive SHA-1 and SHA-512, and latest resolved to 0.2.4. A new anonymous cache/runtime verified pinned setup, private owner credentials, MCP initialize/tools-list, runtime reuse and the persistent service interpreter. Unversioned npx also resolved to 0.2.4. This used the real bundled engine and official bootstrap on macOS arm64, with no Atmet PyPI release or installer override.

## Automatic release guards, 0.2.5

Release tests exercise actual annotated/lightweight tags in a temporary Git repository, checkout mismatch and main ancestry. Registry tests reject duplicate versions, missing package metadata, malformed versions, downgrades, non-404 HTTP errors, mismatched public digests and an incorrect latest tag. They also check numeric version ordering. These tests do not substitute for a successful OIDC upload; record that separately after account activation.

## Registry propagation handling, 0.2.6

The first accepted OIDC upload was not visible within the previous 25-second metadata window. The verifier now polls missing metadata/latest for up to ten minutes without publishing again. Regression cases cover delayed version/latest visibility, exhausted attempts and immediate integrity-mismatch failure. The npm job has a fifteen-minute execution bound.

## Verified OIDC release, 0.2.6

The [release workflow](https://github.com/anashamad9/Atmet-brain/actions/runs/39830420887) passed its build, 139 Python tests, 8 launcher tests, archive checks, OIDC upload, public integrity/latest verification and a fresh public CLI install on Ubuntu. The workflow was dispatched from the immutable v0.2.6 tag after GitHub's push event was delayed; the version-tag trigger is configured and was observed on v0.2.5. No per-release npm authentication prompt or stored npm publishing token was used.

An independent anonymous macOS arm64 install with an empty cache/runtime verified pinned and unversioned resolution to 0.2.6, setup, private owner credential mode, MCP initialize/tools-list, runtime reuse and a persistent service interpreter import. Public SHA-512/SHA-1 matched the actual CI archive, which includes npm provenance metadata. No actual OS service lifecycle or hosted/Playground availability is inferred. The accepted 0.2.5 upload and its initial metadata timeout remain historical; no version or tag was overwritten.

## Published 0.2.6 checkpoint, 22 October 2026

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

## Published 0.3.1 checkpoint, 23 October 2026

Atmet Brain 0.3.1 uses schema 1. The local release checks cover 155 Python regressions and 8 Node launcher tests. The Host/Join tests exercise real loopback HTTPS, private connection files, scope/identity checks, expiry/revocation, malformed inputs and SSH failure/cleanup, including rejection of port readiness without an SSH-owned listener. The version-tag release workflow also passed build/archive checks, GitHub OIDC publication, exact public npm integrity/latest verification and a fresh Ubuntu CLI installation. [Verified workflow](https://github.com/anashamad9/Atmet-brain/actions/runs/39859008158) identifies this release.

A disposable macOS arm64 integration exercised real OpenSSH forwarding with temporary host/member keys and a loopback-only SSH daemon, joining Sales, denying Finance, rejecting an unknown host key and enforcing revocation. No system SSH configuration was changed. This is an isolated integration check, not a customer-network deployment assessment.

Read the [support matrix](implementation-status.md) before relying on a capability. Older release evidence is preserved in [historical validation](release-validation.md).


## 0.4.0 task-history verification

Atmet Brain 0.4.0 uses schema 2. The local suite passed 181 Python tests and 8 launcher tests; the seven-block reporting walkthrough ran with the installed engine, and all 18 Mermaid diagrams rendered. Task-report checks cover actual caller attribution, read/observe/contribute/history/publish separation, private/source audience intersections, immutable replay, stale evidence and reviews, report/source erasure, encrypted recovery replay, old-schema/backup migration and rollback on a failed migration. CLI and real local REST/MCP fixtures exercise reporting, search and skill drafts through the same core. The [tag-push release workflow](https://github.com/anashamad9/Atmet-brain/actions/runs/39867328965) passed build/archive checks, OIDC upload, public npm integrity/latest and a fresh Ubuntu install. Independent anonymous macOS arm64 pinned/unversioned installs verified task commands, schema 2, MCP and persistent runtime reuse.

## 0.5.0 completion-feedback verification

Atmet Brain 0.5.0 uses schema 2. The local suite passed 202 Python tests and 8 launcher tests. Its 21 completion-feedback regressions cover automatic local/real remote Python hooks, CLI stdin/file delivery, MCP opt-in instructions, reporter identity, separate publisher authority, private/inherited/source audiences, partial failures, concurrent and ambiguous retries, revocation and erasure. Host task exceptions retain their original behavior while reports omit raw error details. Existing source/skill/backup/migration/SSH/Host/Join tests remain in the full suite.

The packed npm archive installed in a fresh anonymous macOS arm64 environment, reused its matching runtime, generated clean MCP protocol output and retained a valid service interpreter. The automatic-feedback guide's two Python examples, reporter provisioning, installed MCP config/subprocess, stdin callback and separate publisher approval passed with fictional data outside the source checkout. The 19 diagrams in the immutable 0.5.0 release were rendered. The [immutable tag-push release workflow](https://github.com/anashamad9/Atmet-brain/actions/runs/39950557856) also passed the build/archive guards, GitHub OIDC upload, public npm identity/integrity/latest verification and a fresh Ubuntu install. Public distribution is checked separately from the local suite.

## 0.6.0 guided connection verification

Atmet Brain 0.6.0 uses schema 2. The local suite passed 228 Python tests and 8 launcher tests. Its 26 agent-setup regressions cover actual core scope preflight, local/shared/Join routes, narrowed service/child identities, expiry and parent revocation, cancellation, private files, partial-failure revocation and explicit token-file precedence over ambient owner credentials. Existing source, skill, reporting, recovery, migration, SSH and Host/Join checks remain in the full suite.

A fresh anonymous macOS arm64 npm archive installation passed. Its installed engine exercised all four generated bundles, executed Python and MCP examples, retained Sales-only access under an ambient owner token, recorded a pending skill and required a separate publisher. The guided wizard ran through a real pseudo-terminal; all 25 diagrams rendered. External agent application settings and real business outcomes are separate acceptance checks. The [immutable tag-push workflow](https://github.com/anashamad9/Atmet-brain/actions/runs/39969275448) passed OIDC publication, public identity/integrity/latest and a fresh Ubuntu install. Independent anonymous macOS pinned/latest installation, public agent setup and its generated terminal command passed; installed PTY/MCP/Python/approval checks repeated against that public wheel. [Core CI](https://github.com/anashamad9/Atmet-brain/actions/runs/39969275433) passed Python 3.11, 3.12 and 3.13.

The existing Host/Join, automation, source, permissions, connector and recovery regressions remain required. Live customer applications, model quality and independently verified business outcomes are outside these tests. Read the [support matrix](implementation-status.md).

## 0.6.1 setup recovery verification

Atmet Brain 0.6.1 uses schema 2. The local suite passed 235 Python tests and 8 launcher tests. Seven setup-recovery regressions cover early existing-Brain detection, reuse without repeating company questions, independent new-home creation, existing-folder/symlink protection, cancellation/EOF, credential checks and executable npm-only next commands. The 26 agent-connection regressions and existing source/audience, reporting, history, recovery, migration, SSH and Host/Join tests remain in the full suite.

The setup fix preserves the existing company, owner credential and workspaces. A different company is initialized only in a new private directory. A fresh packed npm installation and actual Local reuse/new-home terminal flows passed, preserving the original owner. The [tag-push workflow](https://github.com/anashamad9/Atmet-brain/actions/runs/39978013281) passed publication, public integrity/latest and Ubuntu installation. Independent anonymous macOS pinned/latest installs repeated those actual npx terminal flows and executed a generated next command without a global CLI. [Compatibility CI](https://github.com/anashamad9/Atmet-brain/actions/runs/39978013493) passed Python 3.11, 3.12 and 3.13. A fictional Finance/payroll check allowed Operations general-finance reads, denied payroll and restricted same-space sources, and rechecked group removal. Historical 0.6.0 proof remains in [release validation](release-validation.md).

## 0.7.0 publication verification

The immutable tag-push run published npm 0.7.0 through OIDC and passed public archive integrity/latest. Its immediate Ubuntu public install encountered ETARGET because npm's package-list metadata had not caught up. The original run remains failed at that final check; the accepted version is never uploaded again. Independent anonymous macOS pinned/unversioned installs and generated terminal commands passed afterward. [Separate read-only verification](https://github.com/anashamad9/Atmet-brain/actions/runs/39990782937) passed the same public archive and fresh Ubuntu/macOS installs. The complete public installed employee-account PTY/TLS/payroll/MCP-revocation walkthrough also passed.

## 0.7.0 account verification evidence

Atmet Brain 0.7.0 uses schema 3. The suite passed 292 Python tests and 8 launcher tests. Its 57 account/UI/company regressions cover one-time enrollment and concurrency, username/company isolation, password verifiers, persisted attempt limits, session expiry/logout, per-space role isolation, payroll audiences, exact membership reviews, password change/reset/disable, group removal, local owner recovery and schema/backup quarantine. Actual loopback HTTP/TLS and CLI subprocesses exercise the interfaces; redirects cannot forward passwords and forged caller/role fields cannot grant access.

Interactive tests check invalid SSH/slug/workspace input recovery, team-menu cancellation, private password/session state and explicit independent company homes. Existing memory/source/workflow/automation/reporting/skill/recovery/MCP checks remain in the suite. A fresh packed npm installation and actual installed pseudo-terminal/TLS walkthrough verified owner login, single-use employee enrollment, per-workspace review, general-finance access with payroll denied, revocation of an already initialized MCP child, fresh sign-in, separate skill approval and two company homes. Installed 0.6.1 schema-2 data and encrypted backup upgraded to schema 3; restored sources stayed quarantined and old credentials remained revoked. The old engine rejected schema 3. All 27 diagrams rendered. Public OIDC publication, archive integrity and latest passed in the [tag-push run](https://github.com/anashamad9/Atmet-brain/actions/runs/39989909174). Its immediate Ubuntu install hit npm metadata ETARGET propagation; the original failure is retained. The [read-only verification](https://github.com/anashamad9/Atmet-brain/actions/runs/39990782937) separately passed exact registry integrity and fresh anonymous Ubuntu/macOS installs. Independent macOS pinned/latest installation repeated the full installed terminal/TLS account/payroll/MCP/approval walkthrough. [Compatibility CI](https://github.com/anashamad9/Atmet-brain/actions/runs/39989909862) passed Python 3.11, 3.12 and 3.13. No accepted version was uploaded twice. No external identity provider, paid account, customer deployment or production security audit is implied.
