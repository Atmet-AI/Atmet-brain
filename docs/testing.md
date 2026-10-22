# Testing

Documentation changes use the same release checks when they affect packaged commands, examples or release metadata. `python scripts/check_project.py` also verifies that standalone Mermaid files exactly match the current README/guide blocks. Run `python scripts/generate_diagrams.py` to refresh them, or `python scripts/generate_diagrams.py --check` for a read-only check. Render changed diagrams for visual review. See [documentation maintenance](documentation.md).

Install the package, then:

```bash
python -m unittest discover -s tests -v
python scripts/check_project.py
python examples/demo.py
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
- REST/MCP/Python parity, forged identity fields, private operator method denial and actual stdio subprocess messages.

Provider adapters should add fixture tests before live account checks. A mocked provider proves request/response handling under the fixture, not provider compatibility, model quality or a service-level target.

Use [validation](validation.md) for the executed release record. Keep future acceptance ideas in the roadmap rather than reporting them as passed tests.
