# Workflows and automatic discovery

A workflow contains a trigger, required inputs, steps, exceptions, expected outputs and instructions. A step may use a skill pinned as an artifact dependency.

## Create a workflow

Complete the [quickstart](quickstart.md) and set SALES_SPACE to a space you may contribute to. In a private working directory, save this complete proposal:

```bash
cat > quotation-workflow.json <<JSON
{
  "space_id": "$SALES_SPACE",
  "kind": "workflow",
  "name": "prepare-quotation",
  "instruction_path": "departments/sales/quotations",
  "body": {
    "description": "Prepare and review a customer quotation",
    "instructions": "Use current catalogue evidence and obtain manager approval before sending.",
    "trigger": "Customer requests a quotation",
    "inputs": ["Customer", "Items", "Quantities"],
    "outputs": ["Reviewed quotation draft"],
    "steps": [
      {"id":"collect","instruction":"Check requested items and missing fields."},
      {"id":"draft","instruction":"Prepare the draft using permitted current prices."},
      {"id":"review","instruction":"Ask the manager to review before sending."}
    ],
    "exceptions": ["Missing prices require clarification."]
  },
  "expected_revision": 0,
  "reason": "Initial owner-authored Sales procedure",
  "idempotency_key": "quotation-guide-initial"
}
JSON
atmet-brain propose quotation-workflow.json
```

The result has `id`, `revision: 1` and `status: pending_review`. Save the returned ID:

```bash
export WORKFLOW_ID="PASTE_ARTIFACT_ID"
atmet-brain rpc artifacts.get --params "{\"artifact_id\":\"$WORKFLOW_ID\",\"revision\":1}"
atmet-brain review "$WORKFLOW_ID" --revision 1 --approve --reason "Owner checked the procedure and approval boundary"
atmet-brain context "Prepare a quotation" --space "$SALES_SPACE" --artifact "$WORKFLOW_ID" --task-path departments/sales/quotations
```

The approved context now contains the reviewed workflow. A contributor can propose; only a principal with publish access can activate it. This owner-authored example has no document evidence. For a source-derived procedure, include actual source IDs/revisions in `evidence`. If a step includes `skill_id`, pin that skill's exact approved revision in `dependencies`.

## Change or restore instructions

Use the same artifact ID, kind, name, space, instruction path and audience. Submit the full replacement body with `artifact_id`, the current head in `expected_revision`, a new idempotency key and the reason. The old approved revision remains current while the replacement is pending. Review the exact new revision before using it. The [history walkthrough](history-walkthrough.md) gives complete update, diff and restore commands.

An agent can prepare these proposals when connected through an authorized interface. Describing a task in a chat creates Brain records only when that client actually calls the core. A department is a [space with explicit grants](permissions.md); it is not created merely by naming an agent.

## Learning from activity

The current discovery implementation accepts explicit case-linked events through `events.record`. Each event needs a stable key, case ID, activity, timestamp and source evidence. The integration provides the case relationship; the Brain does not guess it from customer names.

```json
{
  "space_id": "SPACE_ID",
  "event_key": "quotation-123-drafted",
  "case_id": "quotation-123",
  "activity": "Prepare quotation draft",
  "evidence": [{"source_id": "SOURCE_ID", "revision": 1}],
  "happened_at": "2026-10-21T10:00:00Z"
}
```

Save the JSON above as `case-event.json`, replacing its IDs with a real permitted source revision and chosen case. Then:

```bash
atmet-brain rpc events.record --params @case-event.json
atmet-brain rpc workflows.discover --params "{\"space_id\":\"$SALES_SPACE\"}"
```

Record events for the real cases you want to compare. Discovery needs enough visible case evidence; incomplete input is not a complete operating procedure. `workflows.discover` returns a draft based on visible event sequences, observed transitions, supporting evidence and questions about missing approval conditions and exceptions. Identical event replays are safe; conflicting reuse of an event key is rejected.

Observed order supports a process draft. It does not establish causality or required policy. If evidence is incomplete, the result remains incomplete. A discovery result never publishes itself.

## Wider onboarding design

Screen recordings, transcripts and cross-tool process correlation are planned extensions. The current release can ingest a supplied text transcript as a source, but does not transcribe video or reconstruct screen actions. A future recording adapter should preserve timestamped evidence and use this same review/version lifecycle.
