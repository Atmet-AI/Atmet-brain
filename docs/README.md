# Use Atmet Brain

Atmet Brain stores company sources, learned memory and reviewed procedures that your agents can retrieve. Start with a small company example, then connect your own agent or team. The [support matrix](implementation-status.md) marks implemented, fixture-tested and planned features.

## Start here

1. [Install the CLI](install.md): use npx or install the command for regular use.
2. [Create your first Brain](quickstart.md): initialize a company, ingest a source, run learning and request context.
3. [Build a company workflow](use-for-your-company.md): add departments, publish instructions and give an agent its own credential.
4. [Connect an agent with MCP](mcp.md) or [use Python/REST](api.md).
5. [Enable automatic task feedback](automatic-task-feedback.md) or [report selected tasks and learn skills](task-history-and-learning.md), then [keep sources current](connectors.md), [inspect history](history-walkthrough.md) and [back up the installation](backup-and-recovery.md).
6. [Host a Brain and help teammates Join](team-server.md#guided-host-and-join) when several people need the same Brain.

The examples use the installed `atmet-brain` command. Install it globally as shown in installation, or substitute `npx atmet-brain@latest` before the same arguments. JSON blocks labeled as files must be saved before a command refers to them. Replace uppercase IDs and example paths with values returned by your own installation; no source checkout is needed unless a page explicitly uses repository examples.

## Task guides and reference

| What you want to do | Guide |
| --- | --- |
| Use terminal commands or a saved remote connection | [Terminal](terminal.md) |
| Add information and understand learning/review | [Memory and learning](memory-and-learning.md) |
| Create and update a business procedure | [Workflows](workflows.md) |
| Create a portable reusable task method | [Skills](skills.md) |
| Turn supported repeated work into reviewed Python | [Automations](automations.md) |
| Automatically report agent results and request reviewed skills | [Automatic task feedback](automatic-task-feedback.md) |
| Report task outcomes and search/learn from past work | [Task history and learning](task-history-and-learning.md) |
| Give a person or service limited access | [Permissions](permissions.md) |
| Configure budgets and remote processing | [Configuration](configuration.md) |
| Inspect, compare and restore revisions | [History walkthrough](history-walkthrough.md), [revision rules](versioning.md) |
| Back up and recover a lost installation | [Backup and recovery](backup-and-recovery.md) |
| Import files or selected Gmail labels | [Connectors](connectors.md) |
| Run background processes or a private company server | [Deployment](deployment.md), [team setup](team-server.md) |
| Fix a setup or usage problem | [Troubleshooting](troubleshooting.md) |
| Understand the core modules, data and trust boundaries | [Architecture](architecture.md) |

## Development and maintenance

| Goal | Guide |
| --- | --- |
| See what changed between releases | [Changelog](../CHANGELOG.md) |
| Check supported behavior and evidence | [Support matrix](implementation-status.md), [validation](validation.md) |
| Contribute and run checks | [Contributing](../CONTRIBUTING.md), [testing](testing.md) |
| Keep guides accurate as behavior changes | [Documentation maintenance](documentation.md) |
| Prepare software versions and release artifacts | [Release versioning](release-versioning.md), [releasing](releasing.md) |
| Configure or operate npm publishing | [Publishing](package-publishing.md) |
| Inspect earlier test records | [Historical validation](release-validation.md) |
| Explore future work and design choices | [Roadmap](roadmap.md), [architecture decision](adr/0001-local-core.md), [references](references.md) |

Mermaid diagrams live in the README and relevant guides. Their [standalone sources](diagrams) are generated from Markdown; see documentation maintenance before changing them.
