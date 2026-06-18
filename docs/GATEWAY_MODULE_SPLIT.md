# mcp-gateway — plan podziału `server.py`

**Powiązane:** [spis dokumentacji](README.md) · [REFACTORING_PLAN.md](../REFACTORING_PLAN.md) · [IDE_AND_AGENT_INTEGRATION.md](IDE_AND_AGENT_INTEGRATION.md) · [`code_analysis.py`](../mcp-skills/code_analysis.py)

Stan wyjściowy: **~2908 linii** w jednym pliku (`mcp-gateway/server.py`).

Cel: moduły po **200–500 linii**, zachowanie API (`import server as gateway` w testach).

## Docelowa struktura

```
mcp-gateway/
├── server.py              # FastAPI routes only (~250 L)
├── gateway_config.py      # env, stałe, SKILL_MODELS (~80 L)
├── gateway_tenants.py     # load_tenants, auth, audit, repo usage (~220 L)
├── gateway_prompt.py      # parse_prompt_context, parse_tool_intent (~400 L)
├── gateway_github.py      # token/org/repo admin + gh2mcp + PR helpers (~750 L)
├── gateway_render.py      # _render_* formatters (~550 L)
├── gateway_skills.py      # _run_skills_analysis, enrich, tools, github_qa (~400 L)
├── gateway_jobs.py        # Redis/RQ job store, execute_dispatch_job (~180 L)
├── gateway_dispatch.py    # dispatch_skill workflow (~240 L)
├── gateway_models.py      # Pydantic request models (~40 L)
└── tests/                 # bez zmian importów: server re-eksportuje symbole
```

## Mapowanie funkcji → moduł

| Moduł | Odpowiedzialność | Kluczowe symbole |
|-------|------------------|------------------|
| `gateway_config.py` | Konfiguracja środowiska | `TENANTS_DIR`, `SKILLS_URL`, `SKILL_MODELS`, `MCP_ASYNC_ENABLED` |
| `gateway_tenants.py` | Multi-tenant + historia repo | `load_tenants`, `authenticate`, `audit`, `_track_repo_usage` |
| `gateway_prompt.py` | Parsowanie promptów użytkownika | `parse_prompt_context`, `parse_tool_intent`, `message_content_to_text` |
| `gateway_github.py` | GitHub admin + PR | `_save_github_token`, `_create_github_pr`, `_list_recent_repos_via_gh2mcp` |
| `gateway_render.py` | Markdown dla chat UI | `_render_analyze_text`, `_render_refactor_text`, `_render_chat_content` |
| `gateway_skills.py` | Klient HTTP mcp-skills | `_run_skills_analysis`, `_enrich_analysis_with_file_metrics`, `_run_skills_tool` |
| `gateway_jobs.py` | Async jobs (Redis/RQ) | `_save_job`, `_load_job`, `execute_dispatch_job` |
| `gateway_dispatch.py` | Orkiestracja sync→analyze→commit | `dispatch_skill` |
| `server.py` | HTTP entrypoint | `app`, `chat_completions`, `get_job`, `health` |

## Kolejność migracji (bezpieczna)

### Etap 1 — bez zmiany zachowania (zrobione)

1. ✅ `mcp-skills/code_analysis.py` — wspólne metryki
2. ✅ `gateway_skills._enrich_analysis_with_file_metrics` — analyze zawsze ma `largest_files`
3. ✅ `gateway_config.py` — stałe env + `SKILL_MODELS`
4. ✅ `gateway_render.py` — formatowanie Markdown chat (~500 L)
5. ✅ **mcp-skills split:** `tools_registry.py`, `tool_run.py`, `http_models.py`, `redsl_runner.py`, `mcp_parse.py` — `server.py` ~1311→~690 L

### Etap 2 — następny

6. ⬜ `gateway_prompt.py` — `parse_tool_intent`, `parse_prompt_context`
7. ⬜ `gateway_github.py` — token/org/PR

### Etap 2 — parsowanie i GitHub

5. `gateway_prompt.py` — testy: `test_tool_intent.py`
6. `gateway_github.py` — testy: `test_gateway_token_command.py`

### Etap 3 — orkiestracja

7. `gateway_jobs.py` + `gateway_dispatch.py`
8. `server.py` → cienka warstwa routes

## Kontrakt kompatybilności

`server.py` na końcu etapu 3:

```python
from gateway_prompt import parse_tool_intent, parse_prompt_context  # noqa: F401
from gateway_render import _render_chat_content, _render_analyze_text  # noqa: F401
# ... pozostałe re-eksporty dla testów
```

Testy (`import server as gateway`) **nie wymagają zmian**.

## Priorytet splitu po rozmiarze plików

Na podstawie analyze `semcod/mcp`:

| Plik | Linie | Akcja |
|------|-------|-------|
| `mcp-gateway/server.py` | ~2908 | split wg tabeli powyżej |
| `mcp-skills/server.py` | ~1482 | osobny etap: `tools_registry.py`, `analysis_http.py`, `mcp_stdio.py` |
| `llm-agent/agent_git2mcp.py` | ~360 | użyć `code_analysis` zamiast duplikatu `CachedCodeAnalyzer` |

## Definition of Done

- [ ] `server.py` < 400 linii
- [ ] `pytest mcp-gateway/` green bez zmian importów
- [x] `make smoke` + analyze job zwraca `largest_files[0].path` konkretny — [`code_analysis.py`](../mcp-skills/code_analysis.py), gateway `_enrich_analysis_with_file_metrics`
- [ ] brak cyklicznych importów między modułami gateway
