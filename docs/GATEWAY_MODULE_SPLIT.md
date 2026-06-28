# mcp-gateway — architektura modułów po refaktoryzacji

**Powiązane:** [spis dokumentacji](README.md) · [USAGE.md](USAGE.md) · [SEMCOD_MCP_CLI.md](SEMCOD_MCP_CLI.md) · [REFACTORING_PLAN.md](../REFACTORING_PLAN.md)

Stan wyjściowy (2026-06): **~2908 linii** w jednym pliku (`mcp-gateway/server.py`).

Stan docelowy: **~228 linii** w `server.py` (tylko routes + re-eksporty dla testów), logika w modułach `gateway_*` po **50–460 linii**.

---

## Po co ten podział — korzyści

| Korzyść | Co to daje w praktyce |
|---------|------------------------|
| **Niższa złożoność (CC)** | code2llm wskazywał 20 metod z CC>15; po splicie łatwiej utrzymać limit i review PR |
| **Szybsze testy** | `pytest mcp-gateway/` ~1 s; monkeypatch na `import server as gateway` bez zmian w testach |
| **Izolowane zmiany** | NLP GitHub, render Markdown, dispatch refactor — osobne pliki, mniejsze konflikty merge |
| **Bezpieczniejszy Docker** | `make reload-gateway` kopiuje tylko potrzebne moduły; bind-mounty w compose dla dev |
| **Łatwiejsze rozszerzanie** | nowy skill → `gateway_dispatch.py` + ewentualnie `dispatch_*.py`; nowa komenda czatu → `gateway_github_nlp.py` |
| **Lepsza obserwowalność** | audit w `gateway_tenants`, joby w `gateway_jobs`, chat routing w `chat_workflow_handlers.py` |

---

## Jak używać (developer)

### Uruchomienie i weryfikacja

```bash
# Stack + smoke (health, modele, tools/list, webui)
make start
make smoke

# Po zmianach w gateway / gh2mcp / skills
make reload-gateway

# Testy jednostkowe (gateway + gh2mcp + fragmenty skills)
make pytest
# lub tylko gateway:
cd mcp-gateway && python3 -m pytest -q
```

### Gdzie szukać logiki

| Chcesz… | Plik |
|---------|------|
| Dodać endpoint HTTP | `server.py` |
| Zmienić routing czatu / SSE | `gateway_chat.py`, `chat_workflow_handlers.py` |
| Nowa komenda „pokaż repo GitHub” | `gateway_github_nlp.py` |
| Token, PR, URL repo | `gateway_github.py` |
| Analyze / refactor workflow | `gateway_dispatch.py`, `dispatch_refactor.py` |
| Format odpowiedzi w czacie | `gateway_render.py`, `render_tools.py`, `render_system_actions.py` |
| Parsowanie promptu użytkownika | `gateway_prompt.py` |
| GitHub Q&A (OpenRouter) | `gateway_gh2mcp.py` + `gateway_skills.ask_openrouter_github_qa` |
| Joby w tle (Redis/RQ) | `gateway_jobs.py` |

### Kontrakt testów

Testy używają `import server as gateway` i monkeypatchują `gateway._*` — **nie zmieniaj nazw re-eksportów** na końcu `server.py` bez aktualizacji testów.

### Konfiguracja GitHub Q&A

W `.env`:

```bash
OPENROUTER_API_KEY=sk-or-v1-...
LLM_MODEL=openrouter/x-ai/grok-code-fast-1
```

Model w czacie: `mcp-skills/github-qa`. Bez klucza gateway zwróci czytelny komunikat o `OPENROUTER_API_KEY` (nie wywołuje OpenRouter).

```bash
curl -s -H "Authorization: Bearer sk-mcp-default-dev-key" \
  -H "Content-Type: application/json" \
  -d '{"model":"mcp-skills/github-qa","messages":[{"role":"user","content":"jakie mam ostatnie repo?"}]}' \
  http://localhost:9000/v1/chat/completions
```

---

## Struktura plików (aktualna)

### mcp-gateway

```
mcp-gateway/
├── server.py                  # ~228 L  routes + re-eksporty
├── gateway_config.py          # env, SKILL_MODELS
├── gateway_models.py          # Pydantic request models
├── gateway_tenants.py         # auth, audit, repo usage
├── gateway_prompt.py          # parse_prompt_context, parse_tool_intent
├── gateway_github.py          # URL, token, PR, env file
├── gateway_github_nlp.py      # detekcja komend NLP (token, org, lista repo)
├── gateway_gh2mcp.py          # klient gh2mcp, repo templates, GitHub Q&A
├── gateway_skills.py          # klient HTTP mcp-skills, OpenRouter Q&A
├── gateway_jobs.py            # Redis/RQ job store
├── gateway_dispatch.py        # sync + analyze + delegacja refactor
├── dispatch_refactor.py       # commit, push, PR w refactor
├── gateway_chat.py            # handle_chat_completions, SSE
├── chat_workflow_handlers.py  # GitHub admin, tools list, tool intent
├── gateway_render.py          # render_chat_content, analyze/refactor MD
├── render_tools.py            # render_tool_text, tools list
├── render_system_actions.py   # render list repo/org
├── render_refactor_actions.py # sekcja statusu refactor
└── worker.py                  # RQ worker
```

### mcp-skills (split tool_run)

```
mcp-skills/
├── server.py
├── code_analysis.py
├── analysis_recommendations.py
├── tool_run.py           # cienki orchestrator (~106 L)
├── tool_materialize.py   # git clone / git-proxy sync
├── tool_exec.py          # pip install, subprocess, fallback
├── tool_common.py        # truncate, limity
├── tools_registry.py
└── ...
```

### gh2mcp

```
gh2mcp/
├── sync.py              # GitHubTokenSyncService (cienki)
└── gh_repo_queries.py   # gh repo list, token resolve, dedupe
```

---

## Mapowanie funkcji → moduł

| Moduł | Odpowiedzialność |
|-------|------------------|
| `gateway_config.py` | `TENANTS_DIR`, `SKILLS_URL`, `SKILL_MODELS`, `OPENROUTER_API_KEY` |
| `gateway_tenants.py` | `load_tenants`, `authenticate`, `audit` |
| `gateway_prompt.py` | `parse_tool_intent`, `parse_prompt_context` |
| `gateway_github_nlp.py` | `is_repo_list_command`, `is_github_token_save_command`, … |
| `gateway_github.py` | `normalize_repo_url`, `create_github_pr`, `save_github_token` |
| `gateway_render.py` | `render_chat_content`, `render_analyze_text` |
| `gateway_skills.py` | `run_skills_tool`, `ask_openrouter_github_qa` |
| `gateway_dispatch.py` | `dispatch_skill` (sync → skill) |
| `dispatch_refactor.py` | commit / push / PR w refactor |
| `server.py` | `app`, routes HTTP |

---

## Historia migracji (zakończona)

1. ✅ `gateway_config.py`, `gateway_render.py`
2. ✅ mcp-skills: `tools_registry`, `tool_run`, `code_analysis`
3. ✅ `gateway_prompt.py`, `gateway_github.py`
4. ✅ `gateway_skills`, `gateway_jobs`, `gateway_dispatch`
5. ✅ `gateway_gh2mcp`, `gateway_chat`, `gateway_tenants`, `server.py` < 400 L
6. ✅ `render_tools.py`, `render_system_actions.py`, `render_refactor_actions.py`
7. ✅ `dispatch_refactor.py`, `gateway_github_nlp.py`, `chat_workflow_handlers.py`
8. ✅ tool_run → `tool_materialize` + `tool_exec`; gh2mcp → `gh_repo_queries`
9. ✅ Dockerfile + `semcod/.dockerignore` + compose bind-mounty

## Definition of Done

- [x] `server.py` < 400 linii (~228 L)
- [x] `pytest mcp-gateway/` green (91+ testów)
- [x] `make reload-gateway` + `make smoke` OK
- [x] brak cyklicznych importów między modułami gateway
- [x] `render_tool_text` wydzielony do `render_tools.py`
- [x] code2llm HEALTH: główne hotspoty gateway/skills/gh2mcp zaadresowane

## Kolejne kroki (opcjonalnie)

- `mcp-webui/server.py`, `llm-agent/*` — osobne etapy
- `env2mcp/config.save` (CC=20)
- pełny `make test` (skrypty + ansible E2E)
