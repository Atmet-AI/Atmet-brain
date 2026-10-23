# Skills

A skill packages a reusable method for a task. The core stores, versions and serves it. An agent runtime chooses how to execute its permitted steps.

## Package

```text
prepare-quotation/
  SKILL.md
  manifest.json
  templates/
    quotation.md
```

`manifest.json` declares a name, description, inputs, outputs, required tools, explicit resource paths and checks. Optional `dependencies` pin exact approved artifact revisions. See the [complete example](../examples/skills/prepare-quotation/manifest.json).

Importing a package creates a pending artifact. Paths must remain inside the selected directory. Parent traversal and symlink reads are rejected. Only listed resources are imported. Resources are text in this release, with a total artifact limit of 200000 characters.

## Create and install your own package

Use an initialized Brain and a space you may contribute to. In a fresh private working directory, create these files; no source checkout is required:

```bash
mkdir -p quotation-skill/templates
cat > quotation-skill/SKILL.md <<'MD'
# Prepare a quotation
Check the customer, items and quantities. Use current permitted price evidence.
List missing inputs and ask for manager review before any send action.
Use the quotation template to structure the draft.
MD
cat > quotation-skill/manifest.json <<'JSON'
{
  "name": "prepare-quotation",
  "description": "Prepare a quotation draft from permitted current evidence.",
  "inputs": ["Customer", "Items", "Quantities"],
  "outputs": ["Quotation draft", "Evidence references"],
  "required_tools": ["Authorized price lookup"],
  "resources": ["templates/quotation.md"],
  "checks": ["Prices have evidence", "Manager review is requested"]
}
JSON
cat > quotation-skill/templates/quotation.md <<'MD'
# Quotation draft
Customer:
Items and quantities:
Prices and evidence:
Missing information:
Required approval:
MD
atmet-brain skill-install quotation-skill --space "$SALES_SPACE"
```

Set SALES_SPACE to your permitted space ID. Save the returned artifact ID as SKILL_ID. Check the pending body before an authorized publisher approves it:

```bash
export SKILL_ID="PASTE_ARTIFACT_ID"
atmet-brain rpc artifacts.get --params "{\"artifact_id\":\"$SKILL_ID\",\"revision\":1}"
atmet-brain review "$SKILL_ID" --revision 1 --approve --reason "Checked method, boundaries and template"
atmet-brain context "Prepare a quotation" --space "$SALES_SPACE" --artifact "$SKILL_ID"
atmet-brain rpc skills.resource --params "{\"artifact_id\":\"$SKILL_ID\",\"path\":\"templates/quotation.md\"}"
```

Context includes the selected approved method and resource names. The resource call returns the template text with `executable: false`. Your agent uses that text through its own authorized tools. Repository contributors can also try the complete package under `examples/skills/`; that directory is not installed by the wheel.

## Retrieval

1. List permitted skill descriptions through `artifacts.list` with `kind=skill` or the MCP skill tool.
2. Select the relevant skill.
3. Assemble context with its exact approved version and current compatible dependencies.
4. Fetch a specific template/reference through `skills.resource` only when needed.
5. Record the selected version in the task manifest.

The context envelope contains resource names rather than loading every resource. Generic `artifacts.get` returns the retained body for inspection; task execution should use context assembly so compatibility and applicable policy are checked.

## Updating a skill

Edit the local package, then import it with its stable artifact ID and current head revision:

```bash
atmet-brain skill-install quotation-skill --space "$SALES_SPACE" --artifact-id "$SKILL_ID" --expected-revision 1
atmet-brain review "$SKILL_ID" --revision 2 --approve --reason "Checked the revised method and dependencies"
```

These revision numbers assume exactly one prior approved revision. Reload the head before a real update; do not overwrite a newer draft. Inspect the proposed body before publication; importing alone leaves it pending. A changed dependency blocks task assembly until the skill is revalidated. Retiring a skill adds a retirement revision. Rollback adds a new proposal; it does not erase history.

## Learning a skill

The design path is run evidence -> observation -> reusable lesson -> skill draft -> validation -> publication. Current code supports evidence-linked skill proposals and their lifecycle. The reports.record/reports.search/skills.learn interfaces now retain selected task outcomes and assemble reviewed skill drafts from explicit steps/corrections. Follow the [task-history walkthrough](task-history-and-learning.md). General model-based extraction from arbitrary agent traces remains planned. Model-generated success claims are not accepted as proof of a successful business outcome.

## Execution authority

`required_tools` describes prerequisites. It does not grant them. Even a resource under `scripts/` is returned with `executable=false`; Atmet Brain never runs it. Keep private company data and secrets out of public generic packages. Company-specific evidence remains protected by source access.

With [automatic task feedback](automatic-task-feedback.md), a configured completion hook attempts a pending candidate after an eligible result. A publisher still inspects the exact revision. Each new run gets a separate candidate rather than rewriting an approved method; use task-learn explicitly to combine reports or revise an existing artifact. Failed-only reports remain history and cannot establish a successful method.
