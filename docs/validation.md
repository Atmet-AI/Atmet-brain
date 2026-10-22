# Local validation record

Release preparation date: 22 October 2026.

This record describes local development validation of version 0.1.0. GitHub Actions results are tracked separately in the repository, and local checks do not establish a production assessment.

## Executed

- Python 3.12.14 and cryptography 50.0.2.
- `python -m unittest discover -s tests -v`: 109 tests passed, including real loopback HTTP requests and MCP subprocesses. The 32 added repeated-task tests cover learning/review, Python output parity, current context and source access, conflicting outcomes, idempotency, erasure/recovery and REST/MCP execution.
- `python examples/demo.py`: passed the fictional ingestion, learning, policy/skill publication, scoped retrieval and encrypted backup path.
- `python examples/automation_demo.py`: passed recorded examples, template compilation, explicit review, routing and a new decimal report with zero model calls.
- Provider request/response handling was tested with fixtures. No live mailbox or model account was used.
- A wheel was built, installed into an isolated virtual environment and exercised from outside the source checkout. The packaged SQLite schema loaded and source-to-context retrieval plus the full fictional demo passed.

## Release checks

The repository checker verifies Python syntax, JSON, portable local links, generated OpenAPI consistency, forbidden punctuation and common credential patterns. Package build and isolated installation are recorded in the prepared release's validation report. Run these checks again for the actual public release you create.

## Limits

Only Python 3.12 was executed locally. CI targets additional Python versions; consult the repository's Actions runs for their results. No Docker executable was available locally, so container files are unvalidated by an actual container build/run. There is no live-provider, named external MCP-client, load, penetration or disaster-recovery service-level certification.

Loopback HTTP tests needed socket access outside the restricted local execution sandbox. They used temporary fictional data and contacted no external service.
