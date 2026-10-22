# Security

Atmet Brain is a local/private-pilot alpha. It has behavior tests for scope isolation, current authorization, source revocation, reviewed publication and recovery. It has not received an independent production security audit.

## Reporting

Use GitHub private vulnerability reporting if enabled by the repository owner. If it is unavailable, ask the maintainer for a private reporting channel without disclosing exploit details in a public issue. No response-time commitment is published for this initial repository.

## Boundaries

- The filesystem/database owner controls the installation.
- Public interfaces authenticate scoped credentials and recheck current grants.
- Company administration does not automatically bypass content permissions.
- Retrieved source text cannot change policy or permissions.
- Skills are read as instructions/resources; the core never executes their scripts.
- The local HTTP server is not a hardened public internet gateway.
- Remote clients require verified HTTPS or loopback HTTP inside a controlled local/SSH connection, refuse redirects and never infer a user's identity from their network address.
- Saved connection profiles bind a verified organization/principal; copied raw credential files are private, device-specific and outside the canonical backup.
- Host connection files contain reusable scoped bearer credentials, not single-use invitations. Deliver them privately; revocation and expiry remain server-enforced. Join checks the pinned organization/principal/credential identity before saving a profile.
- Automatic SSH forwarding requires administrator-approved SSH keys and known hosts, uses strict non-interactive authentication and closes each request's process. It does not provision SSH accounts, accept unknown keys or grant Brain roles.
- Network access, SSH accounts and individual Brain grants are separate. An employee must not receive host filesystem access as a side effect of sharing a Brain.
- Per-user background service installation does not configure TLS, SSO, VPN/firewall rules, machine-wide boot services or independent monitoring.
- Provider processing is opt-in; local storage does not imply offline processing when an external adapter is enabled.
- Logical deletion, physical-media erasure and backup retention are separate concerns.
- Restore requires a fresh home, revokes old credentials and quarantines source access.

Bearer tokens are stored as hashes; credentials supplied through files need private file permissions. Issued descendant tokens depend on their issuer remaining active. Raw provider credentials are read from the operator environment and must remain outside exports and logs.

Future identity adapters must validate a trusted issuer and user binding rather than accept arbitrary role/name fields. Future runtime tools must separately authorize external side effects.
