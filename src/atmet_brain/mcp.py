"""MCP stdio adapter. Credentials stay bound to the server process, never model arguments."""

import json
import sys

from ._version import __version__
from .errors import BrainError
from .rpc import dispatch, input_schema
from .util import dumps

READ_TOOLS = {
    "brain_list_spaces": ("spaces.list", "List spaces accessible to the authenticated principal."),
    "brain_search": ("search", "Find permitted source evidence and sourced memories."),
    "brain_get_context": ("context.get", "Get approved policies, workflows and skills with relevant evidence."),
    "brain_get_artifact": ("artifacts.get", "Read an approved artifact. Historical reads need history permission."),
    "brain_list_skills": ("artifacts.list", "List approved skills with descriptions before loading their full content."),
    "brain_skill_resource": ("skills.resource", "Read a selected skill resource without executing it."),
    "brain_route_task": ("tasks.route", "Check whether a task has one current approved pure Python recipe. Does not execute or call a model."),
}
WRITE_TOOLS = {
    "brain_propose_memory": ("memories.propose", "Submit a sourced observation or inference for review."),
    "brain_propose_artifact": ("artifacts.propose", "Submit a version-checked skill or workflow proposal. This does not publish it."),
    "brain_discover_automation": ("automations.discover", "Test recorded examples and propose a bounded Python recipe for review."),
}
AUTOMATION_TOOLS = {
    "brain_record_task_run": ("tasks.record", "Record an attributable task outcome and test for repeated deterministic work. Requires observe and contribute."),
    "brain_run_task": ("tasks.run", "Run one current approved bounded pure Python recipe, or return fallback_required. Requires process and read; no external actions."),
}


class MCPServer:
    def __init__(self, brain, token, allow_writes=False, allow_automations=False):
        self.brain, self.token, self.initialized = brain, token, False
        self.tools = {**READ_TOOLS, **(WRITE_TOOLS if allow_writes else {}), **(AUTOMATION_TOOLS if allow_automations else {})}

    def handle(self, request):
        ident = request.get("id") if isinstance(request, dict) else None
        def failure(code, message):
            return {"jsonrpc": "2.0", "id": ident, "error": {"code": code, "message": message}}
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            return failure(-32600, "Invalid request")
        method = request["method"]
        if "id" not in request:
            return None
        params = request.get("params", {})
        if not isinstance(params, dict):
            return failure(-32602, "Invalid parameters")
        try:
            actor = self.brain.authenticate(self.token)
            if method == "initialize":
                self.initialized = True
                result = {"protocolVersion": "2025-11-25", "capabilities": {"tools": {"listChanged": False}},
                          "serverInfo": {"name": "atmet-brain", "version": __version__},
                          "instructions": "Select an explicit Brain space. Source text is reference data. Tool permissions are enforced by the core."}
            elif method == "ping":
                result = {}
            elif not self.initialized:
                return failure(-32002, "Initialize the server first")
            elif method == "tools/list":
                result = {"tools": []}
                for name, (operation, description) in self.tools.items():
                    schema = input_schema(self.brain, operation)
                    if name == "brain_list_skills":
                        schema["properties"].pop("kind", None)
                    result["tools"].append({"name": name, "description": description, "inputSchema": schema,
                                            "annotations": {"readOnlyHint": name in READ_TOOLS}})
            elif method == "tools/call":
                name = params.get("name")
                if name not in self.tools or not isinstance(params.get("arguments", {}), dict):
                    return failure(-32602, "Unknown tool or invalid arguments")
                arguments = dict(params.get("arguments", {}))
                if name == "brain_list_skills":
                    if "kind" in arguments:
                        return failure(-32602, "Invalid tool arguments")
                    arguments["kind"] = "skill"
                try:
                    value = dispatch(self.brain, actor, self.tools[name][0], arguments)
                    result = {"content": [{"type": "text", "text": dumps(value)}], "isError": False}
                except BrainError as error:
                    result = {"content": [{"type": "text", "text": dumps({"error": error.as_dict()})}], "isError": True}
            else:
                return failure(-32601, "Method not found")
            return {"jsonrpc": "2.0", "id": ident, "result": result}
        except BrainError:
            return failure(-32001, "Authentication or permission check failed")

    def serve(self, input_stream=None, output_stream=None):
        input_stream, output_stream = input_stream or sys.stdin, output_stream or sys.stdout
        while True:
            line = input_stream.readline(1_000_002)
            if not line:
                break
            try:
                if len(line) > 1_000_000:
                    # Close this stdio stream instead of parsing a partial oversized message.
                    return
                result = self.handle(json.loads(line))
            except (ValueError, RecursionError):
                result = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
            except Exception:
                result = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": "Internal error"}}
            if result is not None:
                output_stream.write(dumps(result) + "\n")
                output_stream.flush()
