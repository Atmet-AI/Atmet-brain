# Team access, identity and private information

One company Brain runs on a controlled host. People connect with separate credentials. Its company ID identifies the organization, workspace grants select permitted areas, operation grants select permitted actions, and source audiences can narrow individual information. These checks run in the core; a prompt or folder name cannot grant access.

## Open the existing Brain

Run `npx atmet-brain@latest setup` and select local. If a Brain exists, choose reuse, new or cancel before company questions. Reuse opens the current company; new requires an unused private directory for an independent Brain. Both keep the existing owner/data. For a new department use `npx atmet-brain@latest space marketing`, with the same --home if customized. Do not repeat initialization or delete a database to add a department.

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

On the host run `npx atmet-brain@latest host`, select that route and create a separate private connection file for each intended teammate with only their required workspaces/role. Host offers explicit background API service setup; keep the host awake and reachable. On the employee device run `npx atmet-brain@latest join` with their file, then `npx atmet-brain@latest --connection company agent` to configure their agent. Join verifies the actual server identity and permitted spaces. The company database is not copied. [Exact Host/Join steps](team-server.md).

## How authentication works today

An administrator creates a separate human or service principal and issues a random scoped credential. The private connection file contains that credential. The server stores its hash and uses the credential on each request to resolve the principal, scope, expiry, current grants and revocation. SSH, when selected, separately authenticates possession of the configured SSH key.

This authenticates possession of an issued key. It does not independently establish that the person holding it is the named employee. A copied connection file can impersonate its principal until revocation/expiry, if the holder can reach the server. Give each person a separate credential, transfer it privately, protect their device and revoke compromised/departed access. Never distribute owner keys or use one broadly authorized department service for employees who need narrower access. Returned data cannot be withdrawn from an external application's existing copies or conversation.

There is no email/password login, company SSO, MFA or verified on-behalf-of-user adapter in this release. Those need a separate identity integration; a prompt's name/user field is not authentication. An eventual login flow should bind the verified user to their server-side memberships before issuing a bounded session. It is not supplied by the current Host/Join wizard.

## Company ID versus invitation and login

The Brain already has an organization ID, but it is an identifier, not an address or password. A device cannot discover an arbitrary private company server from numbers alone. That needs a directory/resolver or an administrator-provided server address; globally resolving arbitrary company IDs is not implemented.

A possible future flow is company address/ID discovery, authenticated login, an expiring invitation and administrator-approved memberships. A public company number would locate the organization only. A short code granting access needs its own secure expiry, attempt limits and recipient verification. Current .atmet-join.json files are reusable bearer credentials, not one-time invitation codes. No discovery or SSO service is silently enabled.

The core's scoped credentials and audiences are implemented; detailed group/document administration still uses CLI/API. A full user/permission editor is separate future UI work.
