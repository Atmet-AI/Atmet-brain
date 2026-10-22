# Deployment

Start locally, run the acceptance tests and choose a bounded company workflow before handling sensitive information. The core is a local/private-pilot alpha, without a production security or availability claim.

## Processes

Run the HTTP adapter and learning worker as separate processes using the same private data home:

```bash
atmet-brain --home /private/brain-data serve
atmet-brain --home /private/brain-data --token-file /private/worker.token worker --space SPACE_ID --loop --interval 5
```

SQLite WAL supports the local process model. Jobs use leases and bounded retries. There is no distributed lease service or multi-node deployment contract. Long model calls and large data volumes require measurements before scaling.

Connector synchronization is explicit. Run `sync` from an operator-managed scheduler or invoke it deliberately. API and worker processes can run in the foreground or as explicitly installed per-user services. See [team server setup](team-server.md) for launchd/systemd installation, login-session limits and separate worker selection. No service is installed during package installation or company setup.

## Network

The REST adapter binds loopback by default and uses scoped bearer credentials. It rejects browser-origin requests, validates local Host headers and bounds request size. It is built on Python's standard HTTP server for local development and private integration testing.

Use `--allow-network` only behind a controlled private ingress. TLS termination, SSO, delegated user authentication, stronger admission/rate controls, monitoring and public production hardening remain deployment work. The Docker example publishes only a loopback host port and does not make this a public SaaS server.

## Containers

Use a source checkout containing the Dockerfile and a separately installed container engine. These are developer/operator examples, not prerequisites for npm installation:

```bash
docker build -t atmet-brain:local .
docker run --rm -v atmet-data:/data atmet-brain:local init --organization example-company
docker run --rm -p 127.0.0.1:7310:7310 -v atmet-data:/data atmet-brain:local serve --host 0.0.0.0 --allow-network
```

The container runs as an unprivileged user. Keep the volume private and initialize it once. The Dockerfile and Compose configuration are provided for reproducibility; a container engine was not available during local validation, so their image/runtime behavior still needs an actual build and run.

## Data flow

Local extraction and retrieval require no model network access. The optional model extractor sends selected source text to the configured provider after explicit enablement and permission checks. Gmail synchronization contacts Google using an operator-managed token. Package installation downloads normal Python dependencies. No telemetry or license server call is implemented.

Filesystem permissions protect the data directory at the host boundary. Disk encryption, provider contracts, secret storage, backup retention and external incident handling are operator responsibilities. Keep backups and the latest recovery journal in an independent recovery location.

## Updates

Back up, export the current recovery journal, run tests against a copied environment, then update the package. Schema version 1 is the only supported schema in this initial release. A different schema version is rejected; cross-version migrations need a future explicit migration path. Never replace a live data directory with an old backup as a software downgrade.
