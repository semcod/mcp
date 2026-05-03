# git2mcp

SUMD - Structured Unified Markdown Descriptor for AI-aware project refactorization

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Dependencies](#dependencies)
- [Source Map](#source-map)
- [Test Contracts](#test-contracts)
- [Refactoring Analysis](#refactoring-analysis)
- [Intent](#intent)

## Metadata

- **name**: `git2mcp`
- **version**: `0.1.6`
- **python_requires**: `>=3.11`
- **ai_model**: `openrouter/qwen/qwen3-coder-next`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: pyproject.toml, testql(2), app.doql.less, .env.example, src(2 mod), project/(5 analysis files)

## Architecture

```
SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)
```

### DOQL Application Declaration (`app.doql.less`)

```less markpact:doql path=app.doql.less
// LESS format — define @variables here as needed

app {
  name: git2mcp;
  version: 0.1.6;
}

dependencies {
  runtime: "httpx>=0.24.0, GitPython>=3.1.43, goal>=2.1.0, costs>=0.1.20, pfix>=0.1.60";
  dev: "fastapi>=0.104.0, pytest>=7.4.0, goal>=2.1.0, costs>=0.1.20, pfix>=0.1.60";
}

deploy {
  target: pip;
}

environment[name="local"] {
  runtime: python;
  env_file: .env;
  python_version: >=3.11;
}
```

### Source Modules

- `git2mcp.client`
- `git2mcp.proxy`

## Dependencies

### Runtime

```text markpact:deps python
httpx>=0.24.0
GitPython>=3.1.43
goal>=2.1.0
costs>=0.1.20
pfix>=0.1.60
```

### Development

```text markpact:deps python scope=dev
fastapi>=0.104.0
pytest>=7.4.0
goal>=2.1.0
costs>=0.1.20
pfix>=0.1.60
```

## Source Map

*Top 2 modules by symbol density — signatures for LLM orientation.*

### `git2mcp.proxy` (`git2mcp/proxy.py`)

```python
class GitProxyManager:
    def __init__(base_dir, cache_dir)  # CC=1
    def _repo_path(repo_id)  # CC=1
    def _ensure_parent(path)  # CC=1
    def _allow_local_repo_url(repo_url)  # CC=9
    def list_repos()  # CC=3
    def sync_repo(repo_id, repo_url, source_path, branch)  # CC=12 ⚠
    def export_package(repo_id, ref)  # CC=6
    def export_fragments(repo_id, ref, max_fragment_bytes)  # CC=9
    def commit_changes(repo_id, message, changes, author_name, author_email)  # CC=5
    def push(repo_id, remote, branch)  # CC=7
```

### `git2mcp.client` (`git2mcp/client.py`)

```python
class Git2MCPClient:
    def __init__(base_url, timeout)  # CC=1
    def _request(method, path, payload)  # CC=4
    def health()  # CC=1
    def list_repos()  # CC=1
    def sync_repo(repo_id, repo_url, source_path, branch)  # CC=1
    def export_package(repo_id, ref)  # CC=1
    def commit_changes(repo_id, message, changes, author_name, author_email)  # CC=1
    def run_tests(repo_id, command)  # CC=1
    def push(repo_id, remote, branch)  # CC=1
```

## Test Contracts

*Scenarios as contract signatures — what the system guarantees.*

### Api (1)

**`API Integration Tests`**
- `GET /health` → `200`
- `GET /api/v1/status` → `200`
- `POST /api/v1/test` → `201`
- assert `status == ok`
- assert `response_time < 1000`

### Integration (1)

**`Auto-generated from Python Tests`**
- `GET /health` → `200`
- `GET /repos` → `200`
- `POST /packages/export` → `200`
- assert `_status == 200`
- assert `status == "ok"`
- assert `_status == 200`

## Refactoring Analysis

*Pre-refactoring snapshot — use this section to identify targets. Generated from `project/` toon files.*

### Call Graph & Complexity (`project/calls.toon.yaml`)

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/semcod/mcp/git2mcp
# nodes: 0 | edges: 0 | modules: 0
# CC̄=3.5

HUBS[20]:

MODULES:

EDGES:
```

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 11f 488L | python:5,txt:4,shell:1,toml:1 | 2026-05-03
# CC̄=3.5 | critical:0/19 | dups:0 | cycles:0

HEALTH[0]: ok

REFACTOR[0]: none needed

PIPELINES[18]:
  [1] Src [__init__]: __init__
      PURITY: 100% pure
  [2] Src [_request]: _request
      PURITY: 100% pure
  [3] Src [health]: health
      PURITY: 100% pure
  [4] Src [list_repos]: list_repos
      PURITY: 100% pure
  [5] Src [sync_repo]: sync_repo
      PURITY: 100% pure

LAYERS:
  git2mcp/                        CC̄=3.5    ←in:0  →out:0
  │ proxy                      290L  1C   10m  CC=12     ←0
  │ client                      61L  1C    9m  CC=4      ←0
  │
  ./                              CC̄=0.0    ←in:0  →out:0
  │ pyproject.toml              57L  0C    0m  CC=0.0    ←0
  │ project.sh                  47L  0C    0m  CC=0.0    ←0
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │ client                       3L  0C    0m  CC=0.0    ←0
  │ proxy                        3L  0C    0m  CC=0.0    ←0
  │
  git2mcp.egg-info/               CC̄=0.0    ←in:0  →out:0
  │ requires.txt                12L  0C    0m  CC=0.0    ←0
  │ SOURCES.txt                 10L  0C    0m  CC=0.0    ←0
  │ dependency_links.txt         1L  0C    0m  CC=0.0    ←0
  │ top_level.txt                1L  0C    0m  CC=0.0    ←0
  │

COUPLING: no cross-package imports detected

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 0 groups | 6f 363L | 2026-05-03

SUMMARY:
  files_scanned: 6
  total_lines:   363
  dup_groups:    0
  dup_fragments: 0
  saved_lines:   0
  scan_ms:       4055
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 19 func | 2f | 2026-05-03

NEXT[0]: no refactoring needed

RISKS[0]: none

METRICS-TARGET:
  CC̄:          3.5 → ≤2.4
  max-CC:      12 → ≤6
  god-modules: 0 → 0
  high-CC(≥15): 0 → ≤0
  hub-types:   0 → ≤0

PATTERNS (language parser shared logic):
  _extract_declarations() in base.py — unified extraction for:
    - TypeScript: interfaces, types, classes, functions, arrow funcs
    - PHP: namespaces, traits, classes, functions, includes
    - Ruby: modules, classes, methods, requires
    - C++: classes, structs, functions, #includes
    - C#: classes, interfaces, methods, usings
    - Java: classes, interfaces, methods, imports
    - Go: packages, functions, structs
    - Rust: modules, functions, traits, use statements

  Shared regex patterns per language:
    - import: language-specific import/require/using patterns
    - class: class/struct/trait declarations with inheritance
    - function: function/method signatures with visibility
    - brace_tracking: for C-family languages ({ })
    - end_keyword_tracking: for Ruby (module/class/def...end)

  Benefits:
    - Consistent extraction logic across all languages
    - Reduced code duplication (~70% reduction in parser LOC)
    - Easier maintenance: fix once, apply everywhere
    - Standardized FunctionInfo/ClassInfo models

HISTORY:
  (first run — no previous data)
```

## Intent

Git proxy and MCP package sync toolkit
