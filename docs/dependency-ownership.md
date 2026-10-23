# Subproject dependency ownership

Every subproject requirement manifest is owned by the `application`
workstream and resolves to ticket-020 (cross-subproject dependency
maintenance). Automated dependency PRs that touch exactly these files
resolve to that single active ticket:

| Manifest | Owner |
| --- | --- |
| `llm-agent/requirements.txt` | application / ticket-020 |
| `mcp-docs/requirements.txt` | application / ticket-020 |
| `mcp-gateway/requirements.txt` | application / ticket-020 |
| `mcp-git-proxy/requirements.txt` | application / ticket-020 |
| `mcp-skills/requirements.txt` | application / ticket-020 |
| `mcp-webui/requirements.txt` | application / ticket-020 |

The managed standard contracts are pinned by `.governance/standard-adoption.json`;
its manifest artifact digest is re-pinned whenever the coordination
declaration changes through an adopted `goal governance` transaction.
