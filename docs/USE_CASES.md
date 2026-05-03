# MCP Skills — Use Cases (Refactor / Migration / Integration)

Dokument zawiera gotowe przykłady użycia systemu dla:
- refaktoryzacji,
- migracji technologicznej,
- integracji wielu repozytoriów.

Najpierw repo demo są generowane przez sam system (`scripts/generate_demo_repos.sh`), a potem używane w promptach przez `mcp-gateway`.

Szczegółowe dialogi chat-playbook (krok po kroku): `docs/CHAT_PLAYBOOKS.md`.

---

## 1) Generowanie repo demo przez system

```bash
make generate-demo-repos
```

Domyślnie działa tryb `auto`:
- jeśli dostępne są `gh auth status` + token + user, repo powstaną bezpośrednio na GitHub,
- w przeciwnym razie skrypt automatycznie zrobi fallback do lokalnych bare repo.

Wymuszenie providerów:

```bash
# wymuś GitHub (z fallbackiem do local, gdy gh/token niegotowe)
make generate-demo-repos-github

# wymuś local bare
GH_DEMO_PROVIDER=local make generate-demo-repos
```

Konfiguracja nazw i widoczności repo na GitHub:

```bash
GH_DEMO_PREFIX=mcp-demo GH_DEMO_VISIBILITY=private make generate-demo-repos
```

Przykładowe nazwy tworzone na GitHub:
- `mcp-demo-refactor-lab`
- `mcp-demo-migration-lab`
- `mcp-demo-integration-lab`

Skrypt tworzy i seeduje 3 repozytoria:
- `demo/refactor-lab`
- `demo/migration-lab`
- `demo/integration-lab`

Źródła i „GitHub-like” remotes (lokalne bare):
- `repos/generated-sources/*`
- `repos/generated-remotes/*.git`

Jeśli provider to GitHub, remote będzie `https://github.com/<user>/<prefix>-<repo>.git`.

Skrypt automatycznie synchronizuje je do `mcp-git-proxy`.

---

## 2) Use case: refaktoryzacja (`demo/refactor-lab`)

Cel: uproszczenie logiki i poprawa czytelności bez zmiany API.

### Prompt (OpenWebUI lub API)

```text
Repo: demo/refactor-lab
Branch: main
Execute: true
Push: false
Draft: true
Draft name: usecase-refactor
PR: false
Test: python3 -m compileall -q .
Zadanie: Uprość funkcje normalize_items i score_payload bez zmiany API publicznego.
```

---

## 3) Use case: migracja (`demo/migration-lab`)

Cel: przygotować plan migracji z legacy packaging (`setup.py`) do `pyproject.toml`.

### Prompt

```text
Repo: demo/migration-lab
Branch: main
Execute: true
Push: false
Draft: true
Draft name: usecase-migration
PR: false
Test: python3 -m compileall -q .
Zadanie: Przygotuj plan migracji z setup.py/requirements.txt do pyproject.toml i nowego układu pakietu.
```

---

## 4) Use case: integracja (`demo/integration-lab`)

Cel: przygotować plan integracji modułów users/orders i kontraktu danych.

### Prompt

```text
Repo: demo/integration-lab
Branch: main
Execute: true
Push: false
Draft: true
Draft name: usecase-integration
PR: false
Test: python3 -m compileall -q .
Zadanie: Przygotuj plan integracji modułów users/orders z czytelną warstwą orchestratora i kontraktem danych.
```

---

## 5) Integracja kilku przykładowych repo na GitHub

Poniżej gotowe przykłady dla repo publicznych (lub własnych prywatnych po ustawieniu tokena):

### 5.1 Refactor API service

```text
Repo: github/fastapi
Repo URL: tiangolo/fastapi
Branch: master
Execute: true
Push: false
Draft: true
Draft name: api-maintainability
PR: false
Zadanie: Przygotuj plan ograniczenia złożoności modułów routing i walidacji.
```

### 5.2 Migration packaging / dependencies

```text
Repo: github/requests
Repo URL: psf/requests
Branch: main
Execute: true
Push: false
Draft: true
Draft name: migration-packaging
PR: false
Zadanie: Przygotuj plan migracji packaging i strategię aktualizacji zależności.
```

### 5.3 Multi-repo integration blueprint

```text
Repo: github/flask
Repo URL: pallets/flask
Branch: main
Execute: false
Push: false
Zadanie: Przygotuj plan integracji komponentów Flask + FastAPI + Requests w architekturze gateway/service/client.
```

Uwaga:
- `Repo URL: owner/repo` jest wspierane i mapowane do `https://github.com/owner/repo.git`.
- `Repo: {{show last pushed repo from github}}` jest wspierane i automatycznie rozwiązywane przez dodatkowy call (`mcp-gateway -> gh2mcp /repo/last-pushed`).
- Dla prywatnych repo ustaw token przez:
  - `make setup-github`, albo
  - w prompt: `GitHub Token: <token>`.

---

## 6) Chat playbook — pełne przykłady (multi-project / migration / integration / modularization)

Poniżej masz gotowe wiadomości do czatu (OpenWebUI), które możesz wkleić 1:1.

### 6.1 Refaktoryzacja wielu projektów (portfolio)

Rekomendowany przebieg:
1. Najpierw model `mcp-skills/analyze` i `Execute: false` dla każdego repo.
2. Potem model `mcp-skills/refactor` i `Execute: true` dla wybranych priorytetów.

#### Krok A — analiza repo 1

```text
Repo: demo/refactor-lab
Branch: main
Execute: false
Push: false
Zadanie: Przygotuj etapowy plan refaktoryzacji (Etap 1/2/3), oszacuj ryzyko i quick wins.
```

#### Krok B — analiza repo 2

```text
Repo: demo/migration-lab
Branch: main
Execute: false
Push: false
Zadanie: Przygotuj etapowy plan refaktoryzacji i modernizacji struktury projektu.
```

#### Krok C — analiza repo 3

```text
Repo: demo/integration-lab
Branch: main
Execute: false
Push: false
Zadanie: Przygotuj etapowy plan poprawy spójności kontraktów danych i odpowiedzialności modułów.
```

#### Krok D — wdrożenie etapu 1 dla wybranego repo

```text
Repo: demo/refactor-lab
Branch: main
Execute: true
Push: true
Remote: origin
Draft: true
Draft name: portfolio-refactor-stage1
PR: true
PR title: MCP: Stage 1 refactor for demo/refactor-lab
PR body: Etap 1 refaktoryzacji wg planu portfolio.
Test: python3 -m compileall -q .
Zadanie: Wdróż Etap 1 refaktoryzacji, skup się na czytelności i ograniczeniu złożoności bez zmiany API.
```

### 6.2 Migracja technologiczna (pełny przykład chat)

```text
Repo: demo/migration-lab
Branch: main
Execute: true
Push: true
Remote: origin
Draft: true
Draft name: migration-to-pyproject
PR: true
PR title: MCP: migration to pyproject-based packaging
PR body: Plan i artefakty migracji packaging/dependencies.
Test: python3 -m compileall -q .
Zadanie: Przygotuj i wdroż etap 1 migracji z setup.py/requirements.txt do pyproject.toml, z checklistą ryzyk i rollback planem.
```

### 6.3 Integracja komponentów/usług (pełny przykład chat)

```text
Repo: demo/integration-lab
Branch: main
Execute: true
Push: false
Draft: true
Draft name: integration-contract-hardening
PR: false
Test: python3 -m compileall -q .
Zadanie: Zaproponuj i wdroż etap 1 integracji users/orders: kontrakty danych, walidacja wejścia, jasny orchestrator i granice odpowiedzialności.
```

### 6.4 Modularyzacja monolitu (pełny przykład chat)

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
PR body: Wydzielenie granic modułów i plan dalszej dekompozycji.
Test: python3 -m compileall -q .
Zadanie: Zaproponuj i wdroż etap 1 modularyzacji: wyznacz granice modułów (core/api/infrastructure), zdefiniuj zależności kierunkowe i plan dekompozycji na kolejne etapy.
```

### 6.5 Przykład „zarządzania przez chat” (kolejna iteracja)

Po pierwszym wyniku możesz kontynuować jednym krótkim promptem:

```text
Kontynuuj na tym samym repo i branchu. Zaproponuj Etap 2 na podstawie poprzedniego planu, zachowując kompatybilność API i ograniczając ryzyko regresji.
```

---

## 8) Automatyczny workflow: `refactor-last-repo.sh`

Skrypt automatyzujący najczęstszy przepływ: wybór ostatnio pushowanego repo z GitHub → analiza → refactor.

```bash
# analyze-only
bash scripts/refactor-last-repo.sh

# pełny cykl
bash scripts/refactor-last-repo.sh --execute --push --pr

# konkretne repo
bash scripts/refactor-last-repo.sh --repo semcod/mcp --execute --task "Etap 2 refaktoryzacji"
```

Szczegółowy opis opcji: `docs/USAGE.md` → Scenariusz 10.

---

## 9) Szablony repo i komendy systemowe (gateway)

Gateway rozpoznaje specjalne komendy w treści promptu i routuje je do akcji systemowych:

### Szablon repo (`{{ ... }}`)

```text
Repo: {{pokaż ostatnie repo z github}}
Branch: main
Execute: false
Zadanie: Zaproponuj plan refaktoryzacji.
```

Gateway odpyta `gh2mcp /repo/last-pushed` i automatycznie rozwieże `repo_id`.
W odpowiedzi JSON pojawi się pole `repo_selection` z informacją o wybranym repo.

### Zarządzanie organizacjami

```text
Ustaw organizację: semcod
```

```text
Pokaż listę repo organizacji
```

### Zarządzanie tokenem

```text
Pobierz token GitHub z gh CLI
```

```text
Zapisz token github do .env: ghp_xxx...
```

---

## 10) Wyniki testów wykonanych na repo demo

W tej sesji use-case zostały uruchomione przez gateway i zapisane do:
- `output/usecase_refactor.json`
- `output/usecase_migration.json`
- `output/usecase_integration.json`
- `output/usecase_summary.json`

Skrót wyników:
- wszystkie 3 przypadki: `HTTP 200`
- `execution.committed=true`
- `execution.tests.ok=true`
- `execution.draft_branch.branch` ustawione
- artefakty: `.mcp/refactor-plan.json`, `.mcp/refactor-summary.md`
