# Report tasks and learn reusable skills

New and changed document imports start restricted. Enroll/sign in to your human administrator account, inspect admin intake, and run admin classify SOURCE_ID for each source returned by ingest/sync before processing or using it as evidence. The wizard requires explicit private approval. Approved term/connector rules can classify subsequent imports; unmatched stays restricted. See [classification and conversational administration](conversational-administration.md).

Atmet Brain can retain selected task outcomes, search them and assemble a skill draft from their steps and corrections. Configure [automatic task feedback](automatic-task-feedback.md) once for agent completion hooks or MCP completion instructions. The manual CLI, REST and MCP operations below remain useful for inspection and selected reporting. The Brain does not automatically observe external conversations, verify business success or run the reported steps.

Reports are operational history, separate from ordinary document search and approved instructions. A report defaults to the submitting principal's private audience. Choose a department audience deliberately when its members should be able to learn from that work. Every read also checks access to all cited original source evidence.

## Before you start

Use engine 0.4.0 or newer and a Brain where you have the required permissions. The example uses a disposable fictional company and its owner credential. In a real company, issue individual scoped credentials instead.

Schema 2 adds report records and marks their evidence sources separately. Opening a schema-1 Brain upgrades it transactionally and preserves existing identities, sources and artifacts. Back up the installation and independent recovery journal before upgrading; older engines cannot open schema 2. Schema-1 encrypted snapshots can be restored into a new home and upgraded before recovery quarantine. There is no in-place downgrade.

## 1. Prepare a fictional source

These commands use a persistent installed `atmet-brain` CLI. You can substitute `npx atmet-brain@latest` before the same arguments.

```bash
export TASK_DEMO="$(mktemp -d)"
export ATMET_HOME="$TASK_DEMO/brain"
cd "$TASK_DEMO"
atmet-brain setup --mode local --organization example-company --spaces sales
atmet-brain space
```

Copy the returned Sales ID, then ingest a source:

```bash
export SALES_SPACE="PASTE_SALES_SPACE_ID"
printf '%s\n' 'Example catalogue: confirm current item prices before preparing a quotation.' > catalogue.md
atmet-brain ingest catalogue.md --space "$SALES_SPACE"
```

Copy the returned source ID. Its revision is 1 in this fresh example.

## 2. Report the task result

```bash
export SOURCE_ID="PASTE_SOURCE_ID"
cat > task-report.json <<JSON
{
  "report_key": "quotation-example-1",
  "task_key": "prepare-quotation",
  "summary": "Prepared a customer quotation draft",
  "outcome": "corrected",
  "result": "The revised draft used the customer-specific template.",
  "steps": ["Read the current catalogue", "Prepare the quotation draft"],
  "corrections": ["Check whether the customer requires a specific template"],
  "checks": ["Prices match the permitted current source", "Required approvals are identified"],
  "evidence": [{"source_id":"$SOURCE_ID","revision":1}],
  "audience": ["space"]
}
JSON
atmet-brain task-report task-report.json --space "$SALES_SPACE"
```

The returned report ID identifies an immutable report. `recorded_by` and the credential ID come from authentication, not model-supplied names. `outcome` can be `succeeded`, `failed` or `corrected`; all are client-reported, with `outcome_verified=false`. Original evidence is required and must be current when first recording. Task reports cannot cite one another as original business evidence.

Omit audience to make the report private to its submitting principal. `["space"]` allows eligible members of this workspace; source audiences can narrow that further. Group/principal selectors use the existing permission model. The integration must supply complete provenance. Brain validates supplied references and permissions; it cannot detect an undisclosed dependency on other sources or external data. Do not submit credentials or unnecessary conversation logs. No automatic secret-removal or external transcript-capture guarantee is provided.

A report key is unique for its authenticated reporter within a space. Retrying the exact request acknowledges the same report; different content under that key is a conflict. Only a hash of the report key is retained. Use a new key for a corrected follow-up, preserving the original history. Replays recheck current access and cannot restore erased reports.

## 3. Search and inspect history

```bash
export REPORT_ID="PASTE_REPORT_ID"
atmet-brain task-history "quotation template" --space "$SALES_SPACE"
atmet-brain task-history --space "$SALES_SPACE" --task-key prepare-quotation --limit 10
atmet-brain task-get "$REPORT_ID"
```

An empty query lists recent permitted reports. Search matches task labels, summaries, results, steps, corrections and checks using lexical ranking. It filters current permissions/evidence audiences before returning results. It does not provide semantic/vector search or a full conversation archive. Results contain summaries and IDs; task-get returns the complete bounded report and evidence.

Raw reports are excluded from ordinary search, context reference snippets, source listings and space exports. Direct source-body access to a report also requires history permission. Approved learned methods can be retrieved normally if all contributing evidence remains readable.

## 4. Create a skill draft

```bash
atmet-brain task-learn --space "$SALES_SPACE" --report "$REPORT_ID" --name prepare-quotation --idempotency-key quotation-skill-1
```

This assembles a pending skill from explicit reported approaches, corrections and checks. It makes zero model calls. Select up to 10 reports for the same task key in one space by repeating `--report`. At least one succeeded/corrected report must provide steps. Failed reports can contribute explicit corrections, but failed-only reports cannot establish a method. Keep the combined evidence within the existing 50-source budget and the skill size limits.

The compiler preserves reported alternatives for review; it does not independently generalize arbitrary transcripts, resolve contradictory business rules or prove that a method works. Inspect applicability, required tools and approvals, source evidence and actual outcomes. The draft includes a non-executable references/task-evidence.json resource linking its report IDs.

## 5. Inspect, approve and retrieve the method

```bash
export SKILL_ID="PASTE_SKILL_ARTIFACT_ID"
atmet-brain rpc artifacts.get --params "{\"artifact_id\":\"$SKILL_ID\",\"revision\":1}"
atmet-brain review "$SKILL_ID" --revision 1 --approve --reason "Reviewed the method, evidence, checks and required approvals"
atmet-brain context "Prepare a quotation" --space "$SALES_SPACE" --artifact "$SKILL_ID"
```

Publication is the existing authorized exact-revision review operation. Reporting and learning do not publish, execute scripts or grant tools. A new report does not silently modify an approved method.

To propose a revision of the same skill, use its current head revision:

```bash
atmet-brain task-learn --space "$SALES_SPACE" --report "$REPORT_ID" --name prepare-quotation --artifact-id "$SKILL_ID" --expected-revision 1 --idempotency-key quotation-skill-2
```

Inspect revision 2 and review it separately. If another draft changed the head, reload before retrying. Use `--task-path departments/sales/quotations` for a new task-scoped method; an existing artifact's path and audience remain fixed. API users can choose an explicit audience when creating the artifact; contributing report/source audiences always remain additional restrictions. [Skill lifecycle](skills.md) and [history](history-walkthrough.md) explain inspection, comparison and rollback.

## Permissions and agent integration

| Action | Required space operations |
| --- | --- |
| Record a report | read, observe, contribute |
| Search/read task history | read, history |
| Learn a skill draft | read, history, contribute |
| Publish a skill | publish plus current evidence/dependency access |
| Erase through task-erase | read, history, erase plus source audience access |

Credentials, grants, source audiences, expiry and revocation all apply. A department membership or tool switch alone grants no additional access. The existing worker role can report but lacks history; the reporter role provides read/observe/contribute/history for a reporting/learning agent. For example, an authorized administrator can use grants.create with read/observe/contribute/history, then mint an individually scoped credential. Keep publish/erase separate where appropriate. The core does not require a different person to approve their own draft; publication is a separate explicit permission/operation.

REST operations are reports.complete, reports.record, reports.get, reports.search, reports.erase and skills.learn on /v1/rpc. CLI remote commands use the same core:

```bash
atmet-brain --connection company task-history "quotation" --space SPACE_ID
atmet-brain --connection company task-report task-report.json --space SPACE_ID
```

For MCP, generate a configuration with explicit reporting/proposal tools:

```bash
atmet-brain --connection company mcp-config --allow-task-reports --allow-proposals
```

A default MCP server exposes brain_search_task_history and brain_get_task_report, with underlying history grants still required. --allow-task-reports adds brain_report_task; --allow-proposals adds brain_learn_skill. No publication or erasure tool is added. These switches expose tools, not permissions. For local MCP configuration, provide a dedicated scoped --token-file instead of --connection. No named external agent integration is certified by these generic interfaces.

Configure your agent to report only selected completed tasks or useful failures/corrections, supply the original sources it actually used, and request a skill draft when a reusable method is plausible. Ask a publisher to review it. A completion hook can submit this selected result automatically; MCP completion instructions depend on the client following them. Neither path records every conversation.

## Changes, erasure and recovery

- Source updates preserve inspectable report history while blocking learning/publication from stale evidence. Approved learned skills become unavailable through normal current-evidence checks until revalidated through a new proposal.
- Narrowed source/report audiences or revoked source access immediately restrict reports and derived methods. Revoking a caller's credential blocks their next request; it does not erase everyone else's retained reports.
- `atmet-brain task-erase REPORT_ID` clears the report body and task label, preserves minimal attribution/hash tombstones and retracts dependent skill bodies. Erasing original source evidence also clears dependent report payloads and methods. No report-body text is stored in audit events.
- Encrypted whole-installation backups include task history. Portable space exports do not include raw reports. Recovery replays the existing source-erasure journal before reauthorization, including later report/source erasures. Previously exported client files and retained encrypted snapshots require their own retention handling.
- Reports are retained until explicitly erased; this release has no automatic age-based purge or background learning scheduler. It adds no general script runner or external business actions.

For the pre-upgrade snapshot, use your currently installed schema-1-compatible engine. If using npx, pin atmet-brain@0.3.1 for those backup/journal commands rather than @latest. The first 0.4.0 command that opens an existing Brain already performs the migration. Follow the [backup procedure](backup-and-recovery.md) before that first open; use a fresh home when restoring an older snapshot.
