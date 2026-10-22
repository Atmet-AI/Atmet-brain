# MCP integration

This release implements MCP over stdio using the 2025-11-25 protocol version. The client launches a local subprocess, which can use a local Brain or bridge to an explicitly selected remote REST service. Messages are newline-delimited JSON-RPC and stdout contains only protocol messages. No remote MCP HTTP/OAuth transport is claimed.

## Set up a client

1. [Create a company Brain](quickstart.md), then create a dedicated service credential as shown in the [company walkthrough](use-for-your-company.md). Keep its token file private and use absolute paths.
2. Generate the local client configuration:

```bash
atmet-brain --json --token-file /absolute/path/to/scoped-worker.token mcp-config
```

3. Copy the returned MCP server entry into your agent application's MCP settings and restart/reconnect that client. It records the installed interpreter, data home and credential-file path so a desktop app does not need your terminal's PATH. Do not remove that interpreter environment while the client uses it.
4. Ask the client to list available Brain spaces, then request context for a permitted space and task. A successful response contains sourced context, not a final business action. If the subprocess fails, check [troubleshooting](troubleshooting.md).

For an existing remote company Brain, save a personal connection first and use the remote configuration command below. For a different local home, include `--home /absolute/path/to/brain-data` before mcp-config. The owner credential is for administration, not an ordinary agent.

## Configuration

Create a dedicated scoped credential, then adapt the [client configuration example](../examples/mcp-client-config.json):

```json
{
  "mcpServers": {
    "atmet-brain": {
      "command": "atmet-brain",
      "args": [
        "--home", "/absolute/path/to/brain-data",
        "--token-file", "/absolute/path/to/scoped-worker.token",
        "mcp"
      ]
    }
  }
}
```

The command must be on the host application's PATH. Use an absolute virtual-environment executable if needed. Client configuration formats and protocol-version support vary; only protocol fixtures and subprocess tests are validated here, not a universal named-client matrix.

## Tools

| Tool | Purpose |
| --- | --- |
| `brain_list_spaces` | Discover accessible spaces |
| `brain_search` | Retrieve permitted source evidence and memories |
| `brain_get_context` | Assemble approved context with evidence |
| `brain_get_artifact` | Inspect an artifact/version under current access |
| `brain_list_skills` | Discover permitted skill descriptions |
| `brain_skill_resource` | Load one text resource without execution |
| `brain_route_task` | Check for one current approved recipe without executing or calling a model |

Add `--allow-proposals` to expose `brain_propose_memory`, `brain_propose_artifact` and `brain_discover_automation`. This changes tool availability only. The credential still needs the corresponding core operation grants and cannot publish through these tools.

Add `--allow-automations` to expose `brain_record_task_run` and `brain_run_task`. Recording requires `observe`, `contribute` and current context/evidence access. Running a reviewed pure recipe requires `process` and `read`. The server never evaluates arbitrary stored code or grants external actions. See [automation lifecycle and input contracts](automations.md).

Each request rechecks the bound credential, its lineage and current grants. Model-supplied user IDs or role labels cannot change the principal. Every task uses an explicit space ID. There is no process-global active-company selection.

## Expected agent pattern

1. List permitted spaces and choose the correct one.
2. For an explicit supported task key/workflow, check `brain_route_task` before expensive model work; an opted-in runtime can invoke `brain_run_task`. Handle denied or unavailable context as an error, without broader-credential fallback.
3. If a model is needed, request task context and applicable skill/workflow IDs.
4. Read selected supporting resources when needed.
5. Execute external actions only through separately authorized host tools.
6. Submit a sourced observation or proposal when useful. Opted-in trusted runtimes can report accepted task outcomes for repeated-task learning.

Keep approved instructions separate from untrusted retrieved source text in the host's prompt construction. The Brain can enforce access to returned content, but arbitrary external model obedience remains the host/runtime's responsibility.

## Use a company Brain remotely

After saving an individual connection, print a client configuration:

```bash
atmet-brain --json --connection company mcp-config
```

Or configure your MCP client to launch `atmet-brain --connection company mcp` with an absolute executable and data-home path. The local stdio bridge authenticates on each request and forwards selected tools through REST. It uses the same exact operation schemas, tool opt-in flags and current authorization as local MCP. No company database or owner credential needs to be copied to the employee device. MCP stdout remains protocol-only. This is not an HTTP MCP/OAuth server. Follow [team setup](team-server.md) for HTTPS or restricted SSH forwarding.
