# mcp-gateway — plan podziału `server.py`

**Powiązane:** [spis dokumentacji](README.md) · [REFACTORING_PLAN.md](../REFACTORING_PLAN.md) · [IDE_AND_AGENT_INTEGRATION.md](IDE_AND_AGENT_INTEGRATION.md) · [`code_analysis.py`](../mcp-skills/code_analysis.py)

Stan wyjściowy: **~2908 linii** w jednym pliku (`mcp-gateway/server.py`).

Cel: moduły po **200–500 linii**, zachowanie API (`import server as gateway` w testach).

## Docelowa struktura

```
mcp-gateway/
├── server.py              # FastAPI routes only (~250 L)
├── gateway_config.py      # env, stałe, SKILL_MODELS (~80 L)
├── gateway_prompt.py      # parse_prompt_context, parse_tool_intent (~270 L) ✅
├── gateway_github.py      # NLP GitHub commands, repo URL helpers (~240 L) ✅
├── gateway_skills.py      # klient HTTP mcp-skills (~260 L) ✅
├── gateway_jobs.py        # Redis/RQ job store (~175 L) ✅
├── gateway_dispatch.py    # dispatch_skill workflow (~250 L) ✅
├── gateway_tenants.py     # load_tenants, auth, audit, repo usage (~220 L)
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

### Etap 2 — parsowanie i GitHub (zrobione)

6. ✅ `gateway_prompt.py` — `parse_tool_intent`, `parse_prompt_context`, `message_content_to_text`
7. ✅ `gateway_github.py` — NLP detekcja komend GitHub + `normalize_repo_url`, `github_repo_from_url`

### Etap 3 — orkiestracja (zrobione)

8. ✅ `gateway_skills.py` — klient HTTP mcp-skills (`expect_json`, `run_skills_analysis`, `run_skills_tool`, …)
9. ✅ `gateway_jobs.py` — Redis/RQ job store, `execute_dispatch_job`
10. ✅ `gateway_dispatch.py` — `dispatch_skill` (sync → analyze → commit/push/PR)
11. ✅ `gateway_github.py` — rozszerzony o token/PR/URL helpers (`inject_github_token`, `create_github_pr`, …)

### Etap 3 — następny

12. ⬜ `gateway_chat.py` — logika `chat_completions` runner (opcjonalnie)
13. ⬜ `gateway_gh2mcp.py` — gh2mcp HTTP helpers z `server.py`
14. ⬜ `server.py` → routes only (**< 400 L**)

## Kontrakt kompatybilności

`server.py` na końcu etapu 3:

```python
from gateway_prompt import parse_tool_intent, parse_prompt_context  # noqa: F401
from gateway_github import normalize_repo_url, github_repo_from_url  # noqa: F401
from gateway_render import render_chat_content, render_analyze_text  # noqa: F401
# ... pozostałe re-eksporty dla testów
```

Testy (`import server as gateway`) **nie wymagają zmian**.

## Priorytet splitu po rozmiarze plików

Na podstawie analyze `semcod/mcp`:

| Plik | Linie | Akcja |
|------|-------|-------|
| `mcp-gateway/server.py` | ~1205 | routes + gh2mcp + chat (było ~2908) |
| `mcp-gateway/gateway_dispatch.py` | ~248 | ✅ etap 3 |
| `mcp-gateway/gateway_jobs.py` | ~175 | ✅ etap 3 |
| `mcp-gateway/gateway_skills.py` | ~263 | ✅ etap 3 |
| `mcp-gateway/gateway_github.py` | ~432 | ✅ etap 2b+3 |
| `mcp-gateway/gateway_prompt.py` | ~271 | ✅ etap 2a |
| `mcp-skills/server.py` | ~1482 | osobny etap: `tools_registry.py`, `analysis_http.py`, `mcp_stdio.py` |
| `llm-agent/agent_git2mcp.py` | ~360 | użyć `code_analysis` zamiast duplikatu `CachedCodeAnalyzer` |

## Definition of Done

- [ ] `server.py` < 400 linii
- [x] `pytest mcp-gateway/` green bez zmian importów (90/90; `test_import` mcp_gateway — pre-existing)
- [x] `make smoke` + analyze job zwraca `largest_files[0].path` konkretny — [`code_analysis.py`](../mcp-skills/code_analysis.py), gateway `_enrich_analysis_with_file_metrics`
- [x] brak cyklicznych importów między modułami gateway
