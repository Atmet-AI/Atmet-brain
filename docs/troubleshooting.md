# Troubleshooting setup and use

Start with `atmet-brain --version`, `atmet-brain status` and, for a local installation, `atmet-brain doctor`. Check which `--home` or named `--connection` you selected. Global options go before a subcommand. Use fictional data while diagnosing a new installation.

| Problem | What to check and do |
| --- | --- |
| Command not found after npx | npx does not install a global command. Run the same arguments through `npx atmet-brain@latest`, or install globally as shown in [installation](install.md). Desktop clients can use generated absolute-path [MCP configuration](mcp.md). |
| First launch cannot install the runtime | Check Node 22.14+, supported OS/architecture, network access and standard tar. Bootstrap messages go to stderr. The launcher has no fallback to a different engine. See [runtime paths and overrides](../npm/atmet-brain/README.md). |
| setup says the Brain already exists | Reuse the existing installation with status/space. setup and init are first-time provisioning, not login or upgrades. Choose a different empty --home for a separate example; do not delete company data to repeat setup. |
| The selected space or organization is wrong | List spaces using the intended home/connection and save the returned immutable ID. Space names do not grant access or automatically share department information. |
| Ingest succeeded but context has no learned fact | Run worker for the space and inspect jobs.list and memories.list. Ingest captures sources; learning is separate. The local extractor recognizes explicit ordinary Fact[key] markers; plain text is reference/observation material. See [learning](memory-and-learning.md). |
| A file edit is not reflected | For manual ingestion, keep its external ID and supply the current expected revision. For a connector, run sync for that binding and then the worker. Running serve alone does not sync apps. |
| An agent does not know a new workflow | Inspect its current artifact revision, publish the reviewed draft, and make sure the agent requests current context with that artifact/task path and its own credential. A chat alone does not write Brain records. |
| Context returns JSON instead of an answer | This is expected: the Brain supplies evidence and instructions. The external agent/runtime uses its own model to write an answer and separately authorized tools to act. |
| unauthenticated or forbidden | Check the credential file, expiry, issuer revocation and space/operation grants. Check source audiences too. Use an administrator to fix intended access; do not borrow an owner key or broaden a model prompt. |
| revision_conflict or idempotency_conflict | Read the current head. Use that head and a new request key for a new change. Reuse a key only for an identical retry. See [history](history-walkthrough.md). |
| dependency_changed or stale_evidence | Inspect the changed source/skill/policy version, prepare a compatible new proposal and obtain its exact review. Do not silently rewrite dependency pins. |
| incomplete_context | Required operating material may be inaccessible or too large for effective budgets. Check grants/audiences and [configuration](configuration.md); do not drop a required policy just to fit. |
| Remote CLI cannot connect | Check server health, the private HTTPS route or active restricted SSH tunnel, trusted CA, saved profile and individual credential. Plaintext non-loopback HTTP and redirects are refused. See [team setup](team-server.md). |
| MCP connects but has fewer tools than expected | Tool opt-in flags and credential grants are separate. Proposal/automation flags expose tools but do not grant publish or external-action authority. Check [MCP](mcp.md). |
| Service stops after logout or cannot find Python | These are per-user services. Check login-session requirements and the persistent interpreter path. After an environment move/upgrade, remove and reinstall its managed definition. Actual OS lifecycle needs deployment validation. |
| Old version still runs | Use npx atmet-brain@latest --version or update the global install. A pinned version, old virtual environment or saved MCP executable continues to select that version. Regenerate saved configuration as needed. |

Share only redacted error codes, engine version and reproduction steps when asking for help. Keep token files, provider keys and real company sources private. For lost storage, use [encrypted recovery](backup-and-recovery.md); for one changed instruction, use [history](history-walkthrough.md).
