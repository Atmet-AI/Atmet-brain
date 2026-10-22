# First registry publication and account setup

The PyPI distribution and npm launcher are prepared as version 0.2.1. Neither registry package has been published by this preparation. A public 404 name check is not ownership or a reservation; confirm the name again immediately before the first upload. Existing GitHub releases remain available independently.

The maintainer needs verified PyPI and npm accounts with two-factor authentication. Do not paste passwords, recovery codes, one-time codes, tokens or `.npmrc` contents into chat or repository files. Only account usernames and confirmation that setup is complete are needed for coordination.

## 1. Configure PyPI without an API token

Sign in at [PyPI account publishing](https://pypi.org/manage/account/publishing/) and add a pending GitHub trusted publisher:

| Field | Exact value |
| --- | --- |
| PyPI project name | `atmet-brain` |
| GitHub owner | `anashamad9` |
| Repository | `Atmet-brain` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

PyPI can create the project on the first successful trusted publish. A pending publisher does not reserve the name. [PyPI's official pending-publisher instructions](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

In the GitHub repository, create the `pypi` and `npm` environments. For maintainer review before publication, configure required reviewers on each environment and keep trusted publisher values matched exactly. Repository administration is needed for these settings. No registry secret is required by the prepared workflow.

## 2. Build reviewed release artifacts

The [publish workflow](../.github/workflows/publish.yml) runs only through manual dispatch. Its two publication switches default to false. It checks an immutable `vX.Y.Z` tag, requires the checkout/engine/launcher versions to match, runs Python/Node checks and builds separate artifacts:

- `python-package`: wheel and source distribution, checked with twine.
- `npm-launcher`: the npm `.tgz` with its executable, metadata, README and licenses.

First run it for the reviewed `v0.2.1` tag with both publication switches off. Review/download the artifacts. The tag must exist and must point to this packaging change. A main-branch preparation commit alone is not a published registry release.

## 3. Publish the engine first

After the PyPI publisher/environment is ready, dispatch again with `publish_pypi=true` and `publish_npm=false`, then complete any environment approval. Confirm the official project/repository identity and wheel:

```bash
python scripts/check_registry_release.py
```

Do not publish the npm launcher until that check passes. A launcher cannot download a Python version that has not been uploaded.

## 4. Make the first npm publication interactively

npm's trusted-publisher settings are attached to an existing package. Create the first release from the reviewed npm tarball using your own account in a private terminal. With Node.js 24 and npm installed, run:

```bash
npm login
npm whoami
npm publish /path/to/atmet-brain-0.2.1.tgz --access public
```

Replace the path with the exact downloaded `npm-launcher` artifact from the verified tag. Complete npm's login/2FA prompts locally. This upload establishes package ownership; no shared automation token is needed. The first interactive upload is not an OIDC-attested CI publication. [npm first-publication instructions](https://docs.npmjs.com/creating-and-publishing-unscoped-public-packages/).

Then, in npm package settings, add a GitHub trusted publisher:

| Field | Exact value |
| --- | --- |
| Package | `atmet-brain` |
| GitHub owner | `anashamad9` |
| Repository | `Atmet-brain` |
| Workflow filename | `publish.yml` |
| Environment | `npm` |
| Allowed action | Allow direct `npm publish` |

Configure it when ready to use it; npm currently requires the first successful use of a new configuration within two days. For future versions, the workflow's npm job uses OIDC and automatically supplied provenance. It requires npm 11.5.1+ / Node 22.14+; this workflow selects Node 24 and npm 11.17.0. [npm trusted-publishing instructions](https://docs.npmjs.com/trusted-publishers/).

## 5. Verify the actual public commands

After both uploads, test from a fresh runtime directory:

```bash
npx atmet-brain@0.2.1 --version
npx atmet-brain@0.2.1 setup
uvx --python 3.12 atmet-brain@0.2.1 --version
```

Only then mark registry availability as verified in the README/support matrix and release evidence. The unversioned `npx atmet-brain setup` resolves npm's current default dist-tag; maintain versioned examples for reproducibility.

Future releases can publish both packages through the workflow after account configuration. Retry only the registry that still needs publication: published registry versions cannot be overwritten. Keep old tags immutable. Do not enable `publish_npm` for an npm version already uploaded interactively.

## What the owner supplies

PyPI username, npm username, and confirmation that the pending PyPI publisher and GitHub environments are configured. The owner performs the first npm login/publish privately, then configures its trusted publisher. No passwords or tokens are needed in chat. Account creation, verified email, 2FA and registry name ownership must be completed by the account owner.
