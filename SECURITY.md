# Security

Version 0.1.1 is a local alpha. It has behavior tests for scope isolation, current authorization, source revocation, reviewed publication and recovery. It has not received an independent production security audit.

## Reporting

Use GitHub private vulnerability reporting if enabled by the repository owner. If it is unavailable, ask the maintainer for a private reporting channel without disclosing exploit details in a public issue. No response-time commitment is published for this initial repository.

## Boundaries

- The filesystem/database owner controls the installation.
- Public interfaces authenticate scoped credentials and recheck current grants.
- Company administration does not automatically bypass content permissions.
- Retrieved source text cannot change policy or permissions.
- Skills are read as instructions/resources; the core never executes their scripts.
- The local HTTP server is not a hardened public internet gateway.
- Provider processing is opt-in; local storage does not imply offline processing when an external adapter is enabled.
- Logical deletion, physical-media erasure and backup retention are separate concerns.
- Restore requires a fresh home, revokes old credentials and quarantines source access.

Bearer tokens are stored as hashes; credentials supplied through files need private file permissions. Issued descendant tokens depend on their issuer remaining active. Raw provider credentials are read from the operator environment and must remain outside exports and logs.

Future identity adapters must validate a trusted issuer and user binding rather than accept arbitrary role/name fields. Future runtime tools must separately authorize external side effects.
