# Security

Atmet Brain is a local/private-pilot alpha. It has behavior tests for scope isolation, current authorization, source revocation, reviewed publication and recovery. It has not received an independent production security audit.

## Reporting

Use GitHub private vulnerability reporting if enabled by the repository owner. If it is unavailable, ask the maintainer for a private reporting channel without disclosing exploit details in a public issue. No response-time commitment is published for this initial repository.

## Boundaries

- The filesystem/database owner controls the installation.
- Public interfaces authenticate scoped credentials and recheck current grants.
- Company administration does not automatically bypass content permissions.
- Retrieved source text cannot change policy or permissions.
- Opt-in completion hooks submit selected safe summaries, not raw transcripts. Reporter credentials omit publication authority. Callback delivery and complete source provenance remain host responsibilities; deliberately supplied fields have no automatic secret scrubber.
- Task reports are explicit client observations with authenticated attribution. Raw report reads require history access, source audiences intersect, and reports stay out of ordinary retrieval. Skill learning creates pending drafts through existing evidence/review checks.
- Skills are read as instructions/resources; the core never executes their scripts.
- The local HTTP server is not a hardened public internet gateway.
- Remote clients require verified HTTPS or loopback HTTP inside a controlled local/SSH connection, refuse redirects and never infer a user's identity from their network address.
- Saved connection profiles bind a verified organization/principal; copied raw credential files are private, device-specific and outside the canonical backup.
- Interactive Host defaults to private single-use expiring password invitations. Explicit legacy bearer connection files remain reusable until expiry/revocation. Join validates the returned or legacy pinned identity before saving private session/connection state.
- Automatic SSH forwarding requires administrator-approved SSH keys and known hosts, uses strict non-interactive authentication and closes each request's process. It does not provision SSH accounts, accept unknown keys or grant Brain roles.
- Network access, SSH accounts and individual Brain grants are separate. An employee must not receive host filesystem access as a side effect of sharing a Brain.
- Per-user background service installation does not configure TLS, SSO, VPN/firewall rules, machine-wide boot services or independent monitoring.
- Provider processing is opt-in; local storage does not imply offline processing when an external adapter is enabled.
- Logical deletion, physical-media erasure and backup retention are separate concerns.
- Restore requires a fresh home, revokes old credentials and quarantines source access.

Bearer tokens are stored as hashes; credentials supplied through files need private file permissions. Issued descendant tokens depend on their issuer remaining active. Raw provider credentials are read from the operator environment and must remain outside exports and logs.

Future identity adapters must validate a trusted issuer and user binding rather than accept arbitrary role/name fields. Future runtime tools must separately authorize external side effects.

Guided agent bundles derive a new scoped credential rather than copying the broad issuer. New service identities or current-identity child credentials are bounded by core grants and parent lineage; generated scopes exclude publish/manage/erase/process. Explicit CLI token-file selection overrides ambient tokens. Partial setup failures attempt revocation and disclose only the credential ID/paths needed for recovery, never the raw credential.

## Company-local employee authentication

Password accounts use independent random salts and scrypt N=32768, r=8, p=3. Inputs are normalized, bounded and checked against a small common/trivial-password list; no external breach-check service or compliance certification is claimed. Password work is bounded to two concurrent KDF calls. Sign-in attempts are persisted and limited per canonical company/username, in addition to HTTP rate/origin/body guards. Passwords are not logged, stored in client profiles or accepted as command arguments.

Private invitation secrets are stored hashed on the server, expire and are consumed once in an atomic transaction. Enrollment is bound to the approved username, issuer's current authority and workspace roles. An email-shaped username does not verify mailbox ownership; private recipient verification/delivery remains the administrator's responsibility. No automatic email, SSO, MFA, browser session or global discovery service is enabled.

Password login issues hashed opaque 12-hour credentials; requests still enforce current grants and source audiences. Membership edits use an expected revision and revoke existing credentials. Password changes revoke all that principal's credentials; logout revokes the selected session and children. Retained client routes do not cache the password or refresh without explicit sign-in. A signed-out local marker prevents silent fallback to an owner key unless the operator explicitly selects another credential.

The trusted filesystem owner can perform explicitly confirmed local owner-account recovery; it is not exposed by RPC or MCP and cannot bypass quarantined installation recovery. Employees must not receive database/shell access with their login. Encrypted restore clears password verifiers, disables old accounts/principals and revokes invitations/credentials before journal reconciliation. Each company home needs independent recovery handling. See [account operation and limits](docs/employee-accounts.md).

## Human-approved administration and intake

Default document ingestion is fail-closed: new/changed sources are held from normal retrieval/extraction until an approved explicit rule or exact human-reviewed classification releases them. Unknown stays restricted. Matching audiences intersect and old restrictive classifications protect retained source revisions. Term matching and model suggestions are not universal DLP or perfect salary recognition. A trusted connector binding is required for workspace-wide automatic release.

Administration bundles are child credentials linked to the current human authority. They can inspect permitted intake and prepare catalog changes, but have no direct manage/publish/erase operations. Applying a proposal needs the same human principal, an independent current admin session, the exact digest/current state and a private password. MCP/RPC tools cannot call the review endpoint. Password work and review attempts are bounded. Revoked/expired parents, changed source/group/member/rule state and repeat reviews fail closed. Server filesystem control remains a stronger local trust boundary.

Restore revokes controls/rejects pending changes/disables rules and keeps sources quarantined for fresh recovery review. Erasure redacts source-associated classification notes/previews without removing non-content audit hashes. Large-scale queues/load, external agent/model egress and production security assessment remain deployment responsibilities.
