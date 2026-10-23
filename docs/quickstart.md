# Quickstart

[Install the released CLI](install.md), then start with fictional data and one space. You do not need a source checkout for the steps below. The [company walkthrough](use-for-your-company.md) adds a reviewed workflow, scoped agent identity and department organization.

## Initialize

You can run `atmet-brain setup` for guided company/department setup. If it already created your Sales space, list it with `atmet-brain space` and skip initialization below. Otherwise follow this manual path in a fresh data home:

```bash
atmet-brain --help
atmet-brain init --organization example-company --owner "Company owner"
atmet-brain space sales
```

Initialization runs once per data home. It prints organization/principal IDs and the location of the owner credential; it does not print the token. The default home is `~/.atmet-brain`. Use `--home /private/path/to/data` before a subcommand for a separate installation.

## Add a fictional source

Save the returned Sales space ID:

```bash
export SALES_SPACE="paste-the-returned-space-id"
printf '%s\n' \
  'Fact[product.price]: Example product price is 100 USD.' \
  'Fact[delivery.window]: Standard delivery is five business days.' > company.md
atmet-brain ingest company.md --space "$SALES_SPACE" --authority authoritative
atmet-brain worker --space "$SALES_SPACE"
atmet-brain search "product price" --space "$SALES_SPACE"
atmet-brain context "Prepare a product quotation" --space "$SALES_SPACE"
```

Authoritative source classification requires the corresponding management authority. Use it only for genuinely approved company material. Eligible ordinary `Fact[key]: statement` lines can activate through the bounded local extractor. Inferences and rule-like text still require their review path.

A successful context result includes `approved_context`, `reference_evidence`, `manifest_id` and `external_actions_authorized: false`. `context` returns structured facts, evidence and approved instructions to a caller. It does not generate a customer-facing reply. An external agent/runtime uses that context and its separately authorized tools.

## Add a workflow or agent

For a guided agent connection, run `atmet-brain agent` and select your workspace, method and access. It prepares private configuration files and verifies the scoped credential. [Agent wizard](agent-setup.md).

Continue with [use for your company](use-for-your-company.md) for a self-contained workflow JSON example and scoped agent credential. Use [MCP](mcp.md) or [REST](api.md) to connect the chosen runtime. Guided setup asks company/space questions; an AI interview about business workflows and a dashboard are not implemented. For later changes, follow the [history and rollback walkthrough](history-walkthrough.md).

## Run disposable repository demos

If you want the bundled fictional scenarios, use the source-install route in [installation](install.md). From that checkout and its activated environment:

```bash
python examples/demo.py
python examples/automation_demo.py
```

The first demo covers ingestion, learning, a policy, skill and workflow, scoped context retrieval and encrypted backup. The second covers explicit task reports, reviewed Python and a new report with no model call. Both remove their temporary data on exit. These files are repository examples, not files installed with the wheel.

## Before keeping real data

Keep the data directory private, create dedicated scoped credentials and read the [backup/recovery guide](backup-and-recovery.md). Record the current recovery journal independently of the disk holding your Brain and test a restoration. The selected-directory connector is validated on POSIX; Windows and live Gmail/model accounts need separate checks.

For command-not-found, existing-installation, missing-memory or permission errors, follow [troubleshooting](troubleshooting.md).
