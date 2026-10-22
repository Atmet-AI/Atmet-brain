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

The source repository is [anashamad9/Atmet-brain](https://github.com/anashamad9/Atmet-brain). Keep the Git author configured to the actual maintainer. Review source, license, supported scope and version consistency before committing. For the 0.2.2 npm-only preparation, before its tag exists:

```bash
git add .
git status --short
git diff --cached --stat
git commit -m "Bundle the core for npm-only installation in v0.2.2"
git tag -a v0.2.2 -m "Atmet Brain v0.2.2 npm-only preparation"
git push --atomic origin main v0.2.2
```

Review staged content before the commit. The ignore rules exclude ordinary data, key, token and backup paths, but they cannot identify every possible confidential file. Enable private vulnerability reporting and repository branch rules as appropriate for the team.

Publish a GitHub prerelease for an alpha, using notes that describe the actual supported behavior and limits. Verify the remote commit/tag and inspect the Actions runs. Do not claim remote checks passed until those jobs complete successfully. Publishing a source tag or GitHub release does not upload to PyPI or launch a hosted service.

## Version changes

Follow [release versioning](release-versioning.md). Update package/runtime version references, generated OpenAPI, implementation status and changelog together. A schema change requires a migration/recovery plan; do not treat a package version bump as a database migration. Never replace a published tag with different code.

## npm distribution

Read [first account/publication setup](package-publishing.md). The manually dispatched `publish.yml` builds a reviewed immutable tag and defaults to build-only. The npm archive includes the exact matching wheel from that build. No Atmet PyPI project or upload is needed. Future npm publication uses the separately configured `npm` environment and OIDC; the first upload requires the owner's private local login.

```bash
python -m build --outdir dist/python
python -m twine check dist/python/*
python scripts/prepare_npm.py --wheel dist/python/atmet_brain-0.2.2-py3-none-any.whl
node --test npm/atmet-brain/test/*.test.mjs
mkdir -p dist/npm
npm pack ./npm/atmet-brain --pack-destination dist/npm
python scripts/check_npm_package.py dist/npm/atmet-brain-0.2.2.tgz
```

The generated `npm/atmet-brain/vendor/` is excluded from Git and the Python source distribution. Build it before every npm pack/publish. The exact archive checker rejects missing, stale or unexpected entries and verifies wheel identity, licenses and hash. Core and npm versions must match. Mark public registry availability only after a fresh real npm install succeeds. Never overwrite a published tag/version.
