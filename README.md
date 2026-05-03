# Autonomiczny Agent Refaktoryzacji MCP


## AI Cost Tracking

![PyPI](https://img.shields.io/badge/pypi-costs-blue) ![Version](https://img.shields.io/badge/version-0.1.31-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)
![AI Cost](https://img.shields.io/badge/AI%20Cost-$1.80-orange) ![Human Time](https://img.shields.io/badge/Human%20Time-3.7h-blue) ![Model](https://img.shields.io/badge/Model-openrouter%2Fqwen%2Fqwen3--coder--next-lightgrey)

- 🤖 **LLM usage:** $1.8000 (12 commits)
- 👤 **Human dev:** ~$374 (3.7h @ $100/h, 30min dedup)

Generated on 2026-05-03 using [openrouter/qwen/qwen3-coder-next](https://openrouter.ai/qwen/qwen3-coder-next)

---

System autonomicznej refaktoryzacji kodu oparty na Model Context Protocol (MCP), integrujący:
- **MCP Git Proxy** - izolowany serwis git z osobnym volume i API do sync/commit/test/push
- **MCP Skills Server** - analiza kodu i metryki na cache repozytoriów
- **LLM Agent (`git2mcp`)** - planowanie refaktoryzacji i commitowanie zmian przez proxy git
- **MCP Gateway** - publiczny shim OpenAI-compatible (auth, multi-tenant, SSE) do integracji z OpenWebUI
- **MCP WebUI** - panel testowy QA / admin dla `mcp-skills`

## Quick start

```bash
cp .env.example .env   # ustaw OPENROUTER_API_KEY i WEBUI_API_KEY
make start             # killuje porty hostowe i uruchamia cały stack
# make stop            # zatrzymuje wszystko
# make smoke           # szybki test API gateway/webui
# make help            # pełna lista targetów
```

- OpenWebUI:  http://localhost:3000
- MCP WebUI:  http://localhost:8092
- Gateway:    http://localhost:9000
- Dashboard:  http://localhost:8085

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
├── docker-compose.yml          # Konfiguracja Docker
├── .env.example                # Przykładowa konfiguracja
├── README.md                   # Dokumentacja
│
├── mcp-git-proxy/              # MCP Git Proxy service
│   ├── Dockerfile
│   ├── requirements.txt
│   └── server.py
│
├── git2mcp/                    # Pakiet python do sync/commit przez MCP
│   ├── __init__.py
│   ├── client.py
│   ├── proxy.py
│   └── pyproject.toml
│
├── mcp-skills/                 # MCP Skills Server
│   ├── Dockerfile
│   ├── requirements.txt
│   └── server.py               # Implementacja narzędzi MCP
│
├── llm-agent/                  # Autonomiczny Agent
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── agent.py                # Logika agenta LLM
│   ├── agent_standalone.py     # Wersja standalone
│   └── agent_git2mcp.py        # Workflow commit/test/push przez git2mcp
│
├── dashboard/                  # Wizualizacja wyników
│   ├── Dockerfile
│   ├── server.py               # Serwer HTTP
│   └── index.html              # Interfejs webowy
│
├── scripts/                    # Skrypty pomocnicze
│   ├── deploy.sh               # Deployment
│   └── test.sh                 # Testy
│
├── repos/                      # Repo hosta (read-only mount)
└── output/                     # Wyniki analizy (volume)
```

## MCP Skills - Narzędzia

### analyze_code_structure
Analiza struktury kodu dla podanych ścieżek:
- Liczba linii kodu
- Liczba importów
- Liczba funkcji i klas
- Podgląd kodu

### compute_metrics_for_repo
Metryki całego repozytorium:
- Całkowita liczba plików
- Całkowita liczba linii
- Średnia liczba linii na plik
- Liczba funkcji i klas

### detect_code_patterns
Wykrywanie wzorców i antywzorców:
- Duże pliki (>500 linii)
- Wysoka złożoność
- Najczęściej używane importy
- Potencjalne problemy

### recommend_refactoring
Rekomendacje refaktoryzacji:
- Priorytetyzacją zmian
- Sugestie podziału plików
- Sugestie organizacji kodu

### sync_repo_from_git_proxy
Synchronizacja repozytorium z izolowanego `mcp-git-proxy` do cache skills:
- import paczki repo (`tar.gz + base64`)
- odświeżanie lokalnego cache `/skills-cache/<repo_id>`
- analiza na spójnej wersji kodu

## git2mcp - paczka proxy

`git2mcp` dostarcza dwa komponenty:
- `GitProxyManager` (serwer) — sync repo, export paczek, commit/test/push
- `Git2MCPClient` (agent) — API client używany przez `llm-agent`

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

1. **Sync Git** - `mcp-git-proxy` pobiera/aktualizuje repo do własnego volume.
2. **Cache Skills** - `git2mcp` eksportuje paczkę repo i odświeża cache w skills.
3. **Analiza** - agent liczy metryki i wykrywa wzorce.
4. **Planowanie** - lite LLM generuje plan refaktoryzacji.
5. **Commit via MCP** - zmiany idą jako payload do `/commit`, bez ręcznej edycji plików przez shell.
6. **Test lokalny** - `/run-tests` w izolowanym repo git proxy.
7. **Push (opcjonalny)** - tylko po przejściu testów.

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

## Dokumentacja MCP

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [MCP GitHub Server](https://github.com/github/github-mcp-server)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

## Licencja

Zobacz plik LICENSE.

## License

Licensed under Apache-2.0.
