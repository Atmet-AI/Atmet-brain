# Use history: inspect, compare and restore

This walkthrough changes one fictional workflow, inspects its history and restores its earlier instructions. Use the installed CLI from the [installation guide](install.md). You do not need a checkout, model key or running HTTP server. Run the commands in order in a private working directory. JSON files below are files you create there, outside the source repository.

History is already stored when you change supported sources or artifacts; there is no switch to enable it. Access to old content still depends on your current credentials, grants and source audience.

## 1. Create a separate example Brain

Use a fresh terminal without `ATMET_TOKEN` / `ATMET_TOKEN_FILE` overrides. Choose an empty data home so these examples do not change your company's actual workflow:

```bash
export BRAIN_HOME="$HOME/.atmet-brain-history-demo"
atmet-brain --home "$BRAIN_HOME" init --organization history-example
atmet-brain --home "$BRAIN_HOME" space sales
```

If that home is already initialized, choose a new directory. Do not delete or overwrite an existing Brain to repeat the example. Copy the returned Sales `id`:

```bash
export SALES_SPACE="PASTE_SPACE_ID"
```

The example uses the new installation owner's credential. For real teams, history inspection needs the relevant read/history access; proposing/restoring also needs contribute, and publication needs publish. The existing reviewer role does not itself grant publication. [Permission model](permissions.md).

## 2. Create and publish revision 1

Create the initial workflow file:

```bash
cat > quotation-v1.json <<JSON
{
  "space_id": "$SALES_SPACE",
  "kind": "workflow",
  "name": "prepare-quotation",
  "body": {
    "instructions": "Prepare a quotation draft and request manager approval before sending.",
    "steps": [{"id": "draft", "instruction": "Prepare a draft for manager review."}]
  },
  "expected_revision": 0,
  "reason": "Initial fictional workflow",
  "idempotency_key": "history-demo-quotation-v1"
}
JSON
atmet-brain --home "$BRAIN_HOME" propose quotation-v1.json
```

The result has `revision: 1` and `status: pending_review`. Copy its `id`, then approve that exact revision:

```bash
export WORKFLOW_ID="PASTE_ARTIFACT_ID"
atmet-brain --home "$BRAIN_HOME" review "$WORKFLOW_ID" --revision 1 --approve --reason "Reviewed the initial example"
```

This is an owner-authored example without source/dependency references. A real source-derived workflow must include its current evidence and dependencies. It cannot bypass those checks by following this example.

## 3. Propose revision 2

Keep the artifact ID, space, kind, name and instruction path the same. Submit the complete replacement body with the expected head revision:

```bash
cat > quotation-v2.json <<JSON
{
  "space_id": "$SALES_SPACE",
  "artifact_id": "$WORKFLOW_ID",
  "kind": "workflow",
  "name": "prepare-quotation",
  "body": {
    "instructions": "Include the delivery window in the quotation draft and request manager approval before sending.",
    "steps": [{"id": "draft", "instruction": "Prepare a draft with its delivery window for manager review."}]
  },
  "expected_revision": 1,
  "reason": "Add the delivery window to the example",
  "idempotency_key": "history-demo-quotation-v2"
}
JSON
atmet-brain --home "$BRAIN_HOME" propose quotation-v2.json
atmet-brain --home "$BRAIN_HOME" rpc artifacts.get --params "{\"artifact_id\":\"$WORKFLOW_ID\"}"
```

The proposal creates revision 2, but it does not publish it. The `get` result still serves revision 1. Its `head` can be 2 while its served `revision` is 1: the latest submitted draft and the current approved version are different.

## 4. View history and compare versions

```bash
atmet-brain --home "$BRAIN_HOME" rpc artifacts.history --params "{\"artifact_id\":\"$WORKFLOW_ID\"}"
atmet-brain --home "$BRAIN_HOME" rpc artifacts.get --params "{\"artifact_id\":\"$WORKFLOW_ID\",\"revision\":1}"
atmet-brain --home "$BRAIN_HOME" rpc artifacts.get --params "{\"artifact_id\":\"$WORKFLOW_ID\",\"revision\":2}"
atmet-brain --home "$BRAIN_HOME" rpc artifacts.diff --params "{\"artifact_id\":\"$WORKFLOW_ID\",\"from_revision\":1,\"to_revision\":2}"
```

History returns revision numbers, stored states, authors/reviewers, timestamps, hashes and `rollback_of`. It does not include every body; use `artifacts.get` for the contents. The diff compares retained JSON bodies, showing removed and added lines. It does not compare evidence/dependency/audience metadata or write an AI explanation. Inspect each full revision when those fields matter.

For easier inspection/save-to-file, add the global `--json` option before `rpc`. History can show both revisions as `approved` after publication: current/superseded status is resolved separately, not written over an older approval record.

## 5. Publish revision 2 and inspect task traceability

```bash
atmet-brain --home "$BRAIN_HOME" review "$WORKFLOW_ID" --revision 2 --approve --reason "Reviewed the delivery-window change"
atmet-brain --home "$BRAIN_HOME" context "Prepare a quotation" --space "$SALES_SPACE" --artifact "$WORKFLOW_ID"
```

The context's `approved_context` now references revision 2. Copy the returned `manifest_id`:

```bash
export MANIFEST_ID="PASTE_MANIFEST_ID"
atmet-brain --home "$BRAIN_HOME" rpc context.manifest --params "{\"manifest_id\":\"$MANIFEST_ID\"}"
```

The manifest records the versions used by this context request. It belongs to its original principal and current access still applies. It stores version references and a query hash, not the full agent conversation, generated answer or a guaranteed replay of model output.

## 6. Restore revision 1 as a new revision

```bash
atmet-brain --home "$BRAIN_HOME" rpc artifacts.rollback --params "{\"artifact_id\":\"$WORKFLOW_ID\",\"target_revision\":1,\"expected_revision\":2,\"reason\":\"Restore the earlier example instructions\",\"idempotency_key\":\"history-demo-restore-v1\"}"
atmet-brain --home "$BRAIN_HOME" rpc artifacts.get --params "{\"artifact_id\":\"$WORKFLOW_ID\"}"
```

Rollback returns `revision: 3` and `status: pending_review`. Revision 2 remains current until an authorized publisher approves revision 3:

```bash
atmet-brain --home "$BRAIN_HOME" review "$WORKFLOW_ID" --revision 3 --approve --reason "Reviewed restoring the earlier instructions"
atmet-brain --home "$BRAIN_HOME" rpc artifacts.history --params "{\"artifact_id\":\"$WORKFLOW_ID\"}"
atmet-brain --home "$BRAIN_HOME" rpc artifacts.get --params "{\"artifact_id\":\"$WORKFLOW_ID\"}"
```

Now revision 3 is served, its body matches revision 1, and its history has `rollback_of: 1`. Revisions 1 and 2 remain retained subject to erasure/retention rules. The old context manifest still references revision 2. Neither company memory nor software version was rewound.

| Step | Latest submitted head | Currently served revision |
| --- | --- | --- |
| Initial proposal | 1 | None until approval |
| Initial publication | 1 | 1 |
| Update draft | 2 | 1 |
| Update publication | 2 | 2 |
| Restore draft | 3 | 2 |
| Restore publication | 3 | 3, using revision 1's body |

This restores one retained artifact. It is not a complete agent snapshot or a backup restore. Old grants, erased sources and retired dependencies cannot be recovered by rolling back instructions. If required evidence/dependencies changed, prepare a compatible new reviewed proposal instead.

## 7. Inspect source history and the audit trail

The workflow example has not created any source documents yet. Add one now:

```bash
printf '%s\n' 'Original document text.' > history-notes.md
atmet-brain --home "$BRAIN_HOME" ingest history-notes.md --space "$SALES_SPACE" --external-id history-notes
```

Copy the returned source `id`, then update its content using the same `external_id` and the current source revision:

```bash
export SOURCE_ID="PASTE_SOURCE_ID"
printf '%s\n' 'Changed document text.' > history-notes.md
atmet-brain --home "$BRAIN_HOME" ingest history-notes.md --space "$SALES_SPACE" --external-id history-notes --expected-revision 1
```

Now list the sources, read the current document, read its original content and inspect the audit trail:

```bash
atmet-brain --home "$BRAIN_HOME" rpc sources.list --params "{\"space_id\":\"$SALES_SPACE\"}"
atmet-brain --home "$BRAIN_HOME" rpc sources.get --params "{\"source_id\":\"$SOURCE_ID\"}"
atmet-brain --home "$BRAIN_HOME" rpc sources.get --params "{\"source_id\":\"$SOURCE_ID\",\"revision\":1}"
atmet-brain --home "$BRAIN_HOME" rpc audit.list --params "{\"space_id\":\"$SALES_SPACE\",\"limit\":20}"
```

The current document has revision 2 and the changed text. The historical read returns revision 1's original text with `current_revision: 2`. This is raw source capture; run `worker` separately if you also want to process learning jobs. Changed content under the same `external_id` creates a new revision only when the expected current revision matches. An unchanged import can return `status: unchanged` instead of creating another revision.

Older source reads need history access and today's audience permission; deleted/inaccessible bodies are not revived. There is no generic source rollback or universal memory-history browser in this release. Audit results are filtered for current access and are not full saved conversations.

For a remote company Brain, replace `--home "$BRAIN_HOME"` with `--connection company` in supported commands. Keep each person's scope and approval authority explicit. MCP exposes `brain_get_artifact` for permitted revision inspection, but has no dedicated history-list/diff/rollback tools; those operations use CLI/REST/Python.

## If a command fails

| Error | Next step |
| --- | --- |
| `revision_conflict` | Reload the current `head`, inspect intervening changes and submit a fresh request against that head. Do not overwrite another person's work. |
| `idempotency_conflict` | A request key was reused with different content. Use a new key for a new intended change; reuse a key only for the identical request. |
| `forbidden` / `unauthenticated` | Check current scope, expiry and issuer revocation with your administrator. Do not borrow an owner key. |
| `stale_evidence` / `dependency_changed` | Revalidate against current evidence/dependencies and submit a new reviewed proposal. |
| `invalid_state` | The target may be pending, rejected or retired, or the review may already have happened. Inspect its retained revision/history. |
| `not_found` | Check the installation, space/ID, retained revision, effective time and current audience. It may be intentionally hidden or erased. |

Read [effective/recorded time and lifecycle details](versioning.md) for scheduled policy changes. Use [backup and recovery](backup-and-recovery.md) for installation loss, not ordinary workflow changes.
