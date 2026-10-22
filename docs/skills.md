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

```bash
atmet-brain skill-install examples/skills/prepare-quotation --space SPACE_ID
atmet-brain review ARTIFACT_ID --revision 1 --approve --reason "Checked method, boundaries and template"
```

## Retrieval

1. List permitted skill descriptions through `artifacts.list` with `kind=skill` or the MCP skill tool.
2. Select the relevant skill.
3. Assemble context with its exact approved version and current compatible dependencies.
4. Fetch a specific template/reference through `skills.resource` only when needed.
5. Record the selected version in the task manifest.

The context envelope contains resource names rather than loading every resource. Generic `artifacts.get` returns the retained body for inspection; task execution should use context assembly so compatibility and applicable policy are checked.

## Updating a skill

Use its stable ID and current head revision when submitting an update. The result remains pending until publication. A changed dependency blocks task assembly until the skill is revalidated. Retiring a skill adds a retirement revision. Rollback adds a new proposal; it does not erase history.

## Learning a skill

The design path is run evidence -> observation -> reusable lesson -> skill draft -> validation -> publication. Current code supports evidence-linked skill proposals and their lifecycle. Automatic extraction of complete portable skill packages from arbitrary agent traces is planned. Model-generated success claims are not accepted as proof of a successful business outcome.

## Execution authority

`required_tools` describes prerequisites. It does not grant them. Even a resource under `scripts/` is returned with `executable=false`; Atmet Brain never runs it. Keep private company data and secrets out of public generic packages. Company-specific evidence remains protected by source access.
