# git2mcp examples

Przykłady pokazują pracę w trybie agenta i transfer repozytorium do `mcp-skills` przez MCP,
bez współdzielenia volume z `mcp-git-proxy`.

## Wymagania

1. Uruchom serwisy:

```bash
docker-compose up -d mcp-git-proxy mcp-skills
```

2. Ustaw OpenRouter w `.env` (bez Ollama):

```env
OPENROUTER_API_KEY=
#LLM_MODEL=openrouter/qwen/qwen3-coder-next
LLM_MODEL=openrouter/x-ai/grok-code-fast-1
LLM_PROVIDER=openrouter-lite
```

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

```bash
docker-compose run --rm llm-agent python agent_git2mcp.py \
  --repo semcod/taskinity-demo \
  --source-path /host-semcod/taskinity \
  --branch main \
  --execute
```

Agent używa OpenRouter (`LLM_PROVIDER=openrouter-lite`) i wykonuje:
`sync -> analysis -> commit -> run-tests`.
