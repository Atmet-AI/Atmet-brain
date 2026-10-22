# Release versions

The first public source release is **v0.1.0**, a local alpha. Package versions use `0.1.0`; Git tags add the `v` prefix. The changelog records the scope and date of each release.

The current feature release is **v0.2.0**, adding guided terminal setup, private remote connections, a stdio-to-REST MCP bridge, bounded team provisioning and user-session service management. Schema version 1 is unchanged. Agent profile/release bundles remain a separate design; these are engine software versions. Previous release tags remain immutable.

## Version numbers

Versions follow `MAJOR.MINOR.PATCH`:

- During `0.x`, add capabilities or make incompatible API changes in a new minor version, such as `0.2.0`. Document any migration or changed client contract.
- Fix compatible defects in a patch release, such as `0.1.1`.
- Reserve `1.0.0` for a deliberately defined stable API and supported operating scope. An alpha tag does not imply production readiness.
- If several preview builds of the same future version are needed, use explicit identifiers such as `0.2.0a1` in Python metadata and `v0.2.0a1` as the matching Git tag.

## Sources and checks

`src/atmet_brain/_version.py` supplies the runtime version used by health responses, MCP, OpenAPI, context manifests and backup metadata. Keep the package version in `pyproject.toml` equal to it. `scripts/check_project.py` rejects a package/runtime mismatch or a missing current changelog entry.

Database schema, source revisions, workflow versions and recipe-runtime versions remain independent. A package bump does not migrate a database or approve a business workflow. A schema change needs a documented compatibility, migration and recovery plan.

## Release sequence

1. Update the package/runtime version, changelog, README/support scope, default install URLs/source tags and applicable migration notes.
2. Regenerate OpenAPI and diagrams; run the suite, project checker, both demos and clean wheel installation.
3. Commit reviewed source on `main` and create an annotated tag for that exact commit.
4. Push the commit and tag. Mark alpha releases as GitHub prereleases and describe their supported limits.
5. Verify the remote tag, release and CI results. Never move a published version tag; ship a new version for corrections.

See [releasing](releasing.md) for commands. PyPI upload is a separate publishing step.

## Registry preparation

Version 0.2.1 prepares registry packaging without changing the Brain API/schema. The npm launcher version and its exact Python engine pin match the Python package/runtime version. The project checker enforces this parity. GitHub assets, PyPI publication and npm publication have separate availability states; preparation is not a successful registry upload. [Publishing/account steps](package-publishing.md).


Version 0.2.2 replaces the initial registry preparation with npm-only distribution. The matching core wheel is built from the same tag and included in the npm archive with a digest manifest. An Atmet PyPI project is not needed. First npm upload remains a separate owner login/publication step; do not move the previous v0.2.1 preparation tag.


Version 0.2.3 is the first npm publication candidate, with the same npm-only runtime as 0.2.2 and final package-page instructions. Older preparation tags remain unchanged. Public upload and fresh registry validation are recorded separately from the source tag.
