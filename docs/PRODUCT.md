# MCP Skills as a Product

Pakiet usług dla klientów: `mcp-skills` jako serwis SaaS, sterowany przez własnego LLM-agenta poprzez `git2mcp`, dostępny dla użytkowników końcowych przez OpenWebUI.

Praktyczne use-case i gotowe prompty (refactor/migration/integration): `docs/USE_CASES.md`.

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
                           |  gh2mcp-agent  |
                           | (gh token sync |
                           |   to .env)     |
                           +----------------+
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
                    -> mcp-docs  (8093) -> statyczna dokumentacja + playbooki
```

## Sieci Docker

- `mcp-internal` — wewnętrzna, bez publicznych portów (proxy, skills, agent)
- `mcp-public` — publiczne usługi: gateway (9000), webui (8092), mcp-docs (8093), openwebui (3000), dashboard (8085)

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

## Endpointy mcp-git-proxy (port 8081)

**Repo:**
- `GET /health`
- `GET /repos` — lista lokalnych repo
- `POST /repos/sync` — klonuj lub sync repo (z URL lub source_path)
- `POST /repos/{id}/sync-pull` — pull z remote
- `POST /repos/{id}/commit` — commit zmian
- `POST /repos/{id}/push` — push do remote
- `POST /repos/{id}/run-tests` — uruchom testy
- `POST /repos/{id}/worktree/read|write` — odczyt/zapis pliku
- `POST /repos/{id}/worktree/diff` — diff roboczy
- `POST /repos/{id}/branch/draft` — stwórz draft branch
- `POST /repos/{id}/checkpoint` — snapshot worktree
- `POST /repos/{id}/checkpoint/restore` — przywróć snapshot
- `POST /repos/{id}/patch/apply` — aplikuj patch
- `POST /repos/{id}/stage` — staging plików
- `POST /repos/{id}/stash/save|pop` — stash

**GitHub API (przez mcp-git-proxy):**
- `POST /github/create-repo` — stwórz nowe repo na GitHubie + opcjonalne klonowanie lokalne

  ```json
  {
    "name": "nowe-repo",
    "description": "opis",
    "private": true,
    "auto_clone": true,
    "branch": "main",
    "github_token": "ghp_..."
  }
  ```
  Token można przekazać w body lub ustawić `GITHUB_PAT` w env kontenera.

## Endpointy mcp-webui (port 8092)

- `GET /` — dashboard
- `GET /repos` — lista + sync form
- `GET /github` — konfiguracja GitHub (token, create-repo, clone, sync)
- `POST /github/fetch-token-from-cli` — pobierz token z `gh auth token` i zapisz do `.env`
- `POST /github/configure` — zapisz/usuń token ręcznie
- `POST /github/create-repo` — utwórz nowe repo (przez mcp-git-proxy)
- `POST /github/clone` — sklonuj repo
- `POST /github/sync` — pull updates
- `GET /skills` — invoke modeli przez gateway
- `GET /playground` — free-form prompt
- `GET /diff` — worktree diff

## Endpointy mcp-docs (port 8093)

- `GET /health` — healthcheck
- `GET /` — strona główna dokumentacji i playbooki chat

## Endpointy gh2mcp-agent (port 8079)

- `GET /health` — status usługi
- `GET /status` — status tokenu (`configured`, `user`, `token_hint`)
- `POST /sync/token` — wymuś synchronizację tokenu do `.env`
- `POST /org/set` — ustaw domyślną organizację GitHub (`{"org": "semcod"}`)
- `POST /org/list` — lista organizacji i ich repo (`{"repos_limit": 30}`)
- `POST /repo/last-pushed` — znajdź ostatnio pushowane repo (`{"owner": "...", "limit": 100}`)

### Prompt contract dla `mcp-skills/refactor`

Gateway parsuje z promptu (lub z `extra_body`) pola:

- `Repo` (lub template: `{{pokaż ostatnie repo z github}}`)
- `Repo URL` (opcjonalnie, shorthand `owner/repo`)
- `GitHub Token` (opcjonalnie, zapisywany do `.env` przez `env2mcp`)
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
Przy podaniu `GitHub Token: ...` gateway zapisuje token do `.env` i używa go przy kolejnych synchronizacjach GitHub.

`Repo URL` wspiera również skrót `owner/repo` (mapowany do `https://github.com/owner/repo.git`).

### Komendy systemowe w czacie (gateway)

Gateway rozpoznaje intencje tekstowe i routuje je do odpowiednich akcji systemowych zamiast workflow refactor/analyze:

| Komenda (przykład) | Akcja |
|---|---|
| `Pobierz token GitHub z gh CLI` | `gh2mcp /sync/token` → sync tokenu do `.env` |
| `Zapisz token github do .env: ghp_xxx` | `env2mcp.EnvConfig` → zapis `GITHUB_PAT` |
| `Ustaw organizację: semcod` | `gh2mcp /org/set` |
| `Pokaż listę repo organizacji` | `gh2mcp /org/list` |
| `Repo: {{pokaż ostatnie repo z github}}` | `gh2mcp /repo/last-pushed` → auto-resolve repo_id |

### Skrypt `refactor-last-repo.sh`

Automatyzuje najczęstszy przepływ: wybór ostatnio pushowanego repo z GitHub → analiza → refactor.

```bash
bash scripts/refactor-last-repo.sh                          # analyze-only
bash scripts/refactor-last-repo.sh --execute --push --pr    # pełny cykl
bash scripts/refactor-last-repo.sh --repo owner/repo --execute --task "Etap 2"
```

Wyniki zapisywane do `output/refactor-last-repo-<timestamp>/`.

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
- Generowanie i testowanie repo demo przez system (`make generate-demo-repos`) pod scenariusze produktu.
- Skrypt `refactor-last-repo.sh` do automatycznego workflow: ostatnie repo → analiza → refactor → push → PR.
- Komendy systemowe w czacie: sync/zapis tokenu, zarządzanie organizacjami, auto-resolve repo.
- Serwis `mcp-docs` (port 8093) z dokumentacją i playbookami chat.

### Co działa przez MCP WebUI (`http://localhost:8092/github`)

- **Konfiguracja GitHub tokenu** — 3 metody: gh CLI jednym kliknięciem, PAT ręcznie, lub `.env`.
- **Pobieranie tokenu z gh CLI** — `POST /github/fetch-token-from-cli` odczytuje `gh auth token` i zapisuje do `.env`.
- **Tworzenie nowego repo na GitHubie** — formularz + `POST /github/create-repo` przez `mcp-git-proxy`.
- **Klonowanie repo** — `owner/repo` lub pełny URL z automatycznym wstrzyknięciem tokenu.
- **Sync/pull** istniejących lokalnych repo.
- **Test integracji GitHub** — `make ansible-github-test` (weryfikacja tokenu + create-repo + cleanup).

### Co jeszcze wymaga pracy do pełnego „auto-refactor + GitHub update”

1. Automatyczna modyfikacja kodu źródłowego (obecnie commitowane są artefakty planu `.mcp/*`).
2. Iteracyjny loop patchowania z rollbackiem checkpointów i polityką retry.
3. Rozszerzenie PR workflow (reviewers/labels/assignees, polityki merge i approval gates).
4. Dodatkowe guard-raile produkcyjne (approval gates, repo allowlist, limits na zakres zmian).
5. Trwała kolejka i storage jobów (`Redis/Postgres`) zamiast in-memory `JOBS`.
