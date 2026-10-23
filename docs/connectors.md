# Connectors

New and changed document imports start restricted. Enroll/sign in to your human administrator account, inspect admin intake, and run admin classify SOURCE_ID for each source returned by ingest/sync before processing or using it as evidence. The wizard requires explicit private approval. Approved term/connector rules can classify subsequent imports; unmatched stays restricted. See [classification and conversational administration](conversational-administration.md).

A connector has a selected resource boundary, space, audience and authority. It captures source revisions through the same core APIs as manual ingestion. Registration that selects server filesystem paths is a local operator operation, not public RPC.

## Local directory

Create a private JSON file:

```json
{"root": "/absolute/path/to/selected-company-documents"}
```

Register and synchronize:

```bash
atmet-brain connector-add --space SPACE_ID --kind files --config /private/path/files.json --authority reference
atmet-brain sync CONNECTOR_ID
atmet-brain worker --space SPACE_ID
```

Only `.txt`, `.md`, `.json` and `.csv` files are accepted. Roots and imported files cannot be symlinks. Reads use descriptor-relative no-follow checks on supported POSIX systems, enforce size limits and detect changes during capture. Hidden supported files cause an explicit error; select a dedicated import directory. The snapshot limit is 500 accepted files of up to 200000 bytes each.

Changed files create revisions. Missing files are revoked from serving while retained content follows explicit erasure policy. A permanent tombstone prevents a replay from reviving that source. A failed scan does not revoke every prior source. Connector workers need explicit management/contribution grants for the binding and its configured authority in this first implementation.

## Check synchronization and changes

Use a dedicated selected directory and save the returned binding ID as CONNECTOR_ID. After the first sync, inspect imported source IDs and process jobs:

```bash
atmet-brain rpc connectors.list --params "{\"space_id\":\"$SALES_SPACE\"}"
atmet-brain rpc sources.list --params "{\"space_id\":\"$SALES_SPACE\"}"
atmet-brain rpc jobs.list --params "{\"space_id\":\"$SALES_SPACE\"}"
```

The SPACE_ID in the earlier registration example is your SALES_SPACE value. Edit an existing file in that selected directory, then run sync with the same CONNECTOR_ID and worker with the same space. The matching file becomes a new source revision, not a second independent document. Check sources.list and context again to verify the new state. Missing supported files are excluded from serving after a successful reconciliation.

To stop a binding deliberately:

```bash
atmet-brain rpc connectors.disable --params '{"connector_id":"CONNECTOR_ID"}'
```

Replace the ID. `serve` does not schedule synchronization: run sync explicitly or through an operator-managed scheduler. [Deployment](deployment.md) explains the separate API, sync and learning processes.

## Gmail labels

Create an operator-managed access token with an appropriate read scope through your approved Google account/application setup. The connector does not provide that login flow. Supply it through your private secret environment. For a private Bash session, the following reads it without echoing it or placing the value in the command text:

```bash
read -r -s ATMET_GMAIL_TOKEN
export ATMET_GMAIL_TOKEN
```

Paste the token at the waiting input and press Enter. Do not save it inside gmail.json. Restart/re-authorize the adapter through the operator process when that access token expires.

Binding configuration:

```json
{"token_env":"ATMET_GMAIL_TOKEN","label_ids":["YOUR_SELECTED_LABEL_ID"]}
```

```bash
atmet-brain connector-add --space SPACE_ID --kind gmail --config /private/path/gmail.json
atmet-brain sync CONNECTOR_ID
```

The adapter lists messages matching all selected label IDs, fetches their text and captures stable message IDs. It performs a bounded full reconciliation of up to 500 messages. Expired/denied authorization disables the binding. An incomplete provider snapshot fails rather than interpreting missing results as deletion.

The adapter does not send mail. It does not implement OAuth login, token refresh, webhooks, attachment extraction, cross-user mailbox ACL mapping or historical Gmail process reconstruction. Text/plain body parts are preferred; an HTML-only message falls back to the provider snippet and is incomplete evidence. Live Gmail account validation remains to be done.

## Future adapters

New adapters should return bounded records with stable IDs, titles, MIME and source text. Keep credentials outside business records, validate the complete snapshot before interpreting omissions, define update/delete/revocation behavior, and publish the provider's actual detection window. For large systems, implement durable cursors/history APIs rather than extending this bounded full-scan pattern indefinitely.

Do not infer source permissions from content. Use supported identity/ACL mapping or an explicit isolated audience. An app integration's ability to fetch a record does not authorize every company member to read it.
