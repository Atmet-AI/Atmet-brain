# Testing

Documentation changes use the same release checks when they affect packaged commands, examples or release metadata. `python scripts/check_project.py` also verifies that standalone Mermaid files exactly match the current README/guide blocks. Run `python scripts/generate_diagrams.py` to refresh them, or `python scripts/generate_diagrams.py --check` for a read-only check. Render changed diagrams for visual review. See [documentation maintenance](documentation.md).

Use a [source checkout](install.md#source-examples-and-contributions) with the package installed in its Python environment, then run from the repository root:

```bash
python -m unittest discover -s tests -v
python scripts/check_project.py
python examples/demo.py
python examples/automation_demo.py
node --test npm/atmet-brain/test/*.test.mjs
```

All examples and tests use fictional data in temporary directories. No mailbox, paid model API or real company information is required. HTTP tests need permission to bind loopback sockets; run them in an environment that permits local connections.

## Behavioral coverage

- Cross-company/space denial, source audiences and derived-source intersection.
- Credential narrowing, expiry, lineage and revocation after authentication.
- Source update conflicts, deduplicated capture and dependent invalidation.
- Observation versus ordinary authoritative fact versus policy candidate.
- Bounded retries, denied remote processing and revocation during extraction.
- Stale reviews, concurrent writers, scheduled activation and controlled rollback.
- Dependency revalidation, skill resources and parent-path rejection.
- Context budget failures, current-access history and manifest restrictions.
- Connector changes, disappearance, symlinks, disabled bindings and permanent tombstones.
- Encrypted backup tampering, fresh restore, later erasure reconciliation and old-key rejection.
- Explicit task reports, private and original-source audience intersections, immutable replay, history access, draft-only skill learning, stale source/review rejection, report erasure/recovery and schema migration rollback.
- REST/MCP/Python parity, forged identity fields, private operator method denial and actual stdio subprocess messages.

Provider adapters should add fixture tests before live account checks. A mocked provider proves request/response handling under the fixture, not provider compatibility, model quality or a service-level target.

Use [validation](validation.md) for the executed release record. Keep future acceptance ideas in the roadmap rather than reporting them as passed tests.

## Check changed documentation examples

Use an isolated temporary data home and fictional sources with the released installed engine. Exercise the changed commands in order, filling in IDs returned by the core. Check outcomes such as pending versus published revisions, changed source versions, current permission denial and recovery quarantine. Do not test an example by overwriting a real company installation.

Network/provider/SSH/VPN/service-manager steps need their own authorized environment. Mark them unvalidated when only local fixtures were exercised. Regenerate/render diagrams only if their source changes. A prose-only change does not require tests that simply repeat its wording.
