# Keeping documentation current

Documentation is part of the change. For every project update, assess which reader-facing behavior, command, supported boundary or diagram is affected and update those files in the same commit. A behavior change is not complete while its examples describe the old behavior.

## README purpose

The root README is the entry guide for someone deciding whether to use the Brain and setting up their first company. Explain what it does, how its architecture works, how to install it, and how to use it with agents and a team. Keep examples and diagrams focused on those tasks.

Describe current behavior directly: "Run atmet-brain to see setup and status commands." Avoid release-note wording such as "The terminal refresh adds..." or chronological summaries of previous work. Put version-by-version changes in CHANGELOG.md, publishing/account procedures in package-publishing.md, and detailed test/release evidence in validation.md. Link to those guides when relevant rather than copying their history into the README.

Keep required platform/support boundaries visible, but put installer internals and version-pinning details in install.md. A terminal preview illustrates usage; it is not a release announcement. Documentation-only README edits do not require a runtime version bump or a new npm release when the published launcher README and behavior are unaffected.

The README uses the supplied Atmet Brain SVG with a white dark-mode variant. Keep their paths and geometry together. Its version badge reads the public npm version automatically; it must not advertise an unpublished version.

## Keep guides useful when versions change

Updating documentation means keeping the current setup steps, examples, expected results, architecture and supported boundaries accurate. It does not mean appending what the team just changed to every page. Review all affected guides when behavior changes; leave unrelated guides alone.

A task guide should identify its prerequisites, files/IDs the user supplies, commands in order, expected results, common failures and the next useful page. A concept/reference page can link to a complete walkthrough instead of duplicating it. Distinguish installed commands from repository-only examples and operator steps from ordinary member access.

Use one canonical CHANGELOG.md for release history. Add meaningful user-visible items under Unreleased, grouped as Added, Changed, Fixed, Security or Breaking changes where useful. At a release, move those entries into its version/date section and include migration steps if needed. Keep current user guides in the present tense; keep dated evidence in release-validation.md. Changelog entries complement working instructions, rather than replacing them.

Check versioned install URLs, explicit installer arguments, schemas, protocol/config examples and cross-links when preparing a release. Preserve historical version references in changelog/evidence/ADRs. A new version does not require a paragraph announcing it on every page.

## Which files to review

| Change | Documentation to review |
| --- | --- |
| Product purpose, core boundaries or default install | `README.md`, `install.md`, `implementation-status.md` |
| CLI/bootstrap/setup | `quickstart.md`, `use-for-your-company.md`, `install.md` and affected README commands |
| Core modules/data flow or schema | `architecture.md`, relevant lifecycle guide and migration/recovery notes |
| API or MCP operations | `api.md`, `mcp.md`, generated `openapi.json` and client examples |
| Source/extraction/provider support | `connectors.md`, `memory-and-learning.md`, support matrix and fixture/live-account distinctions |
| Permissions, policy, history or deletion | `permissions.md`, `versioning.md`, `backup-and-recovery.md` and affected task examples |
| Skills or pure script reuse | `skills.md`, `automations.md`, architecture and company examples |
| Release/version/deployment behavior | `CHANGELOG.md`, `release-versioning.md`, `releasing.md`, `deployment.md`, support matrix and validation |

Paths in this table are relative to `docs/` unless they name a root file. Review the README when the change affects first understanding, installation, main commands or the overall architecture. Internal refactors may need only a code-map or contributor note. If no documentation change is needed, explain that impact decision in the pull request.

## Diagrams

Mermaid blocks in the README and top-level Markdown guides are the editable source. `docs/diagrams/` contains generated standalone `.mmd` copies only. Change the Markdown, then run:

```bash
python scripts/generate_diagrams.py
python scripts/generate_diagrams.py --check
python scripts/check_project.py
```

Generation refreshes copies and removes obsolete generated `.mmd` files. Do not hand-edit or place unrelated drawings in that directory. The project checker rejects missing, stale or extra generated diagrams, in addition to stale OpenAPI, broken local links, version mismatch and repository hygiene issues. CI uses that checker.

For diagram content, keep one clear question per chart, short labels, explicit direction and current versus planned boundaries. Show real authorization, revision and runtime boundaries. A diagram is not evidence that a future feature is available. Render changed charts to inspect syntax, clipping and readability before release.

## Commands and examples

Distinguish installed CLI use from a source checkout. A wheel does not include the repository examples. Verify executable commands and JSON against the current core; placeholders must be identified. Use fictional data and do not add secrets, private paths or customer information.

Generated schemas/diagrams must be refreshed after editing their source. When the package version changes, update default install URLs, source tags, current README/support scope and release notes together. Keep historical release notes and immutable tags intact.

## Evidence and release

Label tested behavior, fixture-only adapters and future targets explicitly. Separate ordinary fact learning from authorized policy publication, context retrieval from external actions, and pure recipes from general code execution. A local test pass is different from an actual CI/provider/client/container check.

Follow [contributing](../CONTRIBUTING.md), the [support matrix](implementation-status.md) and [release procedure](releasing.md). Include the documentation-impact decision and verification in the pull request.
