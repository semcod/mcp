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
