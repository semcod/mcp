# MCP Skills — Use Cases (Refactor / Migration / Integration)

Dokument zawiera gotowe przykłady użycia systemu dla:
- refaktoryzacji,
- migracji technologicznej,
- integracji wielu repozytoriów.

Najpierw repo demo są generowane przez sam system (`scripts/generate_demo_repos.sh`), a potem używane w promptach przez `mcp-gateway`.

---

## 1) Generowanie repo demo przez system

```bash
make generate-demo-repos
```

Skrypt tworzy i seeduje 3 repozytoria:
- `demo/refactor-lab`
- `demo/migration-lab`
- `demo/integration-lab`

Źródła i „GitHub-like” remotes (lokalne bare):
- `repos/generated-sources/*`
- `repos/generated-remotes/*.git`

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
- Dla prywatnych repo ustaw token przez:
  - `make setup-github`, albo
  - w prompt: `GitHub Token: <token>`.

---

## 6) Wyniki testów wykonanych na repo demo

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
