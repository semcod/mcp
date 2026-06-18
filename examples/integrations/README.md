# Przykłady integracji IDE i agentów

Gotowe pliki konfiguracyjne dla [`docs/IDE_AND_AGENT_INTEGRATION.md`](../docs/IDE_AND_AGENT_INTEGRATION.md).

| Plik | Narzędzie |
|------|-----------|
| [`cursor-mcp.json`](cursor-mcp.json) | Cursor — MCP stdio przez Docker |
| [`claude-desktop-mcp.json`](claude-desktop-mcp.json) | Claude Desktop — MCP stdio |
| [`continue-config.snippet.json`](continue-config.snippet.json) | Continue.dev — fragment `config.json` |

## Szybki start

```bash
# 1) Uruchom stack
cd ~/github/semcod/mcp && make start

# 2) Cursor — skopiuj config (dostosuj ścieżkę docker-compose)
cp examples/integrations/cursor-mcp.json ~/.cursor/mcp.json

# 3) VS Code / Continue — wklej modele z continue-config.snippet.json

# 4) Test gateway
curl -s -H "Authorization: Bearer sk-mcp-default-dev-key" http://localhost:9000/v1/models
```
