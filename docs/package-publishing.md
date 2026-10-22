# npm-only publication and account setup

Version 0.2.3 includes the matching Atmet Brain Python wheel inside the npm archive. **An npm account is the only publishing account needed.** There is no dependency on an Atmet PyPI project. The first npm upload is complete under maintainer `anashamad0`, and fresh public commands were verified on macOS arm64. The initial upload used owner-authenticated npm CLI publishing; future OIDC setup remains separate.

The owner has created an npm account. Verify its email and enable two-factor authentication. Do not send passwords, tokens, recovery codes, one-time codes or `.npmrc` contents in chat. The npm username and confirmation of completed local login are enough for coordination.

## 1. Build the exact release

The [publish workflow](../.github/workflows/publish.yml) is manually dispatched. Use the reviewed immutable release tag and leave `publish_npm=false` to build without another upload. Version 0.2.3 is already published and cannot be uploaded again. It checks tag/version identity, runs Python and launcher tests, builds the universal wheel, checks it with twine, copies it into the npm archive with a SHA-256 manifest, then inspects the archive.

The workflow produces:

- `python-package`: wheel and source distribution, for independent Python/GitHub use. They are not uploaded to PyPI.
- `npm-launcher`: the complete `.tgz`, including launcher, core wheel, digest manifest, README and licenses.

Download and extract the `npm-launcher` artifact. Its `.tgz` is the complete publishable package; do not publish the source subfolder without first preparing its generated core bundle.

For a local build, follow [releasing](releasing.md#npm-distribution). The generated `vendor/` stays out of Git and the Python source distribution. [npm's package file rules](https://docs.npmjs.com/cli/v11/configuring-npm/package-json/#files) describe archive inclusion.

## 2. Owner-authenticated publication

With Node.js 24 and npm installed, use a private terminal:

```bash
npm login --registry=https://registry.npmjs.org
npm whoami --registry=https://registry.npmjs.org
npm publish /path/to/atmet-brain-0.2.3.tgz --access public --registry=https://registry.npmjs.org
```

The command above documents the completed first upload. For a future owner-authenticated release, use its new version and exact reviewed `.tgz` from the build. Complete browser login/2FA prompts yourself. No shared API token is needed. The first successful upload establishes package ownership; it is not an OIDC-attested CI publication. [npm's first-publication instructions](https://docs.npmjs.com/creating-and-publishing-unscoped-public-packages/).

If `atmet-brain` is taken, stop and choose an owner-approved alternative before changing package metadata or commands. Do not use a similarly named third-party package as a fallback.

## 3. Verify public installation

After npm confirms the upload, use a fresh runtime directory and npm cache for the explicit release:

```bash
npx atmet-brain@0.2.3 --version
npx atmet-brain@0.2.3 setup
```

Then the ordinary user route is:

```bash
npx atmet-brain setup
```

The launcher verifies its included wheel and prepares a private Python environment. First use can still download uv, Python and third-party Python dependencies. It never downloads the Atmet core from PyPI or GitHub. There is no need to publish an Atmet Python package and no need for users to have a PyPI account. This is an online bootstrap, not a fully offline installer.

Mark npm availability as verified in the README/support matrix only after actual upload and fresh public install checks. Keep the existing GitHub fallback available until then.

## 4. Configure future token-free publication

npm trusted-publisher settings belong to an existing package, so configure them after the first upload. In the GitHub repository, create an environment named `npm`; use required reviewers if the maintainers want a review gate. In npm package settings, add:

| Field | Exact value |
| --- | --- |
| Package | `atmet-brain` |
| GitHub owner | `anashamad9` |
| Repository | `Atmet-brain` |
| Workflow filename | `publish.yml` |
| Environment | `npm` |
| Allowed action | Allow direct `npm publish` |

Configure it when ready to use it; npm currently requires the first successful use of a new configuration within two days. Future release tags can use the workflow's `publish_npm=true` switch. It selects Node 24 and npm 11.17.0 for OIDC publication with automatic provenance. No PyPI job or registry-token secret is required. [npm trusted publishing](https://docs.npmjs.com/trusted-publishers/).

Do not republish version 0.2.3 from CI after uploading it locally. Published package versions and Git tags are immutable; ship a new version for corrections. A standalone Atmet package on PyPI can be added later as an independent distribution route.

## Saved approval through npm staging

If a terminal publishing approval expires before the owner finishes browser verification, first check `npm view` and `npm stage list` to establish whether an upload happened. Do not blindly retry an accepted or already staged version.

To save an exact reviewed archive for later website approval:

```bash
npm stage publish /path/to/atmet-brain-VERSION.tgz --access public --tag latest
npm stage list atmet-brain
npm stage view STAGE_ID
```

Replace `VERSION` and `STAGE_ID` with the reviewed release and returned stage ID. Check the package, version, actor, tag and digest before approval. Staging saves the archive but does not make it publicly installable. The owner can sign in to npm, open **Staged Packages**, select the release and approve it with private 2FA. This avoids depending on a waiting terminal authentication request. A staged version shares the published version namespace; do not upload it again. [npm's staged publication instructions](https://docs.npmjs.com/staged-publishing/).

After approval, verify public version/latest/integrity and a fresh install before updating availability claims. The prepared GitHub workflow currently uses direct OIDC publication; switching that workflow to staged publishing would be a separate explicit change.
