# References

The implementation is independently written for Atmet Brain. The following projects and documents informed design choices or protocol checks. Their code is not vendored into this repository.

| Reference | Relevant idea |
| --- | --- |
| [Supermemory](https://github.com/supermemoryai/supermemory) | Memory interfaces, scoped adapters and inspectable lifecycle |
| [Hy-Memory extractor](https://github.com/Tencent-Hunyuan/Hy-Memory/blob/main/hy_memory/coding/extractor.py) | Distinguishing task facts from reusable experience candidates |
| [Hy-Memory change store](https://github.com/Tencent-Hunyuan/Hy-Memory/blob/main/hy_memory/coding/chain_store.py) | Exact revision evidence alongside summaries |
| [MemHub architecture](https://github.com/Tencent-Hunyuan/Hy-Memory/blob/main/memhub/docs/ARCHITECTURE.md) | Shared core, evidence and client adapters |
| [MCP transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) | Stdio JSON-RPC framing |
| [MCP tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) | Tool schemas and result envelopes |
| [Python SQLite backup](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup) | Coherent database snapshots |
| [Fernet documentation](https://cryptography.io/en/latest/fernet/) | Authenticated symmetric encryption |
| [Compatible chat-completions shape](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) | Optional model adapter request/response shape |
| [Gmail message listing](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list) | Selected-label enumeration |
| [Gmail message retrieval](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get) | Read-only message capture |

Primary references were inspected during initial development. Upstream main-branch documents can change. No competitor benchmark, full source audit or inherited production guarantee is claimed. Use actual release tests when evaluating a new dependency or provider.
