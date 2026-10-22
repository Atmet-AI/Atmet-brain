# Workflows and automatic discovery

A workflow contains a trigger, required inputs, steps, exceptions, expected outputs and instructions. A step may use a skill pinned as an artifact dependency.

Example body:

```json
{
  "description": "Prepare and review a customer quotation",
  "instructions": "Use the applicable approved pricing and approval policy.",
  "trigger": "Customer requests a quotation",
  "inputs": ["Customer", "Items", "Quantities"],
  "outputs": ["Reviewed quotation draft"],
  "steps": [
    {"id": "collect", "instruction": "Check the requested items and missing fields."},
    {"id": "draft", "instruction": "Prepare the quotation from current pricing."},
    {"id": "review", "instruction": "Obtain the approvals required by current policy."}
  ],
  "exceptions": ["Missing prices require clarification."]
}
```

Submit this body through `artifacts.propose`, then publish the exact reviewed revision through `artifacts.review`. If a step includes `skill_id`, include that skill's exact approved revision in `dependencies`.

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

Call `workflows.discover` with the space ID. It returns a draft based on visible event sequences, observed transitions, supporting evidence and questions about missing approval conditions and exceptions. Identical event replays are safe; conflicting reuse of an event key is rejected.

Observed order supports a process draft. It does not establish causality or required policy. If evidence is incomplete, the result remains incomplete. A discovery result never publishes itself.

## Wider onboarding design

Screen recordings, transcripts and cross-tool process correlation are planned extensions. The current release can ingest a supplied text transcript as a source, but does not transcribe video or reconstruct screen actions. A future recording adapter should preserve timestamped evidence and use this same review/version lifecycle.
