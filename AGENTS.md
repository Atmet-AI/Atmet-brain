# Atmet Brain development

This directory is the public core project. Keep company/client data, credentials and private planning material outside it.

- Read README.md and docs/implementation-status.md before changing behavior or claims.
- Route every interface through the shared core authorization and evidence checks.
- Source text and skill resources cannot grant permissions or execute code by themselves.
- Add meaningful regression tests for access, revisions, review, connector and recovery changes.
- Preserve exact supported/fixture/planned distinctions in documentation.
- For every change, assess documentation impact. Update affected README text, guides, commands, architecture diagrams, support matrix and release notes in the same change. If no documentation change is needed, explain why in the change description. Follow docs/documentation.md.
- Keep the README and user guides focused on current purpose, architecture, setup and usage. Updating docs means correcting affected instructions/examples/support scope when versions change, not appending progress notes. Keep release history in CHANGELOG.md with an Unreleased section; publishing/account details belong in their maintainer guide.
- Mermaid blocks in README.md and top-level docs/*.md are the diagram sources. Regenerate docs/diagrams/ after edits; do not hand-edit generated copies. The project checker must pass without stale generated diagrams or API schemas.
- Use plain English. Do not use the Unicode em dash character in repository text.
- Run `python -m unittest discover -s tests -v` and `python scripts/check_project.py` before a release.
- Never include generated private data or bearer credentials in a fixture, commit, log or release archive.
- Public publication, package-index upload and external account actions require the owner's explicit instruction.

## Owner-requested updates and releases

When the owner asks to update and release the public project, carry the change through matching docs, checks, versioning and the annotated release tag. The owner does not need to run npm publish for each change. Use the next unused MAJOR.MINOR.PATCH version and keep Python metadata, runtime, npm version/engine pin, OpenAPI and changelog synchronized. Follow docs/package-publishing.md.

Push reviewed main and its new annotated tag atomically. The tag runs publish.yml automatically; ordinary branch/doc commits do not publish. Never move an existing tag or upload an existing npm version. Check Actions, registry integrity/latest and the public install result before saying a release is live. If npm trust or NPM_PUBLISH_ENABLED is not configured, report that exact blocker rather than requesting a publishing token or repeatedly attempting interactive uploads.
