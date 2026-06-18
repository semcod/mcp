# MCP Skills — Scenariusze użycia

Ten dokument pokazuje 10 konkretnych przepływów end-to-end. Wszystkie używają OpenRouter (`LLM_MODEL=openrouter/x-ai/grok-code-fast-1`), bez Ollama.

Powiązane dokumenty:
- **[docs/README.md](docs/README.md)** — spis całej dokumentacji z linkami
- `docs/PRODUCT.md` — architektura i deployment
- `docs/IDE_AND_AGENT_INTEGRATION.md` — **Cursor, VS Code, Devin, A2A, jakość kodu**
- `docs/SEMCOD_MCP_CLI.md` — pakiet CLI `semcod-mcp` (`init`, `doctor`, `validate`, `analyze`)
- `docs/GATEWAY_MODULE_SPLIT.md` — plan podziału `mcp-gateway/server.py`
- `docs/USE_CASES.md` — gotowe use-case (refactor/migration/integration)
- `docs/CHAT_PLAYBOOKS.md` — szczegółowe dialogi chat-playbook (multi-project/migration/integration/modularization)
- `git2mcp/examples/README.md` — przykłady CLI
- `env2mcp/README.md` — zarządzanie konfiguracją
- OpenWebUI docs:
  - https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/
  - https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/

---

## Wymagania wstępne

```bash
# 1) sklonuj projekt i przygotuj .env
cp .env.example .env
# wpisz OPENROUTER_API_KEY i WEBUI_API_KEY (klucz tenanta z mcp-gateway/tenants/default.yaml)

# Opcjonalnie: skonfiguruj GitHub (token do pobierania repo)
make setup-github
# lub ręcznie: wpisz GITHUB_PAT w .env

# 2) wystartuj zestaw
make start          # killuje porty hostowe + docker-compose up -d (z OpenWebUI)
# make stop         # zatrzymuje
# make smoke        # smoke-test API
# make ansible-e2e  # E2E między usługami Docker + sample prompty
# make help         # lista targetów
```

Po starcie:
- `mcp-gateway`     → http://localhost:9000        (publiczny, OpenAI-compat)
- `mcp-webui`       → http://localhost:8092        (panel testowy)
  - `/github`       → konfiguracja GitHub i zarządzanie repo
- `mcp-docs`        → http://localhost:8093        (dokumentacja projektu + playbooki chat)
- `openwebui`       → http://localhost:3000        (frontend dla użytkowników)
- `mcp-git-proxy`   → http://localhost:8081        (dev only)
- `gh2mcp-agent`    → http://localhost:8079        (sync tokenu `gh` -> `.env`)
- `dashboard`       → http://localhost:8085

Wewnętrzne usługi (`mcp-skills`, `llm-agent`) nie są publiczne.

---

## Scenariusz 1 — użytkownik końcowy w OpenWebUI

**Cel:** klient wpisuje zadanie po polsku w OpenWebUI, dostaje wynik refaktoringu (commit + diff).

### 1.1 Konfiguracja OpenWebUI (jednorazowo)

OpenWebUI w naszym compose jest już skonfigurowany przez env (`OPENAI_API_BASE_URL`, `OPENAI_API_KEY`). Jeśli chcesz dodać/zmienić ręcznie, w UI:

1. Wejdź na http://localhost:3000 i utwórz konto admina.
2. **Settings → Admin Settings → Connections → OpenAI API** (zgodnie z [OpenWebUI – OpenAI-Compatible](https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/)):
   - **Base URL:** `http://mcp-gateway:9000/v1`
   - **API Key:** `sk-mcp-default-dev-key` (lub wartość z `WEBUI_API_KEY`)
   - włącz toggle.
3. **Workspace → Models** — pojawią się:
   - `mcp-skills/refactor`
   - `mcp-skills/analyze`

### 1.2 Wysłanie zadania

1. Otwórz nowy chat w OpenWebUI.
2. Wybierz model `mcp-skills/refactor`.
3. Treść wiadomości:

   ```
   Repo: team/code2schema-demo
   Source: /host-semcod/code2schema
   Branch: main
   Zadanie: Zaproponuj refaktor modułu utils, popraw nazewnictwo, dodaj typowanie, nie zmieniaj API publicznego.
   ```

4. Otrzymasz czytelny plan w formie tekstu/Markdown (bez surowego JSON w treści czatu).
5. Surowy JSON debug (workflow payload) jest dostępny przez `GET /jobs/{job_id}` na `mcp-gateway`.
6. Diff możesz obejrzeć w `mcp-webui` na http://localhost:8092/diff?repo_id=team/code2schema-demo

> Uwaga (stan obecny): gateway wykonuje **sync + analyze + zapis artefaktów planu** (`.mcp/refactor-plan.json`, `.mcp/refactor-summary.md`) i opcjonalnie `commit/push`, ale nie wykonuje jeszcze automatycznych zmian kodu źródłowego modułów.

---

## Scenariusz 2 — konfiguracja GitHub i zarządzanie repo

**Cel:** skonfigurować GitHub (token lub gh CLI), sklonować istniejące repo, utworzyć nowe repo i synchronizować je.

### 2.1 Konfiguracja GitHub — 3 metody

#### Metoda A — gh CLI (zalecana, 2 kroki)

```bash
# 1. Zaloguj się przez gh CLI (raz)
gh auth login

# 2. Pobierz i zapisz token do .env automatycznie
make setup-github
# lub: env2mcp setup-github
```

Jeśli masz już uruchomiony stack, możesz pobrać token **bezpośrednio z WebUI**:
1. Otwórz http://localhost:8092/github
2. Kliknij **"Pobierz token z gh CLI"** — token zostanie odczytany z `gh auth token`
   i zapisany do `.env` bez ponownego logowania.

`gh2mcp-agent` korzysta z mounta `${HOME}/.config/gh:/root/.config/gh:ro`,
więc token z lokalnego `gh auth login` jest dostępny również w Dockerze.

Weryfikacja:
```bash
env2mcp github status     # czy token jest w .env
env2mcp github repos -L 5 # lista twoich repo
gh auth status            # status gh CLI
make gh2mcp-status        # status agenta sync tokenu
```

#### Metoda B — Personal Access Token (ręcznie)

1. Wejdź na https://github.com/settings/tokens/new?scopes=repo,delete_repo
2. Zaznacz scope: `repo` (obowiązkowy) + `delete_repo` (opcjonalnie, do testów)
3. Skopiuj token

Zapisz token — jeden z wariantów:
```bash
# a) przez WebUI
# http://localhost:8092/github → sekcja "Opcja 2" → wpisz token → "Zapisz token"

# b) przez CLI
env2mcp env set GITHUB_PAT ghp_twoj_token

# c) ręcznie w .env
echo "GITHUB_PAT=ghp_twoj_token" >> .env
```

#### Metoda C — zmienna środowiskowa (tymczasowa)

```bash
export GITHUB_PAT=ghp_twoj_token
# Token dostępny dla make setup-github i ansible-github-test,
# ale nie zapisany trwale — zniknie po restart terminalu.
```

### 2.2 Zarządzanie repo przez MCP WebUI (http://localhost:8092/github)

Po skonfigurowaniu tokenu strona pokazuje status **"Connected"** z nazwą użytkownika.

#### Tworzenie nowego repo na GitHubie

1. Sekcja **"Create New Repository on GitHub"** (zielona)
2. Wypełnij: nazwa, opis, private/public, opcja "Clone locally"
3. Kliknij **Create** — repo zostanie:
   - utworzone na GitHubie przez API,
   - sklonowane lokalnie do `mcp-git-proxy` (jeśli "Clone locally" zaznaczone).

#### Klonowanie istniejącego repo

1. Sekcja **"Clone Repository from GitHub"**
2. Repository URL: `owner/repo` (np. `semcod/mcp`) lub pełny URL
3. Local Repo ID: unikalna nazwa lokalna (np. `mcp-main`)
4. Branch: `main`
5. Kliknij **Clone**

#### Synchronizacja (pull)

1. Sekcja **"Sync Repository"**
2. Wybierz repo z listy → **Pull Updates**

#### Przeglądanie sklonowanych repo

Sklonowane repo pojawiają się na http://localhost:8092/repos i http://localhost:8081/repos

### 2.3 Zarządzanie repo przez API (curl / shell)

```bash
# Weryfikacja tokenu bezpośrednio
curl -sS -H "Authorization: Bearer $GITHUB_PAT" \
  https://api.github.com/user | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['login'])"

# Tworzenie nowego repo przez mcp-git-proxy
curl -sS -X POST http://localhost:8081/github/create-repo \
  -H 'Content-Type: application/json' \
  -d "{
    \"name\": \"moje-nowe-repo\",
    \"description\": \"Opis repo\",
    \"private\": true,
    \"auto_clone\": true,
    \"github_token\": \"$GITHUB_PAT\"
  }" | python3 -m json.tool

# Klonowanie istniejącego repo
curl -X POST http://localhost:8081/repos/sync \
  -H 'Content-Type: application/json' \
  -d "{
    \"repo_id\": \"my-project\",
    \"repo_url\": \"https://$GITHUB_PAT@github.com/owner/repo.git\",
    \"branch\": \"main\"
  }"

# Synchronizacja (pull)
curl -X POST http://localhost:8081/repos/my-project/sync-pull \
  -H 'Content-Type: application/json' \
  -d '{"branch": "main"}'

# Lista lokalnych repo
curl -sS http://localhost:8081/repos | python3 -m json.tool
```

### 2.4 Test integracji GitHub przez Ansible

```bash
export GITHUB_PAT=ghp_twoj_token
make ansible-github-test
```

Playbook `ansible/test-github-integration.yml` weryfikuje:
- poprawność tokenu (wywołanie `GET /user` na GitHub API),
- działanie `POST /github/create-repo` przez `mcp-git-proxy`,
- sklonowanie repo lokalnie,
- widoczność w `/repos`,
- i usuwa testowe repo po teście (cleanup).

---

## Scenariusz 3 — QA / developer w `mcp-webui`

**Cel:** szybki test usług bez OpenWebUI, na panelu admina.

1. Otwórz http://localhost:8092.
2. **Repos → Sync**:
   - `repo_id`: `team/code2schema-demo`
   - `source_path`: `/host-semcod/code2schema`
   - `branch`: `main`
   - klik **Sync**.
3. **Skills**:
   - model: `mcp-skills/analyze`
   - `repo_id`: `team/code2schema-demo`
   - prompt: `policz metryki tego repo`
   - klik **Run** — wynik pojawia się pod formularzem.
4. **Diff** → wpisz `team/code2schema-demo` → zobacz aktualny worktree diff.

---

## Scenariusz 4 — developer lokalny z `git2mcp` (CLI)

**Cel:** developer chce ręcznie zlecać sync/commit/test do MCP, bez UI.

```bash
# sync + commit + test
python3 git2mcp/examples/01_sync_and_commit.py \
  --repo-id team/code2schema-demo \
  --source-path /home/tom/github/semcod/code2schema

# fragment sync do mcp-skills
python3 git2mcp/examples/02_fragment_sync_to_skills.py \
  --repo-id team/code2schema-demo \
  --source-path /home/tom/github/semcod/code2schema

# pełny agent przez compose
python3 git2mcp/examples/03_agent_git2mcp.py \
  --repo team/code2schema-demo \
  --source-path /host-semcod/code2schema \
  --execute

# dry-run vs execute z auto-revertem
python3 git2mcp/examples/04_dry_run_vs_execute.py \
  --repo-id team/code2schema-demo \
  --source-path /home/tom/github/semcod/code2schema \
  --execute

# lokalna iteracja (worktree + patch + checkpoint, bez commitów)
python3 git2mcp/examples/05_local_iterate.py \
  --repo-id team/code2schema-demo \
  --source-path /home/tom/github/semcod/code2schema \
  --task-id refactor-utils
```

---

## Scenariusz 5 — programatyczne użycie OpenAI SDK przez `mcp-gateway`

**Cel:** integracja z istniejącym narzędziem (Codex, Continue.dev, własny skrypt).

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:9000/v1",
    api_key="sk-mcp-default-dev-key",
)

resp = client.chat.completions.create(
    model="mcp-skills/refactor",
    messages=[{"role": "user", "content": "Przeanalizuj i zaproponuj refaktor"}],
    extra_body={
        "repo_id": "team/code2schema-demo",
        "source_path": "/host-semcod/code2schema",
        "branch": "main",
    },
)
print(resp.choices[0].message.content)
```

`extra_body` mapuje na nasze pola `repo_id` / `source_path` / `branch` w gateway.

---

## Scenariusz 6 — wdrożenie u klienta (multi-tenant)

**Cel:** dodać nowego klienta jako tenanta z osobnym kluczem i quotami.

1. Stwórz `mcp-gateway/tenants/acme.yaml`:

   ```yaml
   tenant_id: acme
   api_keys:
     - "sk-mcp-acme-prod-XXXX"
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

2. Restart gateway:

   ```bash
   docker-compose restart mcp-gateway
   ```

3. Klient w OpenWebUI ustawia `Base URL = https://twoja-domena/v1` i `API Key = sk-mcp-acme-prod-XXXX`.

4. Audit log dostępny: 

   ```bash
   curl -H 'Authorization: Bearer sk-mcp-acme-prod-XXXX' \
        http://localhost:9000/audit/tail?limit=50
   ```

   lub bezpośrednio w wolumenie `audit-storage`.

---

## Scenariusz 7 — bezpieczne iterowanie LLM-em bez śmiecenia historii

**Cel:** LLM próbuje refaktoryzacji wielokrotnie; tylko sukces ląduje w historii Git.

```bash
# 1) checkpoint working-tree (snapshot tarball, bez commita)
curl -X POST http://localhost:8081/repos/team/code2schema-demo/checkpoint \
  -H 'Content-Type: application/json' -d '{"label":"iter-1"}'

# 2) draft branch
curl -X POST http://localhost:8081/repos/team/code2schema-demo/branch/draft \
  -H 'Content-Type: application/json' -d '{"name":"refactor-utils"}'

# 3) patch apply (zmiany lokalne, bez commita)
curl -X POST http://localhost:8081/repos/team/code2schema-demo/patch/apply \
  -H 'Content-Type: application/json' --data-binary @patch.json

# 4) testy
curl -X POST http://localhost:8081/repos/team/code2schema-demo/run-tests \
  -H 'Content-Type: application/json' -d '{"command":"python3 -m compileall -q ."}'

# 5a) jeśli OK -> stage + commit
curl -X POST http://localhost:8081/repos/team/code2schema-demo/stage -d '{}'
curl -X POST http://localhost:8081/repos/team/code2schema-demo/commit \
  -H 'Content-Type: application/json' \
  -d '{"message":"refactor utils","changes":[],"author_name":"bot","author_email":"bot@local"}'

# 5b) jeśli FAIL -> restore checkpoint (czysta historia)
curl -X POST http://localhost:8081/repos/team/code2schema-demo/checkpoint/restore \
  -H 'Content-Type: application/json' -d '{"checkpoint_id":"iter-1"}'
```

---

## Scenariusz 8 — E2E między usługami przez Ansible

**Cel:** automatycznie sprawdzić połączenia `openwebui -> gateway -> git-proxy/skills`, wykonać sample prompty i asercje na odpowiedziach.

```bash
make ansible-e2e
```

Playbook `ansible/e2e-docker-stack.yml` wykonuje:

- `docker-compose up -d --build` (profil `openwebui`),
- health-check `gateway`, `openwebui`, `mcp-webui`,
- walidację `/v1/models` z auth,
- prompt `mcp-skills/refactor` z polami `Repo/Source/Branch/Execute/Push/Test/Zadanie`,
- prompt `mcp-skills/analyze`,
- asercję, że routing używa `team/code2schema-demo` i `/host-semcod/code2schema`.

---

## Scenariusz 9 — OpenWebUI: refactor + commit + push

**Cel:** wywołać refaktoryzację z OpenWebUI i automatycznie wykonać commit oraz (opcjonalnie) push.

W wiadomości do modelu `mcp-skills/refactor` podaj:

```text
Repo: team/code2schema-demo
Source: /host-semcod/code2schema
Branch: main
Execute: true
Push: false
Remote: origin
Draft: true
Draft name: refactor-utils
PR: false
Test: python3 -m compileall -q .
Zadanie: Zaproponuj refaktor modułu utils, popraw nazewnictwo, dodaj typowanie, nie zmieniaj API publicznego.
```

Lub (dla zdalnego repo):

```text
Repo: team/code2schema-demo
Repo URL: https://github.com/<org>/<repo>.git
Branch: main
Execute: true
Push: true
Remote: origin
Draft: true
Draft name: refactor-utils
PR: false
Test: python3 -m compileall -q .
Zadanie: Zaproponuj refaktor modułu utils, popraw nazewnictwo, dodaj typowanie, nie zmieniaj API publicznego.
```

### Konfiguracja GitHub bezpośrednio z OpenWebUI (`localhost:3000`)

Możesz ustawić token GitHub bez wychodzenia z OpenWebUI, dodając w prompt:

```text
GitHub Token: ghp_xxx... lub github_pat_xxx...
```

Gateway zapisze token do `.env` przez `env2mcp` i użyje go do:

- klonowania/sync repo GitHub,
- push,
- tworzenia PR.

Następnie możesz używać skrótu repo bez pełnego URL:

```text
Repo URL: owner/repo
```

Gateway zamieni to na `https://github.com/owner/repo.git` i automatycznie wstrzyknie token.

Możesz też uruchomić synchronizację tokenu z `gh` CLI przez **sam tekst w czacie**
(bez wklejania tokenu), np.:

```text
Pobierz token GitHub z gh CLI
```

lub:

```text
Pokaż github token i zsynchronizuj
```

albo:

```text
Zaktualizuj token GitHub z gh CLI
```

Wtedy `mcp-gateway` rozpozna intencję i wywoła `gh2mcp-agent /sync/token`
zamiast uruchamiać workflow refactor/analyze dla repo.

Oddzielne komendy systemowe (chat / OpenWebUI):
- `Pobierz token github` → pobranie przez `gh2mcp` (`gh auth token`) i sync do `.env`.
- `Zapisz token github do .env: ghp_xxx...` → bezpośredni zapis przez `env2mcp` (`EnvConfig`) do `GITHUB_PAT`.
- `Ustaw organizację: semcod` → `gh2mcp /org/set` — ustawia domyślną organizację GitHub.
- `Pokaż listę repo organizacji` → `gh2mcp /org/list` — zwraca organizacje i ich repo.
- `Repo: {{pokaż ostatnie repo z github}}` → `gh2mcp /repo/last-pushed` — gateway automatycznie rozpoznaje szablon `{{ ... }}` w polu `Repo` i odpytuje gh2mcp, żeby wybrać ostatnio pushowane repo.

Token jest zapisywany do `.env` (`/app/.env` w kontenerach), z którego korzystają
inne usługi stacku, m.in. `mcp-gateway`, `mcp-webui` oraz workflow LLM (`llm-agent`).

Przy tym trybie:
- **pobranie** tokenu jest wymuszane przez `gh2mcp` z `gh auth token` (`force_gh_cli=true`),
- **zapis** tokenu odbywa się przez `env2mcp` (`EnvConfig`) do pliku
  `/home/tom/github/semcod/mcp/.env` (w kontenerach widocznego jako `/app/.env`).

W praktyce Docker:
- `make start` próbuje pobrać `GH_TOKEN` z hostowego `gh auth token` i przekazuje go do `gh2mcp-agent`,
- dzięki temu `gh auth token` w kontenerze zwraca aktualny token, nawet jeśli hostowy `gh` używa keyring.

### Jak czytać wynik w czacie

Gateway zwraca **czytelny Markdown** zamiast surowego JSON w treści wiadomości czatu:

- `analyze` → nagłówek `# Analiza repo`, sekcje `## Największe pliki`, `## Proponowane etapy` (konkretne ścieżki w `` `target` ``).
- `refactor` → nagłówek `# Plan refaktoryzacji`, sekcje `## Status wykonania`, `## Push/PR`.
- komendy systemowe (token, org) → krótki status inline.

**Surowy JSON** (pełny payload) jest dostępny przez:
```bash
curl http://localhost:9000/jobs/{job_id}
```

Przykładowe pola w `result.analysis`:

```json
{
  "metrics": {
    "largest_files": [
      {"path": "mcp-gateway/server.py", "lines": 2908, "functions": 80}
    ]
  },
  "recommendations": {
    "recommendations": [
      {
        "type": "split_module",
        "priority": "high",
        "target": "mcp-gateway/server.py",
        "suggested_action": "split_module"
      }
    ]
  }
}
```

Logika metryk: [`mcp-skills/code_analysis.py`](../mcp-skills/code_analysis.py). Silnik może być `redsl` lub `mcp-skills` — gateway uzupełnia puste `largest_files` automatycznie.

### Tryb asynchroniczny (Redis/RQ)

Gateway obsługuje tryb background-jobs dla modeli `mcp-skills/analyze` i `mcp-skills/refactor`.

Warunki:
- `MCP_ASYNC_ENABLED=true`
- działające usługi `redis` i `mcp-gateway-worker`

W tym trybie `/v1/chat/completions` zwraca szybko status `queued` i `job_id`, a workflow wykonuje się w tle.

Przykład API:

```bash
curl -sS http://localhost:9000/v1/chat/completions \
  -H 'Authorization: Bearer sk-mcp-default-dev-key' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "mcp-skills/refactor",
    "messages": [{"role": "user", "content": "Repo: team/code2schema-demo\nSource: /host-semcod/code2schema\nBranch: main\nExecute: false\nZadanie: Zaproponuj kolejne etapy refaktoryzacji."}],
    "async_mode": true
  }'
```

Sprawdzenie statusu:

```bash
curl -sS -H 'Authorization: Bearer sk-mcp-default-dev-key' \
  http://localhost:9000/jobs/<job_id> | python3 -m json.tool
```

Stream statusu (SSE):

```bash
curl -N -H 'Authorization: Bearer sk-mcp-default-dev-key' \
  http://localhost:9000/jobs/<job_id>/stream
```

Typowe fazy:
- `queued`
- `analyzing`
- `refactoring`
- `testing`
- `done` / `failed`

### Auto-recovery przy błędach autoryzacji GitHub

Jeśli template `{{show last pushed repo from github}}` zwróci błąd 401 lub `Requires authentication`, gateway **automatycznie**:

1. Wywołuje `gh2mcp /sync/token` (`force_gh_cli=true`) — pobiera świeży token z `gh auth token`.
2. Zapisuje token do `.env` przez `env2mcp` (`EnvConfig`).
3. Ponawia oryginalne wywołanie `/repo/last-pushed`.

Jeśli auto-recovery nie zadziała (np. brak `gh auth login`), gateway zwraca **przyjazny komunikat z 3 opcjami**:

```
1) W czacie podaj token bezpośrednio:
   Zapisz token github do .env: ghp_xxx...
2) Zaloguj się przez gh CLI na hoście, potem odśwież w czacie:
   gh auth login → Pobierz token github
3) Z terminala:
   env2mcp env set GITHUB_PAT ghp_xxx → make reload-gateway
```

Recovery jest wykonywane wyłącznie dla błędów autoryzacji (`401`, `Bad credentials`, `gh auth login`, `Requires authentication`, `no token`). Inne błędy (np. `No repositories found`) są zwracane natychmiast bez retry.

### Pola `Repo` i `Repo URL` — kolejność priorytetów

| Pole | Znaczenie |
|------|-----------|
| `Repo: owner/repo` | Identyfikator repo (skrócony lub lokalny) |
| `Repo URL: owner/repo` | Nadpisuje URL sync/push/PR; akceptuje `owner/repo` lub pełny HTTPS |
| `Repo: {{show last pushed repo from github}}` | Template — gateway odpytuje `gh2mcp /repo/last-pushed` i podstawia wynik |

Jeśli użyjesz template `{{ ... }}` w `Repo:` bez podania `Repo URL:`, gateway **automatycznie pobierze `repo_url`** z metadanych odpowiedzi `gh2mcp` i użyje go do sync/push/PR. Jeśli `Repo URL:` jest podany ręcznie, ma **wyższy priorytet** niż `repo_url` z template.

Przykład — auto-resolve URL z template:
```text
Repo: {{show last pushed repo from github owner=semcod}}
Branch: main
Execute: true
Push: true
PR: true
PR title: MCP: auto-refactor
Zadanie: Wdróż Etap 1 planu.
```

### Jak czytać pola wykonania

- `analysis` — metryki/wzorce/rekomendacje z `mcp-skills`.
- `plan_preview` — podsumowanie i artefakty planu.
- `execution.committed=true` — commit utworzony przez `mcp-git-proxy`.
- `execution.tests.ok=true` — test command przeszedł.
- `execution.pushed=true` — push wykonany (gdy `Push: true` i feature `push` jest włączony dla tenant).
- `execution.draft_branch` — informacje o utworzonym `draft/*` branch (gdy `Draft: true`).
- `execution.pull_request` — dane PR (lub `skipped` z powodem, gdy PR nie mógł zostać utworzony).
- `github.configured=true` — token GitHub został zapisany do `.env` podczas wywołania.
- `repo_selection.strategy` — `last_pushed_repo_from_github` jeśli użyto template `{{ ... }}`.

### Zasady `Draft` / `PR`

1. `Draft: true` tworzy branch `draft/<nazwa>` przed commitem (domyślnie przy `Push: true`).
2. `PR: true` działa tylko gdy push się powiedzie.
3. PR jest tworzony tylko dla repo GitHub (`Repo URL: https://github.com/...` albo `git@github.com:...`).
4. Gateway używa `GITHUB_TOKEN` lub `GITHUB_PAT` z environment.

### Co jest jeszcze do zrobienia, aby mieć „pełny auto-refactor kodu”

1. Generowanie i aplikacja patchy kodu (nie tylko artefaktów `.mcp/*`).
2. Iteracyjna pętla: patch -> test -> rollback/checkpoint restore -> kolejna próba.
3. Bogatsza strategia branch/PR (reviewers/labels/assignees, polityki merge).
4. Lepsze guard-raile: limity scope zmian, allowlist ścieżek, reguły bezpieczeństwa push.
5. Trwały storage jobów (Redis/Postgres) zamiast in-memory `JOBS`.

---

## Scenariusz 10 — refactor-last-repo.sh (automatyczny workflow)

**Cel:** automatycznie wybrać ostatnio pushowane repo z GitHub, wykonać analizę i (opcjonalnie) refactor + commit + push + PR — jednym poleceniem.

```bash
# 1) analyze-only: pokaż ostatnie repo i zaproponuj plan etapowy
bash scripts/refactor-last-repo.sh

# 2) analyze + execute (commit artefaktów .mcp/*)
bash scripts/refactor-last-repo.sh --execute

# 3) pełny cykl: analyze + execute + push + PR
bash scripts/refactor-last-repo.sh --execute --push --pr

# 4) konkretne repo i własne zadanie
bash scripts/refactor-last-repo.sh --repo semcod/mcp --execute --task "Etap 2 refaktoryzacji gateway"

# 5) z własnym ownerem (inna organizacja)
bash scripts/refactor-last-repo.sh --owner semcod --execute
```

Opcje:
- `--repo owner/repo` — użyj konkretnego repo zamiast auto-wyboru
- `--owner <owner>` — właściciel dla auto-wyboru (domyślnie: aktualny user `gh`)
- `--branch <branch>` — branch (domyślnie: `main`)
- `--task "..."` — zadanie refaktoryzacji
- `--test "..."` — komenda testowa
- `--execute` — commit artefaktów
- `--push` — push (wymaga `--execute`)
- `--pr` — otwórz PR (wymaga `--execute --push`)
- `--no-draft` — bez draft branch
- `--show-top N` — ile repo pokazać w rankingu (domyślnie: 10)

Wyniki zapisywane do `output/refactor-last-repo-<timestamp>/`:
- `analyze.response.json` / `analyze.result.json`
- `refactor.response.json` / `refactor.result.json`

---

## Smoke-test po wdrożeniu

```bash
# health
curl http://localhost:9000/health

# auth wymagany
curl -o /dev/null -w '%{http_code}\n' http://localhost:9000/v1/models   # -> 401

# auth ok
curl -H 'Authorization: Bearer sk-mcp-default-dev-key' http://localhost:9000/v1/models

# OpenWebUI
curl -o /dev/null -w '%{http_code}\n' http://localhost:3000/   # -> 200

# mcp-webui
curl -o /dev/null -w '%{http_code}\n' http://localhost:8092/   # -> 200

# mcp-docs
curl -o /dev/null -w '%{http_code}\n' http://localhost:8093/   # -> 200
```

---

## FAQ

**Jak uruchomić automatyczny workflow refactor-last-repo?**
```bash
bash scripts/refactor-last-repo.sh                          # analyze-only
bash scripts/refactor-last-repo.sh --execute --push --pr    # pełny cykl
```
Więcej opcji: `bash scripts/refactor-last-repo.sh --help`

**Jak użyć szablonu repo w czacie?**
W polu `Repo:` wpisz template w podwójnych nawiasach:
```text
Repo: {{pokaż ostatnie repo z github}}
```
Gateway automatycznie odpyta `gh2mcp` i rozwiąże repo_id.

**Jak szybko wygenerować repo demo i uruchomić use-case?**
```bash
make generate-demo-repos
```
Warianty:
```bash
make generate-demo-repos-github                # preferuj GitHub
GH_DEMO_PROVIDER=local make generate-demo-repos  # wymuś local bare
```
Szczegółowe prompty i scenariusze: `docs/USE_CASES.md`.

**Jak skonfigurować GitHub?**

Najszybciej (jeśli masz `gh` zainstalowane):
```bash
gh auth login          # jednorazowe logowanie przez przeglądarkę
make setup-github      # pobiera token z gh i zapisuje do .env
```
Alternatywnie przez WebUI: http://localhost:8092/github → **"Pobierz token z gh CLI"**

Bez `gh` CLI:
```bash
# Wejdź na https://github.com/settings/tokens/new?scopes=repo,delete_repo
# Skopiuj token, następnie:
env2mcp env set GITHUB_PAT ghp_twoj_token
# lub wpisz ręcznie w http://localhost:8092/github
```

**Jak pobrać aktualny token jeśli jestem zalogowany przez gh?**
```bash
gh auth token               # wyświetl aktualny token
gh auth status              # sprawdź status logowania
make setup-github           # pobierz i zapisz do .env
```
Przez WebUI: http://localhost:8092/github → **"Pobierz token z gh CLI"** — jeden klik.

**Jak przetestować czy token i create-repo działają?**
```bash
export GITHUB_PAT=ghp_twoj_token
make ansible-github-test
```
Playbook weryfikuje token, tworzy testowe repo, sprawdza klonowanie i usuwa repo po teście.

**Skąd wziąć GitHub Personal Access Token?**
1. Wejdź na https://github.com/settings/tokens/new?scopes=repo,delete_repo
2. Kliknij **Generate new token (classic)**
3. Zaznacz scope: `repo` (obowiązkowy) + `delete_repo` (do testów z cleanup)
4. Skopiuj token i zapisz w `.env` jako `GITHUB_PAT` lub przez WebUI

**Jak utworzyć nowe repo na GitHubie?**

Przez WebUI: http://localhost:8092/github → sekcja **"Create New Repository on GitHub"**

Przez API:
```bash
curl -X POST http://localhost:8081/github/create-repo \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"nowe-repo\",\"private\":true,\"auto_clone\":true,\"github_token\":\"$GITHUB_PAT\"}"
```

**Jak włączyć/wyłączyć skill dla tenanta?**
W `mcp-gateway/tenants/<tenant>.yaml` w sekcji `features`. Po zmianie restart gateway.

**Gdzie są commit-y?**
W wolumenie `git-repo-storage` (kontener `mcp-git-proxy`). `git push` pushuje do skonfigurowanego remote.

**Jak dodać własny model OpenRouter?**
Ustaw `LLM_MODEL` w `.env`, restart `mcp-gateway` i `llm-agent`.

**Czy OpenWebUI widzi tylko moje skille?**
Tak. Gateway zwraca `/v1/models` z listą `mcp-skills/*`, OpenWebUI nie ma bezpośredniego dostępu do OpenRouter.

**Jak dodać nowego klienta produkcyjnie?**
Dodaj plik YAML w `mcp-gateway/tenants/`, restart gateway. Klient dostaje swój `API Key`.
