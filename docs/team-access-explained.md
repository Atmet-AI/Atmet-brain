# Team access, identity and private information

One company Brain runs on a controlled host. Employees enroll with private single-use invitations, choose passwords and connect with separate scoped sessions. Services can keep dedicated API credentials. [Exact login/company steps](employee-accounts.md). Its company ID identifies the organization, workspace grants select permitted areas, operation grants select permitted actions, and source audiences can narrow individual information. These checks run in the core; a prompt or folder name cannot grant access.

## Open the existing Brain

Run `npx atmet-brain@latest setup` and select local. If a Brain exists, choose reuse, new or cancel before company questions. Reuse opens the current company; new requires an unused private directory for an independent Brain. Both keep the existing owner/data. For multiple companies, use brains create/add and explicit --brain selection, with a separate data home per company. For a new department use `npx atmet-brain@latest space marketing`, with the same --home if customized. Do not repeat initialization or delete a database to add a department.

## Grant the spaces someone needs

A workspace is a permission boundary, not a mandatory department mapping. An Operations employee assigned only operations cannot read finance or shared automatically. Assign each space deliberately. The current team-add/Host presets use one chosen role across selected spaces; different operations by space use explicit grants and appropriately scoped credentials. A grant alone cannot widen a credential's allowed spaces/operations. Existing restricted credentials may need deliberate replacement when adding spaces.

For a simple Finance/payroll setup:

| Workspace | Operations | Finance | Authorized administrator |
| --- | --- | --- | --- |
| shared | Read if granted | Read if granted | Explicit appropriate grant |
| operations | Appropriate grant | Only if needed | Explicit appropriate grant |
| finance-general | Read | Appropriate grant | Explicit appropriate grant |
| payroll | No grant | Appropriate grant | Explicit appropriate grant |

Import ordinary invoices/budgets into finance-general and salary originals into payroll. The default source audience follows the selected space's permitted readers; you do not configure every employee on every file. Selected-directory connectors can apply a chosen destination and audience to a collection. Naming a folder payroll does not establish access controls or automatically choose its import destination.

If using a single finance workspace, general sources can use ["space"], while salary sources use the Finance/admin group IDs as alternatives, for example ["group:FINANCE_GROUP_ID", "group:ADMIN_GROUP_ID"]. Do not add space to that restricted audience: it would admit other permitted readers of the space. Group membership does not replace workspace/operation grants. Admin status itself is not a content bypass. Mixed-access documents must be separated; the core does not automatically hide salary rows or fields. Current audiences restrict derived content and retained-history reads too. The [permission reference](permissions.md) covers selectors and operations.

## Join from another IP address

Different employee IPs are fine if they can reach the company's configured trusted HTTPS ingress or restricted SSH host. A private LAN address is not normally reachable from the public internet. Prepare a company VPN/private route or an appropriately administered internet-reachable HTTPS/SSH endpoint. An ID cannot bypass routing, firewall or certificate trust.

On the host run `npx atmet-brain@latest host`, select that route and create a private single-use account invitation for each intended teammate with only their required workspaces/role. Use team for a different role in each workspace. Host offers explicit background API service setup; keep the host awake and reachable. On the employee device run `npx atmet-brain@latest join` with their file, then `npx atmet-brain@latest --connection company agent` to configure their agent. Join verifies the actual server identity and permitted spaces. The company database is not copied. [Exact Host/Join steps](team-server.md).

## How authentication works today

An administrator approves a company-local account username and memberships, then privately hands its intended recipient an expiring single-use invitation. The employee chooses a password. The server stores a salted scrypt verifier and issues 12-hour opaque sessions after password authentication. Account usernames are company-specific; an email-shaped login does not verify its mailbox. Clients keep a private session credential, not the password.

Every request checks the resolved principal, current grants, credential expiry/lineage and source audiences. Permission changes revoke current credentials; the employee signs in again to receive the reviewed scope. Logout revokes the selected session; password change revokes all that principal's credentials. The terminal team menu handles access, disabling and reset invitations. [Daily commands and recovery](employee-accounts.md).

Services and explicit legacy .atmet-join.json files still use individually issued bearer keys. A copied key/session can act as its principal until expiry/revocation if it can reach the server. Use separate users/services and protect their devices. A shared Finance service key cannot identify which employee is speaking to that service. Returned data cannot be withdrawn from another application's existing copies.

SSO, MFA, browser login, verified email delivery and a trusted identity-provider on-behalf-of-user adapter are not implemented. The server filesystem owner remains trusted. No prompt-supplied name, role or company number grants access.

## Company ID versus invitation and login

The Brain already has an organization ID, but it is an identifier, not an address or password. A device cannot discover an arbitrary private company server from numbers alone. That needs a directory/resolver or an administrator-provided server address; globally resolving arbitrary company IDs is not implemented.

The current flow uses an administrator-provided address in a private invitation, password enrollment and approved memberships. Global numeric discovery is separate future work. A public company number would locate the organization only. A short code granting access needs its own secure expiry, attempt limits and recipient verification. Legacy .atmet-join.json files are reusable bearer credentials. New .atmet-invite.json enrollment files are expiring and single-use. No discovery or SSO service is silently enabled.

The core's scoped credentials and audiences are implemented; detailed group/document administration still uses CLI/API. The terminal employee/workspace-role editor is available; a graphical document-policy editor remains future UI work.
