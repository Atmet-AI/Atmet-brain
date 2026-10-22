# Quickstart

Use Python 3.11 or newer, a private local directory and fictional data for the first run.

## Install

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
atmet-brain --help
```

On Windows, activate with `.venv\Scripts\activate`. Core Python support is intended to be portable; the selected-directory connector uses POSIX descriptor-relative reads and is currently validated on macOS and in Linux CI configuration, not on Windows.

## Initialize

```bash
atmet-brain init --organization example-company --owner "Company owner"
atmet-brain space sales
```

Initialization prints organization/principal IDs and the location of `owner.token`. It does not print the token. Keep the data directory private. Use `--home /path/to/data` before a subcommand to choose another installation.

Save the returned space ID in a shell variable:

```bash
export SALES_SPACE="paste-the-returned-space-id"
atmet-brain ingest examples/company/catalogue.md --space "$SALES_SPACE" --authority authoritative
atmet-brain ingest examples/company/request.txt --space "$SALES_SPACE"
atmet-brain worker --space "$SALES_SPACE"
atmet-brain search "product price" --space "$SALES_SPACE"
```

The local extractor recognizes explicit `Fact[key]: statement` lines. An authoritative source can activate an eligible ordinary fact. Rule-like text and inferred claims remain reviewable. Plain lines become sourced observations. This is a deliberately bounded first learning implementation.

## Add a skill

```bash
atmet-brain skill-install examples/skills/prepare-quotation --space "$SALES_SPACE"
```

The result is pending. Review the package and use its returned artifact ID:

```bash
atmet-brain review ARTIFACT_ID --revision 1 --approve --reason "Reviewed the task method and template"
atmet-brain context "Prepare a quotation" --space "$SALES_SPACE" --artifact ARTIFACT_ID
```

Skills and workflows can depend on exact approved versions of policies and other skills. See the [skills guide](skills.md) for dependency checks and resource loading.

## Give an agent access

```bash
atmet-brain principal quotation-worker --kind service
atmet-brain grant --principal PRINCIPAL_ID --space "$SALES_SPACE" --role worker
atmet-brain token --principal PRINCIPAL_ID --space "$SALES_SPACE" --operation read --operation contribute --output /private/path/quotation-worker.token
```

Replace the returned principal ID and choose a private token path. That credential can read and propose within its underlying grants. It cannot publish policy. All derived credentials also depend on their issuing credential remaining active.

Connect it through [MCP](mcp.md) or run the [REST example](../examples/rest_client.py).

## Run everything in a disposable environment

```bash
python examples/demo.py
```

The demo demonstrates the full implemented local path and does not retain data or credentials.

For the repeated-task-to-script path:

```bash
python examples/automation_demo.py
```

This records three fictional accepted reports, prepares and explicitly reviews Python, then computes a new report without calling a model. See [automations](automations.md) for client reporting and routing requirements.

## Back up before keeping real data

```bash
atmet-brain backup-key --output /private/path/brain-backup.key
atmet-brain backup --key-file /private/path/brain-backup.key --output /separate/storage/brain.atmet
atmet-brain journal --output /separate/storage/recovery-journal.json
```

Store the key separately from backup storage. Keep the recovery journal current and test restoration. The [recovery guide](backup-and-recovery.md) explains why an old backup alone cannot establish today's permissions or deletions.
