# Local validation record

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
