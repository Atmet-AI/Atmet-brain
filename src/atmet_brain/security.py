"""Approved document-access rules and fail-closed ingestion classification."""

from .auth import authorize, audience_allows, validate_audience
from .db import audit
from .errors import require
from .util import dumps, loads, now, slug, text


def policy_revision(conn, org_id):
    row = conn.execute("SELECT revision FROM security_heads WHERE org_id=?", (org_id,)).fetchone()
    return row[0] if row else 0


def rule_definition(conn, org_id, body):
    require(isinstance(body, dict) and set(body) == {"key", "name", "space_ids", "terms_any", "connector_id", "audience", "decision"},
            "invalid_rule", "Provide key, name, space_ids, terms_any, connector_id, audience and decision.")
    slug(body["key"]); text(body["name"], maximum=120)
    require(body["decision"] in {"release", "hold"}, "invalid_rule", "Choose release or hold.")
    spaces = body["space_ids"]
    require(isinstance(spaces, list) and 0 < len(spaces) <= 100 and len(set(spaces)) == len(spaces)
            and all(isinstance(s, str) and conn.execute("SELECT 1 FROM spaces WHERE id=? AND org_id=?", (s, org_id)).fetchone() for s in spaces),
            "invalid_rule", "Select distinct existing company workspaces.")
    terms = body["terms_any"]
    require(isinstance(terms, list) and len(terms) <= 20 and all(isinstance(t, str) and 2 <= len(t.strip()) <= 100 for t in terms),
            "invalid_rule", "Use up to 20 explicit content terms of 2 to 100 characters.")
    connector = body["connector_id"]
    require(connector is None or isinstance(connector, str), "invalid_rule", "Choose a connector ID or null.")
    require(terms or connector, "invalid_rule", "A rule needs explicit content terms or a trusted connector binding; no implicit allow-all rule.")
    if connector:
        require(conn.execute("SELECT 1 FROM connectors WHERE id=? AND space_id IN (" + ",".join("?" for _ in spaces) + ") AND enabled=1", (connector, *spaces)).fetchone(),
                "invalid_rule", "Choose an enabled connector in the selected workspaces.")
    require(body["decision"] != "release" or "space" not in body["audience"] or connector,
            "trusted_binding_required", "Workspace-wide automatic release requires a trusted connector binding. Content words alone cannot authorize broad sharing.")
    return {**body, "space_ids": sorted(spaces), "terms_any": sorted(set(t.strip().casefold() for t in terms)),
            "audience": validate_audience(conn, org_id, body["audience"])}


def evaluate(conn, org_id, source, content):
    clauses, matches, held = [], [], False
    haystack = (source["title"] + "\n" + content).casefold()
    for row in conn.execute("SELECT * FROM security_rules WHERE org_id=? AND state='active' ORDER BY rule_key", (org_id,)):
        body = loads(row["body"])
        if source["space_id"] not in body["space_ids"] or (body["connector_id"] and source["connector_id"] != body["connector_id"]):
            continue
        if body["terms_any"] and not any(term in haystack for term in body["terms_any"]):
            continue
        clauses.append(body["audience"])
        matches.append({"key": row["rule_key"], "revision": row["revision"]})
        held |= body["decision"] == "hold"
    previous = conn.execute("SELECT clauses FROM source_security WHERE source_id=?", (source["id"],)).fetchone()
    if previous:
        for clause in loads(previous[0]):
            if clause not in clauses: clauses.append(clause)
    return {"decision": "released" if matches and not held else "pending", "clauses": clauses, "matches": matches,
            "policy_revision": policy_revision(conn, org_id)}


def record_classification(conn, source, result, reason, review_id=None):
    conn.execute("INSERT INTO source_security VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET source_revision=excluded.source_revision,policy_revision=excluded.policy_revision,decision=excluded.decision,clauses=excluded.clauses,matches=excluded.matches,reason=excluded.reason,review_id=excluded.review_id,updated_at=excluded.updated_at",
                 (source["id"], source["revision"], result["policy_revision"], result["decision"], dumps(result["clauses"]), dumps(result["matches"]), reason, review_id, now()))
    conn.execute("UPDATE sources SET status=?,updated_at=? WHERE id=?", ("active" if result["decision"] == "released" else "intake", now(), source["id"]))


def enforce_classification(conn, actor, source, require_released=True):
    if source["category"] != "document":
        return
    row = conn.execute("SELECT * FROM source_security WHERE source_id=?", (source["id"],)).fetchone()
    head = policy_revision(conn, actor.org_id)
    if row is None and head == 0:
        return  # Pre-upgrade active documents retain their existing explicit access.
    if require_released:
        require(row and row["decision"] == "released" and row["source_revision"] == source["revision"]
                and row["policy_revision"] == head, "not_found", "Source not found.", 404)
    if row is None:
        return
    require(all(audience_allows(conn, actor, clause) for clause in loads(row["clauses"])),
            "not_found", "Source not found.", 404)


def intake_source(conn, authority, source_id):
    source = conn.execute("SELECT s.* FROM sources s JOIN spaces p ON p.id=s.space_id WHERE s.id=? AND p.org_id=? AND s.category='document' AND s.status!='deleted'", (source_id, authority.org_id)).fetchone()
    require(source, "not_found", "Intake source not found.", 404)
    authorize(conn, authority, source["space_id"], "manage")
    authorize(conn, authority, source["space_id"], "read")
    require(audience_allows(conn, authority, source["audience"]), "not_found", "Intake source not found.", 404)
    if source["connector_id"]:
        require(conn.execute("SELECT 1 FROM connectors WHERE id=? AND enabled=1", (source["connector_id"],)).fetchone(),
                "not_found", "Intake source not found.", 404)
    revision = conn.execute("SELECT * FROM source_revisions WHERE source_id=? AND revision=?", (source_id, source["revision"])).fetchone()
    content = bytes(revision["body"]).decode("utf-8")
    result = evaluate(conn, authority.org_id, source, content)
    require(all(audience_allows(conn, authority, clause) for clause in result["clauses"]),
            "not_found", "Intake source not found.", 404)
    # A pending manually restricted source never loses restrictions merely because rules changed.
    old = conn.execute("SELECT clauses FROM source_security WHERE source_id=?", (source_id,)).fetchone()
    require(not old or all(audience_allows(conn, authority, clause) for clause in loads(old[0])),
            "not_found", "Intake source not found.", 404)
    return source, revision, content, result
