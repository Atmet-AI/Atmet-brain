# Documentation

Start with the [quickstart](quickstart.md), then read the pages for the part you are changing. The [implementation status](implementation-status.md) separates working behavior from the wider roadmap.

| Topic | Guide |
| --- | --- |
| Choose an installation route | [Installation](install.md) |
| Setup and first task | [Quickstart](quickstart.md) |
| Use it in a company | [Company walkthrough](use-for-your-company.md) |
| Shared core and storage | [Architecture](architecture.md) |
| Business knowledge | [Memory and learning](memory-and-learning.md) |
| Processes and observed activity | [Workflows](workflows.md) |
| Reusable methods | [Skills](skills.md) |
| Repeated work and scripts | [Automations](automations.md) |
| Identity and access | [Permissions](permissions.md) |
| Settings and precedence | [Configuration](configuration.md) |
| Revisions and rollback | [Versioning](versioning.md) |
| Snapshots and restoration | [Backup and recovery](backup-and-recovery.md) |
| Python and REST | [API](api.md) |
| Agent integration | [MCP](mcp.md) |
| Ingestion adapters | [Connectors](connectors.md) |
| Running a service | [Deployment](deployment.md) |
| Checks and fixtures | [Testing](testing.md) |
| Public packaging | [Releasing](releasing.md) |
| Release numbers and tags | [Release versioning](release-versioning.md) |
| Keep guides and diagrams current | [Documentation maintenance](documentation.md) |
| Current support | [Implementation status](implementation-status.md) |
| Next development | [Roadmap](roadmap.md) |
| Design rationale | [Architecture decisions](adr/0001-local-core.md) |
| Prior work and protocol references | [References](references.md) |

Diagrams are Mermaid source so they remain editable and render directly on GitHub. The README has six diagrams covering company spaces, the shared core, learning, task retrieval, pure scripts and change handling. The architecture guide maps the current modules, data records and trust boundaries. [Standalone chart sources](diagrams) are generated from Markdown by `scripts/generate_diagrams.py`; the project checker rejects missing, stale or obsolete copies.
