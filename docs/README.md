# Dokumentacja semcod/mcp

Spis treści i linki między dokumentami projektu [semcod/mcp](https://github.com/semcod/mcp).

---

## Start

| Dokument | Opis |
|----------|------|
| [README.md](../README.md) | Quick start, architektura, lista serwisów |
| [**CURSOR_MCP_WORKFLOW.md**](CURSOR_MCP_WORKFLOW.md) | **Cursor Agent** — reload MCP, test, workflow 3-fazowy |
| [USAGE.md](USAGE.md) | 10+ scenariuszy end-to-end (OpenWebUI, GitHub, analyze, refactor) |
| [SEMCOD_MCP_CLI.md](SEMCOD_MCP_CLI.md) | Pakiet `semcod-mcp`: `init`, `deinit`, `doctor`, `validate`, `analyze` |
| [IDE_AND_AGENT_INTEGRATION.md](IDE_AND_AGENT_INTEGRATION.md) | Cursor, VS Code, Windsurf, Continue, Devin, A2A |

---

## Integracja IDE i wielu projektów

| Temat | Gdzie |
|-------|-------|
| Idempotentny `semcod-mcp init` | [SEMCOD_MCP_CLI.md](SEMCOD_MCP_CLI.md) |
| Rejestry paczek, skilli, manifestów | [IDE_AND_AGENT_INTEGRATION.md § Rejestry](IDE_AND_AGENT_INTEGRATION.md#rejestry-paczek-skilli-i-integracji-ide) |
| Hurtowe `init` dla folderu/org | [IDE_AND_AGENT_INTEGRATION.md §9](IDE_AND_AGENT_INTEGRATION.md#9-automatyczne-podpięcie-do-wielu-projektów) |
| Przykłady plików MCP | [examples/integrations/README.md](../examples/integrations/README.md) |

---

## Analiza kodu i refaktoryzacja

| Dokument | Opis |
|----------|------|
| [USAGE.md § Jak czytać wynik](USAGE.md#jak-czytać-wynik-w-czacie) | Markdown w czacie + `GET /jobs/{id}` |
| [GATEWAY_MODULE_SPLIT.md](GATEWAY_MODULE_SPLIT.md) | Plan podziału `mcp-gateway/server.py` |
| [REFACTORING_PLAN.md](../REFACTORING_PLAN.md) | Roadmap produktowy (etapy 1–6) |
| [USE_CASES.md](USE_CASES.md) | Gotowe prompty refactor/migration |
| [CHAT_PLAYBOOKS.md](CHAT_PLAYBOOKS.md) | Dialogi operacyjne copy/paste |

### Moduły po refaktorze (2026-06)

**mcp-skills:** `server.py` (~690 L), `code_analysis.py`, `tools_registry.py`, `tool_run.py`, `http_models.py`, `redsl_runner.py`, `mcp_parse.py`

**mcp-gateway:** `server.py` (~2480 L), `gateway_config.py`, `gateway_render.py` — etap 2 w [GATEWAY_MODULE_SPLIT.md](GATEWAY_MODULE_SPLIT.md)

---

## Architektura i API

| Dokument | Opis |
|----------|------|
| [PRODUCT.md](PRODUCT.md) | Multi-tenant, bezpieczeństwo, deployment |
| [ENV2MCP.md](ENV2MCP.md) | Zarządzanie `.env` i tokenem GitHub |
| [LINKED_EXAMPLES.md](LINKED_EXAMPLES.md) | Powiązane przykłady w ekosystemie |

### Rejestry runtime (gdy stack działa)

```bash
# Modele / skilli gateway (analyze, refactor, tool, github-qa)
curl -s -H "Authorization: Bearer sk-mcp-default-dev-key" http://localhost:9000/v1/models

# Paczki CLI semcod/* (sumd, code2llm, pyqual, …)
docker compose exec -T mcp-skills python -c \
  "import urllib.request,json; print(json.dumps(json.loads(urllib.request.urlopen('http://127.0.0.1:8080/tools/list').read()), indent=2))"
```

Źródło prawdy w kodzie: `mcp-skills/server.py` (`SUPPORTED_TOOLS`), `mcp-gateway/server.py` (`SKILL_MODELS`).

---

## Inne

| Dokument | Opis |
|----------|------|
| [CHANGELOG.md](../CHANGELOG.md) | Historia zmian |
| [TODO.md](../TODO.md) | Zadania pyqual / roadmap |
| [git2mcp/README.md](../git2mcp/README.md) | Pakiet git2mcp |
| [env2mcp/README.md](../env2mcp/README.md) | Pakiet env2mcp |
