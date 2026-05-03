# Autonomiczny Agent Refaktoryzacji MCP


## AI Cost Tracking

![PyPI](https://img.shields.io/badge/pypi-costs-blue) ![Version](https://img.shields.io/badge/version-0.1.31-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)
![AI Cost](https://img.shields.io/badge/AI%20Cost-$3.00-orange) ![Human Time](https://img.shields.io/badge/Human%20Time-4.7h-blue) ![Model](https://img.shields.io/badge/Model-openrouter%2Fqwen%2Fqwen3--coder--next-lightgrey)

- 🤖 **LLM usage:** $3.0000 (20 commits)
- 👤 **Human dev:** ~$469 (4.7h @ $100/h, 30min dedup)

Generated on 2026-05-03 using [openrouter/qwen/qwen3-coder-next](https://openrouter.ai/qwen/qwen3-coder-next)

---

System autonomicznej refaktoryzacji kodu oparty na Model Context Protocol (MCP), integrujący:
- **MCP Git Proxy** - izolowany serwis git z osobnym volume i API do sync/commit/test/push
- **MCP Skills Server** - analiza kodu i metryki na cache repozytoriów
- **LLM Agent (`git2mcp`)** - planowanie refaktoryzacji i commitowanie zmian przez proxy git
- **MCP Gateway** - publiczny shim OpenAI-compatible (auth, multi-tenant, SSE) do integracji z OpenWebUI
- **MCP WebUI** - panel testowy QA / admin dla `mcp-skills`
- **gh2mcp Agent** - synchronizacja tokenu GitHub z `gh` CLI do `.env` (autostart w Docker)

## Quick start

```bash
cp .env.example .env          # ustaw OPENROUTER_API_KEY i WEBUI_API_KEY
make start                    # killuje porty hostowe i uruchamia cały stack
```

### Konfiguracja GitHub (opcjonalna, wymagana do clone/push/create-repo)

```bash
# Metoda A — gh CLI (zalecana)
gh auth login                 # jednorazowe logowanie
make setup-github             # pobiera token z gh i zapisuje do .env

# Metoda B — przez WebUI (po make start)
# http://localhost:8092/github → "Pobierz token z gh CLI"

# Metoda C — ręcznie
echo "GITHUB_PAT=ghp_xxx" >> .env

# Test integracji GitHub
export GITHUB_PAT=ghp_xxx
make ansible-github-test      # weryfikuje token + create-repo + cleanup
```

`make start` uruchamia także `gh2mcp-agent`, który przy starcie może zsynchronizować token do `.env`
(`GH2MCP_SYNC_ON_START=true`).

```bash
# make stop                   # zatrzymuje wszystko
# make smoke                  # szybki test API gateway/webui
# make generate-demo-repos    # tworzy 3 repo demo (auto: github/local fallback)
# make generate-demo-repos-github  # wymusza tryb github (gh + fallback)
# make help                   # pełna lista targetów
```

| Serwis | URL |
|---|---|
| OpenWebUI (chat) | http://localhost:3000 |
| MCP WebUI (admin) | http://localhost:8092 |
| MCP WebUI GitHub | http://localhost:8092/github |
| Gateway (API) | http://localhost:9000 |
| Dashboard | http://localhost:8085 |
| Git Proxy (dev) | http://localhost:8081 |

Pełne scenariusze użycia: [`docs/USAGE.md`](docs/USAGE.md).
Architektura produktowa: [`docs/PRODUCT.md`](docs/PRODUCT.md).
Plan refaktoryzacji: [`REFACTORING_PLAN.md`](REFACTORING_PLAN.md).

## Architektura

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  LLM Agent  │────▶│ MCP Skills  │◀────│ MCP Git     │
│ (git2mcp)   │     │  Server     │     │ Proxy       │
└─────────────┘     └─────────────┘     └─────────────┘
      │
      ▼
┌─────────────┐
│  LLM API    │
│ (OpenRouter │
│  lite/model)│
└─────────────┘
```

### Jak działa separacja Git ↔ Skills

1. `mcp-git-proxy` zarządza wieloma repozytoriami (`team/repo-a`, `team/repo-b`, ...), klonuje je i utrzymuje historię git.
2. `git2mcp` eksportuje repo jako paczkę (`tar.gz + base64`) przez endpoint `/packages/export`.
3. `mcp-skills` synchronizuje paczkę do własnego cache (`/skills-cache`) narzędziem `sync_repo_from_git_proxy`.
4. `llm-agent` analizuje cache, tworzy plan i zapisuje zmiany jako commit przez API proxy (bez ręcznej edycji przez shell).
5. Commit można lokalnie przetestować (`/run-tests`) i dopiero potem wypchnąć (`/push`).

Tryb transferu do `mcp-skills`:
- preferowany: `POST /packages/export-fragments` (fragmenty `path + content_b64`, rekonstrukcja plików po stronie skills)
- fallback: `POST /packages/export` (`tar.gz + base64`)

`mcp-skills` nie współdzieli volume `/git-repos` z git proxy — otrzymuje repo wyłącznie przez MCP transfer.

## Szybki Start

### 1. Wymagania

- Docker & Docker Compose
- Python 3.11+ (dla lokalnego uruchomienia)
- (Opcjonalnie) GitHub PAT - dla operacji na repo
- (Opcjonalnie) OpenAI API Key - dla zaawansowanej analizy LLM

### 2. Instalacja

```bash
# Klonowanie i setup
./scripts/deploy.sh
```

### 3. Konfiguracja

```bash
# Skopiuj przykładową konfigurację
cp .env.example .env

# Edytuj .env zgodnie z potrzebami
nano .env
```

### 4. Uruchomienie

```bash
# Uruchom wszystkie serwisy
docker-compose up -d

# Uruchom agenta z analizą repozytorium
docker-compose run --rm llm-agent python agent_git2mcp.py \
  --repo team/my-repo \
  --repo-url https://github.com/team/my-repo.git
```

## Struktura Projektu

```
.
├── docker-compose.yml          # Konfiguracja Docker (dev)
├── docker-compose.prod.yml   # Overlay produkcyjny
├── Makefile                  # Zarządzanie cyklem życia (start, stop, smoke)
├── .env.example              # Przykładowa konfiguracja
├── README.md                 # Dokumentacja
├── CHANGELOG.md              # Historia zmian
├── TODO.md                   # Zadania do zrobienia
├── REFACTORING_PLAN.md       # Plan architektoniczny
│
├── mcp-git-proxy/            # MCP Git Proxy - operacje git przez HTTP API
│   ├── Dockerfile
│   ├── requirements.txt
│   └── server.py
│
├── git2mcp/                  # Pakiet Python do operacji git przez MCP
│   ├── git2mcp/
│   │   ├── client.py         # Async HTTP client
│   │   └── proxy.py          # GitProxyManager (serwer)
│   ├── examples/             # Przykłady użycia (01-05)
│   ├── tests/                # Testy pytest
│   ├── pyproject.toml
│   └── README.md
│
├── gh2mcp/                   # NOWOŚĆ: agent sync tokenu GitHub (gh -> .env)
│   ├── gh2mcp/
│   │   ├── sync.py
│   │   ├── server.py
│   │   └── cli.py
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── README.md
│
├── mcp-skills/               # MCP Skills Server - analiza kodu
│   ├── Dockerfile
│   ├── requirements.txt
│   └── server.py             # FastAPI HTTP API + MCP STDIO
│
├── mcp-gateway/              # NOWOŚĆ: OpenAI-compatible shim
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── server.py             # FastAPI + SSE + multi-tenant
│   └── tenants/              # Konfiguracja tenantów (YAML)
│       └── default.yaml
│
├── mcp-webui/                # NOWOŚĆ: Panel testowy QA/admin
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── server.py             # FastAPI + Jinja2 + HTMX
│   └── templates/            # HTML templates
│
├── llm-agent/                # Autonomiczny Agent
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── agent.py
│   ├── agent_standalone.py
│   └── agent_git2mcp.py      # Workflow przez git2mcp
│
├── dashboard/                # Wizualizacja wyników
│   ├── Dockerfile
│   ├── server.py
│   └── index.html
│
├── ansible/                  # NOWOŚĆ: Ansible E2E tests
│   ├── inventory.ini
│   ├── e2e-docker-stack.yml
│   └── test-github-integration.yml
│
├── env2mcp/                  # NOWOŚĆ: konfiguracja .env i GitHub auth helper
│   ├── env2mcp/
│   │   ├── cli.py
│   │   ├── config.py
│   │   └── github_cli.py
│   ├── pyproject.toml
│   └── README.md
│
├── docs/                       # Dokumentacja produktowa
│   ├── PRODUCT.md            # Architektura produktowa
│   └── USAGE.md              # Scenariusze użycia
│
├── scripts/
│   ├── deploy.sh
│   └── test.sh
│
├── repos/                      # Repo hosta (read-only mount)
└── output/                     # Wyniki analizy (volume)
```

## Nowa Architektura Produktowa (Maj 2026)

### MCP Gateway - Publiczny Entrypoint
OpenAI-compatible HTTP API shim dla integracji z zewnętrznymi klientami:
- **Endpointy**: `/v1/models`, `/v1/chat/completions` (z SSE streaming)
- **Autoryzacja**: Bearer token (per-tenant API keys)
- **Multi-tenant**: Konfiguracja przez `tenants/*.yaml`
- **Audit logging**: JSONL logi w wolumenie `audit-storage`
- **Prompt parsing**: Automatyczne parsowanie pól (Repo, Repo URL, Source, Branch, Execute, Push, Draft, PR, Test, Remote, Zadanie)

### MCP WebUI - Panel Testowy
FastAPI + HTMX + Tailwind dla QA i administratorów:
- Dashboard ze statusem gateway
- Lista repozytoriów + sync form
- Uruchamianie skilli przez gateway
- Podgląd diffów
- Playground dla free-form promptów
- Konfiguracja GitHub i zarządzanie repo na `/github`
- **URL**: http://localhost:8092

### OpenWebUI - Dla Użytkowników Końcowych
Oficjalny frontend (docker image) podłączony do MCP Gateway:
- Chat z modelami `mcp-skills/refactor` i `mcp-skills/analyze`
- **URL**: http://localhost:3000

### MCP Skills - HTTP API
Serwer FastAPI z endpointami (poza MCP STDIO):
- `POST /sync` - Synchronizacja repo z git-proxy
- `POST /analyze/structure` - Analiza struktury kodu
- `POST /analyze/metrics` - Metryki repozytorium
- `POST /analyze/patterns` - Wykrywanie wzorców
- `POST /refactor/recommend` - Rekomendacje refaktoryzacji
- `GET /health` - Healthcheck

## MCP Skills - Narzędzia

### analyze_code_structure
Analiza struktury kodu dla podanych ścieżek (via HTTP API lub MCP).

### compute_metrics_for_repo
Metryki całego repozytorium.

### detect_code_patterns
Wykrywanie wzorców i antywzorców.

### recommend_refactoring
Rekomendacje refaktoryzacji z priorytetyzacją.

### sync_repo_from_git_proxy
Synchronizacja repozytorium z `mcp-git-proxy` do cache skills.

## git2mcp - Pakiet Proxy

`git2mcp` dostarcza dwa komponenty:
- `GitProxyManager` (serwer w `mcp-git-proxy`) — sync repo, export paczek, commit/test/push
- `Git2MCPClient` (klient async) — używany przez agentów i gateway

### Nowe Operacje Lokalne (v0.1.9)
Operacje na working tree bez commitowania:
- `worktree_read/write/diff` - Bezpośrednia edycja plików
- `patch_apply` - Aplikowanie unified diff
- `stage` - Dodawanie do indeksu
- `stash_save/pop` - Stash operacje
- `branch_draft` - Tworzenie branchy draft/*
- `checkpoint_create/restore` - Snapshoty tarball dla rollback
- `reset` - Git reset (hard/soft/mixed)

Zobacz `git2mcp/examples/05_local_iterate.py` dla workflow: checkpoint → patch → test → commit (lub rollback).

Najważniejsze endpointy `mcp-git-proxy`:
- `POST /repos/sync` - klonowanie/pull repo do izolowanego volume
- `POST /packages/export-fragments` - export repo jako fragmenty (`path + content_b64`)
- `POST /packages/export` - eksport pełnego repo do paczki
- `POST /repos/{repo_id}/commit` - commit zmian przesłanych jako payload
- `POST /repos/{repo_id}/run-tests` - test commitu przed pushem
- `POST /repos/{repo_id}/push` - push po pozytywnych testach

## Przykłady Użycia

### Analiza lokalnego repozytorium

```bash
# Przygotuj testowe repozytorium
mkdir -p repos/my-project
cp -r /path/to/code/* repos/my-project/

# Uruchom analizę
docker-compose run --rm llm-agent python agent_git2mcp.py \
  --repo test/sample-project \
  --source-path /host-repos/test/sample-project \
  --branch main
```

### Użycie z OpenAI

```bash
# W .env ustaw:
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-...

docker-compose run --rm llm-agent python agent_git2mcp.py \
  --repo team/my-repo \
  --source-path /host-repos/my-project
```

### Użycie z lokalnym Ollama

```bash
# Uruchom Ollama
docker-compose --profile ollama up -d ollama

# W .env ustaw:
# LLM_PROVIDER=ollama
# OLLAMA_HOST=http://ollama:11434

docker-compose run --rm llm-agent python agent_git2mcp.py \
  --repo my-project \
  --source-path /host-repos/my-project
```

### Użycie z lokalnym OpenRouter Lite

```bash
# LLM Provider: openrouter-lite, mock, openai, ollama
# LLM_PROVIDER=openrouter-lite
# OPENROUTER_API_KEY=...
# LLM_MODEL=openrouter/x-ai/grok-code-fast-1

docker-compose run --rm llm-agent python agent_git2mcp.py \
  --repo my-project \
  --source-path /host-repos/my-project \
  --execute
```

## Workflow Autonomicznej Refaktoryzacji

### Nowy Gateway Workflow (via OpenWebUI lub API)

1. **Prompt** - Użytkownik wysyła prompt przez OpenWebUI (lub API) z polami:
   - `Repo: team/project`, `Source: /path`, `Branch: main`
   - `Execute: true` (opcjonalnie wykonaj commit)
   - `Push: true` (opcjonalnie wypchnij)
   - `Zadanie: Przeanalizuj i zaproponuj refaktor...`

2. **Gateway Processing**:
   - Parsuje prompt i routing do `mcp-git-proxy` (sync repo)
   - Wywołuje `mcp-skills` HTTP API (analyze, metrics, patterns)
   - Generuje plan refaktoryzacji (`.mcp/refactor-plan.json`)
   - Tworzy summary (`.mcp/refactor-summary.md`)
   - Jeśli `Execute=true`: commit artefaktów + test + push (jeśli `Push=true`)

3. **Wynik** - JSON z analizą, planem i statusem wykonania.

### Tradycyjny Agent Workflow

1. **Sync Git** - `mcp-git-proxy` pobiera/aktualizuje repo do własnego volume.
2. **Cache Skills** - `git2mcp` eksportuje paczkę repo i odświeża cache w skills.
3. **Analiza** - agent liczy metryki i wykrywa wzorce.
4. **Planowanie** - lite LLM generuje plan refaktoryzacji.
5. **Commit via MCP** - zmiany idą jako payload do `/commit`, bez ręcznej edycji plików przez shell.
6. **Test lokalny** - `/run-tests` w izolowanym repo git proxy.
7. **Push (opcjonalny)** - tylko po przejściu testów.

## Użycie z Makefile (Zalecane)

```bash
# Start całego stacku (zabija porty, build, up, smoke-test)
make start

# Sprawdź status
make ps

# Logi w czasie rzeczywistym
make logs

# Smoke test API
make smoke

# Stop wszystkiego
make stop

# Produkcja (bez dev mountów)
make prod-up

# Więcej opcji
make help
```

## Dashboard - Wizualizacja Wyników

Dashboard webowy dostarcza interaktywny interfejs do przeglądania wyników analizy.

### Uruchomienie dashboardu

```bash
# Dashboard startuje automatycznie z deploy.sh
# Lub ręcznie:
docker-compose up -d dashboard
```

### Dostęp do dashboardu

- **Dashboard UI**: http://localhost:8085
- **API Status**: http://localhost:8085/api/status
- **Lista analiz**: http://localhost:8085/api/analyses

### Funkcje dashboardu

- **Metryki w czasie rzeczywistym** - liczba plików, linii, funkcji, klas
- **Lista plików** - ranking największych plików z metrykami
- **Analiza importów** - najczęściej używane biblioteki
- **Rekomendacje** - priorytetowe akcje refaktoryzacji
- **Plan refaktoryzacji** - podsumowanie z architekturą i ryzykami
- **Szczegóły techniczne** - pełny JSON z analizy

### Przykładowe użycie

```bash
# Wygeneruj analizę
docker-compose run --rm llm-agent python agent_git2mcp.py \
  --repo test/sample-project \
  --source-path /host-repos/test/sample-project \
  --execute

# Otwórz dashboard w przeglądarce
open http://localhost:8085
# lub
xdg-open http://localhost:8085
```

## Testowanie

```bash
# Uruchom wszystkie testy
./scripts/test.sh

# Uruchom tylko testy e2e API/proxy
python3 -m pytest -q git2mcp/tests/test_git2mcp.py

# E2E skrypt pokrywa też push-path (commit -> test -> push do lokalnego bare remote)
# i waliduje obecność artefaktu .mcp/refactor-plan.json po pushu

# E2E skrypt testuje też 3 repo z /home/tom/github/semcod
# (docs, code2schema, ats-benchmark) oraz transfer do mcp-skills bez shared volume,
# wyłącznie przez MCP fragmenty/path updates.

# Sprawdź strukturę
ls -la repos/ output/

# Sprawdź logi
docker-compose logs -f mcp-git-proxy mcp-skills
```

## Rozwój

### Lokalne uruchomienie serwera MCP Skills

```bash
cd mcp-skills
pip install -r requirements.txt
python server.py
```

### Lokalne uruchomienie agenta git2mcp

```bash
cd llm-agent
pip install -r requirements.txt
PYTHONPATH=.. python agent_git2mcp.py --repo test/sample-project --source-path ../repos/test/sample-project
```

## Dokumentacja Projektu

- **[docs/USAGE.md](docs/USAGE.md)** - Pełne scenariusze użycia (9 przepływów end-to-end)
- **[docs/USE_CASES.md](docs/USE_CASES.md)** - Gotowe use-case i prompty dla refactor/migration/integration
- **[docs/PRODUCT.md](docs/PRODUCT.md)** - Architektura produktowa, multi-tenant, bezpieczeństwo
- **[env2mcp/README.md](env2mcp/README.md)** - Konfiguracja `.env` i integracja GitHub (`gh`/PAT)
- **[REFACTORING_PLAN.md](REFACTORING_PLAN.md)** - Plan refaktoryzacji i roadmap
- **[git2mcp/README.md](git2mcp/README.md)** - Dokumentacja pakietu git2mcp
- **[CHANGELOG.md](CHANGELOG.md)** - Historia zmian
- **[TODO.md](TODO.md)** - Zadania do zrobienia i product roadmap

## Dokumentacja Zewnętrzna (MCP)

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [MCP GitHub Server](https://github.com/github/github-mcp-server)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [OpenWebUI Documentation](https://docs.openwebui.com/)

## Licencja

Zobacz plik LICENSE.

## License

Licensed under Apache-2.0.
