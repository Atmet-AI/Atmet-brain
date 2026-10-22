# Installation

Install the CLI with Node.js 22.14+ and npm on macOS or glibc Linux x64/arm64. The launcher includes the matching Python core and prepares its runtime on first use. Company data is stored separately from that runtime. Windows is not validated.

## npm and npx

With Node.js 22.14+ and npm:

```bash
npx atmet-brain@latest setup
```

For regular use:

```bash
npm install --global atmet-brain
atmet-brain setup
```

Pin an explicit release with `npx atmet-brain@0.4.0 setup`. The npm launcher verifies and installs the exact matching Python wheel included in the npm archive, using a checksum-verified pinned official uv runtime and Python 3.12. Python is obtained automatically when needed. No manual Python/uv installation is required for this route. Standard `tar` is needed on supported macOS/Linux systems for automatic bootstrap. Downloads occur on first use, not in an npm postinstall hook.

Runtime storage is separate from company data; [launcher details](../npm/atmet-brain/README.md) documents its paths, environment overrides, platform scope and network requirements. A service or MCP configuration may reference its persistent Python environment: do not remove that runtime directory while it is in use. The npm tarball includes the launcher and engine software, never company data. There is one core and one authorization model. Python and dependencies may still require public downloads on first use.

## Python and platform scope

A standalone Atmet package on PyPI is deferred. The npm launcher installs its included wheel locally and uses the public Python index only for declared dependencies such as `cryptography`. Users need no Python package-index account. Python applications can use existing release wheels or source instructions below.

The core is locally validated on macOS and Ubuntu CI. Automatic uv bootstrap has pinned assets for macOS/glibc Linux x64/arm64; the non-local/non-CI targets need deployment checks. Windows is not validated.

## GitHub release fallback

Versioned GitHub release wheels are an alternative for Python/uv users. The following paths are alternatives, not prerequisites for the registry route. An npm install does not require Git or a source checkout.

## Guided release installer

With [uv installed](https://docs.astral.sh/uv/getting-started/installation/) and curl available, download the versioned installer, inspect it if desired, then run it:

```bash
curl -fsSL https://raw.githubusercontent.com/anashamad9/Atmet-brain/v0.4.0/install.sh -o install-atmet.sh
sh install-atmet.sh 0.4.0
atmet-brain setup
```

The script downloads the selected GitHub wheel and release checksum manifest, checks the SHA-256 digest, then installs it into the current user's isolated uv tool environment. No sudo or repository clone is needed. The checksum protects release download consistency; authenticity still depends on trusting the repository/release and HTTPS. The script does not install uv, initialize company data, open network ports or start a service. If uv is missing, it exits with its official installation link. Always pass the chosen version, as in `sh install-atmet.sh 0.4.0`; an explicit version keeps the install reproducible. Review schema compatibility and back up before changing versions.

## Regular CLI use

First [install uv](https://docs.astral.sh/uv/getting-started/installation/). Then:

```bash
uv tool install --python 3.12 \
  "https://github.com/anashamad9/Atmet-brain/releases/download/v0.4.0/atmet_brain-0.4.0-py3-none-any.whl"
atmet-brain --help
```

uv installs the tool into an isolated environment and exposes its executable. If your shell cannot find it, use `uv tool update-shell` and open a new terminal. No Git executable or manual repository clone is needed for this wheel route. The download and declared dependencies need network access.

## One-off use

```bash
uvx --python 3.12 \
  --from "https://github.com/anashamad9/Atmet-brain/releases/download/v0.4.0/atmet_brain-0.4.0-py3-none-any.whl" \
  atmet-brain --help
```

Replace `--help` with a supported subcommand. Repeated commands use the default data home `~/.atmet-brain` unless you explicitly choose another. uvx isolates the installed tool environment; it does not make company data disposable or isolate arbitrary script actions. See the [uv tool guide](https://docs.astral.sh/uv/guides/tools/).

To use a Git source instead, this also works with Git installed:

```bash
uvx --python 3.12 \
  --from "git+https://github.com/anashamad9/Atmet-brain.git@v0.4.0" \
  atmet-brain --help
```

## Python applications

Inside your own Python 3.11+ project:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install \
  "https://github.com/anashamad9/Atmet-brain/releases/download/v0.4.0/atmet_brain-0.4.0-py3-none-any.whl"
```

The package provides `from atmet_brain import Brain` and the `atmet-brain` executable. Keep this environment activated when using its CLI. On Windows, the activation command is `.venv\Scripts\activate`; Windows support still needs validation.

## Source, examples and contributions

```bash
git clone https://github.com/anashamad9/Atmet-brain.git
cd Atmet-brain
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python examples/demo.py
python examples/automation_demo.py
```

This uses the default branch for current development. For a reproducible release, add `--branch v0.4.0` to git clone and create a branch before editing its detached checkout. Editable installation uses your checkout. The demo scripts and fixture files belong to the repository and are not installed as wheel data.

## Data and upgrades

Installation and company initialization are separate. Installing a package does not create a company or import company information. Run `atmet-brain setup` for guided initialization, or continue with the [quickstart](quickstart.md) / [company walkthrough](use-for-your-company.md). For a shared installation, follow [team server setup](team-server.md).

For an upgrade, read the release notes, back up the installation and check schema compatibility. Install a deliberate new release URL rather than assuming a pinned Git tag or wheel URL follows future releases. Never assume a package upgrade also approves new workflow instructions. [Release versioning](release-versioning.md) and [recovery](backup-and-recovery.md) describe these boundaries.

To update an npm installation:

```bash
npm install --global atmet-brain@latest
atmet-brain --version
atmet-brain status
```

For npx, use `npx atmet-brain@latest --version`. Do not rerun `init` or `setup` to upgrade an existing company. Its data home and credentials remain separate from the installed software. If a saved MCP/service configuration points at the old runtime executable, regenerate that configuration and reinstall the service through its normal lifecycle. [Terminal](terminal.md) and [team services](team-server.md) explain those steps.
