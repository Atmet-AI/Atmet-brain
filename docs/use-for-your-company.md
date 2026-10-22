# Use the Brain for your company

Start with one useful task and one accountable owner. This walkthrough builds a Sales Brain for preparing quotation drafts. It uses fictional information; replace it with your own reviewed sources before real use.

The current core has terminal, Python, REST and MCP access. A dashboard, chat interview and general autonomous business setup are not part of this alpha. An agent interface can call the core, but it must be configured to do so.

## 1. Install and initialize

If guided `setup` already created the company and Sales space, list spaces with `atmet-brain space`, save its ID and continue to step 2. The manual commands below are an alternative for a fresh installation; do not run `init` again after setup.

Follow [installation](install.md), then initialize a fresh company:

```bash
atmet-brain init --organization example-company --owner "Company owner"
atmet-brain space sales
```

`init` runs once per data home. It prints the company/principal IDs and a private owner-token path, not the token itself. `space` returns an immutable space ID. Save it:

```bash
export SALES_SPACE="paste-the-returned-space-id"
```

The default database and configuration live in `~/.atmet-brain`. Keep the owner credential for administration and create scoped credentials for agents. Use `--home /private/path/to/brain` before a subcommand if you operate a different installation.

## 2. Add the information the task needs

Begin with a small catalogue or company fact file. These files can live in a private working directory outside the source repository:

```bash
printf '%s\n' \
  'Fact[product.price]: Example product price is 100 USD.' \
  'Fact[delivery.window]: Standard delivery is five business days.' > company.md
atmet-brain ingest company.md --space "$SALES_SPACE" --authority authoritative
atmet-brain worker --space "$SALES_SPACE"
atmet-brain context "Prepare a product quotation with its delivery window" --space "$SALES_SPACE"
```

Mark information authoritative only if the company has actually approved that source. The local extractor recognizes explicit ordinary `Fact[key]: statement` lines; it does not infer every rule from a document. Ingestion captures a source revision; `worker` processes its learning jobs. The context response separates approved instructions from reference material and records versions/evidence. It does not write a final quotation by itself.

Accepted text inputs are `.txt`, `.md`, `.json` and `.csv`. Screen recordings, binary brand books and audio do not become understood sources automatically. See [source coverage](connectors.md) and [learning](memory-and-learning.md).

## 3. Save an approved workflow

Create a private `quotation-workflow.json`. Replace `SPACE_ID` with the Sales ID:

```json
{
  "space_id": "SPACE_ID",
  "kind": "workflow",
  "name": "prepare-quotation",
  "body": {
    "description": "Prepare a customer quotation draft",
    "instructions": "Use current permitted catalogue evidence. Ask about missing information and obtain manager approval before sending.",
    "inputs": ["Customer", "Items", "Quantities"],
    "outputs": ["Quotation draft"],
    "steps": [
      {"id": "collect", "instruction": "Check the customer, items and quantities."},
      {"id": "draft", "instruction": "Prepare a draft using current catalogue and delivery evidence."},
      {"id": "review", "instruction": "Present the draft for manager approval before any send action."}
    ]
  },
  "reason": "Initial Sales workflow",
  "idempotency_key": "sales-quotation-initial"
}
```

Submit and inspect it:

```bash
atmet-brain propose quotation-workflow.json
atmet-brain rpc artifacts.get --params '{"artifact_id":"ARTIFACT_ID","revision":1}'
```

Use the returned artifact ID. An authorized publisher reviews the exact content and activates that revision:

```bash
atmet-brain review ARTIFACT_ID --revision 1 --approve --reason "Company owner reviewed the quotation procedure"
atmet-brain context "Prepare a customer quotation" --space "$SALES_SPACE" --artifact ARTIFACT_ID
```

This first owner-written workflow has no source-evidence references in its JSON. For instructions derived from documents, add the actual source IDs/revisions as `evidence` and pin required skill/policy versions as `dependencies`. An external agent may draft the same structured request through authorized interfaces; conversation does not bypass publication or source permissions.

## 4. Give an agent its own identity

```bash
atmet-brain principal sales-assistant --kind service
atmet-brain grant --principal PRINCIPAL_ID --space "$SALES_SPACE" --role worker
atmet-brain token --principal PRINCIPAL_ID --space "$SALES_SPACE" \
  --operation read --operation contribute \
  --output "$HOME/.atmet-brain/sales-assistant.token"
```

Replace `PRINCIPAL_ID` with the returned principal. This credential can read and propose within its grant, but cannot publish or manage access. It is intentionally narrower than all worker operations. Task-outcome recording and pure recipe execution need additional `observe`/`process` scope when explicitly enabled. Do not give an ordinary agent the owner token.

For MCP, configure the client to launch the absolute installed executable and use that token file. Find the executable with `command -v atmet-brain`. [MCP configuration](mcp.md) explains the tool flags and supported transport. For REST, run `atmet-brain serve` and supply the scoped bearer credential. REST defaults to loopback and is not a public-hosting or browser UI setup.

Tell the agent which task/space to use, require it to request current Brain context before acting, and keep external-tool authority in the runtime. Sending the quotation still requires the separate tool permission and the required approval. The Brain cannot observe every conversation or force an arbitrary model to follow its text.

## 5. Add departments deliberately

Create additional spaces only as useful boundaries:

```bash
atmet-brain space shared
atmet-brain space finance
```

A space name is not a team role or running agent. Grant each service/person explicit access. A Sales agent can be granted Shared and Sales without Finance. It must retrieve each space explicitly; this alpha does not assemble cross-space context automatically. Collections/folders are organizational, while space grants and source audiences enforce access.

## 6. Keep the Brain current

A source update uses the same source identity and its current expected revision. The [selected-directory connector](connectors.md) can reconcile selected file changes when synced; continuous operation requires the operator/client to run the sync and workers. The bounded Gmail adapter has fixture coverage and still needs live-account validation and richer authorization/refresh work.

Changes can refresh eligible ordinary facts or produce reviewable candidates. Material workflow/policy changes need authorized publication. Exact dependency versions stop an old skill or recipe from silently using a new rule. When business procedures change, review the workflow too, rather than assuming a repeated observation has approved a new operating policy.

## 7. Reuse stable computation

For mechanical steps, a trusted runtime can report accepted task inputs/outputs with source evidence. The Brain can propose a Python recipe for supported record cleanup or grouped decimal totals. After authorized review, explicit future requests can use it without a model call. Unsupported work returns to the client; revoked access remains an error. This is not an arbitrary Python executor or scheduler. [Automation guide](automations.md).

## 8. Back up and test recovery

Create an encryption key, keep it separately from backups, and mirror the recovery journal outside the installation's failure domain. Restore into a fresh directory and reconcile current revocations/deletions before granting access again. The local data owner remains responsible for host access, retention and any external model/tool data flows. [Backup and recovery](backup-and-recovery.md).

Your first success should be small: the right agent retrieves the current quotation procedure and company facts, an unauthorized identity is denied, a changed source is reprocessed, and a reviewed workflow revision becomes the one used for later tasks.

For a failed step, use [troubleshooting](troubleshooting.md). To inspect an approved workflow changing over time, continue with the [complete history walkthrough](history-walkthrough.md).
