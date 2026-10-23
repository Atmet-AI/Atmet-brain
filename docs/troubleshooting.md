# Troubleshooting setup and use

Start with `atmet-brain --version`, `atmet-brain status` and, for a local installation, `atmet-brain doctor`. Check which `--home` or named `--connection` you selected. Global options go before a subcommand. Use fictional data while diagnosing a new installation.

| Problem | What to check and do |
| --- | --- |
| Command not found after npx | npx does not install a global command. Run the same arguments through `npx atmet-brain@latest`, or install globally as shown in [installation](install.md). Desktop clients can use generated absolute-path [MCP configuration](mcp.md). |
| First launch cannot install the runtime | Check Node 22.14+, supported OS/architecture, network access and standard tar. Bootstrap messages go to stderr. The launcher has no fallback to a different engine. See [runtime paths and overrides](../npm/atmet-brain/README.md). |
| setup says the Brain already exists | Use host to share the existing installation, or status/space to inspect it. Local setup and init are first-time provisioning, not login or upgrades. Choose a different empty --home for a separate example; do not delete company data to repeat setup. |
| The selected space or organization is wrong | List spaces using the intended home/connection and save the returned immutable ID. Space names do not grant access or automatically share department information. |
| Ingest succeeded but context has no learned fact | Run worker for the space and inspect jobs.list and memories.list. Ingest captures sources; learning is separate. The local extractor recognizes explicit ordinary Fact[key] markers; plain text is reference/observation material. See [learning](memory-and-learning.md). |
| A file edit is not reflected | For manual ingestion, keep its external ID and supply the current expected revision. For a connector, run sync for that binding and then the worker. Running serve alone does not sync apps. |
| An agent does not know a new workflow | Inspect its current artifact revision, publish the reviewed draft, and make sure the agent requests current context with that artifact/task path and its own credential. A chat alone does not write Brain records. |
| Context returns JSON instead of an answer | This is expected: the Brain supplies evidence and instructions. The external agent/runtime uses its own model to write an answer and separately authorized tools to act. |
| unauthenticated or forbidden | Check the credential file, expiry, issuer revocation and space/operation grants. Check source audiences too. Use an administrator to fix intended access; do not borrow an owner key or broaden a model prompt. |
| revision_conflict or idempotency_conflict | Read the current head. Use that head and a new request key for a new change. Reuse a key only for an identical retry. See [history](history-walkthrough.md). |
| dependency_changed or stale_evidence | Inspect the changed source/skill/policy version, prepare a compatible new proposal and obtain its exact review. Do not silently rewrite dependency pins. |
| incomplete_context | Required operating material may be inaccessible or too large for effective budgets. Check grants/audiences and [configuration](configuration.md); do not drop a required policy just to fit. |
| Remote CLI cannot connect | Check server health, trusted HTTPS/CA or administrator-configured SSH key/known host/forwarding account, saved profile and individual credential. Automatic SSH profiles manage the tunnel; legacy loopback profiles still need their own tunnel. Plaintext non-loopback HTTP and redirects are refused. See [team setup](team-server.md). |
| MCP connects but has fewer tools than expected | Tool opt-in flags and credential grants are separate. Proposal/automation flags expose tools but do not grant publish or external-action authority. Check [MCP](mcp.md). |
| Service stops after logout or cannot find Python | These are per-user services. Check login-session requirements and the persistent interpreter path. After an environment move/upgrade, remove and reinstall its managed definition. Actual OS lifecycle needs deployment validation. |
| Old version still runs | Use npx atmet-brain@latest --version or update the global install. A pinned version, old virtual environment or saved MCP executable continues to select that version. Regenerate saved configuration as needed. |

Share only redacted error codes, engine version and reproduction steps when asking for help. Keep token files, provider keys and real company sources private. For lost storage, use [encrypted recovery](backup-and-recovery.md); for one changed instruction, use [history](history-walkthrough.md).

## Host and Join problems

- **Host has no network route yet:** choose `later`, then run Host again after your administrator prepares SSH or HTTPS. A workspace called shared does not enable network access.
- **SSH forwarding failed:** have the administrator verify the destination, your key, trusted host key and forwarding-only account. Password-only access and untrusted host keys are not accepted by the automated route. No Brain request falls back to a public/plaintext address.
- **Connection file expired:** ask for current access. Editing the file's timestamp cannot extend the server credential.
- **Identity changed or file changed:** stop and obtain a current file from your administrator. Join refuses to save a mismatched identity.
- **Connection already exists:** choose another local connection name, or explicitly remove the old profile before reconnecting.
- **Workspace missing after Join:** the server's current grants and source audiences decide visibility. Ask the administrator to check your access; file labels do not grant it.
- **Background service already exists:** inspect/start it with `service status` / `service start`. Do not repeatedly reinstall or initialize the Brain.

## Task history and learned skills

- **History denied:** a reporting/worker credential does not automatically have history permission. Ask an authorized administrator for the required scoped operations and report/source audience access.
- **Report absent from ordinary search:** use task-history or task-get. Raw reports intentionally stay separate from ordinary company retrieval.
- **Report key conflict:** retry the exact same request or submit a new immutable follow-up key. The old body is not overwritten.
- **No method to learn:** choose the same task key in one space and include a succeeded/corrected report with explicit steps. Failed-only outcomes do not establish a method.
- **Stale evidence or review:** inspect current source/artifact revisions and submit a new report or reviewed draft. Reported historical results do not authorize an obsolete procedure.
- **Schema mismatch after upgrade:** stop old processes, use the schema-2 engine and restart services using its runtime. Backups restore to fresh homes; there is no in-place downgrade. See [schema upgrades](versioning.md#schema-2-upgrade).

## A task finished but feedback is missing

Enable the agent's host completion hook or MCP --task-feedback configuration. A running Brain alone cannot observe unrelated agents. MCP clients must follow the supplied completion instructions. Inspect delivery errors and both report/skill statuses; blocked drafting may still mean the report was saved. Retry the same key/payload instead of repeating the business task. Check original evidence, read/observe/contribute/history grants, audience access and credential expiry. A default-private report must be deliberately shared with its publisher for review. [Integration and retry guide](automatic-task-feedback.md).

## Agent setup cannot finish

Run agent interactively, or provide name/method/spaces/access/identity flags with --json. A missing local Brain needs setup first; a team server can be selected through Join. Guided setup requires engine 0.6.0+ at both ends. Read credentials cannot choose learning mode, and non-administrators cannot create a separate service identity. Current-identity mode derives a narrower child only. Existing folders/profiles are protected. On partial failure, read the revocation result before choosing a new setup name. [Wizard steps and recovery](agent-setup.md).

## Setup says already_initialized

The selected data home already contains a Brain. In 0.6.1+, run `npx atmet-brain@latest setup`, choose local, then reuse to open it. The wizard checks before asking company details. Choose new only when you want an independent company Brain in a fresh data directory; the existing Brain stays intact. Cancellation changes nothing.

To add Marketing to the existing company, run `npx atmet-brain@latest space marketing`. To inspect its company identity and spaces, run status and space. For a custom data location, pass the same --home before each command. Do not delete the database or owner token to get past setup. Explicit organization/owner/spaces creation flags against an existing home are rejected with these recovery choices.
