# Identity and permissions

For employees, use the [company login/invitation and permission walkthrough](employee-accounts.md). Run team to select an employee by name, choose allowed workspaces and a role for each, and review the change. Applying it revokes their existing credentials; they sign in again for the new scope. Interactive Host defaults to a single-use password invitation. Legacy service/key commands below remain available for integrations.

The core authorizes each operation before it returns content. A client supplies a credential; it cannot supply its own privileged identity.

## Choose a practical access structure

A workspace is an explicit scope, not necessarily one department. Grant someone every space they need; no other department or shared space is automatically included. A simple payroll arrangement uses finance-general for Operations/Finance and payroll for Finance/authorized administrators. New imports remain restricted until classification; after release the chosen space audience is the default base, so ordinary setup does not need per-person rules for each file. Selected-directory connectors can apply an explicit target space/audience to a batch. Avoid importing confidential originals into broader spaces.

Alternatively keep one Finance workspace and restrict payroll source audiences to Finance and explicitly authorized admin groups. A document's group membership still requires space/operation permission. There is no automatic row/column salary redaction, folder ACL inheritance or implicit classification from a filename. Keep mixed-access information in separate sources. Groups create no space grants by themselves.

Current authentication proves possession of a credential bound to a principal. A display name or company ID does not verify a human, and a shared service credential does not identify each employee using it. Company-local password login is implemented, with private single-use enrollment and expiring sessions. SSO/MFA, email verification and identity-provider delegation are not implemented. [Worked team example and current limits](team-access-explained.md).

## Give a reader access and verify it

An administrator first initializes the company and creates its spaces through [setup](quickstart.md). Save a permitted Sales ID as SALES_SPACE. Create a separate expiring reader credential:

```bash
atmet-brain team-add "Sales reader" --space "$SALES_SPACE" --role reader --output "$HOME/.atmet-brain/sales-reader.token"
atmet-brain --token-file "$HOME/.atmet-brain/sales-reader.token" rpc identity.me
atmet-brain --token-file "$HOME/.atmet-brain/sales-reader.token" space
atmet-brain --token-file "$HOME/.atmet-brain/sales-reader.token" context "What are the support hours?" --space "$SALES_SPACE"
```

Use a new private output path if that file already exists, and adapt the path for a custom data home. `team-add` prints the principal, credential ID, scope and saved file location instead of the raw key. Save the credential ID for revocation. The reader can retrieve permitted Sales information, but cannot ingest documents, publish procedures or access Finance without further grants. Source audiences can narrow this access further.

Test a known Finance ID with that reader: the request should be denied. For an agent, use `--kind service` and choose a role/scope deliberately. The [company walkthrough](use-for-your-company.md) shows a narrower read/contribute service credential; [team setup](team-server.md) covers secure delivery and remote access.

As the administrator, revoke the returned credential ID when it should no longer work:

```bash
atmet-brain rpc credentials.revoke --params '{"credential_id":"CREDENTIAL_ID"}'
```

Replace CREDENTIAL_ID with the issued ID. The next request using that file is denied even if the client already authenticated earlier. Removing a local connection file is not server-side revocation.

## Principals and credentials

Humans and services have separate principals. A credential resolves to a principal and can narrow operations, spaces and expiry. Tokens are random and only their hashes are stored. Current database state is checked on each call, including parent credentials. A child cannot widen or outlive its issuer; revoking an issuer invalidates its descendants.

An app using one shared key is acting as that service. Passing `user=CEO`, a role header or a person's name in a prompt does not authenticate that person. Password login binds a company-local account to its principal and issues a bounded session. SSO and trusted delegated user tokens remain planned adapters. An email-shaped username is not proof of mailbox ownership.

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

The CLI includes reader, contributor, reporter, reviewer, publisher, worker and owner role presets. Roles are convenient collections of explicit operations, not special bypass paths.

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

Use brains create/add and --brain for independent company data homes. The low-level organization-add command also remains available within a single installation. Each gets an independent owner token; a company credential cannot access another company by changing an ID.

## Task reporting and learning

Task reporting requires read/observe/contribute. Reading/searching reports requires read/history and current access to the report plus original evidence. Learning a draft additionally requires contribute. Publication keeps the existing publish operation and exact-revision review; reporting/learning does not grant it. Reports default to their submitting principal's audience; explicitly choose a department audience when sharing is intended. [Full workflow and grant requirements](task-history-and-learning.md#permissions-and-agent-integration).

The reporter preset combines read/observe/contribute/history for completion feedback. It does not include publish, erase, manage or process. Use it for an individually attributable service agent, and deliberately share reports with the authorized publisher when review is wanted. The [automatic feedback guide](automatic-task-feedback.md) explains setup, inherited audiences and partial failures.

## Guided agent credentials

`atmet-brain agent` restricts generated credentials to reader or reporter operations and selected spaces. An administrator may create a separate service; another caller may derive a narrower child for their current identity. It verifies current access before issuance and never includes publish/manage/erase/process. An explicit --token-file takes precedence over an ambient ATMET_TOKEN; saved connections use their own credential. See [agent setup](agent-setup.md).

For rule-based future imports and exact human approvals, see [conversational administration](conversational-administration.md). Reader/User/Editor are everyday presets; company administration is separate. Keyword/model suggestions do not provide perfect salary detection.

## Renaming departments and inspecting drafts

Use spaces.rename with space_id, name and expected_name. The caller needs company administration and current workspace management; IDs, source bindings and grants remain unchanged. A stale name or duplicate slug fails.

artifacts.list normally returns approved effective versions. Explicit include_pending true requires history plus contribute/review/publish and keeps audience/evidence checks. It lists current head state for review without making a draft available to ordinary agent context.
