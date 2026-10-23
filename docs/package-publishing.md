# Automatic npm releases

This maintainer guide explains how to release the npm launcher and its bundled Python core. Users installing the Brain need only the [installation guide](install.md). Publishing uses GitHub OIDC after one-time package-owner trust setup; no Atmet PyPI account or stored npm publishing token is required.

## Everyday updates

Ask the maintainer or coding agent to make the change and release it. They handle the implementation, matching docs, tests, version bump, commit and annotated tag. You do not need to approve a separate npm upload each time after trusted publishing is activated.

1. Update source and affected documentation. Choose a new unused MAJOR.MINOR.PATCH version.
2. Synchronize pyproject.toml, src/atmet_brain/_version.py, npm version/engineVersion, OpenAPI and CHANGELOG.md. Run the [release checks](releasing.md).
3. Commit on main, create an annotated matching tag and push both atomically.
4. GitHub tests, builds and inspects the wheel/npm archive. It refuses tag/version mismatches, lightweight tags and release commits outside main.
5. With the publishing switch enabled, GitHub refuses duplicate npm versions or latest downgrades, then publishes through OIDC with provenance. It waits up to ten minutes for public metadata/latest, checks identity/digests, runs a fresh public CLI install and saves a registry receipt.
6. Check the Actions result before announcing availability. A successful build with a skipped npm job is not a published release.

Ordinary branch commits do not publish. This lets documentation work and unfinished changes remain separate from releases. Immutable version tags are the release signal. Existing installations do not update themselves: users run `npx atmet-brain@latest setup`, or update a global install with `npm install --global atmet-brain@latest`.

## One-time npm trust setup for a new publisher

Skip this section when the existing trusted publisher already works. The repository has an environment named `npm`, without a required-reviewer gate. The workflow needs npm to trust that exact repository/workflow/environment. This account setting requires the package owner's private npm verification. No password, token, recovery code, one-time code or .npmrc contents should be shared in chat.

With Node 24 and npm 11.17.0 or newer, signed in as the package owner:

```bash
npm whoami --registry=https://registry.npmjs.org
npm trust github atmet-brain --repo Atmet-AI/Atmet-brain --file publish.yml --env npm --allow-publish
```

Run this command in your own terminal and keep it open until npm reports that trust was created. Complete npm's private verification when prompted. An approved browser page alone does not confirm that configuration was saved: if a waiting CLI request expires, use the local command again or the stable package settings form. The same configuration can be added in npm package settings under Trusted Publisher:

| Field | Exact value |
| --- | --- |
| Package | atmet-brain |
| GitHub owner | Atmet-AI |
| Repository | Atmet-brain |
| Workflow filename | publish.yml |
| Environment | npm |
| Allowed action | Direct publish |

Direct publishing is required for releases without individual staged approvals. Do not select stage-only publishing for this flow. npm requires the first successful use of a new trusted publisher within two days. Configure it when ready to publish the next version. [npm trust CLI](https://docs.npmjs.com/cli/v11/commands/npm-trust/) and [trusted publishing](https://docs.npmjs.com/trusted-publishers/).

After trust is configured, prepare a new unused release with the [release procedure](releasing.md). Set RELEASE_VERSION to that package version, then activate the repository switch and publish its reviewed tag:

```bash
gh variable set NPM_PUBLISH_ENABLED --body true --repo Atmet-AI/Atmet-brain
gh workflow run publish.yml --repo Atmet-AI/Atmet-brain --ref main -f release_tag="v$RELEASE_VERSION" -f publish_npm=true
```

Manual dispatch is for activation or recovery before an upload has been accepted. Never select a version npm already accepted. Subsequent new tag pushes publish automatically. No npm publishing secret or PyPI job is used. The workflow uses GitHub-hosted Ubuntu, Node 24, npm 11.17.0 and a job-scoped OIDC identity. Keep the workflow filename/environment consistent with npm trust.

## Build-only validation

Before account setup, leave NPM_PUBLISH_ENABLED absent or false. Tag pushes still build/test the exact release but skip the npm job. A manual build-only run works with an existing reviewed tag. Set RELEASE_VERSION to that tag's version:

```bash
gh workflow run publish.yml --repo Atmet-AI/Atmet-brain --ref main -f release_tag="v$RELEASE_VERSION" -f publish_npm=false
```

Artifacts are `python-package` (wheel/sdist) and `npm-launcher` (the complete checked tgz). Successful publication additionally saves `npm-publication-receipt`. A delayed registry response never triggers another upload; a digest/identity mismatch fails immediately. Generated vendor files stay out of Git; [local build commands](releasing.md#npm-distribution) describe preparing the exact archive.

## Failure and recovery

- Build/test failure: fix it before publishing. Never move a tag; create a new version when source changes.
- npm job skipped: inspect NPM_PUBLISH_ENABLED. A missing switch intentionally leaves publishing disabled.
- OIDC rejection: check package owner/repository/workflow/environment, direct-publish permission and the initial two-day window. A provenance signing message followed by an npm PUT rejection is not a successful upload. Pause NPM_PUBLISH_ENABLED until account trust is confirmed. Do not repeatedly request interactive uploads or add a token as a workaround.
- Publish failed before upload: confirm the version is absent using npm view, then retry the same immutable tag via manual dispatch with publish_npm=true.
- Publish succeeded but verification/install failed: inspect the public version, latest and digest. Do not upload the accepted version again. A package-version endpoint and npm's package-list metadata can propagate at different times; the fresh install check retries only ETARGET/E404 with new temporary caches for up to two minutes. Other install errors fail immediately. Fix actual bootstrap defects in a new release; preserve the failed run as evidence.
- Pause future uploads: set NPM_PUBLISH_ENABLED=false. This does not remove existing releases.

Public npm versions and tags remain immutable. Package publication does not launch the hosted platform or Playground. First use can still download uv, Python and third-party dependencies, so npm-only distribution is not a fully offline installer.

## Manual fallback

If trusted publishing is unavailable, the owner can publish the exact checked tgz privately with npm publish and complete npm's verification. For an approval that must outlive a CLI request, npm stage publish can save a reviewed archive for later Staged Packages approval. Check npm view and npm stage list before retrying any version; staging reserves that version without making it public. [npm staging](https://docs.npmjs.com/staged-publishing/). The normal automated workflow uses direct publishing instead.

## Verify an already published version

When npm accepted the upload, rerun only verification. The separate workflow has read-only permissions and no publishing step. It checks the immutable tag, downloads the exact GitHub release archive, compares public registry integrity/latest and installs anonymously on Ubuntu and macOS. Set RELEASE_VERSION to the existing current published version:

```bash
gh workflow run verify-release.yml --repo Atmet-AI/Atmet-brain --ref main -f release_tag="v$RELEASE_VERSION"
```

Inspect the run and its public-install artifacts. The original failed run remains part of the record; a successful verification does not rewrite its result. No npm account verification or upload is needed. This check expects the selected release to remain npm latest; older historical versions require a separately scoped check.

## Moving the repository to another owner

GitHub repository transfers preserve the repository history and redirect its old URL. npm trust identifies an exact GitHub owner, repository, workflow and environment; update that account setting after a transfer before creating another release tag. A GitHub redirect does not update the npm trusted publisher.

1. Save a Git bundle and record branch/tag SHAs, release IDs/assets and the repository ID before transferring the existing repository. Do not create a replacement repository or rewrite tags.
2. Transfer through GitHub, verify the same repository ID/history/releases, then update local origin, live documentation/package URLs and the publish workflow's repository guard. Keep historical release evidence unchanged.
3. Pause NPM_PUBLISH_ENABLED while trust is being changed. In the npm package's Publishing access settings, replace the trusted publisher with Atmet-AI/Atmet-brain, publish.yml, environment npm, with direct publishing allowed. Complete private npm verification yourself.
4. Verify npm trust and the retained GitHub npm environment, then re-enable the switch. The next fresh version tag tests the complete publishing path. Do not republish an existing version to test the move.

The package remains atmet-brain, so users keep the same npx command. Existing published versions remain immutable. Historical provenance names the original repository identity used for that release. See [GitHub transfers](https://docs.github.com/en/repositories/creating-and-managing-repositories/transferring-a-repository) and [npm trusted publishing](https://docs.npmjs.com/trusted-publishers/).
