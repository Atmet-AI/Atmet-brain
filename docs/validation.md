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
