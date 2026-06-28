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
| [SEMCOD_ECOSYSTEM.md](SEMCOD_ECOSYSTEM.md) | semcod-mcp + code2llm, koru, planfile, wup — korzyści i workflow bez commita |
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
| [GATEWAY_MODULE_SPLIT.md](GATEWAY_MODULE_SPLIT.md) | Architektura gateway po splicie: korzyści, jak używać, mapa modułów |
| [REFACTORING_PLAN.md](../REFACTORING_PLAN.md) | Roadmap produktowy (etapy 1–6) |
| [USE_CASES.md](USE_CASES.md) | Gotowe prompty refactor/migration |
| [CHAT_PLAYBOOKS.md](CHAT_PLAYBOOKS.md) | Dialogi operacyjne copy/paste |

### Moduły po refaktorze (2026-06)

**mcp-gateway** (~228 L `server.py` + moduły `gateway_*`): szczegóły, korzyści i workflow developera w [**GATEWAY_MODULE_SPLIT.md**](GATEWAY_MODULE_SPLIT.md).

**mcp-skills:** `server.py`, `code_analysis.py`, `analysis_recommendations.py`, `tool_run.py` (+ `tool_materialize`, `tool_exec`, `tool_common`), `tools_registry.py`, `http_models.py`, `redsl_runner.py`, `mcp_parse.py`

**gh2mcp:** `sync.py`, `gh_repo_queries.py`

**CLI:** `semcod-mcp init` / `deinit` — [SEMCOD_MCP_CLI.md](SEMCOD_MCP_CLI.md)

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
