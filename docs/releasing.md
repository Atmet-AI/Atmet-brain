# Releasing Atmet Brain

The public repository is this directory. Keep company harness files, private plans, customer data and local state outside it.

## Verify

```bash
python -m unittest discover -s tests -v
python scripts/generate_openapi.py
python scripts/generate_diagrams.py
python scripts/check_project.py
python examples/demo.py
python examples/automation_demo.py
python -m pip wheel --no-deps . -w dist
```

Install the wheel into a fresh environment and run a first task. Verify the license, README, supported scope, security reporting setup and examples. Record real provider/container checks separately from fixtures and local Python tests.

## Commit and tag

The source repository is [anashamad9/Atmet-brain](https://github.com/anashamad9/Atmet-brain). Keep the Git author configured to the actual maintainer. Review source, license, supported scope and version consistency before committing. For the 0.2.1 registry preparation, before its tag exists:

```bash
git add .
git status --short
git diff --cached --stat
git commit -m "Prepare PyPI distribution and npm launcher for v0.2.1"
git tag -a v0.2.1 -m "Atmet Brain v0.2.1 registry preparation"
git push --atomic origin main v0.2.1
```

Review staged content before the commit. The ignore rules exclude ordinary data, key, token and backup paths, but they cannot identify every possible confidential file. Enable private vulnerability reporting and repository branch rules as appropriate for the team.

Publish a GitHub prerelease for an alpha, using notes that describe the actual supported behavior and limits. Verify the remote commit/tag and inspect the Actions runs. Do not claim remote checks passed until those jobs complete successfully. Publishing a source tag or GitHub release does not upload to PyPI or launch a hosted service.

## Version changes

Follow [release versioning](release-versioning.md). Update package/runtime version references, generated OpenAPI, implementation status and changelog together. A schema change requires a migration/recovery plan; do not treat a package version bump as a database migration. Never replace a published tag with different code.

## Registry distributions

Read [first account/publication setup](package-publishing.md). The manually dispatched `publish.yml` builds a reviewed immutable tag and defaults to build-only. It can publish through separately configured `pypi` and `npm` environments using OIDC. The npm job requires the exact matching official PyPI engine wheel first. The first npm upload is an owner-authenticated local step before trusted publishing exists for that package. No raw registry token is required by the workflow.

Run `node --test npm/atmet-brain/test/*.test.mjs` and `npm pack ./npm/atmet-brain --dry-run` as well as Python checks. Inspect the npm archive's allowlisted files. A version change must keep the Python metadata, runtime version, npm version and npm engine pin equal. Do not claim registry availability until actual uploads and fresh public install checks pass; a GitHub release is separate evidence.
