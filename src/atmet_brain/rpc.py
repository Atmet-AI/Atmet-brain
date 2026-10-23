"""Explicit public operations. Local operator methods never enter this registry."""

import inspect

from ._version import __version__
from .errors import BrainError, require

METHODS = {
    "identity.me": "whoami", "access.check": "check_access", "spaces.list": "list_spaces", "spaces.create": "create_space",
    "team.add": "add_team_member",
    "accounts.setup": "setup_account", "accounts.password": "change_password",
    "invites.create": "create_invite", "invites.list": "list_invites", "invites.revoke": "revoke_invite",
    "members.list": "list_members", "members.access": "set_member_access", "members.disable": "disable_member",
    "principals.create": "create_principal", "grants.create": "grant", "grants.revoke": "revoke_grant",
    "credentials.create": "create_credential", "credentials.revoke": "revoke_credential",
    "groups.create": "create_group", "groups.remove_member": "remove_group_member",
    "sources.put": "put_source", "sources.get": "get_source", "sources.list": "list_sources",
    "sources.access": "set_source_access", "sources.erase": "erase_source",
    "memories.propose": "propose_memory", "memories.review": "review_memory", "memories.list": "list_memories",
    "artifacts.propose": "propose_artifact", "artifacts.review": "review_artifact", "artifacts.get": "get_artifact",
    "artifacts.list": "list_artifacts", "artifacts.history": "artifact_history", "artifacts.rollback": "rollback_artifact",
    "artifacts.retire": "retire_artifact", "skills.resource": "skill_resource",
    "artifacts.diff": "artifact_diff",
    "search": "search", "context.get": "get_context", "context.manifest": "get_manifest",
    "graph.get": "graph", "space.export": "export_space", "audit.list": "list_audit",
    "jobs.list": "list_jobs", "jobs.run": "run_jobs", "jobs.retry": "retry_job",
    "events.record": "record_event", "workflows.discover": "discover_workflow",
    "tasks.record": "record_task_run", "tasks.runs": "list_task_runs",
    "reports.record": "record_task_report", "reports.complete": "complete_task_report", "reports.get": "get_task_report",
    "reports.search": "search_task_reports", "reports.erase": "erase_task_report",
    "skills.learn": "learn_skill_from_reports",
    "automations.discover": "discover_automation", "tasks.route": "route_task", "tasks.run": "run_task",
    "connectors.list": "list_connectors", "connectors.disable": "disable_connector", "connectors.sync": "sync_connector",
}

AUTH_METHODS = {"login": "login", "accept": "accept_invite"}


def dispatch_auth(brain, action, params):
    require(action in AUTH_METHODS and isinstance(params, dict), "invalid_auth", "Invalid sign-in request.")
    function = getattr(brain, AUTH_METHODS[action])
    allowed = inspect.signature(function).parameters
    require(set(params) == set(allowed), "invalid_auth", "Provide only the required sign-in fields.")
    try:
        return function(**params)
    except (TypeError, ValueError, OverflowError):
        raise BrainError("invalid_auth", "Invalid sign-in fields.") from None


def parameters(brain, method):
    require(method in METHODS, "unknown_method", "Unknown public operation.", 404)
    function = getattr(brain, METHODS[method])
    return {name: value for name, value in inspect.signature(function).parameters.items()
            if name not in {"self", "actor", "extractor"} and not name.startswith("_")}


def dispatch(brain, actor, method, params=None):
    require(isinstance(method, str) and method in METHODS, "unknown_method", "Unknown public operation.", 404)
    require(params is None or isinstance(params, dict), "invalid_params", "params must be an object.")
    params = params or {}
    allowed = parameters(brain, method)
    require(not (set(params) - set(allowed)), "invalid_params", "Unknown or reserved parameter.")
    required = {name for name, value in allowed.items() if value.default is inspect.Parameter.empty}
    require(required <= set(params), "invalid_params", "Missing required parameter.")
    try:
        return getattr(brain, METHODS[method])(actor, **params)
    except (TypeError, ValueError, OverflowError):
        raise BrainError("invalid_params", "Invalid operation parameter type or value.") from None


def input_schema(brain, method):
    params = parameters(brain, method)
    properties = {}
    integers = {"limit", "max_jobs", "expected_revision", "revision", "target_revision", "from_revision", "to_revision", "max_chars", "min_runs", "ai_tokens"}
    booleans = {"approve", "active", "org_admin", "include_pending", "include_payload", "succeeded", "learn"}
    arrays = {"operations", "space_ids", "audience", "evidence", "dependencies", "artifact_ids", "principal_ids", "report_ids", "steps", "corrections", "checks", "access"}
    for name in params:
        kind = "integer" if name in integers else "boolean" if name in booleans else "array" if name in arrays else "object" if name in {"body", "inputs", "output"} else "string"
        properties[name] = {"type": kind}
        if "password" in name:
            properties[name].update(writeOnly=True, maxLength=128)
        if kind == "array":
            properties[name]["items"] = {"type": "object" if name in {"evidence", "dependencies", "access"} else "string"}
            if name == "access":
                from .auth import ROLES
                properties[name]["items"].update(additionalProperties=False, required=["space_id", "role"],
                    properties={"space_id": {"type": "string"}, "role": {"type": "string", "enum": sorted(set(ROLES) - {"owner"})}})
        if name.endswith("_at") or name == "at":
            properties[name] = {"anyOf": [{"type": "number"}, {"type": "string"}]}
    return {"type": "object", "properties": properties, "additionalProperties": False,
            "required": [name for name, value in params.items() if value.default is inspect.Parameter.empty]}


def openapi(brain):
    variants = [{"type": "object", "required": ["method", "params"], "additionalProperties": False,
                 "properties": {"method": {"const": method}, "params": input_schema(brain, method)}} for method in METHODS]
    result = {"openapi": "3.1.0", "info": {"title": "Atmet Brain", "version": __version__},
            "components": {"securitySchemes": {"BearerAuth": {"type": "http", "scheme": "bearer"}}},
            "paths": {"/v1/rpc": {"post": {"operationId": "brain_rpc", "security": [{"BearerAuth": []}],
                "requestBody": {"required": True, "content": {"application/json": {"schema": {"oneOf": variants}}}},
                "responses": {"200": {"description": "Operation result"}, "400": {"description": "Invalid request"},
                              "401": {"description": "Invalid or revoked credential"}, "403": {"description": "Permission denied"},
                              "409": {"description": "Revision or lifecycle conflict"}}}}}}
    for action, method in AUTH_METHODS.items():
        fields = {name: {"type": "string", **({"writeOnly": True} if name in {"password", "secret"} else {})}
                  for name in inspect.signature(getattr(brain, method)).parameters}
        result["paths"]["/v1/auth/" + action] = {"post": {"operationId": "account_" + action, "security": [],
            "requestBody": {"required": True, "content": {"application/json": {"schema": {
                "type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}}}},
            "responses": {"200": {"description": "Private bounded session; never log the returned token"},
                          "401": {"description": "Invalid login or invitation"}, "429": {"description": "Attempt limit reached"}}}}
    return result
