# MCP Skills — Scenariusze użycia

Ten dokument pokazuje 5 konkretnych przepływów end-to-end. Wszystkie używają OpenRouter (`LLM_MODEL=openrouter/x-ai/grok-code-fast-1`), bez Ollama.

Powiązane dokumenty:
- `docs/PRODUCT.md` — architektura i deployment
- `git2mcp/examples/README.md` — przykłady CLI
- OpenWebUI docs:
  - https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/
  - https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/

---

## Wymagania wstępne

```bash
# 1) sklonuj projekt i przygotuj .env
cp .env.example .env
# wpisz OPENROUTER_API_KEY i WEBUI_API_KEY (klucz tenanta z mcp-gateway/tenants/default.yaml)

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
- `openwebui`       → http://localhost:3000        (frontend dla użytkowników)
- `mcp-git-proxy`   → http://localhost:8081        (dev only)
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

4. Otrzymasz odpowiedź JSON z `job_id`, statusem `checkpoint`, aktualnym `diff`.
5. Diff możesz obejrzeć w `mcp-webui` na http://localhost:8092/diff?repo_id=team/code2schema-demo

> Uwaga: w MVP `mcp-gateway` zwraca payload dispatcher z checkpoint+diff. Pełny LLM-loop (patch+test+commit) jest w pipeline; w międzyczasie używaj scenariuszy 3 i 4 dla pełnego flow.

---

## Scenariusz 2 — QA / developer w `mcp-webui`

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

## Scenariusz 3 — developer lokalny z `git2mcp` (CLI)

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

## Scenariusz 4 — programatyczne użycie OpenAI SDK przez `mcp-gateway`

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

## Scenariusz 5 — wdrożenie u klienta (multi-tenant)

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

## Scenariusz 6 — bezpieczne iterowanie LLM-em bez śmiecenia historii

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

## Scenariusz 7 — E2E między usługami przez Ansible

**Cel:** automatycznie sprawdzić połączenia `openwebui -> gateway -> git-proxy/skills`, wykonać sample prompty i asercje na odpowiedziach.

```bash
make ansible-e2e
```

Playbook `ansible/e2e-docker-stack.yml` wykonuje:

- `docker-compose up -d --build` (profil `openwebui`),
- health-check `gateway`, `openwebui`, `mcp-webui`,
- walidację `/v1/models` z auth,
- prompt `mcp-skills/refactor` z polami `Repo/Source/Branch/Zadanie`,
- prompt `mcp-skills/analyze`,
- asercję, że routing używa `team/code2schema-demo` i `/host-semcod/code2schema`.

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
```

---

## FAQ

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
