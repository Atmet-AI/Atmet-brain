PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS organizations (
 id TEXT PRIMARY KEY, slug TEXT NOT NULL UNIQUE, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS spaces (
 id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(id), slug TEXT NOT NULL,
 created_at REAL NOT NULL, UNIQUE(org_id, slug)
);
CREATE TABLE IF NOT EXISTS principals (
 id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(id), name TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('human','service')), org_admin INTEGER NOT NULL DEFAULT 0,
 active INTEGER NOT NULL DEFAULT 1, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS credentials (
 id TEXT PRIMARY KEY, principal_id TEXT NOT NULL REFERENCES principals(id), token_hash TEXT NOT NULL UNIQUE,
 operations TEXT NOT NULL, space_ids TEXT NOT NULL, expires_at REAL, revoked INTEGER NOT NULL DEFAULT 0,
 created_at REAL NOT NULL, parent_id TEXT REFERENCES credentials(id)
);
CREATE TABLE IF NOT EXISTS grants (
 id TEXT PRIMARY KEY, principal_id TEXT NOT NULL REFERENCES principals(id), space_id TEXT NOT NULL REFERENCES spaces(id),
 operations TEXT NOT NULL, expires_at REAL, revoked INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS groups (
 id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(id), name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS group_members (
 group_id TEXT NOT NULL REFERENCES groups(id), principal_id TEXT NOT NULL REFERENCES principals(id),
 PRIMARY KEY(group_id, principal_id)
);
CREATE TABLE IF NOT EXISTS sources (
 id TEXT PRIMARY KEY, space_id TEXT NOT NULL REFERENCES spaces(id), external_id TEXT NOT NULL,
 title TEXT NOT NULL, revision INTEGER NOT NULL, audience TEXT NOT NULL, authority TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active', created_at REAL NOT NULL, updated_at REAL NOT NULL,
 connector_id TEXT REFERENCES connectors(id), category TEXT NOT NULL DEFAULT 'document',
 UNIQUE(space_id,external_id)
);
CREATE TABLE IF NOT EXISTS source_revisions (
 source_id TEXT NOT NULL REFERENCES sources(id), revision INTEGER NOT NULL, body BLOB NOT NULL,
 mime TEXT NOT NULL, content_hash TEXT NOT NULL, recorded_at REAL NOT NULL, effective_at REAL NOT NULL,
 PRIMARY KEY(source_id,revision)
);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, space_id TEXT NOT NULL REFERENCES spaces(id), source_id TEXT NOT NULL REFERENCES sources(id),
 source_revision INTEGER NOT NULL, requested_by TEXT NOT NULL REFERENCES principals(id), requested_credential TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, lease_until REAL, lease_token TEXT,
 error_code TEXT, extractor TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL,
 UNIQUE(source_id,source_revision)
);
CREATE TABLE IF NOT EXISTS memories (
 id TEXT PRIMARY KEY, space_id TEXT NOT NULL REFERENCES spaces(id), statement TEXT NOT NULL,
 claim_key TEXT, kind TEXT NOT NULL, evidence TEXT NOT NULL, status TEXT NOT NULL, revision INTEGER NOT NULL,
 recorded_at REAL NOT NULL, effective_at REAL NOT NULL, valid_until REAL, extractor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_history (
 memory_id TEXT NOT NULL REFERENCES memories(id), revision INTEGER NOT NULL, status TEXT NOT NULL,
 actor_id TEXT NOT NULL, reason TEXT NOT NULL, recorded_at REAL NOT NULL,
 PRIMARY KEY(memory_id,revision)
);
CREATE TABLE IF NOT EXISTS artifacts (
 id TEXT PRIMARY KEY, space_id TEXT NOT NULL REFERENCES spaces(id), kind TEXT NOT NULL,
 slug TEXT NOT NULL, head INTEGER NOT NULL DEFAULT 0, instruction_path TEXT NOT NULL DEFAULT 'shared',
 audience TEXT NOT NULL, created_at REAL NOT NULL, UNIQUE(space_id,kind,slug)
);
CREATE TABLE IF NOT EXISTS artifact_versions (
 artifact_id TEXT NOT NULL REFERENCES artifacts(id), revision INTEGER NOT NULL, body TEXT NOT NULL,
 evidence TEXT NOT NULL, dependencies TEXT NOT NULL, state TEXT NOT NULL, submitted_by TEXT NOT NULL,
 submitted_at REAL NOT NULL, reviewed_by TEXT, reviewed_at REAL, effective_at REAL NOT NULL,
 reason TEXT NOT NULL, rollback_of INTEGER, content_hash TEXT NOT NULL,
 PRIMARY KEY(artifact_id,revision)
);
CREATE TABLE IF NOT EXISTS idempotency (
 principal_id TEXT NOT NULL, space_id TEXT NOT NULL, request_key TEXT NOT NULL,
 fingerprint TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(principal_id,space_id,request_key)
);
CREATE TABLE IF NOT EXISTS audit_events (
 id TEXT PRIMARY KEY, org_id TEXT NOT NULL, space_id TEXT, actor_id TEXT NOT NULL,
 operation TEXT NOT NULL, target TEXT, details TEXT NOT NULL, recorded_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS manifests (
 id TEXT PRIMARY KEY, space_id TEXT NOT NULL REFERENCES spaces(id), actor_id TEXT NOT NULL,
 query_hash TEXT NOT NULL, revisions TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS process_events (
 id TEXT PRIMARY KEY, space_id TEXT NOT NULL REFERENCES spaces(id), event_key TEXT NOT NULL,
 case_id TEXT NOT NULL, activity TEXT NOT NULL, evidence TEXT NOT NULL, happened_at REAL NOT NULL,
 recorded_by TEXT NOT NULL, UNIQUE(space_id,event_key)
);
CREATE TABLE IF NOT EXISTS connectors (
 id TEXT PRIMARY KEY, space_id TEXT NOT NULL REFERENCES spaces(id), kind TEXT NOT NULL,
 config TEXT NOT NULL, audience TEXT NOT NULL, authority TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
 checkpoint TEXT NOT NULL DEFAULT '{}', last_sync REAL, last_error TEXT
);
CREATE TABLE IF NOT EXISTS recovery_events (
 sequence INTEGER PRIMARY KEY AUTOINCREMENT, instance_id TEXT NOT NULL, operation TEXT NOT NULL,
 target TEXT NOT NULL, payload TEXT NOT NULL, recorded_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source_space ON sources(space_id,status);
CREATE INDEX IF NOT EXISTS idx_memory_space ON memories(space_id,status,effective_at);
CREATE INDEX IF NOT EXISTS idx_artifact_space ON artifacts(space_id,kind);
CREATE INDEX IF NOT EXISTS idx_job_claim ON jobs(space_id,status,lease_until);
CREATE INDEX IF NOT EXISTS idx_audit_scope ON audit_events(space_id,recorded_at);
CREATE TABLE IF NOT EXISTS task_runs (
 id TEXT PRIMARY KEY, space_id TEXT NOT NULL REFERENCES spaces(id), run_key TEXT NOT NULL,
 task_key TEXT NOT NULL, workflow_id TEXT NOT NULL REFERENCES artifacts(id), workflow_revision INTEGER NOT NULL,
 context_refs TEXT NOT NULL, inputs TEXT NOT NULL, output TEXT NOT NULL, succeeded INTEGER NOT NULL,
 ai_tokens INTEGER NOT NULL, evidence TEXT NOT NULL, recorded_by TEXT NOT NULL,
 created_at REAL NOT NULL, UNIQUE(space_id,run_key)
);
CREATE INDEX IF NOT EXISTS idx_task_pattern ON task_runs(space_id,task_key,workflow_id,created_at);
CREATE TABLE IF NOT EXISTS automation_blocks (
 artifact_id TEXT NOT NULL REFERENCES artifacts(id), revision INTEGER NOT NULL,
 run_id TEXT NOT NULL REFERENCES task_runs(id), PRIMARY KEY(artifact_id,revision,run_id)
);
CREATE TABLE IF NOT EXISTS automation_executions (
 id TEXT PRIMARY KEY, space_id TEXT NOT NULL REFERENCES spaces(id), principal_id TEXT NOT NULL,
 request_key TEXT NOT NULL, fingerprint TEXT NOT NULL, artifact_id TEXT NOT NULL REFERENCES artifacts(id),
 revision INTEGER NOT NULL, input_hash TEXT NOT NULL, output_hash TEXT NOT NULL, created_at REAL NOT NULL,
 UNIQUE(principal_id,space_id,request_key)
);
CREATE TABLE IF NOT EXISTS task_reports (
 id TEXT PRIMARY KEY, space_id TEXT NOT NULL REFERENCES spaces(id),
 source_id TEXT NOT NULL UNIQUE REFERENCES sources(id), report_key_hash TEXT NOT NULL,
 task_key TEXT NOT NULL, evidence TEXT NOT NULL, recorded_by TEXT NOT NULL REFERENCES principals(id),
 recorded_credential TEXT NOT NULL REFERENCES credentials(id), request_hash TEXT NOT NULL,
 created_at REAL NOT NULL, UNIQUE(space_id,recorded_by,report_key_hash)
);
CREATE INDEX IF NOT EXISTS idx_report_history ON task_reports(space_id,task_key,created_at);
