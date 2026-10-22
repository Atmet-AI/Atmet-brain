# Atmet Brain development

This directory is the public core project. Keep company/client data, credentials and private planning material outside it.

- Read README.md and docs/implementation-status.md before changing behavior or claims.
- Route every interface through the shared core authorization and evidence checks.
- Source text and skill resources cannot grant permissions or execute code by themselves.
- Add meaningful regression tests for access, revisions, review, connector and recovery changes.
- Preserve exact supported/fixture/planned distinctions in documentation.
- Use plain English. Do not use the Unicode em dash character in repository text.
- Run `python -m unittest discover -s tests -v` and `python scripts/check_project.py` before a release.
- Never include generated private data or bearer credentials in a fixture, commit, log or release archive.
- Public publication, package-index upload and external account actions require the owner's explicit instruction.
