# git2mcp

Git proxy and MCP package sync toolkit

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Interfaces](#interfaces)
- [Configuration](#configuration)
- [Dependencies](#dependencies)
- [Deployment](#deployment)
- [Environment Variables (`.env.example`)](#environment-variables-envexample)
- [Code Analysis](#code-analysis)
- [Source Map](#source-map)
- [Test Contracts](#test-contracts)
- [Intent](#intent)

## Metadata

- **name**: `git2mcp`
- **version**: `0.1.6`
- **python_requires**: `>=3.11`
- **ai_model**: `openrouter/qwen/qwen3-coder-next`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: pyproject.toml, testql(2), app.doql.less, .env.example, src(2 mod), project/(2 analysis files)

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

## Interfaces

### testql Scenarios

#### `testql-scenarios/generated-api-integration.testql.toon.yaml`

```toon markpact:testql path=testql-scenarios/generated-api-integration.testql.toon.yaml
# SCENARIO: API Integration Tests
# TYPE: api
# GENERATED: true

CONFIG[3]{key, value}:
  base_url, http://localhost:8101
  timeout_ms, 30000
  retry_count, 3

API[4]{method, endpoint, expected_status}:
  GET, /health, 200
  GET, /api/v1/status, 200
  POST, /api/v1/test, 201
  GET, /api/v1/docs, 200

ASSERT[2]{field, operator, expected}:
  status, ==, ok
  response_time, <, 1000
```

#### `testql-scenarios/generated-from-pytests.testql.toon.yaml`

```toon markpact:testql path=testql-scenarios/generated-from-pytests.testql.toon.yaml
# SCENARIO: Auto-generated from Python Tests
# TYPE: integration
# GENERATED: true

CONFIG[2]{key, value}:
  base_url, ${api_url:-http://localhost:8101}
  timeout_ms, 10000

# Converted 6 API calls from pytest
API[6]{method, endpoint, expected_status}:
  GET, /health, 200
  GET, /repos, 200
  POST, /packages/export, 200
  GET, /health, 200
  GET, /repos, 200
  POST, /packages/export, 200

# Converted 36 assertions from pytest
ASSERT[36]{field, operator, expected}:
  _status, ==, 200
  status, ==, "ok"
  _status, ==, 200
  sync_payload.repo_id, ==, repo_id
  _status, ==, 200
  _status, ==, 200
  export_payload.repo_id, ==, repo_id
  _status, ==, 200
  commit_payload.repo_id, ==, repo_id
  len(commit_payload.commit), ==, 40
  _status, ==, 200
  tests_payload.repo_id, ==, repo_id
  _status, ==, 200
  _status, ==, 200
  len(commit_payload.commit), ==, 40
  _status, ==, 200
  _status, ==, 200
  pushed_file.read_text(encoding="utf-8"), ==, '{"pushed": true}'
  _status, ==, 200
  status, ==, "ok"
  _status, ==, 200
  sync_payload.repo_id, ==, repo_id
  _status, ==, 200
  _status, ==, 200
  export_payload.repo_id, ==, repo_id
  _status, ==, 200
  commit_payload.repo_id, ==, repo_id
  len(commit_payload.commit), ==, 40
  _status, ==, 200
  tests_payload.repo_id, ==, repo_id
  _status, ==, 200
  _status, ==, 200
  len(commit_payload.commit), ==, 40
  _status, ==, 200
  _status, ==, 200
  pushed_file.read_text(encoding="utf-8"), ==, '{"pushed": true}'
```

## Configuration

```yaml
project:
  name: git2mcp
  version: 0.1.6
  env: local
```

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

## Deployment

```bash markpact:run
pip install git2mcp

# development install
pip install -e .[dev]
```

## Environment Variables (`.env.example`)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | `*(not set)*` | Required: OpenRouter API key (https://openrouter.ai/keys) |
| `LLM_MODEL` | `openrouter/qwen/qwen3-coder-next` | Model (default: openrouter/qwen/qwen3-coder-next) |
| `PFIX_AUTO_APPLY` | `true` | true = apply fixes without asking |
| `PFIX_AUTO_INSTALL_DEPS` | `true` | true = auto pip/uv install |
| `PFIX_AUTO_RESTART` | `false` | true = os.execv restart after fix |
| `PFIX_MAX_RETRIES` | `3` |  |
| `PFIX_DRY_RUN` | `false` |  |
| `PFIX_ENABLED` | `true` |  |
| `PFIX_GIT_COMMIT` | `false` | true = auto-commit fixes |
| `PFIX_GIT_PREFIX` | `pfix:` | commit message prefix |
| `PFIX_CREATE_BACKUPS` | `false` | false = disable .pfix_backups/ directory |

## Code Analysis

### `project/map.toon.yaml`

```toon markpact:analysis path=project/map.toon.yaml
# git2mcp | 9f 621L | python:7,less:1,shell:1 | 2026-05-03
# stats: 4 func | 2 cls | 9 mod | CC̄=7.8 | critical:2 | cycles:0
# alerts[5]: CC test_git_proxy_e2e_sync_export_commit_and_tests=18; CC test_git_proxy_e2e_push_to_bare_remote=10; CC _load_proxy_app=2; CC _create_sample_repo_source=1; fan-out test_git_proxy_e2e_push_to_bare_remote=18
# hotspots[5]: test_git_proxy_e2e_push_to_bare_remote fan=18; test_git_proxy_e2e_sync_export_commit_and_tests fan=10; _load_proxy_app fan=5; _create_sample_repo_source fan=2
# evolution: baseline
# Keys: M=modules, D=details, i=imports, e=exports, c=classes, f=functions, m=methods
M[9]:
  __init__.py,4
  app.doql.less,22
  client.py,4
  git2mcp/__init__.py,4
  git2mcp/client.py,62
  git2mcp/proxy.py,291
  project.sh,47
  proxy.py,4
  tests/test_git2mcp.py,183
D:
  __init__.py:
  client.py:
  git2mcp/__init__.py:
  git2mcp/client.py:
    e: Git2MCPClient
    Git2MCPClient: __init__(2),_request(3),health(0),list_repos(0),sync_repo(4),export_package(2),commit_changes(5),run_tests(2),push(3)
  git2mcp/proxy.py:
    e: GitProxyManager
    GitProxyManager: __init__(2),_repo_path(1),_ensure_parent(1),_allow_local_repo_url(1),list_repos(0),sync_repo(4),export_package(2),export_fragments(3),commit_changes(5),push(3)
  proxy.py:
  tests/test_git2mcp.py:
    e: _load_proxy_app,_create_sample_repo_source,test_git_proxy_e2e_sync_export_commit_and_tests,test_git_proxy_e2e_push_to_bare_remote
    _load_proxy_app(repo_root;cache_root)
    _create_sample_repo_source(source)
    test_git_proxy_e2e_sync_export_commit_and_tests(tmp_path)
    test_git_proxy_e2e_push_to_bare_remote(tmp_path)
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

## Intent

Git proxy and MCP package sync toolkit
