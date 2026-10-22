# Identity and permissions

The core authorizes each operation before it returns content. A client supplies a credential; it cannot supply its own privileged identity.

## Principals and credentials

Humans and services have separate principals. A credential resolves to a principal and can narrow operations, spaces and expiry. Tokens are random and only their hashes are stored. Current database state is checked on each call, including parent credentials. A child cannot widen or outlive its issuer; revoking an issuer invalidates its descendants.

An app using one shared key is acting as that service. Passing `user=CEO`, a role header or a person's name in a prompt does not authenticate that person. Per-user login, company SSO and delegated user tokens are planned identity adapters; this release uses scoped bearer credentials.

## Grant levels

| Operation | Meaning |
| --- | --- |
| `read` | Read permitted source and approved context |
| `contribute` | Capture information or submit proposals |
| `observe` | Record evidence-linked process events or task outcomes |
| `review` | Review ordinary extracted memory |
| `publish` | Approve, reject or retire operating artifacts |
| `history` | Inspect retained revisions and audit metadata |
| `manage` | Manage permitted space grants and bindings |
| `process` | Run learning jobs or approved bounded pure Python recipes under current rights |
| `erase` | Erase source content and dependent logical data |

Organization administration controls membership and space provisioning. It does not bypass a space's content grants. The creator of a new space receives an explicit owner grant. A manager can delegate only operations they themselves possess in that space.

The CLI includes reader, contributor, reviewer, publisher, worker and owner role presets. Roles are convenient collections of explicit operations, not special bypass paths.

## Source audiences

Sources and artifacts accept selectors:

```json
["space"]
```

or:

```json
["principal:PRINCIPAL_ID", "group:GROUP_ID"]
```

Selectors are alternatives within one resource. Across multiple contributing sources, every source must permit the caller. A combined summary cannot make a private source public. Source updates and history use the current audience, not an older audience stored with a prior revision.

The same checks apply to search, graph nodes and edges, lists, resources, exports and manifests. Required operating context that cannot be read returns `incomplete_context`; it is never silently omitted from a task envelope.

## Connector and action boundaries

A provider credential controls what a connector can fetch. The Brain binding controls which space receives it and its permitted audience. Gmail's mailbox credential is not automatic company-wide sharing authorization. This release requires an explicit audience for the selected mailbox labels and does not implement provider-to-company ACL mapping.

The Brain grants no email-send, shell, browser or business-record mutation authority. An execution runtime must enforce those actions independently. Skill scripts are stored as text resources and are never executed by the core.

An [automation artifact](automations.md) is distinct from an arbitrary skill script. Its exact template-compiled Python is reviewed and its pure data transformation runs in a fixed implementation with no external tools. `process` does not permit arbitrary code or side effects. MCP execution is additionally opt-in. Normal observation, publication, source access, history and recovery checks still apply.

## Local operator boundary

Database provisioning, server filesystem selection and backup/recovery are local owner operations outside public RPC. Someone who controls the machine and database files can alter the installation. API grants protect serving paths, not the host administrator.

Additional company organizations can be provisioned with `organization-add`. Each gets an independent owner token; a company credential cannot access another company by changing an ID.
