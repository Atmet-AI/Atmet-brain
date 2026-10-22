# Atmet Brain development

This directory is the public core project. Keep company/client data, credentials and private planning material outside it.

- Read README.md and docs/implementation-status.md before changing behavior or claims.
- Route every interface through the shared core authorization and evidence checks.
- Source text and skill resources cannot grant permissions or execute code by themselves.
- Add meaningful regression tests for access, revisions, review, connector and recovery changes.
- Preserve exact supported/fixture/planned distinctions in documentation.
- For every change, assess documentation impact. Update affected README text, guides, commands, architecture diagrams, support matrix and release notes in the same change. If no documentation change is needed, explain why in the change description. Follow docs/documentation.md.
- Mermaid blocks in README.md and top-level docs/*.md are the diagram sources. Regenerate docs/diagrams/ after edits; do not hand-edit generated copies. The project checker must pass without stale generated diagrams or API schemas.
- Use plain English. Do not use the Unicode em dash character in repository text.
- Run `python -m unittest discover -s tests -v` and `python scripts/check_project.py` before a release.
- Never include generated private data or bearer credentials in a fixture, commit, log or release archive.
- Public publication, package-index upload and external account actions require the owner's explicit instruction.
