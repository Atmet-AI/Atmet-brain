# Python and REST API

All public operations pass an authenticated actor into the same core. Local provisioning, filesystem binding registration and backup/recovery remain installation-owner operations outside RPC.

## Python

```python
from pathlib import Path
from atmet_brain import Brain

brain = Brain("/private/path/to/brain-data")
actor = brain.authenticate(Path("/private/path/to/reader.token").read_text().strip())
result = brain.get_context(actor, "SPACE_ID", "Prepare a customer quotation")
```

The Python library assumes the caller is trusted with the local data home. For an untrusted client, use REST or MCP and never expose direct database/file access.

## REST

```bash
atmet-brain serve --host 127.0.0.1 --port 7310
```

Endpoints:

| Endpoint | Behavior |
| --- | --- |
| `GET /health` | Minimal health status without company data |
| `GET /openapi.json` | Generated public operation schemas |
| `GET /v1/me` | Current authenticated principal |
| `POST /v1/rpc` | Explicit public operation |

Use `Authorization: Bearer <scoped-token>` and `Content-Type: application/json`. The body has `method` and `params`:

```json
{
  "method": "context.get",
  "params": {
    "space_id": "SPACE_ID",
    "query": "Prepare a customer quotation",
    "artifact_ids": ["APPROVED_SKILL_ID"]
  }
}
```

The response has `result`. Failures have `error.code` and `error.message` with an HTTP status. Important errors include `unauthenticated` (401), `forbidden` (403), `not_found` (404), `revision_conflict` (409), `stale_evidence` (409), `dependency_changed` (409) and `incomplete_context` (409).

Use [the Python HTTP client](../examples/rest_client.py) to read a private token file without placing it in a URL. The local reference server rejects browser-origin requests and limits request sizes. Non-loopback deployment requires an explicit network flag and trusted private ingress. It does not supply TLS, SSO or a public production gateway.

## Call the same operation from the terminal

For CLI RPC, supply only the inner params object. With SALES_SPACE set to a space ID you may read:

```bash
cat > context-params.json <<JSON
{"space_id":"$SALES_SPACE","query":"What are the support hours?"}
JSON
atmet-brain rpc identity.me
atmet-brain rpc context.get --params @context-params.json
```

These commands use the selected home's owner credential unless you supply a dedicated token file or saved remote connection. The result is the same operation payload exposed by REST, without its outer result wrapper. Unknown methods/parameters are rejected. [Troubleshooting](troubleshooting.md) explains common error codes.

## Read REST without a source checkout

Start serve in one terminal. In another, use a dedicated [scoped reader credential](permissions.md), set ATMET_TOKEN_FILE to its absolute file path and save the following as reader.py. This client uses standard Python 3 libraries and does not require importing the Brain package:

```python
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

token = Path(os.environ["ATMET_TOKEN_FILE"]).read_text().strip()
request = Request(
    "http://127.0.0.1:7310/v1/rpc",
    data=json.dumps({"method": "identity.me", "params": {}}).encode(),
    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
)
with urlopen(request, timeout=10) as response:
    print(json.load(response))
```

Run it from a terminal with Python 3 available:

```bash
export ATMET_TOKEN_FILE="/absolute/path/to/scoped-reader.token"
python3 reader.py
```

The result identifies that credential's current principal. The token is read from a file and is not printed or placed in a URL. For remote use, select the administrator's trusted HTTPS endpoint as described in [team setup](team-server.md). Only a trusted local Python application should instantiate Brain directly; an untrusted agent should use an authenticated interface.

## Operation groups

| Group | Methods |
| --- | --- |
| Identity | `team.add`, `identity.me`, `principals.create`, `credentials.create`, `credentials.revoke` |
| Scope | `spaces.list`, `spaces.create`, `grants.create`, `grants.revoke`, `groups.create`, `groups.remove_member` |
| Sources | `sources.put`, `sources.get`, `sources.list`, `sources.access`, `sources.erase` |
| Memory | `memories.propose`, `memories.review`, `memories.list` |
| Artifacts | `artifacts.propose`, `artifacts.review`, `artifacts.get`, `artifacts.list`, `artifacts.history`, `artifacts.rollback`, `artifacts.retire`, `artifacts.diff` |
| Context | `search`, `context.get`, `context.manifest`, `skills.resource`, `graph.get` |
| Learning | `jobs.list`, `jobs.run`, `jobs.retry` |
| Discovery | `events.record`, `workflows.discover` |
| Repeated tasks | `tasks.record`, `tasks.runs`, `automations.discover`, `tasks.route`, `tasks.run` |
| Connectors | `connectors.list`, `connectors.disable`, `connectors.sync` |
| Inspection | `audit.list`, `space.export` |

The generated [OpenAPI schema](openapi.json) lists exact required and optional parameters. Unknown parameters, including `actor`, private connector injectors and custom extractor objects, are rejected by the RPC registry. Runtime checks also validate types and permissions.

## A reviewed update

Submit:

```json
{
  "method": "artifacts.propose",
  "params": {
    "space_id": "SPACE_ID",
    "kind": "policy",
    "name": "quotation-approval",
    "body": {"instructions": "Obtain manager approval before sending."},
    "expected_revision": 0,
    "reason": "Initial reviewed procedure",
    "idempotency_key": "company-quotation-policy-initial"
  }
}
```

Then publish the returned ID and revision through `artifacts.review` with `approve=true` and a reason. An update to an existing artifact also includes its `artifact_id` and current head revision. Dependencies and evidence must remain accessible and current.

Credentials and grants are separate. Minting a key does not create a space grant. Issued raw tokens are returned once to an explicitly authorized caller; store them privately and keep them out of logs.

## Export

`space.export` returns the current permitted sources, memories and approved artifact bodies. It excludes raw credentials, installation state and a complete operational recovery set. It is not a backup. This release does not implement automatic cross-installation import or identity/ID remapping; use the backup process for installation recovery.

## Private remote clients

The CLI can save verified HTTPS, automatic SSH or manual SSH-loopback connections and call the same operations using `--connection NAME`. `team.add` atomically creates an individual non-admin identity, chosen space/role grants and a narrowed expiring credential; prefer `team-add --output FILE` to keep the returned token out of terminal output. Connection profiles are not grants. See [terminal usage](terminal.md) and [team server](team-server.md).

## Task outcomes and learned skills

reports.record saves an explicit, immutable client-reported result with original source evidence. reports.search and reports.get read permitted history; reports.erase clears a report through the existing source-erasure journal. skills.learn assembles a pending skill from selected reports and delegates publication to artifacts.review. All operations use the existing RPC envelope and authorization. [Task-report examples](task-history-and-learning.md) define required fields, privacy, bounds and revision behavior. No caller identity or role field is accepted from the model.

## Completion feedback

`reports.complete` accepts the reports.record parameters plus a boolean learn (default true). It saves an authenticated report, then attempts one deterministic pending candidate from eligible succeeded/corrected steps. It returns separate report/skill statuses; drafting can be blocked after the report commits. Exact retries reuse both identities, recheck access and never republish or overwrite an approved method. No caller-supplied identity or approval is accepted. `Client.task_feedback()` and `LocalClient.task_feedback()` provide Python lifecycle wrappers. [Integration and response contract](automatic-task-feedback.md).
