# MCP Chat Playbooks — szczegółowe dialogi (OpenWebUI / gateway)

Ten dokument zawiera gotowe dialogi chat, które można wykorzystać jako playbook operacyjny.
Każdy dialog można wkleić 1:1 do OpenWebUI (model `mcp-skills/analyze` lub `mcp-skills/refactor`).

> Kontekst działania obecnego systemu: gateway wykonuje `sync + analyze + plan artefaktów (.mcp/*)` i opcjonalnie `commit/push/PR`.

---

## 0) Setup przed dialogami

```bash
make start
make setup-github
```

Sprawdzenie:

```bash
curl -fsS http://localhost:9000/health
curl -fsS -H "Authorization: Bearer ${WEBUI_API_KEY:-sk-mcp-default-dev-key}" http://localhost:9000/v1/models
```

### 0.1 Zmienne dynamiczne w polu `Repo` (z dodatkowym call)

Gateway wspiera teraz placeholdery w formacie `{{ ... }}` i wykonuje dodatkowy call do `gh2mcp`.

Wspierany placeholder:

```text
Repo: {{show last pushed repo from github}}
```

Co dzieje się pod spodem:
1. `mcp-gateway` wykrywa template `{{...}}` w polu `Repo`.
2. `mcp-gateway` wywołuje `POST /repo/last-pushed` na `gh2mcp-agent`.
3. `gh2mcp-agent` używa `gh repo list ... --json nameWithOwner,pushedAt,url`.
4. Najnowsze repo (po `pushedAt`) trafia do workflow jako faktyczne `repo_id`.

Przykład dokładnie jak w wymaganiu:

```text
Repo: {{show last pushed repo from github}}
Branch: main
Execute: false
Push: false
Zadanie: Przygotuj etapowy plan refaktoryzacji (Etap 1/2/3), oszacuj ryzyko i quick wins.
```

Opcjonalnie możesz podać owner/org w tym samym placeholderze:

### 0.2 Auto-recovery przy błędzie autoryzacji GitHub

Gdy template `{{show last pushed repo from github}}` zwróci błąd 401 lub podobny, gateway automatycznie:
1. Wywołuje `gh2mcp /sync/token` — pobiera świeży token z `gh auth token`
2. Zapisuje token do `.env` przez `env2mcp`
3. Ponawia wywołanie `/repo/last-pushed`

Jeśli auto-recovery nie zadziała, gateway zwraca **przyjazny komunikat** z 3 opcjami naprawy:
- Opcja 1: Podaj token bezpośrednio w czacie: `Zapisz token github do .env: ghp_xxx...`
- Opcja 2: Zaloguj się przez gh CLI: `gh auth login` → `Pobierz token github`
- Opcja 3: Terminal: `env2mcp env set GITHUB_PAT ghp_xxx`

### 0.3 Tryb asynchroniczny (Redis/RQ)

Długie operacje można wykonywać w tle:

```text
Repo: {{show last pushed repo from github}}
Branch: main
Execute: true
Push: true
async_mode: true
Zadanie: Wdróż pełną refaktoryzację.
```

W tym trybie:
- Gateway zwraca natychmiast `job_id` i status `queued`
- Workflow wykonuje się w tle (`mcp-gateway-worker`)
- Status można sprawdzić: `GET /jobs/{job_id}`
- Streaming via SSE: `GET /jobs/{job_id}/stream`
- Fazy: `queued` → `analyzing` → `refactoring` → `testing` → `done`/`failed`

```text
Repo: {{show last pushed repo from github owner=semcod}}
```

---

## 1) Playbook: refaktoryzacja wielu projektów (portfolio)

### Cel
- Ustalić priorytety dla 3 repo.
- Wdrożyć etap 1 tylko dla najwyższego priorytetu.

### Dialog 1A — triage portfolio (analyze)

**Użytkownik (wiadomość 1):**
```text
Repo: demo/refactor-lab
Branch: main
Execute: false
Push: false
Zadanie: Zrób analizę repo i zaproponuj etapowy plan refaktoryzacji (Etap 1/2/3) z priorytetami i ryzykiem.
```

**Asystent (oczekiwany typ odpowiedzi):**
- JSON z `analysis.metrics`, `analysis.patterns`, `analysis.recommendations`.
- Krótki plan etapowy.

**Użytkownik (wiadomość 2):**
```text
Repo: demo/migration-lab
Branch: main
Execute: false
Push: false
Zadanie: Zrób analizę repo i zaproponuj etapy modernizacji struktury oraz packaging.
```

**Użytkownik (wiadomość 3):**
```text
Repo: demo/integration-lab
Branch: main
Execute: false
Push: false
Zadanie: Zrób analizę repo i zaproponuj etapy integracji users/orders oraz standaryzacji kontraktów danych.
```

### Dialog 1B — wykonanie etapu 1 dla zwycięskiego repo (refactor + push + PR)

**Użytkownik (wiadomość 4):**
```text
Repo: demo/refactor-lab
Branch: main
Execute: true
Push: true
Remote: origin
Draft: true
Draft name: portfolio-stage1-refactor-lab
PR: true
PR title: MCP: portfolio stage 1 for refactor-lab
PR body: Wdrożenie etapu 1 po triage portfolio.
Test: python3 -m compileall -q .
Zadanie: Wdróż etap 1 refaktoryzacji z poprzedniej analizy, bez zmiany publicznego API.
```

**Asystent (oczekiwany typ odpowiedzi):**
- `execution.committed=true`
- `execution.tests.ok=true/false`
- `execution.pushed=true` (jeśli testy OK i tenant pozwala)
- `execution.pull_request.url` (jeśli `PR: true`)

---

## 2) Playbook: migracja technologiczna

### Cel
- Uporządkować migrację do nowego standardu packaging.
- Prowadzić migrację etapami, z rollback planem.

### Dialog 2A — plan migracji

**Użytkownik:**
```text
Repo: demo/migration-lab
Branch: main
Execute: false
Push: false
Zadanie: Przygotuj plan migracji z setup.py/requirements.txt do pyproject.toml. Podaj etapy, ryzyka, kryteria akceptacji i plan rollback.
```

**Asystent (oczekiwane):**
- Etap 1: przygotowanie struktury.
- Etap 2: migracja konfiguracji i zależności.
- Etap 3: walidacja/testy/regresja.

### Dialog 2B — wykonanie etapu 1

**Użytkownik:**
```text
Repo: demo/migration-lab
Branch: main
Execute: true
Push: true
Remote: origin
Draft: true
Draft name: migration-stage1
PR: true
PR title: MCP: migration stage 1
PR body: Etap 1 migracji packaging i struktury.
Test: python3 -m compileall -q .
Zadanie: Wdróż etap 1 planu migracji, przygotuj repo pod pyproject.toml i opisz wpływ na CI/CD.
```

### Dialog 2C — iteracja etapu 2 (kontynuacja)

**Użytkownik:**
```text
Kontynuuj na tym samym repo i branchu draft. Zaproponuj i wdroż Etap 2 migracji, z naciskiem na kompatybilność i minimalizację ryzyka.
```

---

## 3) Playbook: integracja usług/komponentów

### Cel
- Ustalić kontrakty danych i granice odpowiedzialności.
- Zredukować coupling między modułami.

### Dialog 3A — analiza integracji

**Użytkownik:**
```text
Repo: demo/integration-lab
Branch: main
Execute: false
Push: false
Zadanie: Przeanalizuj integrację users/orders i zaproponuj docelowy kontrakt danych, orchestrator oraz zasady obsługi błędów.
```

### Dialog 3B — wykonanie etapu integracji

**Użytkownik:**
```text
Repo: demo/integration-lab
Branch: main
Execute: true
Push: false
Draft: true
Draft name: integration-stage1
PR: false
Test: python3 -m compileall -q .
Zadanie: Wdróż etap 1 integracji: ujednolić kontrakty danych i wyczyścić odpowiedzialności warstwy orchestratora.
```

### Dialog 3C — przygotowanie do wdrożenia produkcyjnego

**Użytkownik:**
```text
Na podstawie poprzedniego wyniku przygotuj checklistę production readiness: monitoring, obserwowalność, testy kontraktowe, scenariusze rollback.
```

---

## 4) Playbook: modularyzacja monolitu

### Cel
- Wyznaczyć moduły domenowe i zależności kierunkowe.
- Przygotować roadmapę dekompozycji.

### Dialog 4A — projekt docelowej architektury

**Użytkownik:**
```text
Repo: team/monolith-app
Repo URL: owner/monolith-app
Branch: main
Execute: false
Push: false
Zadanie: Zaproponuj architekturę modułową (core/api/infrastructure + moduły domenowe), z regułami zależności i planem dekompozycji na 3 etapy.
```

### Dialog 4B — wdrożenie etapu 1 modularyzacji

**Użytkownik:**
```text
Repo: team/monolith-app
Repo URL: owner/monolith-app
Branch: main
Execute: true
Push: true
Remote: origin
Draft: true
Draft name: modularization-stage1
PR: true
PR title: MCP: modularization stage 1
PR body: Wydzielenie granic modułów i przygotowanie pod etap 2.
Test: python3 -m compileall -q .
Zadanie: Wdróż etap 1 modularyzacji bez łamania API i z zachowaniem ścieżki rollback.
```

### Dialog 4C — kontynuacja etapowa

**Użytkownik:**
```text
Kontynuuj etap 2. Zminimalizuj coupling między modułami i dodaj mierzalne kryteria akceptacji dla etapu 3.
```

---

## 5) Playbook: zarządzanie przez chat (operacyjny)

### Cel
- Jednym dialogiem prowadzić iteracje plan -> execute -> review -> next stage.

**Użytkownik:**
```text
Repo: demo/refactor-lab
Branch: main
Execute: false
Push: false
Zadanie: Zrób plan Etap 1/2/3. Po planie zatrzymaj się i czekaj na potwierdzenie wykonania.
```

**Użytkownik (po analizie):**
```text
Wykonaj tylko Etap 1.
Execute: true
Push: false
Draft: true
Draft name: staged-rollout-etap1
PR: false
Test: python3 -m compileall -q .
```

**Użytkownik (po review):**
```text
Kontynuuj Etap 2. Uwzględnij feedback: mniejszy zakres zmian na plik i nacisk na czytelność kontraktów.
```

---

## 6) Wzorzec „krótkich komend systemowych” w czacie

Te komendy nie uruchamiają refaktoryzacji repo, tylko akcje systemowe gateway/gh2mcp:

```text
Pobierz token GitHub z gh CLI
```

```text
Zapisz token github do .env: ghp_xxx...
```

```text
Pokaż listę repo organizacji
```

```text
Ustaw organizację: semcod
```

Szablon repo (auto-resolve przez gh2mcp):

```text
Repo: {{pokaż ostatnie repo z github}}
Branch: main
Execute: false
Zadanie: Zaproponuj plan refaktoryzacji.
```

---

## 7) Dobre praktyki prowadzenia dialogu

- Najpierw `Execute: false`, potem dopiero `Execute: true`.
- Przy `Push: true` zawsze ustaw `Draft: true` i sensowny `Draft name`.
- Dla większych zmian używaj etapów (1/2/3), nie jednego dużego kroku.
- Każdy etap kończ `Test:` i krótką walidacją wyniku.
- Jeśli wynik jest zbyt szeroki, kolejną wiadomością zawężaj zakres (`tylko moduł X`, `bez zmian API`).

---

## 8) Playbook: `refactor-last-repo.sh` (automatyczny workflow)

Skrypt automatyzuje najczęstszy przepływ bez ręcznego wpisywania promptów w czacie:

```bash
# 1) analyze-only: pokaż top-10 repo i zaproponuj plan etapowy
bash scripts/refactor-last-repo.sh

# 2) analyze + execute + push + PR
bash scripts/refactor-last-repo.sh --execute --push --pr

# 3) konkretne repo i zadanie
bash scripts/refactor-last-repo.sh --repo semcod/mcp --execute --task "Etap 2 gateway"
```

Wyniki zapisywane do `output/refactor-last-repo-<timestamp>/`.

Więcej opcji: `bash scripts/refactor-last-repo.sh --help` lub `docs/USAGE.md` → Scenariusz 10.

---

## 9) Szybka ściąga komend (gh2mcp + git2mcp + Skills + LLM)

### 9.1 Komendy systemowe w czacie (OpenWebUI)

```text
Pobierz token github
```
- źródło: `gh2mcp` (`gh auth token`)
- zapis: `.env` przez `env2mcp`

```text
Zapisz token github do .env: ghp_xxx...
```
- zapis bezpośredni: `env2mcp` do `GITHUB_PAT`

```text
Ustaw organizacje github: semcod
```
- zapisuje `GITHUB_ORG=semcod`

```text
Pokaz liste wszystkich organizacji
```
- wywołuje `gh2mcp /org/list` i zwraca org + repo

```text
Repo: {{show last pushed repo from github owner=semcod}}
Branch: main
Execute: false
Zadanie: Zaproponuj kolejne etapy refaktoryzacji.
```
- automatycznie rozwiązuje ostatnio wypchnięte repo przez `gh2mcp /repo/last-pushed`

### 9.2 Kontynuacja pracy na ostatnim repo

```text
Repo: {{show last pushed repo from github}}
Branch: main
Execute: false
Push: false
Zadanie: Zaproponuj Etap 1/2/3 refaktoryzacji i wskaż szybkie wygrane.
```

```text
Repo: {{show last pushed repo from github}}
Branch: main
Execute: true
Push: false
Draft: true
Draft name: etap1-last-repo
PR: false
Test: python3 -m compileall -q .
Zadanie: Wdróż tylko Etap 1 z poprzedniego planu.
```

### 9.3 Wdrożenie na GitHub (push + PR)

```text
Repo: {{show last pushed repo from github owner=semcod}}
Branch: main
Execute: true
Push: true
Remote: origin
Draft: true
Draft name: refactor-stage2
PR: true
PR title: MCP: refactor stage 2
PR body: Kontynuacja etapowej refaktoryzacji z playbooka.
Test: python3 -m compileall -q .
Zadanie: Wdróż Etap 2 i przygotuj repo do review.
```

### 9.4 Auto-recovery przy błędzie autoryzacji

Gdy GitHub zwróci błąd 401 przy template resolution:

```text
Repo: {{show last pushed repo from github}}
Branch: main
Execute: false
Zadanie: Przygotuj plan refaktoryzacji.
```

Gateway automatycznie próbuje odświeżyć token i ponowić żądanie. Jeśli to nie pomoże, zwróci instrukcję z 3 opcjami naprawy:
1. `Zapisz token github do .env: ghp_xxx...` — bezpośredni zapis
2. `gh auth login` → `Pobierz token github` — CLI auth + sync
3. `env2mcp env set GITHUB_PAT ghp_xxx` — terminal

### 9.5 Tryb asynchroniczny — długie operacje

Dla operacji trwających >30s (duże repo, złożona analiza):

```text
Repo: {{show last pushed repo from github}}
Branch: main
Execute: true
Push: true
PR: true
async_mode: true
Zadanie: Wykonaj pełną refaktoryzację z migracją do nowej architektury.
```

Sprawdzenie statusu:
```bash
curl -sS -H 'Authorization: Bearer sk-mcp-default-dev-key' \
  http://localhost:9000/jobs/job-abc123
```

Streaming statusu (SSE):
```bash
curl -N -H 'Authorization: Bearer sk-mcp-default-dev-key' \
  http://localhost:9000/jobs/job-abc123/stream
```

Fazy:
- `queued` → `analyzing` → `refactoring` → `testing` → `done` / `failed`

---

## Podsumowanie funkcji

| Funkcja | Opis | Endpoint/Prompt |
|---------|------|-----------------|
| Repo template | Auto-resolve `{{show last pushed repo from github}}` | `Repo: {{...}}` |
| Repo URL override | Ręczne repo_url ma wyższy priorytet | `Repo URL: https://...` |
| GitHub auth auto-recovery | Auto-sync tokenu przy 401 + 3 opcje naprawy | Automatyczne |
| Async mode | Background jobs via Redis/RQ | `async_mode: true` |
| Job streaming | SSE status updates | `GET /jobs/{id}/stream` |
| Copy/OpenWebUI buttons | Przyciski na blokach `<pre>` w docs | http://localhost:8093 |

