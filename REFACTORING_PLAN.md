# Refactoring Plan: MCP Skills jako produkt

## Cel produktowy

- Sprzedawalny pakiet `mcp-skills` jako usługa (multi-tenant, izolowana).
- OpenWebUI jako frontend dla użytkownika końcowego.
- `git2mcp-agent` jako orchestrator: konsumuje wskazówki z `mcp-skills`, używa `git2mcp` na `mcp-git-proxy`.
- `git2mcp` rozszerzony o operacje lokalne (bez `commit`/`push`).
- Web GUI testowy `mcp-webui` dla QA i demo.

## Docelowy podział usług

- `mcp-git-proxy` — operacje Git, dodane endpointy lokalne.
- `mcp-skills` — własny cache, fragment-sync (jest); HTTP API obok STDIO.
- `git2mcp-agent` (z `llm-agent`) — workflow async, OpenRouter.
- `mcp-gateway` — publiczny endpoint, OpenAI-compatible shim, auth, multi-tenant routing, rate-limit.
- `mcp-webui` — testowy Web GUI (FastAPI + HTMX).
- `openwebui` — `ghcr.io/open-webui/open-webui`, wskazuje na `mcp-gateway`.
- `dashboard` — przepięty na gateway.

## Nowe metody w `git2mcp` (poza commit/push)

- `POST /repos/{id}/worktree/write`
- `POST /repos/{id}/worktree/read`
- `POST /repos/{id}/worktree/diff`
- `POST /repos/{id}/patch/apply`
- `POST /repos/{id}/stage`
- `POST /repos/{id}/stash/save`
- `POST /repos/{id}/stash/pop`
- `POST /repos/{id}/branch/draft`
- `POST /repos/{id}/checkpoint` (snapshot working-tree do tarballa, rollback bez commita)

`commit`, `push`, `reset` — etap finalny.

## Nowy workflow agenta

1. Sync repo do `mcp-git-proxy`.
2. Fragment-sync do `mcp-skills`.
3. `mcp-skills` → wskazówki / recommended_edits.
4. LLM → patch JSON → `patch/apply`.
5. `run-tests` w working-tree.
6. OK → `commit` w `draft/<task-id>` + opcjonalny `push`.
7. NOK → `stash` lub `checkpoint` rollback, kolejna iteracja (max N).
8. Wynik publikowany do gateway → OpenWebUI/Web GUI.

## OpenWebUI

- Mówi OpenAI Chat Completions API.
- `mcp-gateway` jako shim:
  - `POST /v1/chat/completions` (SSE) — woła workflow, streamuje progres.
  - `GET /v1/models` — `mcp-skills/refactor`, `mcp-skills/analyze`, ...
- `OPENROUTER_API_KEY` / `LLM_MODEL` w gateway/agent, nie w przeglądarce.

## Web GUI testowy `mcp-webui`

- FastAPI + Jinja + HTMX + Tailwind.
- Strony: Repos, Skills, Refactor playground, Diff viewer.
- Port `8090`, gada z `mcp-gateway`.

## Multi-tenancy

- `tenant_id` + API key + quota.
- Ścieżki: `git-repos/<tenant>/<repo_id>`, `skills-cache/<tenant>/<repo_id>`.
- Gateway: auth Bearer, rate-limit, billing (koszt LLM per request).
- Konfiguracja tenantów: `tenants/*.yaml` w MVP, Postgres później.

## Bezpieczeństwo

- Wewnętrzne usługi bez publicznych portów.
- Sieć `mcp-internal` (private) i `mcp-public` dla gateway/webui/openwebui.
- Walidacja patchy: rozmiar, allowlist ścieżek per tenant.
- Audyt w `audit-storage`.

## Etapy

- **Etap 1 — lokalne operacje Git** (`worktree/*`, `patch/apply`, `stash`, `branch/draft`, `checkpoint`) + przykład `05_local_iterate.py` + testy.
- **Etap 2 — `mcp-gateway` + HTTP API skills**, OpenAI-compat shim z SSE, auth.
- **Etap 3 — `mcp-webui`** (FastAPI + HTMX).
- **Etap 4 — `openwebui` w compose**, integracja z gateway.
- **Etap 5 — multi-tenant + billing + audyt**.
- **Etap 6 — produktyzacja** (obrazy, dokumentacja, `docker-compose.prod.yml`, licencja).

## Decyzje do zatwierdzenia

- Web GUI: HTMX (rekomendacja MVP) vs React.
- Job store: in-memory vs Redis (rekomendacja: Redis od Etapu 2).
- SSE w gateway: tak, od razu.
- Tenanty: YAML w MVP, Postgres w Etapie 5.

## Kryteria akceptacji

- Klient z OpenWebUI zleca refaktor → streamowany progres → diff w `mcp-webui` → akceptacja → push.
- `mcp-skills` i `mcp-git-proxy` nieosiągalne publicznie.
- Iteracje przed commit-em używają `patch/apply` + `worktree`, historia Git czysta.
- `pytest` + `scripts/test.sh` pokrywają nowe endpointy i workflow.

## Podział kodu (gateway / skills)

Szczegółowy plan modułów dla `mcp-gateway/server.py` (~2900 linii): **[docs/GATEWAY_MODULE_SPLIT.md](docs/GATEWAY_MODULE_SPLIT.md)**.

Wspólne metryki analizy: **`mcp-skills/code_analysis.py`** (używane przez `/analyze/*`, `/refactor/redsl`, enrich w gateway).
