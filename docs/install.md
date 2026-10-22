# Installation

Choose the route that matches how you use the Brain. Version 0.1.1 is an alpha distributed through GitHub releases. No PyPI or npm package is published by this release.

| Goal | Route | Requires source checkout? |
| --- | --- | --- |
| Use the CLI regularly | Install the released wheel with `uv tool install` | No |
| Try one command or launch MCP | `uvx --from` the released wheel | No |
| Import the Brain in a Python application | Install the wheel in that application's virtual environment | No |
| Run repository demos or change code | Clone a tagged version and install the checkout | Yes |

Use Python 3.11+. The commands below request 3.12 where uv selects the interpreter. The CLI and core are validated on macOS locally and Ubuntu in CI; the selected-directory connector relies on POSIX behavior. Windows has not been validated.

## Regular CLI use

First [install uv](https://docs.astral.sh/uv/getting-started/installation/). Then:

```bash
uv tool install --python 3.12 \
  "https://github.com/anashamad9/Atmet-brain/releases/download/v0.1.1/atmet_brain-0.1.1-py3-none-any.whl"
atmet-brain --help
```

uv installs the tool into an isolated environment and exposes its executable. If your shell cannot find it, use `uv tool update-shell` and open a new terminal. No Git executable or manual repository clone is needed for this wheel route. The download and declared dependencies need network access.

## One-off use

```bash
uvx --python 3.12 \
  --from "https://github.com/anashamad9/Atmet-brain/releases/download/v0.1.1/atmet_brain-0.1.1-py3-none-any.whl" \
  atmet-brain --help
```

Replace `--help` with a supported subcommand. Repeated commands use the default data home `~/.atmet-brain` unless you explicitly choose another. uvx isolates the installed tool environment; it does not make company data disposable or isolate arbitrary script actions. See the [uv tool guide](https://docs.astral.sh/uv/guides/tools/).

To use a Git source instead, this also works with Git installed:

```bash
uvx --python 3.12 \
  --from "git+https://github.com/anashamad9/Atmet-brain.git@v0.1.1" \
  atmet-brain --help
```

## Python applications

Inside your own Python 3.11+ project:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install \
  "https://github.com/anashamad9/Atmet-brain/releases/download/v0.1.1/atmet_brain-0.1.1-py3-none-any.whl"
```

The package provides `from atmet_brain import Brain` and the `atmet-brain` executable. Keep this environment activated when using its CLI. On Windows, the activation command is `.venv\Scripts\activate`; Windows support still needs validation.

## Source, examples and contributions

```bash
git clone --branch v0.1.1 https://github.com/anashamad9/Atmet-brain.git
cd Atmet-brain
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python examples/demo.py
python examples/automation_demo.py
```

A tagged clone is a detached checkout of a reproducible release. Contributors can create a branch before changing files, or clone the default branch for current development. Editable installation uses your checkout. The demo scripts and fixture files belong to the repository and are not installed as wheel data.

## Data and upgrades

Installation and company initialization are separate. Installing a package does not create a company or import company information. Continue with the [quickstart](quickstart.md) or the [company walkthrough](use-for-your-company.md).

For an upgrade, read the release notes, back up the installation and check schema compatibility. Install a deliberate new release URL rather than assuming a pinned Git tag or wheel URL follows future releases. Never assume a package upgrade also approves new workflow instructions. [Release versioning](release-versioning.md) and [recovery](backup-and-recovery.md) describe these boundaries.
