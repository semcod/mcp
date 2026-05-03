# git2mcp - przykłady pracy z MCP

Przykłady pokazują, jak `git2mcp` działa w trybie **MCP-agenta**:
- synchronizuje repo do `mcp-git-proxy` przez MCP/HTTP API,
- przesyła fragmenty repo do `mcp-skills`,
- a LLM-agent podejmuje decyzje bez ręcznej edycji plików na dysku.

Refaktoryzacja jest zapisywana jako commit Git przez `git2mcp`, a nie jako bezpośredni zapis pliku przez shell.

## Wymagania

1. Uruchom serwisy:

```bash
docker-compose up -d mcp-git-proxy mcp-skills
```

2. Ustaw OpenRouter w `.env` (bez Ollama):

```env
OPENROUTER_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
#LLM_MODEL=openrouter/qwen/qwen3-coder-next
LLM_MODEL=openrouter/x-ai/grok-code-fast-1
LLM_PROVIDER=openrouter-lite
```

3. `mcp-skills` nie ma shared volume z `/git-repos`. Repo jest kopiowane do cache skills przez MCP fragmenty.

## Przykład 1: sync + commit przez git2mcp

```bash
python3 git2mcp/examples/01_sync_and_commit.py \
  --repo-id semcod/docs-demo \
  --source-path /home/tom/github/semcod/docs
```

Co robi:
- synchronizuje repo do `mcp-git-proxy`,
- tworzy commit z plikiem `.mcp/example-note.md`,
- uruchamia test kompilacji `python3 -m compileall -q .`.

To jest podstawowa pętla:
1. sync z lokalnego repo do proxy Git,
2. commit w repo proxy,
3. test sukces/fail.

## Przykład 2: transfer fragmentów do mcp-skills + migracja różnic

```bash
python3 git2mcp/examples/02_fragment_sync_to_skills.py \
  --repo-id semcod/code2schema-demo \
  --source-path /home/tom/github/semcod/code2schema
```

Co robi:
- synchronizuje repo do `mcp-git-proxy`,
- eksportuje fragmenty (`/packages/export-fragments`),
- aplikuje je po stronie `mcp-skills` (`sync_repo_from_git_proxy`),
- pokazuje metryki migracji:
  - `files_updated`,
  - `files_unchanged`,
  - `files_deleted`.

To jest mechanizm wykrywania różnic i migracji pomiędzy stanem user-repo a cache skills.

## Przykład 3: pełny agent z OpenRouter

Lokalny wrapper:

```bash
python3 git2mcp/examples/03_agent_git2mcp.py \
  --repo semcod/taskinity-demo \
  --source-path /host-semcod/taskinity \
  --execute
```

Bezpośrednio przez Docker Compose:

```bash
docker-compose run --rm llm-agent python agent_git2mcp.py \
  --repo semcod/taskinity-demo \
  --source-path /host-semcod/taskinity \
  --branch main \
  --execute
```

Agent używa OpenRouter (`LLM_PROVIDER=openrouter-lite`) i wykonuje:
`sync -> analysis -> commit -> run-tests`.

## QA: czy zmiany w repo są robione przez git2mcp?

Tak. Przepływ działa tak:
- `git2mcp` synchronizuje repo do `mcp-git-proxy`,
- agent przygotowuje payload zmian,
- `mcp-git-proxy` wykonuje `commit` w repo,
- `run-tests` sprawdza wynik,
- opcjonalnie `push` wysyła commit dalej.

`mcp-skills` nie edytuje repo Git. Skills utrzymuje własny cache i aktualizuje go przez fragmenty:
- nowe/zmienione pliki: `files_updated`,
- bez zmian: `files_unchanged`,
- usunięte z repo, ale istniejące w cache: `files_deleted`.

## Przykład 4: dry-run vs execute + auto-revert na nieudanym teście

```bash
# tylko plan, bez commitów
python3 git2mcp/examples/04_dry_run_vs_execute.py \
  --repo-id team/sample \
  --source-path /home/tom/github/semcod/code2schema \
  --dry-run

# realny commit + run-tests; rollback (git reset --hard HEAD~1) przy failu
python3 git2mcp/examples/04_dry_run_vs_execute.py \
  --repo-id team/sample \
  --source-path /home/tom/github/semcod/code2schema \
  --execute
```

Flow:
- `--dry-run` tylko wypisuje `planned_edits` bez zapisu w repo,
- `--execute` robi commit przez `git2mcp`, uruchamia `run-tests`,
- jeśli testy przejdą: commit pozostaje (`reverted=false`),
- jeśli testy nie przejdą: `git2mcp` wykonuje `POST /repos/{repo_id}/reset` z `HEAD~1` (`reverted=true`).

## Przykład 5: lokalna iteracja przed commitem (`worktree` + `patch/apply` + `checkpoint`)

```bash
python3 git2mcp/examples/05_local_iterate.py \
  --repo-id team/sample \
  --source-path /home/tom/github/semcod/code2schema \
  --task-id refactor-001
```

Flow:
- sync repo do `mcp-git-proxy`,
- `checkpoint` working-tree (rollback bez Gita),
- `branch/draft draft/<task-id>`,
- `patch/apply --check` + `patch/apply` (zmiany lokalne, brak commita),
- `run-tests` w working-tree,
- przy fail: `checkpoint/restore`, brak śmiecenia historii,
- przy success: `stage` + `commit` (dopiero teraz historia Git się zmienia).

To jest podstawa pętli iteracyjnej dla LLM-agenta: wiele prób patchowania bez śmiecenia historii.
