# MCP Autonomous Refactoring — Status systemu

## Architektura

- `mcp-git-proxy` — FastAPI + GitPython, wszystkie operacje Git przez API
- `git2mcp` — klient Python (`Git2MCPClient`) + manager (`GitProxyManager`)
- `mcp-skills` — serwer MCP z własnym cache repo (`/skills-cache`), brak shared volume `/git-repos`
- `llm-agent` — workflow `agent_git2mcp.py` oparty o OpenRouter lite
- `dashboard` — statyczny widok JSON-ów z `output/`

## LLM

- `LLM_PROVIDER=openrouter-lite`
- `LLM_MODEL=openrouter/x-ai/grok-code-fast-1`
- Ollama usunięta z `docker-compose.yml` i `.env`

## Endpointy `mcp-git-proxy`

- `GET /health`
- `GET /repos`
- `POST /repos/sync`
- `POST /packages/export`
- `POST /packages/export-fragments`
- `POST /packages/import`
- `POST /repos/{repo_id}/commit`
- `POST /repos/{repo_id}/run-tests`
- `POST /repos/{repo_id}/push`
- `POST /repos/{repo_id}/reset`

## Kluczowe właściwości

- **Refaktoryzacja = commit** przez API, bez edycji plików na dysku przez shell
- **Izolacja Git ↔ Skills**: `mcp-skills` dostaje repo wyłącznie przez MCP (fragmenty)
- **Migracja różnic** po stronie `mcp-skills`: `files_updated`, `files_unchanged`, `files_deleted`
- **Rollback**: `POST /repos/{repo_id}/reset` dla cofnięcia commitu przy failu testów
- **Hardening**: `safe.directory`, walidacja `PushInfo`, retry w kliencie HTTP

## Przykłady (`git2mcp/examples/`)

- `01_sync_and_commit.py` — sync + commit + `compileall`
- `02_fragment_sync_to_skills.py` — MCP fragmenty + migracja różnic w skills cache
- `03_agent_git2mcp.py` — wrapper pełnego flow agenta
- `04_dry_run_vs_execute.py` — `--dry-run` vs `--execute` z auto-revertem

## Testy

- `scripts/test.sh`:
  - struktura/składnia/docker validate
  - git2mcp workflow (`sample-project`, `another-project`)
  - push do lokalnego bare remote
  - 3x repo `semcod/*` → MCP fragmenty do `mcp-skills` bez shared volume
  - walidacja `files_unchanged` przy powtórnym sync
- `pytest git2mcp/tests/test_git2mcp.py`:
  - `sync → export → commit → run-tests`
  - `commit → reset` (rollback)
  - `sync → commit → push` do bare remote

## Odpowiedzi na kluczowe pytania

- **Czy zmiany w repo są robione przez `git2mcp`?** Tak, przez endpoint `/commit`.
- **Czy lokalny `git2mcp` aktualizuje dowolne repo przez MCP/API?** Tak, przykłady 01/03/04.
- **Czy `mcp-skills` wykrywa różnice i migruje?** Tak, fragment diff + per-file update/unchanged/delete.

## Etap 2-4 (produktyzacja)

- **`mcp-gateway`** — FastAPI, OpenAI-compatible shim:
  - `GET /v1/models`, `POST /v1/chat/completions` (z opcjonalnym SSE)
  - Bearer auth + multi-tenant routing (`tenants/*.yaml`)
  - audit log JSONL w `audit-storage`
  - in-memory job store (Redis → Etap 5+)
- **`mcp-webui`** — FastAPI + Jinja + HTMX + Tailwind, port `8092`:
  - dashboard, repos, skills, diff, playground
- **OpenWebUI** w compose (`profile=openwebui`), port `3000`, podpięty pod gateway
- **Sieci Docker**: `mcp-internal` (private) + `mcp-public` (gateway/webui/openwebui/dashboard)
- **`docker-compose.prod.yml`** — overlay produkcyjny (bez dev mountów)

## Endpointy lokalne git2mcp (Etap 1)

- `worktree/write|read|diff`, `patch/apply`, `stage`, `stash/save|pop`
- `branch/draft`, `checkpoint`, `checkpoint/restore`
- `reset` (rollback po failu testów)

## Smoke-test (po `docker-compose up -d mcp-git-proxy mcp-gateway mcp-webui`)

- `GET /health` -> ok, lista tenantów `["default"]`
- `GET /v1/models` z auth -> 200, bez auth -> 401
- `POST /v1/chat/completions` (analyze, refactor) -> 200, payload z `job_id`
- `mcp-webui /` -> 200

## Status

Gotowe i przetestowane. Wszystkie testy (`scripts/test.sh` + `pytest`) przechodzą.
Gateway, WebUI, OpenWebUI w compose; smoke-test wykonany na żywych kontenerach.
