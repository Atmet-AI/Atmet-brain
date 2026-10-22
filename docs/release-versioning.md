# Release versions

Software versions identify the engine you install. Business source/workflow revisions identify information inside a Brain; see [history](versioning.md) for those. Package versions use `MAJOR.MINOR.PATCH`, and Git tags add the `v` prefix. The [changelog](../CHANGELOG.md) records each release's user-visible changes.

## Version numbers

Versions follow `MAJOR.MINOR.PATCH`:

- During `0.x`, add capabilities or make incompatible API changes in a new minor version, such as `0.2.0`. Document any migration or changed client contract.
- Fix compatible defects in a patch release, such as `0.1.1`.
- Reserve `1.0.0` for a deliberately defined stable API and supported operating scope. An alpha tag does not imply production readiness.
- The automatic npm `latest` pipeline accepts MAJOR.MINOR.PATCH only. Alpha scope is described in release notes and GitHub prerelease status. Python-only preview identifiers require a separate explicit distribution plan.

## Sources and checks

`src/atmet_brain/_version.py` supplies the runtime version used by health responses, MCP, OpenAPI, context manifests and backup metadata. Keep the package version in `pyproject.toml` equal to it. `scripts/check_project.py` rejects a package/runtime mismatch or a missing current changelog entry.

Database schema, source revisions, workflow versions and recipe-runtime versions remain independent. A package bump does not migrate a database or approve a business workflow. A schema change needs a documented compatibility, migration and recovery plan.

## Release sequence

1. Update the package/runtime version, changelog, README/support scope, default install URLs/source tags and applicable migration notes.
2. Regenerate OpenAPI and diagrams; run the suite, project checker, both demos and clean wheel installation.
3. Commit reviewed source on `main` and create an annotated tag for that exact commit.
4. Push main and its annotated tag atomically. The tag automatically runs the npm workflow after one-time [activation](package-publishing.md). Mark alpha releases as GitHub prereleases and describe their supported limits.
5. Verify the remote tag, release and CI results. Never move a published version tag; ship a new version for corrections.

See [releasing](releasing.md) for commands and [publishing](package-publishing.md) for the configured npm flow. An Atmet PyPI upload is not required.

## Maintain the changelog and guides

1. Add a concise user-visible entry under Unreleased in CHANGELOG.md. Use Added, Changed, Fixed, Security or Breaking changes when they apply; omit empty headings.
2. Update the affected setup/use/reference pages so they describe the resulting behavior, including changed commands, prerequisites and expected results. Do not append a release diary to them.
3. At release, move the Unreleased items into the new version/date heading. Include migration or compatibility steps when users must act.
4. Keep older release entries as history. Preserve preparation-time evidence in [historical validation](release-validation.md), not current instructions.

Documentation-only source-guide changes can stay on main without a new npm engine version when runtime, schemas and the published launcher files are unaffected. Record them in Unreleased for the next release. Never create a new version solely to announce that a guide was edited.
