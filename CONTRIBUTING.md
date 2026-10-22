# Contributing

Start with a small reproducible problem and the current [support matrix](docs/implementation-status.md).

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/check_project.py
```

Use Python 3.11 or newer. Tests need loopback socket access and use temporary fictional data.

## Changes

Keep access checks in the core, preserve original evidence, and distinguish candidate memory from approved operating instructions. New adapters need explicit resource selection, source lifecycle behavior, credential boundaries and fixture coverage. Do not introduce a privileged path that only a UI uses.

For schema changes, add a versioned migration design and recovery tests before changing the schema version. For provider changes, describe fixture validation separately from any live account evidence. No API key is needed for the ordinary test suite.

Use plain documentation with concrete examples. Avoid unsupported production/performance claims and the Unicode em dash character. Update the relevant guide, support matrix and release notes when behavior changes.

## Documentation impact

Every change includes a documentation-impact review. Update the README when purpose, installation, primary commands or the overall architecture changes. Update the affected guides, examples, supported scope and changelog alongside the implementation. For internal changes with no reader-facing effect, explain why no documentation edit is needed in the pull request. [Documentation maintenance](docs/documentation.md) maps changes to the relevant guides.

Mermaid blocks in Markdown are the diagram sources. After editing them, run `python scripts/generate_diagrams.py`; CI rejects missing, stale or extra generated copies through the project checker. Review rendered changed diagrams for readability. API changes must also regenerate `docs/openapi.json`.

## Pull requests

Explain the trigger, resulting behavior and validation. Include the smallest useful test evidence. Contributions are submitted under Apache 2.0 as described in LICENSE. No separate contributor agreement is configured for this initial project.

## Security issues

Follow [SECURITY.md](SECURITY.md). Do not place real customer records, tokens or raw private logs in public issues.
