# Connectors

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

## Gmail labels

Create an operator-managed access token with an appropriate read scope, then expose it privately:

```bash
export ATMET_GMAIL_TOKEN=your-private-access-token
```

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
