# MCP Skills as a Product

Pakiet usług dla klientów: `mcp-skills` jako serwis SaaS, sterowany przez własnego LLM-agenta poprzez `git2mcp`, dostępny dla użytkowników końcowych przez OpenWebUI.

## Architektura runtime

```
[ user ]
   |
   v
+-----------------+        +----------------+        +---------------+
|   OpenWebUI     | -----> |  mcp-gateway   | -----> |   mcp-skills  |
| (chat frontend) |  HTTP  | (OpenAI-compat |  HTTP  | (analiza,     |
|                 |  Auth  |  + auth +      |        |  metryki)     |
|                 |  SSE   |  multi-tenant) |        +---------------+
+-----------------+        +-------+--------+
                                   |
                                   v
                           +----------------+
                           |  mcp-git-proxy |
                           | (Git operations |
                           |  via HTTP API)  |
                           +----------------+
                                   ^
                                   |
                           +----------------+
                           |  llm-agent     |
                           | (git2mcp +     |
                           |  OpenRouter)   |
                           +----------------+

[ developer / QA ] -> mcp-webui (8092) -> mcp-gateway
```

## Sieci Docker

- `mcp-internal` — wewnętrzna, bez publicznych portów (proxy, skills, agent)
- `mcp-public` — publiczne usługi: gateway (9000), webui (8092), openwebui (3000), dashboard (8085)

## Konfiguracja klienta (tenant)

Plik YAML w `mcp-gateway/tenants/`, np. `acme.yaml`:

```yaml
tenant_id: acme
api_keys:
  - "sk-mcp-acme-prod-..."
quotas:
  max_repos: 50
  max_iterations_per_task: 10
  monthly_llm_usd: 200
features:
  refactor: true
  analyze: true
  push: true
audit:
  enabled: true
```

Wystarczy dodać plik i restart `mcp-gateway`.

## Endpointy gateway

- `GET /health`
- `GET /v1/models` — modele = skille MCP
- `POST /v1/chat/completions` — OpenAI-compatible (Bearer auth, SSE supported)
- `GET /jobs/{job_id}` — status zadania
- `GET /audit/tail?limit=N` — JSONL audit log

### Prompt contract dla `mcp-skills/refactor`

Gateway parsuje z promptu (lub z `extra_body`) pola:

- `Repo`
- `Repo URL` (opcjonalnie)
- `Source` (opcjonalnie)
- `Branch`
- `Execute` (`true/false`)
- `Push` (`true/false`)
- `Draft` (`true/false`)
- `Draft name` (opcjonalnie)
- `PR` (`true/false`)
- `PR title` / `PR body` / `PR base` (opcjonalnie)
- `Test`
- `Remote`
- `Zadanie`

Przy `Execute: true` gateway tworzy commit artefaktów planu (`.mcp/refactor-plan.json`, `.mcp/refactor-summary.md`) i uruchamia test command.
Przy `Push: true` wykonuje push tylko gdy:

1. tenant ma `features.push: true`,
2. testy zwrócą `ok: true`.

Przy `Draft: true` (domyślnie dla `Push: true`) gateway tworzy branch `draft/*` przed commitem.
Przy `PR: true` gateway próbuje utworzyć draft PR przez GitHub API (wymaga `GITHUB_TOKEN` lub `GITHUB_PAT` i repo URL wskazującego na GitHub).

## OpenWebUI

Konfiguracja środowiskowa kontenera:
- `OPENAI_API_BASE_URL=http://mcp-gateway:9000/v1`
- `OPENAI_API_KEY=<tenant api key>`

Po starcie dostępny pod `http://localhost:3000`.

## Uruchomienie

Dev:
```bash
docker-compose --profile openwebui up -d
```

Prod:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Bezpieczeństwo

- Wewnętrzne usługi (`mcp-git-proxy`, `mcp-skills`, `llm-agent`) nie mają portów na hoście w trybie produkcyjnym (overlay `docker-compose.prod.yml`).
- Wszystkie wywołania API gateway wymagają `Authorization: Bearer <key>`.
- Audit log w wolumenie `audit-storage` (JSONL).
- Walidacja patchy w `mcp-git-proxy` (path traversal blokowany w `worktree/write`).

## Status produktu (maj 2026)

### Co działa przez OpenWebUI (`http://localhost:3000`)

- Wywołanie `mcp-skills/refactor` i `mcp-skills/analyze` przez OpenAI-compatible API.
- Sync repo (`Repo URL` lub `Source`) do `mcp-git-proxy`.
- Analiza repo przez `mcp-skills` (metrics/patterns/recommendations).
- Opcjonalny commit + test + push + draft branch + draft PR przez prompt (`Execute`/`Push`/`Draft`/`PR`).
- Multi-tenant auth + audit.

### Co jeszcze wymaga pracy do pełnego „auto-refactor + GitHub update”

1. Automatyczna modyfikacja kodu źródłowego (obecnie commitowane są artefakty planu `.mcp/*`).
2. Iteracyjny loop patchowania z rollbackiem checkpointów i polityką retry.
3. Rozszerzenie PR workflow (reviewers/labels/assignees, polityki merge i approval gates).
4. Dodatkowe guard-raile produkcyjne (approval gates, repo allowlist, limits na zakres zmian).
5. Trwała kolejka i storage jobów (`Redis/Postgres`) zamiast in-memory `JOBS`.
