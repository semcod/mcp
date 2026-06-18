# Integracja IDE, agentów LLM i A2A

Ten dokument odpowiada na trzy pytania:

1. Czy [semcod/mcp](https://github.com/semcod/mcp) jest poprawnie zbudowany i gotowy do użycia?
2. Czy można go wykorzystać przy rozwijaniu innych projektów?
3. Jak podpiąć Cursor, VS Code, Devin i inne narzędzia (w tym A2A), żeby poprawiać jakość kodu?

Powiązane: [`USAGE.md`](USAGE.md), [`PRODUCT.md`](PRODUCT.md), [`CHAT_PLAYBOOKS.md`](CHAT_PLAYBOOKS.md).

---

## Ocena dojrzałości (stan na 2026-06)

| Warstwa | Status | Uwagi |
|---------|--------|-------|
| **Docker stack** (`make start`) | ✅ Gotowy | `mcp-git-proxy`, `mcp-skills`, `mcp-gateway`, `mcp-webui`, `mcp-docs`, `gh2mcp-agent` |
| **Testy** (`scripts/test.sh`, `pytest`) | ✅ Przechodzą | E2E git-proxy, fragment-sync, push do bare remote |
| **Analiza kodu** | ✅ Działa | MCP tools + CLI semcod (`code2llm`, `sumd`, `pyqual`, …) |
| **Plan refaktoryzacji** | ✅ Działa | `.mcp/refactor-plan.json`, `.mcp/refactor-summary.md` |
| **Automatyczny refactor kodu** | ⚠️ Częściowy | Gateway commituje **artefakty planu**, nie pełne patche modułów (patrz `USAGE.md`) |
| **Plug-and-play bez Dockera** | ❌ Nie | Wymaga stacku lub ręcznej konfiguracji MCP stdio |
| **Integracja IDE out-of-the-box** | ⚠️ Ręczna | Brak auto-instalera — konfiguracja poniżej (~5 min) |

**Wniosek:** projekt jest **poprawnie zbudowany jako platforma dev/QA** do analizy, planowania i kontrolowanego commitowania przez Git API. Nadaje się do rozwoju innych repozytoriów **jako warstwa jakości**, nie jako „magiczny autopilot” zamieniający cały kod bez nadzoru.

---

## Architektura integracji

```
┌─────────────┐  OpenAI-compat   ┌──────────────┐   HTTP/MCP   ┌─────────────┐
│ Cursor      │ ───────────────► │ mcp-gateway  │ ───────────► │ mcp-skills  │
│ VS Code     │  :9000/v1        │ (auth, jobs) │              │ (analiza)   │
│ Devin       │                  └──────┬───────┘              └──────┬──────┘
│ OpenWebUI   │                         │                             │
│ Windsurf    │                         ▼                             ▼
└─────────────┘                  ┌──────────────┐              ┌─────────────┐
                                 │ mcp-git-proxy│◄─────────────│ git2mcp     │
                                 │ commit/push  │              │ llm-agent   │
                                 └──────────────┘              └─────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
              code2llm            pyqual / vallm         koru / redsl
              sumd / intract      regres / redup         (CLI semcod)
```

**Dwa tryby podpięcia IDE:**

| Tryb | Kiedy używać | Protokół |
|------|--------------|----------|
| **A. Gateway OpenAI-compat** | Chat w IDE, agenci cloud (Devin), OpenWebUI | HTTP `POST /v1/chat/completions` |
| **B. MCP stdio** | Cursor, Claude Desktop, VS Code MCP | `mcp-skills` transport stdio |

---

## Szybki start (wymagany dla wszystkich integracji)

```bash
cd ~/github/semcod/mcp
cp .env.example .env
# OPENROUTER_API_KEY, WEBUI_API_KEY=sk-mcp-default-dev-key

gh auth login          # opcjonalnie, do sync repo GitHub
make setup-github      # token → .env
make start             # cały stack
make smoke             # health gateway/webui
```

Po starcie:

| Usługa | URL |
|--------|-----|
| Gateway (OpenAI-compat) | http://localhost:9000/v1 |
| WebUI admin | http://localhost:8092 |
| Dokumentacja + playbooki | http://localhost:8093 |
| OpenWebUI | http://localhost:3000 |

Klucz API (tenant `default`): `sk-mcp-default-dev-key` — patrz `mcp-gateway/tenants/default.yaml`.

---

## 1. Cursor

### Opcja A — MCP stdio (zalecana dla narzędzi w czacie)

Skopiuj [`examples/integrations/cursor-mcp.json`](../examples/integrations/cursor-mcp.json) do:

- **projekt:** `.cursor/mcp.json`
- **globalnie:** `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "semcod-mcp-skills": {
      "command": "docker",
      "args": [
        "compose", "-f", "/home/tom/github/semcod/mcp/docker-compose.yml",
        "exec", "-T", "mcp-skills",
        "python", "server.py"
      ],
      "env": {
        "MCP_SKILLS_TRANSPORT": "stdio",
        "GIT_PROXY_URL": "http://mcp-git-proxy:8080",
        "SKILLS_REPO_BASE": "/skills-cache"
      }
    }
  }
}
```

> Dostosuj ścieżkę `-f` do lokalizacji `docker-compose.yml`. Stack musi działać (`make start`).

Dostępne narzędzia MCP: `analyze_code_structure`, `compute_metrics_for_repo`, `detect_code_patterns`, `recommend_refactoring`, `sync_repo_from_git_proxy`.

### Opcja B — Custom OpenAI endpoint (model w Cursor)

W **Cursor Settings → Models → OpenAI API**:

- **Base URL:** `http://localhost:9000/v1`
- **API Key:** `sk-mcp-default-dev-key`
- **Model:** `mcp-skills/analyze` lub `mcp-skills/refactor`

Przykładowy prompt w czacie:

```text
Repo: semcod/nlp2cmd
Source: /host-semcod/nlp2cmd
Branch: main
Execute: false
Zadanie: Przeanalizuj strukturę modułów i zaproponuj plan refaktoryzacji bez zmian API publicznego.
```

### Efekt jakości

Połącz z regułami Cursor (`.cursor/rules`): wymuszaj wywołanie analizy przed większym refactorem; commituj tylko po `pyqual` / `vallm`.

---

## 2. VS Code

### GitHub Copilot Chat (OpenAI-compatible provider)

Jeśli rozszerzenie wspiera custom endpoint:

- Base URL: `http://localhost:9000/v1`
- API Key: `sk-mcp-default-dev-key`
- Model: `mcp-skills/analyze`

### Continue.dev

Dodaj do `~/.continue/config.json`:

```json
{
  "models": [
    {
      "title": "semcod-mcp-analyze",
      "provider": "openai",
      "model": "mcp-skills/analyze",
      "apiBase": "http://localhost:9000/v1",
      "apiKey": "sk-mcp-default-dev-key"
    },
    {
      "title": "semcod-mcp-refactor",
      "provider": "openai",
      "model": "mcp-skills/refactor",
      "apiBase": "http://localhost:9000/v1",
      "apiKey": "sk-mcp-default-dev-key"
    }
  ]
}
```

### Cline / Roo Code

Analogicznie: **OpenAI-compatible**, ten sam base URL i modele.

### VS Code MCP (oficjalne rozszerzenie MCP)

Użyj tej samej konfiguracji stdio co Cursor (`examples/integrations/cursor-mcp.json` → `.vscode/mcp.json` jeśli wspierane).

### Zadania (tasks.json) — lokalna jakość bez LLM

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "semcod: pyqual",
      "type": "shell",
      "command": "pyqual run",
      "group": "test"
    },
    {
      "label": "semcod: mcp analyze last repo",
      "type": "shell",
      "command": "bash scripts/refactor-last-repo.sh",
      "options": { "cwd": "${env:HOME}/github/semcod/mcp" }
    }
  ]
}
```

---

## 3. Windsurf / Codeium

Te edytory często wspierają MCP podobnie do Cursor:

1. Stack `make start`
2. MCP stdio — ta sama konfiguracja co Cursor
3. Lub HTTP do gateway jako dodatkowy model

---

## 4. Devin / Devin-like (Cognition, factory.ai, itp.)

Devin nie montuje lokalnego MCP stdio bezpośrednio. Integracja przez **HTTP API gateway**:

```bash
curl -sS http://localhost:9000/v1/chat/completions \
  -H "Authorization: Bearer sk-mcp-default-dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mcp-skills/refactor",
    "messages": [{
      "role": "user",
      "content": "Repo: semcod/koru\nBranch: main\nExecute: false\nZadanie: Audyt modułów orchestracji."
    }]
  }'
```

**Wzorzec dla Devin:**

1. Devin pracuje w sandboxie z dostępem do Twojego API (tunnel: `ngrok http 9000` lub VPN).
2. Zadanie w Devin zawiera szablon pól `Repo / Branch / Execute / Zadanie`.
3. Wynik planu (job_id) → PR z artefaktami `.mcp/*` lub ręczny refactor w Devin z planem jako kontekstem.
4. Push przez `mcp-git-proxy` z `Execute: true`, `Push: true` w prompcie gateway.

---

## 5. OpenWebUI (już wbudowane)

Najprostsza ścieżka dla zespołu nietechnicznego:

1. http://localhost:3000
2. Model: `mcp-skills/refactor`
3. Playbooki: http://localhost:8093/docs/CHAT_PLAYBOOKS.md

---

## 6. CLI i skrypty (CI / lokalnie)

```bash
# Analiza ostatniego repo na GitHub
bash scripts/refactor-last-repo.sh

# Konkretne repo + execute + PR
bash scripts/refactor-last-repo.sh \
  --repo semcod/pyqual \
  --execute --push --pr \
  --task "Etap 1: metryki i plan podziału modułów"
```

Wyniki: `output/refactor-last-repo-<timestamp>/`.

---

## 7. Mapa narzędzi semcod → rola w jakości kodu

`mcp-skills` może uruchamiać CLI przez `POST /tools/run` (model `mcp-skills/tool` w gateway):

| Pakiet semcod | Rola | Kiedy w pipeline |
|---------------|------|------------------|
| **code2llm** | Analiza struktury, CFG/DFG | Przed refactorem |
| **sumd** | Deskryptor projektu (SUMD/SUMR) | Kontekst dla LLM |
| **pyqual** | Quality gates (ruff, mypy, bandit) | Po każdej zmianie |
| **vallm** | Walidacja outputu LLM | Przed merge |
| **redsl** | Plan refaktoryzacji DSL | Planowanie |
| **redup** | Duplikaty kodu | Przed split modułów |
| **regres** | Testy regresji | Po refactorze |
| **intract** | Kontrakty intencji | PR / CI |
| **koru** | Pętla detect→plan→heal | Multi-repo workspace |
| **goal** | Inteligentny commit | Po akceptacji zmian |

Przykład wywołania toola przez gateway:

```bash
curl -sS http://localhost:9000/v1/chat/completions \
  -H "Authorization: Bearer sk-mcp-default-dev-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mcp-skills/tool",
    "messages": [{
      "role": "user",
      "content": "tool: pyqual\nrepo_id: semcod/nlp2cmd\nrepo_url: https://github.com/semcod/nlp2cmd.git"
    }]
  }'
```

---

## 8. Integracja A2A (Agent-to-Agent)

[Agent2Agent (A2A)](https://google.github.io/A2A/) definiuje kartę agenta i wymianę zadań między agentami. `semcod/mcp` nie implementuje natywnego serwera A2A, ale mapuje się na wzorzec **hub orchestrator + worker agents**:

```
┌─────────────────────────────────────────────────────────────┐
│  Orchestrator (A2A Client)                                   │
│  np. koru, projektor, własny supervisor                     │
└────────────┬────────────────────────────────────────────────┘
             │ HTTP OpenAI-compat / webhooks
     ┌───────┴───────┬──────────────┬──────────────┐
     ▼               ▼              ▼              ▼
 mcp-gateway    pyqual agent    vallm agent    intract agent
 (analyze/      (quality)       (validate)     (contracts)
  refactor)
```

### Wzorzec integracji A2A

| Krok | Agent A2A | Implementacja semcod |
|------|-----------|----------------------|
| 1. Discovery | Agent Card URL | `GET http://localhost:9000/health` + `GET /v1/models` |
| 2. Task submit | `POST /tasks` (A2A) | `POST /v1/chat/completions` z modelem `mcp-skills/*` |
| 3. Status | polling / SSE | `GET /jobs/{job_id}` |
| 4. Artifact | pliki wynikowe | `.mcp/refactor-plan.json`, raporty CLI |
| 5. Validation | osobny agent | `mcp-skills/tool` → `pyqual`, `vallm` |
| 6. Git delivery | osobny agent | `mcp-git-proxy` commit/push/PR |

### Przykład: Agent Card (szkic dla własnego wrappera)

Jeśli budujesz cienki serwis A2A przed gateway:

```json
{
  "name": "semcod-mcp-analyzer",
  "description": "Code analysis and refactor planning for semcod ecosystem",
  "url": "http://localhost:9000/v1",
  "capabilities": ["analyze", "refactor", "tool-run"],
  "authentication": "bearer",
  "skills": ["mcp-skills/analyze", "mcp-skills/refactor", "mcp-skills/tool"]
}
```

### Łańcuch jakości (zalecany)

```text
1. mcp-skills/analyze     → metryki + wzorce
2. mcp-skills/tool:code2llm → mapa projektu
3. mcp-skills/refactor    → plan (.mcp/*)
4. IDE agent (Cursor)     → implementacja z planu
5. mcp-skills/tool:pyqual → quality gate
6. mcp-skills/tool:vallm  → walidacja LLM patchy
7. mcp-git-proxy          → commit + test + push
8. koru                   → pętla heal jeśli regresja
```

---

## 9. Automatyczne podpięcie do wielu projektów

### Pakiet `semcod-mcp` (zalecane)

```bash
pip install -e ~/github/semcod/mcp

cd /path/to/your/project
semcod-mcp init              # .cursor, .vscode, .windsurf, .continue, manifest
semcod-mcp doctor
semcod-mcp validate
semcod-mcp analyze
```

`init` robi **merge** — nie usuwa istniejących `mcpServers` ani ustawień VS Code.

### Per-repo (ręcznie)

W każdym repozytorium semcod/wronai:

1. `.cursor/mcp.json` — wskazuje na wspólny stack (jeden `make start` na maszynie).
2. `.cursor/rules/semcod-quality.md` — reguła: przed PR uruchom `pyqual`, dla większych zmian wywołaj `mcp-skills/analyze`.
3. `.github/workflows/trigger-org-sync.yml` — już bootstrappowane (odświeża profil org).

### Globalnie (jeden stack, wiele IDE)

```bash
# ~/.cursor/mcp.json — jedna konfiguracja dla wszystkich projektów
# Stack w ~/github/semcod/mcp — mount ../ jako /host-semcod w Docker
```

W prompcie zawsze podawaj `Source: /host-semcod/<repo>` — docker-compose montuje `..:/host-semcod:ro`.

### CI (GitHub Actions)

```yaml
- name: MCP analyze
  run: |
    curl -fsS http://localhost:9000/v1/chat/completions \
      -H "Authorization: Bearer ${{ secrets.MCP_GATEWAY_KEY }}" \
      -d '{"model":"mcp-skills/analyze","messages":[{"role":"user","content":"Repo: semcod/${{ github.event.repository.name }}\nExecute: false\nZadanie: PR quality review"}]}'
```

---

## 10. Ograniczenia i roadmap

| Ograniczenie | Obejście |
|--------------|----------|
| Brak pełnego auto-refactor kodu | Użyj planu `.mcp/*` + IDE agent do implementacji |
| Wymaga Docker | `make start` na hoście dev; tunel dla cloud agentów |
| Push protection / sekrety w repo | Commit przez API (`gh api`) lub PR z czystą gałęzią |
| Pages root `/` failuje dla dużych monorepo | Użyj `/docs` jak w `semcod/mcp` |

Planowane (patrz `REFACTORING_PLAN.md`, `docs/PRODUCT.md`):

- automatyczna aplikacja patchy (nie tylko artefakty),
- natywny adapter A2A,
- generator `mcp.json` w `make setup-ide`.

---

## 11. Checklist „czy działa u mnie?”

```bash
make start && make smoke
curl -s http://localhost:9000/health
curl -s -H "Authorization: Bearer sk-mcp-default-dev-key" http://localhost:9000/v1/models
bash scripts/refactor-last-repo.sh --repo semcod/mcp
```

Jeśli wszystkie kroki OK — możesz podpiąć Cursor/VS Code według sekcji 1–2.
