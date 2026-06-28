# Autonomiczny Agent Refaktoryzacji MCP

Initialize semcod MCP stack integration for Cursor, VS Code, Claude and other IDEs — init, doctor, validate, analyze.

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Interfaces](#interfaces)
- [Workflows](#workflows)
- [Configuration](#configuration)
- [Dependencies](#dependencies)
- [Deployment](#deployment)
- [Environment Variables (`.env.example`)](#environment-variables-envexample)
- [Release Management (`goal.yaml`)](#release-management-goalyaml)
- [Makefile Targets](#makefile-targets)
- [Code Analysis](#code-analysis)
- [Call Graph](#call-graph)
- [Intent](#intent)

## Metadata

- **name**: `semcod-mcp`
- **version**: `0.1.4`
- **python_requires**: `>=3.10`
- **license**: Apache-2.0
- **ai_model**: `openrouter/qwen/qwen3-coder-next`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: pyproject.toml, Makefile, app.doql.less, goal.yaml, .env.example, docker-compose.yml, project/(3 analysis files)

## Architecture

```
SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)
```

### DOQL Application Declaration (`app.doql.less`)

```less markpact:doql path=app.doql.less
// LESS format — define @variables here as needed

app {
  name: semcod-mcp;
  version: 0.1.4;
}

dependencies {
  runtime: "click>=8.0, httpx>=0.26.0, pyyaml>=6.0, rich>=13.0";
  dev: "pytest>=8.0, goal>=2.1.0, costs>=0.1.20, pfix>=0.1.60";
}

database[name="redis"] {
  type: redis;
  url: env.REDIS_URL;
}

interface[type="api"] {
  type: rest;
  framework: fastapi;
}

interface[type="mcp"] {
  framework: stdio;
}
interface[type="mcp"] page[name="semcod-mcp"] {
  entry: semcod_mcp.cli:main;
}

interface[type="web"] {
  type: spa;
  framework: static;
}

integration[name="github"] {
  type: scm;
}

workflow[name="kill-ports"] {
  trigger: manual;
  step-1: run cmd=for p in $(PORTS); do \;
  step-2: run cmd=cids=$$(docker ps --filter "publish=$$p" -q); \;
  step-3: run cmd=if [ -n "$$cids" ]; then \;
  step-4: run cmd=echo "stopping containers binding port $$p: $$cids"; \;
  step-5: run cmd=docker stop $$cids >/dev/null || true; \;
  step-6: run cmd=fi; \;
  step-7: run cmd=pids=$$(ss -lntp 2>/dev/null | grep -E ":$$p[[:space:]]" | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u); \;
  step-8: run cmd=if [ -n "$$pids" ]; then \;
  step-9: run cmd=echo "killing pids on port $$p: $$pids"; \;
  step-10: run cmd=for pid in $$pids; do kill -TERM $$pid 2>/dev/null || true; done; \;
  step-11: run cmd=sleep 1; \;
  step-12: run cmd=for pid in $$pids; do kill -9 $$pid 2>/dev/null || true; done; \;
  step-13: run cmd=fi; \;
  step-14: run cmd=done;
}

workflow[name="start"] {
  trigger: manual;
  step-1: run cmd=echo "Pruning orphaned containers to avoid name conflicts...";
  step-2: run cmd=for c in mcp-redis mcp-git-proxy gh2mcp-agent mcp-skills-server llm-agent mcp-gateway mcp-gateway-worker mcp-webui mcp-docs openwebui mcp-dashboard; do \;
  step-3: run cmd=docker rm -f $$c >/dev/null 2>&1 || true; \;
  step-4: run cmd=done;
  step-5: run cmd=GH_TOKEN_VALUE=$$(gh auth token 2>/dev/null || true); \;
  step-6: run cmd=if [ -n "$$GH_TOKEN_VALUE" ]; then export GH_TOKEN="$$GH_TOKEN_VALUE"; fi; \;
  step-7: run cmd=$(COMPOSE) $(PROFILES) build;
  step-8: run cmd=GH_TOKEN_VALUE=$$(gh auth token 2>/dev/null || true); \;
  step-9: run cmd=if [ -n "$$GH_TOKEN_VALUE" ]; then export GH_TOKEN="$$GH_TOKEN_VALUE"; fi; \;
  step-10: run cmd=$(COMPOSE) $(PROFILES) up -d;
  step-11: run cmd=$(MAKE) smoke;
  step-12: run cmd=echo "";
  step-13: run cmd=echo "MCP Skills stack started:";
  step-14: run cmd=echo "  OpenWebUI:  http://localhost:$(PORT_OPENWEBUI)";
  step-15: run cmd=echo "  MCP WebUI:  http://localhost:$(PORT_WEBUI)";
  step-16: run cmd=echo "  MCP Docs:   http://localhost:$(PORT_DOCS)";
  step-17: run cmd=echo "  Gateway:    http://localhost:$(PORT_GATEWAY)";
  step-18: run cmd=echo "  Dashboard:  http://localhost:$(PORT_DASHBOARD)";
  step-19: run cmd=echo "  Git Proxy:  http://localhost:$(PORT_GIT_PROXY)";
}

workflow[name="stop"] {
  trigger: manual;
  step-1: run cmd=$(COMPOSE) $(PROFILES) down --remove-orphans;
}

workflow[name="restart"] {
  trigger: manual;
  step-1: depend target=stop;
  step-2: depend target=start;
}

workflow[name="up"] {
  trigger: manual;
  step-1: run cmd=$(COMPOSE) $(PROFILES) up -d;
}

workflow[name="down"] {
  trigger: manual;
  step-1: depend target=stop;
}

workflow[name="logs"] {
  trigger: manual;
  step-1: run cmd=$(COMPOSE) $(PROFILES) logs -f --tail=200;
}

workflow[name="ps"] {
  trigger: manual;
  step-1: run cmd=$(COMPOSE) $(PROFILES) ps;
}

workflow[name="build"] {
  trigger: manual;
  step-1: run cmd=$(COMPOSE) $(PROFILES) build;
}

workflow[name="rebuild"] {
  trigger: manual;
  step-1: run cmd=$(COMPOSE) $(PROFILES) build --no-cache;
}

workflow[name="smoke"] {
  trigger: manual;
  step-1: run cmd=echo "--- gateway /health ---"; curl -fsS http://localhost:$(PORT_GATEWAY)/health && echo;
  step-2: run cmd=echo "--- gh2mcp /health ---"; curl -fsS http://localhost:$(PORT_GH2MCP)/health && echo;
  step-3: run cmd=echo "--- mcp-docs /health ---"; curl -fsS http://localhost:$(PORT_DOCS)/health && echo;
  step-4: run cmd=echo "--- gateway /v1/models (no auth) ---"; curl -s -o /dev/null -w '%{http_code}\n' http://localhost:$(PORT_GATEWAY)/v1/models;
  step-5: run cmd=echo "--- gateway /v1/models (auth) ---"; curl -fsS -H "Authorization: Bearer $${WEBUI_API_KEY:-sk-mcp-default-dev-key}" http://localhost:$(PORT_GATEWAY)/v1/models | python3 -m json.tool | head -20;
  step-6: run cmd=echo "--- mcp-skills /health (container) ---"; $(COMPOSE) $(PROFILES) exec -T mcp-skills python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=5).status)";
  step-7: run cmd=echo "--- mcp-skills /tools/list (container) ---"; $(COMPOSE) $(PROFILES) exec -T mcp-skills python -c "import urllib.request, json; r=urllib.request.urlopen('http://127.0.0.1:8080/tools/list', timeout=5); d=json.loads(r.read()); print('tools:', len(d.get('tools',[])))" && echo OK || echo 'SKIP (tools not ready)';
  step-8: run cmd=echo "--- mcp-webui / (wait for 200) ---"; \;
  step-9: run cmd=code=""; \;
  step-10: run cmd=for i in {1..30}; do \;
  step-11: run cmd=code=$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:$(PORT_WEBUI)/ || true); \;
  step-12: run cmd=if [ "$$code" = "200" ]; then break; fi; \;
  step-13: run cmd=sleep 1; \;
  step-14: run cmd=done; \;
  step-15: run cmd=echo "$$code"; \;
  step-16: run cmd=[ "$$code" = "200" ];
}

workflow[name="ansible-e2e"] {
  trigger: manual;
  step-1: run cmd=ansible-playbook -i ansible/inventory.ini ansible/e2e-docker-stack.yml;
}

workflow[name="ansible-gh2mcp"] {
  trigger: manual;
  step-1: run cmd=ansible-playbook -i ansible/inventory.ini ansible/e2e-gh2mcp.yml;
}

workflow[name="ansible-github-qa"] {
  trigger: manual;
  step-1: run cmd=ansible-playbook -i ansible/inventory.ini ansible/e2e-github-qa.yml;
}

workflow[name="reload-gateway"] {
  trigger: manual;
  step-1: run cmd=GH_TOKEN_VALUE=$$(gh auth token 2>/dev/null || true); \;
  step-2: run cmd=if [ -n "$$GH_TOKEN_VALUE" ]; then export GH_TOKEN="$$GH_TOKEN_VALUE"; fi; \;
  step-3: run cmd=$(COMPOSE) $(PROFILES) up -d --build --remove-orphans mcp-gateway mcp-gateway-worker gh2mcp-agent;
  step-4: run cmd=echo "mcp-gateway + mcp-gateway-worker + gh2mcp-agent rebuilt and restarted (GH_TOKEN preserved)";
}

workflow[name="ansible-tools-e2e"] {
  trigger: manual;
  step-1: run cmd=ansible-playbook -i ansible/inventory.ini ansible/e2e-tools.yml;
}

workflow[name="reload-skills"] {
  trigger: manual;
  step-1: run cmd=$(COMPOSE) $(PROFILES) up -d --build --remove-orphans mcp-skills;
  step-2: run cmd=echo "mcp-skills rebuilt and restarted";
}

workflow[name="ansible-github-test"] {
  trigger: manual;
  step-1: run cmd=ansible-playbook -i ansible/inventory.ini ansible/test-github-integration.yml;
}

workflow[name="gh2mcp-status"] {
  trigger: manual;
  step-1: run cmd=echo "--- gh2mcp /health ---"; curl -fsS http://localhost:$(PORT_GH2MCP)/health && echo;
  step-2: run cmd=echo "--- gh2mcp /status ---"; curl -fsS http://localhost:$(PORT_GH2MCP)/status | python3 -m json.tool;
}

workflow[name="pytest"] {
  trigger: manual;
  step-1: run cmd=python3 -m pytest -q git2mcp/tests/test_git2mcp.py;
  step-2: run cmd=cd mcp-gateway && python3 -m pytest -q;
  step-3: run cmd=cd gh2mcp && python3 -m pytest -q;
  step-4: run cmd=cd mcp-skills && SKILLS_REPO_BASE=/tmp/mcp-skills-test python3 -m pytest -q;
}

workflow[name="test"] {
  trigger: manual;
  step-1: run cmd=bash scripts/test.sh;
  step-2: run cmd=$(MAKE) ansible-github-qa;
  step-3: run cmd=$(MAKE) ansible-tools-e2e;
}

workflow[name="prod-up"] {
  trigger: manual;
  step-1: run cmd=$(COMPOSE_PROD) $(PROFILES) up -d --build;
}

workflow[name="prod-down"] {
  trigger: manual;
  step-1: run cmd=$(COMPOSE_PROD) $(PROFILES) down --remove-orphans;
}

workflow[name="clean"] {
  trigger: manual;
  step-1: run cmd=$(COMPOSE) $(PROFILES) down -v --remove-orphans;
}

workflow[name="install-env2mcp"] {
  trigger: manual;
  step-1: run cmd=pip install -e ./env2mcp;
}

workflow[name="setup-github"] {
  trigger: manual;
  step-1: run cmd=env2mcp setup-github;
}

workflow[name="generate-demo-repos"] {
  trigger: manual;
  step-1: run cmd=bash scripts/generate_demo_repos.sh;
}

workflow[name="generate-demo-repos-github"] {
  trigger: manual;
  step-1: run cmd=GH_DEMO_PROVIDER=github bash scripts/generate_demo_repos.sh;
}

tests {
  import: git2mcp/testql-scenarios/**/*.testql.toon.yaml;
}

env_vars {
  keys: GITHUB_ORG, GITHUB_PAT, GITHUB_USER, OPENROUTER_API_KEY, LLM_MODEL, LLM_PROVIDER, COLLAPSE_CODE_BLOCKS, DEFAULT_LOCALE, ENABLE_ARTIFACTS, ENABLE_CODE_EXECUTION, ENABLE_LATEX, ENABLE_MERMAID, OPENAI_API_KEY, OPENWEBUI_URL, OUTPUT_PATH, PORT_DASHBOARD, PORT_DOCS, PORT_GATEWAY, PORT_GH2MCP, PORT_GIT_PROXY, PORT_OPENWEBUI, PORT_WEBUI, REDIS_URL, REPOS_PATH, GH2MCP_SYNC_ON_START, GH2MCP_SYNC_INTERVAL, GIT_PROXY_URL, WEBUI_API_KEY, OPENWEBUI_AUTH;
}

deploy {
  target: docker-compose;
  compose_file: docker-compose.yml;
  ansible: true;
}

environment[name="local"] {
  runtime: docker-compose;
  env_file: .env;
  template_file: .env.example;
  python_version: >=3.10;
  vars: COLLAPSE_CODE_BLOCKS, DEFAULT_LOCALE, ENABLE_ARTIFACTS, ENABLE_CODE_EXECUTION, ENABLE_LATEX, ENABLE_MERMAID, GH2MCP_SYNC_INTERVAL, GH2MCP_SYNC_ON_START, GITHUB_ORG, GITHUB_PAT, GITHUB_USER, GIT_PROXY_URL, LLM_MODEL, LLM_PROVIDER, OPENAI_API_KEY, OPENROUTER_API_KEY, OPENWEBUI_AUTH, OPENWEBUI_URL, OUTPUT_PATH, PORT_DASHBOARD, PORT_DOCS, PORT_GATEWAY, PORT_GH2MCP, PORT_GIT_PROXY, PORT_OPENWEBUI, PORT_WEBUI, REDIS_URL, REPOS_PATH, WEBUI_API_KEY;
  runtime_llm: OPENROUTER_API_KEY;
}

environment[name="prod"] {
  runtime: docker-compose;
}
```

## Interfaces

### CLI Entry Points

- `semcod-mcp`

## Workflows

## Configuration

```yaml
project:
  name: semcod-mcp
  version: 0.1.4
  env: local
```

## Dependencies

### Runtime

```text markpact:deps python
click>=8.0
httpx>=0.26.0
pyyaml>=6.0
rich>=13.0
```

### Development

```text markpact:deps python scope=dev
pytest>=8.0
goal>=2.1.0
costs>=0.1.20
pfix>=0.1.60
```

## Deployment

```bash markpact:run
pip install semcod-mcp

# development install
pip install -e .[dev]
```

### Docker Compose (`docker-compose.yml`)

- **redis** image=`redis:7-alpine`
- **mcp-git-proxy** image=`{'context': '.', 'dockerfile': 'mcp-git-proxy/Dockerfile'}` ports: `${PORT_GIT_PROXY:-8081}:8080`
- **gh2mcp-agent** image=`{'context': '.', 'dockerfile': 'gh2mcp/Dockerfile'}` ports: `${PORT_GH2MCP:-8079}:8079`
- **mcp-skills** image=`{'context': '..', 'dockerfile': 'mcp/mcp-skills/Dockerfile', 'cache_from': ['type=local,src=/tmp/docker-cache/mcp-skills'], 'cache_to': ['type=local,dest=/tmp/docker-cache/mcp-skills,mode=max']}`
- **llm-agent** image=`./llm-agent`
- **mcp-gateway** image=`{'context': '.', 'dockerfile': 'mcp-gateway/Dockerfile'}` ports: `${PORT_GATEWAY:-9000}:9000`
- **mcp-gateway-worker** image=`{'context': '.', 'dockerfile': 'mcp-gateway/Dockerfile'}`
- **mcp-webui** image=`{'context': '.', 'dockerfile': 'mcp-webui/Dockerfile'}` ports: `${PORT_WEBUI:-8092}:8090`
- **mcp-docs** image=`{'context': '.', 'dockerfile': 'mcp-docs/Dockerfile'}` ports: `${PORT_DOCS:-8093}:8090`
- **openwebui** image=`${OPENWEBUI_IMAGE:-ghcr.io/open-webui/open-webui:main}` ports: `${PORT_OPENWEBUI:-3000}:8080`
- **dashboard** image=`./dashboard` ports: `${PORT_DASHBOARD:-8085}:8080`

## Environment Variables (`.env.example`)

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openrouter-lite` | LLM Provider: openrouter-lite, mock, openai, ollama |
| `OPENROUTER_API_KEY` | `*(not set)*` |  |
| `LLM_MODEL` | `openrouter/x-ai/grok-code-fast-1` | LLM_MODEL=openrouter/qwen/qwen3-coder-next |
| `OPENAI_API_KEY` | `sk-...` | OpenAI API Key (wymagane dla LLM_PROVIDER=openai) |
| `GITHUB_PAT` | `ghp_...` | Uzyskaj token przez: make setup-github lub env2mcp github login |
| `GITHUB_USER` | `your-username` |  |
| `GH2MCP_SYNC_ON_START` | `true` | gh2mcp Agent (docker) - synchronizacja tokenu z gh CLI do .env przy starcie |
| `GH2MCP_SYNC_INTERVAL` | `0` |  |
| `GIT_PROXY_URL` | `http://mcp-git-proxy:8080` | MCP Git Proxy |
| `WEBUI_API_KEY` | `sk-mcp-default-dev-key` | MCP Gateway (OpenAI-compatible) - klucz tenanta z mcp-gateway/tenants/*.yaml |
| `OPENWEBUI_AUTH` | `False` | OpenWebUI (zostaw False dla lokalnego dev, True dla produkcji) |
| `REPOS_PATH` | `./repos` | Ścieżki repozytoriów |
| `OUTPUT_PATH` | `./output` |  |
| `PORT_OPENWEBUI` | `3000` | Porty publiczne usług (host:kontener) |
| `PORT_GH2MCP` | `8079` |  |
| `PORT_GIT_PROXY` | `8081` |  |
| `PORT_DASHBOARD` | `8085` |  |
| `PORT_WEBUI` | `8092` |  |
| `PORT_DOCS` | `8093` |  |
| `PORT_GATEWAY` | `9000` |  |
| `REDIS_URL` | `redis://redis:6379/0` | Redis |
| `OPENWEBUI_URL` | `http://localhost:3000/` | URL OpenWebUI (używany przez mcp-docs do linku w UI) |
| `ENABLE_MERMAID` | `true` | OpenWebUI - renderowanie artefaktów i Markdown |
| `ENABLE_LATEX` | `true` |  |
| `ENABLE_ARTIFACTS` | `true` |  |
| `COLLAPSE_CODE_BLOCKS` | `false` |  |
| `ENABLE_CODE_EXECUTION` | `false` |  |
| `DEFAULT_LOCALE` | `pl-PL` |  |

## Release Management (`goal.yaml`)

- **versioning**: `semver`
- **commits**: `conventional` scope=`mcp`
- **changelog**: `keep-a-changelog`
- **build strategies**: `python`, `nodejs`, `rust`
- **version files**: `VERSION`, `pyproject.toml:version`, `semcod_mcp/__init__.py:__version__`

## Makefile Targets

- `SHELL`
- `PORTS`
- `COMPOSE`
- `COMPOSE_PROD`
- `PROFILES`
- `help`
- `kill-ports`
- `start`
- `stop`
- `restart`
- `up`
- `down`
- `logs`
- `ps`
- `build`
- `rebuild`
- `smoke`
- `ansible-e2e`
- `ansible-gh2mcp`
- `ansible-github-qa`
- `reload-gateway`
- `ansible-tools-e2e`
- `reload-skills`
- `ansible-github-test`
- `gh2mcp-status`
- `pytest`
- `test`
- `prod-up`
- `prod-down`
- `clean`
- `install-env2mcp`
- `setup-github`
- `generate-demo-repos`
- `generate-demo-repos-github`

## Code Analysis

### `project/map.toon.yaml`

```toon markpact:analysis path=project/map.toon.yaml
# mcp | 85f 15249L | python:76,shell:7,less:2 | 2026-06-18
# stats: 359 func | 63 cls | 85 mod | CC̄=4.9 | critical:43 | cycles:0
# alerts[5]: CC run_chat_workflow=43; CC render_tool_text=40; CC run_tool_against_repo=37; CC handle_chat_completions=31; CC render_system_text=27
# hotspots[5]: run_tool_against_repo fan=30; handle_chat_completions fan=28; run_init fan=23; run_chat_workflow fan=21; dispatch_skill fan=21
# evolution: baseline
# Keys: M=modules, D=details, i=imports, e=exports, c=classes, f=functions, m=methods
M[85]:
  app.doql.less,262
  dashboard/server.py,190
  env2mcp/env2mcp/__init__.py,14
  env2mcp/env2mcp/cli.py,253
  env2mcp/env2mcp/config.py,159
  env2mcp/env2mcp/github_cli.py,331
  env2mcp/tests/test_env2mcp.py,70
  gh2mcp/gh2mcp/__init__.py,5
  gh2mcp/gh2mcp/cli.py,69
  gh2mcp/gh2mcp/server.py,111
  gh2mcp/gh2mcp/sync.py,431
  gh2mcp/tests/test_gh2mcp.py,278
  git2mcp/__init__.py,4
  git2mcp/app.doql.less,35
  git2mcp/client.py,4
  git2mcp/examples/01_sync_and_commit.py,63
  git2mcp/examples/02_fragment_sync_to_skills.py,69
  git2mcp/examples/03_agent_git2mcp.py,56
  git2mcp/examples/04_dry_run_vs_execute.py,116
  git2mcp/examples/05_local_iterate.py,127
  git2mcp/git2mcp/__init__.py,4
  git2mcp/git2mcp/client.py,105
  git2mcp/git2mcp/proxy.py,438
  git2mcp/project.sh,47
  git2mcp/proxy.py,4
  git2mcp/tests/test_git2mcp.py,327
  llm-agent/agent.py,376
  llm-agent/agent_git2mcp.py,362
  llm-agent/agent_standalone.py,541
  llm-agent/tests/test_llm_agent.py,12
  mcp-docs/server.py,274
  mcp-docs/tests/test_mcp_docs.py,12
  mcp-gateway/conftest.py,5
  mcp-gateway/gateway_chat.py,564
  mcp-gateway/gateway_config.py,57
  mcp-gateway/gateway_dispatch.py,249
  mcp-gateway/gateway_gh2mcp.py,408
  mcp-gateway/gateway_github.py,433
  mcp-gateway/gateway_jobs.py,176
  mcp-gateway/gateway_models.py,35
  mcp-gateway/gateway_prompt.py,272
  mcp-gateway/gateway_render.py,503
  mcp-gateway/gateway_skills.py,264
  mcp-gateway/gateway_tenants.py,142
  mcp-gateway/server.py,229
  mcp-gateway/test_gateway_token_command.py,690
  mcp-gateway/test_github_qa.py,96
  mcp-gateway/test_tool_intent.py,189
  mcp-gateway/tests/test_mcp_gateway.py,12
  mcp-gateway/worker.py,19
  mcp-git-proxy/server.py,444
  mcp-git-proxy/tests/test_mcp_git_proxy.py,12
  mcp-skills/code_analysis.py,283
  mcp-skills/conftest.py,5
  mcp-skills/http_models.py,61
  mcp-skills/mcp_parse.py,19
  mcp-skills/redsl_runner.py,72
  mcp-skills/server.py,692
  mcp-skills/test_code_analysis.py,75
  mcp-skills/test_tools_run.py,156
  mcp-skills/tests/test_mcp_skills.py,12
  mcp-skills/tool_run.py,389
  mcp-skills/tools_registry.py,151
  mcp-webui/server.py,622
  mcp-webui/tests/test_mcp_webui.py,12
  project.sh,47
  scripts/deploy.sh,136
  scripts/generate_demo_repos.sh,397
  scripts/refactor-last-repo.sh,313
  scripts/test.sh,405
  semcod_mcp/__init__.py,4
  semcod_mcp/analyze.py,106
  semcod_mcp/cli.py,133
  semcod_mcp/deinit_cmd.py,138
  semcod_mcp/doctor.py,117
  semcod_mcp/init_cmd.py,177
  semcod_mcp/merge.py,217
  semcod_mcp/paths.py,71
  semcod_mcp/templates.py,163
  semcod_mcp/validate.py,102
  tests/__init__.py,2
  tests/test_deinit.py,74
  tests/test_init.py,71
  tests/test_merge.py,77
  tree.sh,2
D:
  dashboard/server.py:
    e: main,DashboardHandler,TCPServer
    DashboardHandler: end_headers(0),do_GET(0),serve_file(1),send_json(1),get_content_type(1),get_status(0),get_analyses(0),get_analysis(1),get_repos(0)  # Custom HTTP handler for dashboard
    TCPServer:
    main()
  env2mcp/env2mcp/__init__.py:
  env2mcp/env2mcp/cli.py:
    e: cmd_github_login,cmd_github_status,cmd_github_logout,cmd_github_repos,cmd_env_show,cmd_env_set,cmd_env_get,main
    cmd_github_login(args)
    cmd_github_status(args)
    cmd_github_logout(args)
    cmd_github_repos(args)
    cmd_env_show(args)
    cmd_env_set(args)
    cmd_env_get(args)
    main(argv)
  env2mcp/env2mcp/config.py:
    e: load_env,save_env,EnvConfig
    EnvConfig: __init__(1),_load(0),get(2),set(2),remove(1),_format_value(2),save(1),__contains__(1),__getitem__(1),__setitem__(2),items(0)  # Manages .env file configuration.
    load_env(env_path)
    save_env(config;create_backup)
  env2mcp/env2mcp/github_cli.py:
    e: get_github_token,configure_github,GitHubCLI
    GitHubCLI: __init__(0),is_available(0),get_auth_status(0),get_token(0),get_user(0),login(2),logout(1),list_repos(2),clone_url(1)  # Interface to GitHub CLI (gh) tool.
    get_github_token(env_path)
    configure_github(env_path;interactive)
  env2mcp/tests/test_env2mcp.py:
    e: test_import,test_format_value_token_no_quotes,test_format_value_no_double_quote_wrap,test_format_value_spaces_quoted,test_format_value_empty,test_format_value_numeric,test_save_load_roundtrip
    test_import()
    test_format_value_token_no_quotes()
    test_format_value_no_double_quote_wrap()
    test_format_value_spaces_quoted()
    test_format_value_empty()
    test_format_value_numeric()
    test_save_load_roundtrip(tmp_path)
  gh2mcp/gh2mcp/__init__.py:
  gh2mcp/gh2mcp/cli.py:
    e: _cmd_status,_cmd_sync,_cmd_agent,build_parser,main
    _cmd_status(args)
    _cmd_sync(args)
    _cmd_agent(args)
    build_parser()
    main(argv)
  gh2mcp/gh2mcp/server.py:
    e: _periodic_sync,on_startup,on_shutdown,health,status,sync_token,set_org,list_orgs,last_pushed_repo,recent_repos,SyncTokenRequest,SetOrgRequest,ListOrgsRequest,LastPushedRepoRequest,RecentReposRequest
    SyncTokenRequest:
    SetOrgRequest:
    ListOrgsRequest:
    LastPushedRepoRequest:
    RecentReposRequest:
    _periodic_sync()
    on_startup()
    on_shutdown()
    health()
    status(include_token)
    sync_token(payload)
    set_org(payload)
    list_orgs(payload)
    last_pushed_repo(payload)
    recent_repos(payload)
  gh2mcp/gh2mcp/sync.py:
    e: GitHubTokenSyncService
    GitHubTokenSyncService: __init__(1),get_status(1),set_org(1),list_orgs_and_repos(1),get_last_pushed_repo(2),get_recent_repos(3),sync_token(2)
  gh2mcp/tests/test_gh2mcp.py:
    e: test_sync_token_saves_from_env_and_reads_back,test_sync_token_reads_from_env_file_when_env_missing,test_sync_token_force_gh_cli_does_not_fallback_to_env_or_file,test_set_org_defaults_to_gh_username,test_list_orgs_and_repos,test_get_last_pushed_repo_selects_latest,test_get_last_pushed_repo_success,test_get_last_pushed_repo_no_repos,test_get_recent_repos_sorts_across_user_and_orgs,test_get_recent_repos_owner_only,_GhUnavailable,_GhUserRepos,_ProcResult,_GhAvailableUser,_GhNoToken
    _GhUnavailable: is_available(0),get_token(0),get_user(0)
    _GhUserRepos: is_available(0),get_token(0),get_user(0),list_repos(2)
    _ProcResult: __init__(3)
    _GhAvailableUser: is_available(0),get_token(0),get_user(0)
    _GhNoToken: is_available(0),get_token(0),get_user(0)
    test_sync_token_saves_from_env_and_reads_back(monkeypatch;tmp_path)
    test_sync_token_reads_from_env_file_when_env_missing(monkeypatch;tmp_path)
    test_sync_token_force_gh_cli_does_not_fallback_to_env_or_file(monkeypatch;tmp_path)
    test_set_org_defaults_to_gh_username(monkeypatch;tmp_path)
    test_list_orgs_and_repos(monkeypatch;tmp_path)
    test_get_last_pushed_repo_selects_latest(monkeypatch;tmp_path)
    test_get_last_pushed_repo_success(monkeypatch;tmp_path)
    test_get_last_pushed_repo_no_repos(monkeypatch;tmp_path)
    test_get_recent_repos_sorts_across_user_and_orgs(monkeypatch;tmp_path)
    test_get_recent_repos_owner_only(monkeypatch;tmp_path)
  git2mcp/__init__.py:
  git2mcp/client.py:
  git2mcp/examples/01_sync_and_commit.py:
    e: main
    main()
  git2mcp/examples/02_fragment_sync_to_skills.py:
    e: main
    main()
  git2mcp/examples/03_agent_git2mcp.py:
    e: main
    main()
  git2mcp/examples/04_dry_run_vs_execute.py:
    e: run,main
    run(args)
    main()
  git2mcp/examples/05_local_iterate.py:
    e: main
    main()
  git2mcp/git2mcp/__init__.py:
  git2mcp/git2mcp/client.py:
    e: Git2MCPClient
    Git2MCPClient: __init__(2),_request(3),health(0),list_repos(0),sync_repo(4),export_package(2),commit_changes(5),run_tests(2),push(3),reset(3),worktree_write(4),worktree_read(3),worktree_diff(2),patch_apply(3),stage(2),stash_save(2),stash_pop(1),branch_draft(3),checkpoint_create(2),checkpoint_restore(2)
  git2mcp/git2mcp/proxy.py:
    e: GitProxyManager
    GitProxyManager: __init__(2),_repo_path(1),_ensure_parent(1),_allow_local_repo_url(1),list_repos(0),sync_repo(4),export_package(2),export_fragments(3),commit_changes(5),push(3),worktree_write(4),worktree_read(3),worktree_diff(2),patch_apply(3),stage(2),stash_save(2),stash_pop(1),branch_draft(3),checkpoint_create(2),checkpoint_restore(2),reset(3)
  git2mcp/proxy.py:
  git2mcp/tests/test_git2mcp.py:
    e: _load_proxy_app,_create_sample_repo_source,test_git_proxy_e2e_sync_export_commit_and_tests,test_git_proxy_local_operations,test_git_proxy_e2e_commit_and_reset,test_git_proxy_e2e_push_to_bare_remote
    _load_proxy_app(repo_root;cache_root)
    _create_sample_repo_source(source)
    test_git_proxy_e2e_sync_export_commit_and_tests(tmp_path)
    test_git_proxy_local_operations(tmp_path)
    test_git_proxy_e2e_commit_and_reset(tmp_path)
    test_git_proxy_e2e_push_to_bare_remote(tmp_path)
  llm-agent/agent.py:
    e: main,AnalysisResult,RefactoringAgent
    AnalysisResult:  # Wynik analizy repozytorium
    RefactoringAgent: __init__(0),connect_skills(2),connect_git_mcp(2),analyze_repository(2),generate_refactoring_plan(1),_build_refactoring_prompt(1),_call_openai(1),_call_ollama(1),_mock_llm_response(1),_mock_llm_response_from_prompt(1),execute_refactoring_workflow(3),close(0)  # Autonomiczny Agent Refaktoryzacji
    main()
  llm-agent/agent_git2mcp.py:
    e: main,AnalysisResult,CachedCodeAnalyzer,Git2MCPRefactoringAgent
    AnalysisResult:
    CachedCodeAnalyzer: __init__(1),_repo_path(1),import_package(2),compute_metrics(2),detect_patterns(1),recommend_refactoring(2)
    Git2MCPRefactoringAgent: __init__(1),sync_and_cache_repo(4),analyze(1),generate_plan(1),build_commit_changes(1),execute(7)
    main()
  llm-agent/agent_standalone.py:
    e: main,AnalysisResult,LocalCodeAnalyzer,RefactoringAgent
    AnalysisResult:  # Wynik analizy repozytorium
    LocalCodeAnalyzer: __init__(1),analyze_code_structure(2),compute_metrics_for_repo(2),detect_code_patterns(2),recommend_refactoring(2)  # Lokalny analizator kodu - implementacja MCP Skills lokalnie
    RefactoringAgent: __init__(1),analyze_repository(2),generate_refactoring_plan(1),_build_refactoring_prompt(1),_call_openai_sync(1),_mock_llm_response(1),_mock_llm_response_from_prompt(1),execute_refactoring_workflow(3)  # Autonomiczny Agent Refaktoryzacji - Standalone
    main()
  llm-agent/tests/test_llm_agent.py:
    e: test_placeholder,test_import
    test_placeholder()
    test_import()
  mcp-docs/server.py:
    e: _markdown_to_html,_page,_safe_doc_path,health,list_docs,index,render_doc
    _markdown_to_html(md_text)
    _page(title;body)
    _safe_doc_path(rel_path)
    health()
    list_docs()
    index()
    render_doc(doc_path)
  mcp-docs/tests/test_mcp_docs.py:
    e: test_placeholder,test_import
    test_placeholder()
    test_import()
  mcp-gateway/conftest.py:
  mcp-gateway/gateway_chat.py:
    e: run_chat_workflow,handle_chat_completions
    run_chat_workflow(tenant)
    handle_chat_completions(req;tenant)
  mcp-gateway/gateway_config.py:
  mcp-gateway/gateway_dispatch.py:
    e: dispatch_skill
    dispatch_skill(skill;tenant;repo_id;repo_url;github_token;source_path;branch;user_request;execute_commit;push_after_tests;create_draft_branch;draft_name;open_pull_request;pr_title;pr_body;pr_base;test_command;push_remote;job_id)
  mcp-gateway/gateway_gh2mcp.py:
    e: _gateway_hooks,is_github_configured,get_default_github_repo,sync_github_token_via_gh2mcp,set_default_org_via_gh2mcp,list_recent_repos_via_gh2mcp,list_orgs_via_gh2mcp,gh2mcp_status_via_gh2mcp,last_pushed_repo_via_gh2mcp,is_github_auth_error,github_auth_recovery_message,resolve_repo_id_template,save_github_token_via_env2mcp,repo_owner,run_github_qa
    _gateway_hooks()
    is_github_configured()
    get_default_github_repo()
    sync_github_token_via_gh2mcp()
    set_default_org_via_gh2mcp(org)
    list_recent_repos_via_gh2mcp(limit;owner;include_orgs)
    list_orgs_via_gh2mcp(repos_limit)
    gh2mcp_status_via_gh2mcp()
    last_pushed_repo_via_gh2mcp(owner;limit)
    is_github_auth_error(error_text)
    github_auth_recovery_message(original_error)
    resolve_repo_id_template(repo_value)
    save_github_token_via_env2mcp(user_msg;prompt_ctx)
    repo_owner(repo_id)
    run_github_qa(user_request;repo_id;repo_url)
  mcp-gateway/gateway_github.py:
    e: normalize_repo_url,github_repo_from_url,is_github_token_save_command,is_github_token_sync_command,extract_org_from_text,is_org_set_command,is_org_list_command,is_repo_list_command,extract_repo_list_limit,load_env_file_values,runtime_github_token,save_github_token,inject_github_token,redact_repo_url,default_draft_name,default_pr_title,default_pr_body,create_github_pr
    normalize_repo_url(repo_url)
    github_repo_from_url(repo_url)
    is_github_token_save_command(user_msg;prompt_ctx)
    is_github_token_sync_command(user_msg;prompt_ctx)
    extract_org_from_text(user_msg;prompt_ctx)
    is_org_set_command(user_msg)
    is_org_list_command(user_msg)
    is_repo_list_command(user_msg)
    extract_repo_list_limit(user_msg;default;max_limit)
    load_env_file_values(env_path)
    runtime_github_token()
    save_github_token(token)
    inject_github_token(repo_url)
    redact_repo_url(repo_url)
    default_draft_name(repo_id)
    default_pr_title(repo_id;user_request)
    default_pr_body(repo_id;user_request;base_branch)
    create_github_pr(client;owner;repo;head_branch;base_branch;title;body;draft)
  mcp-gateway/gateway_jobs.py:
    e: job_storage_key,get_state_redis_client,get_rq_redis_client,get_queue,save_job,load_job,update_job,queue_workflow_job,execute_dispatch_job
    job_storage_key(job_id)
    get_state_redis_client()
    get_rq_redis_client()
    get_queue()
    save_job(job_id;payload)
    load_job(job_id)
    update_job(job_id)
    queue_workflow_job(job_id;payload)
    execute_dispatch_job(job_id;payload)
  mcp-gateway/gateway_models.py:
    e: ChatMessage,ChatCompletionRequest
    ChatMessage:
    ChatCompletionRequest:
  mcp-gateway/gateway_prompt.py:
    e: message_content_to_text,parse_prompt_context,parse_bool,normalize_command_text,extract_github_token_from_text,extract_repo_template_expression,is_last_pushed_repo_template,extract_owner_from_repo_template,strip_url_suffix,parse_tool_intent
    message_content_to_text(content)
    parse_prompt_context(user_msg)
    parse_bool(value;default)
    normalize_command_text(text)
    extract_github_token_from_text(user_msg)
    extract_repo_template_expression(repo_value)
    is_last_pushed_repo_template(expression)
    extract_owner_from_repo_template(expression)
    strip_url_suffix(url)
    parse_tool_intent(user_msg;prompt_ctx)
  mcp-gateway/gateway_render.py:
    e: summary_text,render_repo_selection_text,render_system_text,render_analyze_text,render_queued_text,render_refactor_text,file_fence_lang,is_markdown_path,render_tool_text,render_github_qa_text,render_chat_content,build_commit_changes,render_tools_list_text
    summary_text(analysis;user_request)
    render_repo_selection_text(repo_selection)
    render_system_text(result)
    render_analyze_text(result)
    render_queued_text(result)
    render_refactor_text(result)
    file_fence_lang(path)
    is_markdown_path(path)
    render_tool_text(result)
    render_github_qa_text(result)
    render_chat_content(result)
    build_commit_changes(plan_payload;summary_md)
    render_tools_list_text(result)
  mcp-gateway/gateway_skills.py:
    e: expect_json,is_tools_list_command,fetch_tools_list,run_skills_tool,ask_openrouter_github_qa,enrich_analysis_with_file_metrics,run_skills_analysis
    expect_json(response;action)
    is_tools_list_command(msg)
    fetch_tools_list()
    run_skills_tool(tool;repo_id;repo_url;subcommand;args;timeout)
    ask_openrouter_github_qa(user_request;github_context)
    enrich_analysis_with_file_metrics(client;repo_id;analysis)
    run_skills_analysis(client;repo_id;execute;user_request;max_actions)
  mcp-gateway/gateway_tenants.py:
    e: load_tenants,get_redis_client,track_repo_usage,get_last_used_repo,get_most_used_repo,get_preferred_repo,find_tenant_by_key,authenticate,audit
    load_tenants()
    get_redis_client()
    track_repo_usage(tenant_id;repo_id;platform)
    get_last_used_repo(tenant_id)
    get_most_used_repo(tenant_id)
    get_preferred_repo(tenant_id)
    find_tenant_by_key(api_key)
    authenticate(authorization)
    audit(event)
  mcp-gateway/server.py:
    e: health,list_models,chat_completions,get_job,stream_job,audit_tail,_ask_openrouter_github_qa
    health()
    list_models(_)
    chat_completions(req;tenant)
    get_job(job_id;_)
    stream_job(job_id;_)
    audit_tail(limit;_)
    _ask_openrouter_github_qa(user_request;github_context)
  mcp-gateway/test_gateway_token_command.py:
    e: _extract_sse_data,_authorized_client,test_is_github_token_sync_command,test_is_github_token_sync_command_false_if_explicit_token_value,test_is_github_token_save_command,test_extract_github_token_from_text,test_is_org_set_command,test_is_org_list_command,test_is_repo_list_command,test_extract_repo_list_limit_defaults_and_bounds,test_extract_org_from_text,test_sync_github_token_via_gh2mcp_success_note,test_sync_github_token_via_gh2mcp_failure_note,test_extract_repo_template_expression,test_is_last_pushed_repo_template,test_resolve_repo_id_template_last_pushed,test_resolve_repo_id_template_last_pushed_repo_url_in_meta,test_resolve_repo_id_template_unsupported,test_is_github_auth_error,test_github_auth_recovery_message_has_three_options,test_resolve_repo_id_template_auto_recovers_on_auth_error,test_resolve_repo_id_template_auth_error_with_failed_recovery_raises_helpful_message,test_resolve_repo_id_template_non_auth_error_does_not_trigger_recovery,_compute_effective_repo_url,test_effective_repo_url_explicit_repo_url_wins,test_effective_repo_url_falls_back_to_resolved,test_effective_repo_url_both_none,test_effective_repo_url_no_template_resolution,test_render_chat_content_analyze_human_readable,test_render_chat_content_refactor_human_readable,test_render_chat_content_system_human_readable,test_render_chat_content_system_recent_repos_human_readable,test_render_chat_content_queued_human_readable,test_is_repo_list_command,test_extract_repo_list_limit,test_summary_text_redsl_engine,test_summary_text_mcp_skills_engine,test_stream_job_not_found_returns_404,test_stream_job_emits_status_updates_and_done,test_stream_job_emits_failure_with_error,_FakeResponse,_FakeAsyncClient
    _FakeResponse: __init__(2),json(0)
    _FakeAsyncClient: __init__(0),__aenter__(0),__aexit__(3),post(2),get(1)
    _extract_sse_data(raw_text)
    _authorized_client()
    test_is_github_token_sync_command(msg;expected)
    test_is_github_token_sync_command_false_if_explicit_token_value()
    test_is_github_token_save_command(msg;expected)
    test_extract_github_token_from_text()
    test_is_org_set_command(msg;expected)
    test_is_org_list_command(msg;expected)
    test_is_repo_list_command(msg;expected)
    test_extract_repo_list_limit_defaults_and_bounds()
    test_extract_org_from_text()
    test_sync_github_token_via_gh2mcp_success_note(monkeypatch)
    test_sync_github_token_via_gh2mcp_failure_note(monkeypatch)
    test_extract_repo_template_expression()
    test_is_last_pushed_repo_template(expression;expected)
    test_resolve_repo_id_template_last_pushed(monkeypatch)
    test_resolve_repo_id_template_last_pushed_repo_url_in_meta(monkeypatch)
    test_resolve_repo_id_template_unsupported()
    test_is_github_auth_error(error;expected)
    test_github_auth_recovery_message_has_three_options()
    test_resolve_repo_id_template_auto_recovers_on_auth_error(monkeypatch)
    test_resolve_repo_id_template_auth_error_with_failed_recovery_raises_helpful_message(monkeypatch)
    test_resolve_repo_id_template_non_auth_error_does_not_trigger_recovery(monkeypatch)
    _compute_effective_repo_url(repo_url;meta)
    test_effective_repo_url_explicit_repo_url_wins(monkeypatch)
    test_effective_repo_url_falls_back_to_resolved(monkeypatch)
    test_effective_repo_url_both_none()
    test_effective_repo_url_no_template_resolution()
    test_render_chat_content_analyze_human_readable()
    test_render_chat_content_refactor_human_readable()
    test_render_chat_content_system_human_readable()
    test_render_chat_content_system_recent_repos_human_readable()
    test_render_chat_content_queued_human_readable()
    test_is_repo_list_command(msg;expected)
    test_extract_repo_list_limit(msg;expected)
    test_summary_text_redsl_engine()
    test_summary_text_mcp_skills_engine()
    test_stream_job_not_found_returns_404(monkeypatch)
    test_stream_job_emits_status_updates_and_done(monkeypatch)
    test_stream_job_emits_failure_with_error(monkeypatch)
  mcp-gateway/test_github_qa.py:
    e: _authorized_client,test_render_chat_content_github_qa,test_run_github_qa_missing_openrouter_key,test_chat_completions_github_qa_model,test_models_include_github_qa
    _authorized_client()
    test_render_chat_content_github_qa()
    test_run_github_qa_missing_openrouter_key(monkeypatch)
    test_chat_completions_github_qa_model(monkeypatch)
    test_models_include_github_qa()
  mcp-gateway/test_tool_intent.py:
    e: test_parse_tool_intent_recognizes_tool_and_repo,test_parse_tool_intent_returns_none_for_non_tool_prompts,test_parse_tool_intent_uses_prompt_ctx_repo_id,test_render_tool_text_includes_artifacts_and_status,test_render_tool_text_handles_failure,test_render_chat_content_dispatches_tool_skill,test_force_tool_skill_with_no_intent_returns_helpful_error
    test_parse_tool_intent_recognizes_tool_and_repo(msg;expected_tool;expected_repo_url;expected_repo_id)
    test_parse_tool_intent_returns_none_for_non_tool_prompts(msg)
    test_parse_tool_intent_uses_prompt_ctx_repo_id()
    test_render_tool_text_includes_artifacts_and_status()
    test_render_tool_text_handles_failure()
    test_render_chat_content_dispatches_tool_skill()
    test_force_tool_skill_with_no_intent_returns_helpful_error()
  mcp-gateway/tests/test_mcp_gateway.py:
    e: test_placeholder,test_import
    test_placeholder()
    test_import()
  mcp-gateway/worker.py:
    e: main
    main()
  mcp-git-proxy/server.py:
    e: health,list_repos,sync_repo,export_fragments,export_package,import_package,commit,push,reset,worktree_write,worktree_read,worktree_diff,patch_apply,stage,stash_save,stash_pop,branch_draft,checkpoint_create,checkpoint_restore,run_tests,github_create_repo,sync_pull,SyncRepoRequest,ExportPackageRequest,ExportFragmentsRequest,CommitRequest,PushRequest,RunTestsRequest,ResetRequest,ImportPackageRequest,WorktreeWriteRequest,WorktreeReadRequest,WorktreeDiffRequest,PatchApplyRequest,StageRequest,StashSaveRequest,BranchDraftRequest,CheckpointCreateRequest,CheckpointRestoreRequest,SyncPullRequest,CreateGithubRepoRequest
    SyncRepoRequest:
    ExportPackageRequest:
    ExportFragmentsRequest:
    CommitRequest:
    PushRequest:
    RunTestsRequest:
    ResetRequest:
    ImportPackageRequest:
    WorktreeWriteRequest:
    WorktreeReadRequest:
    WorktreeDiffRequest:
    PatchApplyRequest:
    StageRequest:
    StashSaveRequest:
    BranchDraftRequest:
    CheckpointCreateRequest:
    CheckpointRestoreRequest:
    SyncPullRequest:
    CreateGithubRepoRequest:
    health()
    list_repos()
    sync_repo(request)
    export_fragments(request)
    export_package(request)
    import_package(request)
    commit(repo_id;request)
    push(repo_id;request)
    reset(repo_id;request)
    worktree_write(repo_id;request)
    worktree_read(repo_id;request)
    worktree_diff(repo_id;request)
    patch_apply(repo_id;request)
    stage(repo_id;request)
    stash_save(repo_id;request)
    stash_pop(repo_id)
    branch_draft(repo_id;request)
    checkpoint_create(repo_id;request)
    checkpoint_restore(repo_id;request)
    run_tests(repo_id;request)
    github_create_repo(request)
    sync_pull(repo_id;request)
  mcp-git-proxy/tests/test_mcp_git_proxy.py:
    e: test_placeholder,test_import
    test_placeholder()
    test_import()
  mcp-skills/code_analysis.py:
    e: _should_skip_path,compute_repo_file_metrics,detect_repo_patterns,build_maintainability_recommendations,merge_recommendations,recommendations_payload
    _should_skip_path(file_path)
    compute_repo_file_metrics(repo_path;extensions)
    detect_repo_patterns(repo_path)
    build_maintainability_recommendations(metrics)
    merge_recommendations(primary;supplemental)
    recommendations_payload(repo_id;metrics;recommendations)
  mcp-skills/conftest.py:
  mcp-skills/http_models.py:
    e: SyncRepoRequest,AnalyzeStructureRequest,RepoMetricsRequest,PatternDetectionRequest,RecommendRefactoringRequest,RedslRefactorRequest,ToolRunRequest
    SyncRepoRequest:
    AnalyzeStructureRequest:
    RepoMetricsRequest:
    PatternDetectionRequest:
    RecommendRefactoringRequest:
    RedslRefactorRequest:
    ToolRunRequest:  # Generic request to run a semcod CLI tool against a repo.
  mcp-skills/mcp_parse.py:
    e: parse_tool_result
    parse_tool_result(result)
  mcp-skills/redsl_runner.py:
    e: run_redsl_refactor
    run_redsl_refactor(project_path;max_actions;dry_run)
  mcp-skills/server.py:
    e: health,sync_repo,analyze_code_structure,compute_metrics,detect_patterns,recommend_refactoring,redsl_refactor,list_tools_endpoint,run_tool_endpoint,main,_run_tool_against_repo,MCPSkillsServer
    MCPSkillsServer: __init__(1),_sync_from_git_proxy(2),_setup_handlers(0),_handle_list_tools(0),_handle_call_tool(2),_analyze_code_structure(1),_compute_metrics_for_repo(1),_detect_code_patterns(1),_sync_repo_tool(1),_recommend_refactoring(1),run(0)  # Serwer MCP Skills z narzędziami do analizy kodu
    health()
    sync_repo(request)
    analyze_code_structure(request)
    compute_metrics(request)
    detect_patterns(request)
    recommend_refactoring(request)
    redsl_refactor(request)
    list_tools_endpoint()
    run_tool_endpoint(request)
    main()
    _run_tool_against_repo(request)
  mcp-skills/test_code_analysis.py:
    e: test_compute_repo_file_metrics_returns_largest_files,test_build_maintainability_recommendations_targets_large_files,test_merge_recommendations_prefers_concrete_targets
    test_compute_repo_file_metrics_returns_largest_files(tmp_path)
    test_build_maintainability_recommendations_targets_large_files(tmp_path)
    test_merge_recommendations_prefers_concrete_targets()
  mcp-skills/test_tools_run.py:
    e: server_module,test_derive_repo_id_from_url,test_supported_tools_registry_has_expected_entries,test_collect_output_files_reads_small_text,test_run_tool_against_repo_unsupported,test_run_tool_against_repo_happy_path,test_run_tool_against_repo_install_fails
    server_module(tmp_path_factory)
    test_derive_repo_id_from_url(server_module)
    test_supported_tools_registry_has_expected_entries(server_module)
    test_collect_output_files_reads_small_text(server_module;tmp_path)
    test_run_tool_against_repo_unsupported(server_module)
    test_run_tool_against_repo_happy_path(server_module;tmp_path;monkeypatch)
    test_run_tool_against_repo_install_fails(server_module;tmp_path;monkeypatch)
  mcp-skills/tests/test_mcp_skills.py:
    e: test_placeholder,test_import
    test_placeholder()
    test_import()
  mcp-skills/tool_run.py:
    e: _truncate_text,_ensure_tool_installed,_inject_github_token,_git_clone_or_update,derive_repo_id_from_url,collect_output_files,run_tool_against_repo
    _truncate_text(text;limit)
    _ensure_tool_installed(tool_name;package;binary;extra_pip_deps)
    _inject_github_token(url)
    _git_clone_or_update(repo_url;target_dir;ref)
    derive_repo_id_from_url(repo_url)
    collect_output_files(repo_path;paths)
    run_tool_against_repo(request;skills_server)
  mcp-skills/tools_registry.py:
  mcp-webui/server.py:
    e: gateway_headers,index,repos_page,repos_sync,diff_page,skills_page,skills_run,playground,_resolve_github_token,_read_gh2mcp_status,_get_github_config,github_page,github_configure,github_fetch_token_from_cli,_github_page_ctx,_normalize_github_url,github_clone,github_create_repo,github_sync
    gateway_headers()
    index(request)
    repos_page(request)
    repos_sync(repo_id;source_path;branch)
    diff_page(request;repo_id)
    skills_page(request)
    skills_run(model;prompt;repo_id;source_path)
    playground(request)
    _resolve_github_token()
    _read_gh2mcp_status()
    _get_github_config()
    github_page(request)
    github_configure(request;token;action)
    github_fetch_token_from_cli(request)
    _github_page_ctx(request)
    _normalize_github_url(repo_url)
    github_clone(request;repo_url;repo_id;branch)
    github_create_repo(request;repo_name;description;private;auto_clone)
    github_sync(request;repo_id;branch)
  mcp-webui/tests/test_mcp_webui.py:
    e: test_placeholder,test_import
    test_placeholder()
    test_import()
  semcod_mcp/__init__.py:
  semcod_mcp/analyze.py:
    e: run_analyze,AnalyzeReport
    AnalyzeReport:
    run_analyze(project_dir)
  semcod_mcp/cli.py:
    e: main,init_cmd,deinit_cmd,doctor_cmd,validate_cmd,analyze_cmd
    main()
    init_cmd(path;stack_path;global_config;dry_run;force;skip_continue)
    deinit_cmd(path;global_config;dry_run;skip_continue)
    doctor_cmd(path)
    validate_cmd(path)
    analyze_cmd(path;task;execute)
  semcod_mcp/deinit_cmd.py:
    e: _deinit_mcp_json,run_deinit,print_deinit_result,DeinitResult
    DeinitResult: changed(0)
    _deinit_mcp_json(path)
    run_deinit(project_dir)
    print_deinit_result(result)
  semcod_mcp/doctor.py:
    e: _http_ok,run_doctor,Check,DoctorReport
    Check:
    DoctorReport: healthy(0),add(3)
    _http_ok(url;headers;timeout)
    run_doctor(project_dir)
  semcod_mcp/init_cmd.py:
    e: _touch_text,_init_mcp_json,run_init,print_init_result,InitResult
    InitResult: changed(0)
    _touch_text(path;content)
    _init_mcp_json(path;stack_path)
    run_init(project_dir)
    print_init_result(result)
  semcod_mcp/merge.py:
    e: load_json,save_json,merge_mcp_servers,merge_continue_models,merge_vscode_settings,_mcp_json_is_empty,_continue_json_is_empty,remove_mcp_server,remove_continue_models,remove_vscode_settings,write_json_or_delete,delete_file
    load_json(path)
    save_json(path;data)
    merge_mcp_servers(existing;server_name;server_cfg)
    merge_continue_models(existing;models)
    merge_vscode_settings(existing;updates)
    _mcp_json_is_empty(data)
    _continue_json_is_empty(data)
    remove_mcp_server(existing;server_name)
    remove_continue_models(existing;titles)
    remove_vscode_settings(existing;keys)
    write_json_or_delete(path;data)
    delete_file(path)
  semcod_mcp/paths.py:
    e: expand,detect_stack_path,infer_repo_id,gateway_url,default_api_key
    expand(path)
    detect_stack_path(explicit)
    infer_repo_id(project_dir)
    gateway_url(stack_path)
    default_api_key()
  semcod_mcp/templates.py:
    e: mcp_server_block,continue_models,vscode_settings_snippet,cursor_rule_text,manifest_data,_manifest_compare_keys,write_manifest,read_manifest
    mcp_server_block(stack_path)
    continue_models(gw;api_key)
    vscode_settings_snippet()
    cursor_rule_text(repo_id;stack_path)
    manifest_data(project_dir;stack_path;repo_id;ides)
    _manifest_compare_keys(data)
    write_manifest(path;data)
    read_manifest(project_dir)
  semcod_mcp/validate.py:
    e: _validate_mcp_json,run_validate,ValidationIssue,ValidationReport
    ValidationIssue:
    ValidationReport: ok(0),error(2),warn(2)
    _validate_mcp_json(path;report;stack_path)
    run_validate(project_dir)
  tests/__init__.py:
  tests/test_deinit.py:
    e: _make_stack,test_deinit_dry_run_leaves_files,test_deinit_removes_init_artifacts,test_deinit_preserves_other_mcp_servers,test_deinit_idempotent_second_run
    _make_stack(tmp_path)
    test_deinit_dry_run_leaves_files(tmp_path)
    test_deinit_removes_init_artifacts(tmp_path)
    test_deinit_preserves_other_mcp_servers(tmp_path)
    test_deinit_idempotent_second_run(tmp_path)
  tests/test_init.py:
    e: test_init_dry_run_writes_nothing,test_init_merges_cursor_mcp,test_init_idempotent_second_run_no_duplicates
    test_init_dry_run_writes_nothing(tmp_path)
    test_init_merges_cursor_mcp(tmp_path)
    test_init_idempotent_second_run_no_duplicates(tmp_path)
  tests/test_merge.py:
    e: test_merge_mcp_servers_adds_without_touching_existing,test_merge_mcp_servers_skips_when_different_without_force,test_merge_continue_models_by_title,test_merge_vscode_settings_non_destructive,test_remove_mcp_server_preserves_other_servers,test_remove_mcp_server_deletes_empty_doc,test_remove_continue_models_by_title,test_remove_vscode_settings_keeps_unrelated_keys
    test_merge_mcp_servers_adds_without_touching_existing()
    test_merge_mcp_servers_skips_when_different_without_force()
    test_merge_continue_models_by_title()
    test_merge_vscode_settings_non_destructive()
    test_remove_mcp_server_preserves_other_servers()
    test_remove_mcp_server_deletes_empty_doc()
    test_remove_continue_models_by_title()
    test_remove_vscode_settings_keeps_unrelated_keys()
```

### `project/logic.pl`

```prolog markpact:analysis path=project/logic.pl
% ── Project Metadata ─────────────────────────────────────
project_metadata('mcp', '0.1.4', 'python').

% ── Project Files ────────────────────────────────────────
project_file('app.doql.less', 262, 'less').
project_file('dashboard/server.py', 190, 'python').
project_file('env2mcp/env2mcp/__init__.py', 14, 'python').
project_file('env2mcp/env2mcp/cli.py', 253, 'python').
project_file('env2mcp/env2mcp/config.py', 159, 'python').
project_file('env2mcp/env2mcp/github_cli.py', 331, 'python').
project_file('env2mcp/tests/test_env2mcp.py', 70, 'python').
project_file('gh2mcp/gh2mcp/__init__.py', 5, 'python').
project_file('gh2mcp/gh2mcp/cli.py', 69, 'python').
project_file('gh2mcp/gh2mcp/server.py', 111, 'python').
project_file('gh2mcp/gh2mcp/sync.py', 431, 'python').
project_file('gh2mcp/tests/test_gh2mcp.py', 278, 'python').
project_file('git2mcp/__init__.py', 4, 'python').
project_file('git2mcp/app.doql.less', 35, 'less').
project_file('git2mcp/client.py', 4, 'python').
project_file('git2mcp/examples/01_sync_and_commit.py', 63, 'python').
project_file('git2mcp/examples/02_fragment_sync_to_skills.py', 69, 'python').
project_file('git2mcp/examples/03_agent_git2mcp.py', 56, 'python').
project_file('git2mcp/examples/04_dry_run_vs_execute.py', 116, 'python').
project_file('git2mcp/examples/05_local_iterate.py', 127, 'python').
project_file('git2mcp/git2mcp/__init__.py', 4, 'python').
project_file('git2mcp/git2mcp/client.py', 105, 'python').
project_file('git2mcp/git2mcp/proxy.py', 438, 'python').
project_file('git2mcp/project.sh', 47, 'shell').
project_file('git2mcp/proxy.py', 4, 'python').
project_file('git2mcp/tests/test_git2mcp.py', 327, 'python').
project_file('llm-agent/agent.py', 376, 'python').
project_file('llm-agent/agent_git2mcp.py', 362, 'python').
project_file('llm-agent/agent_standalone.py', 541, 'python').
project_file('llm-agent/tests/test_llm_agent.py', 12, 'python').
project_file('mcp-docs/server.py', 274, 'python').
project_file('mcp-docs/tests/test_mcp_docs.py', 12, 'python').
project_file('mcp-gateway/conftest.py', 5, 'python').
project_file('mcp-gateway/gateway_chat.py', 571, 'python').
project_file('mcp-gateway/gateway_config.py', 57, 'python').
project_file('mcp-gateway/gateway_dispatch.py', 249, 'python').
project_file('mcp-gateway/gateway_gh2mcp.py', 408, 'python').
project_file('mcp-gateway/gateway_github.py', 433, 'python').
project_file('mcp-gateway/gateway_jobs.py', 176, 'python').
project_file('mcp-gateway/gateway_models.py', 35, 'python').
project_file('mcp-gateway/gateway_prompt.py', 272, 'python').
project_file('mcp-gateway/gateway_render.py', 503, 'python').
project_file('mcp-gateway/gateway_skills.py', 264, 'python').
project_file('mcp-gateway/gateway_tenants.py', 142, 'python').
project_file('mcp-gateway/server.py', 229, 'python').
project_file('mcp-gateway/test_gateway_token_command.py', 690, 'python').
project_file('mcp-gateway/test_github_qa.py', 96, 'python').
project_file('mcp-gateway/test_tool_intent.py', 189, 'python').
project_file('mcp-gateway/tests/test_mcp_gateway.py', 12, 'python').
project_file('mcp-gateway/worker.py', 19, 'python').
project_file('mcp-git-proxy/server.py', 444, 'python').
project_file('mcp-git-proxy/tests/test_mcp_git_proxy.py', 12, 'python').
project_file('mcp-skills/code_analysis.py', 283, 'python').
project_file('mcp-skills/conftest.py', 5, 'python').
project_file('mcp-skills/http_models.py', 61, 'python').
project_file('mcp-skills/mcp_parse.py', 19, 'python').
project_file('mcp-skills/redsl_runner.py', 72, 'python').
project_file('mcp-skills/server.py', 692, 'python').
project_file('mcp-skills/test_code_analysis.py', 75, 'python').
project_file('mcp-skills/test_tools_run.py', 156, 'python').
project_file('mcp-skills/tests/test_mcp_skills.py', 12, 'python').
project_file('mcp-skills/tool_run.py', 389, 'python').
project_file('mcp-skills/tools_registry.py', 151, 'python').
project_file('mcp-webui/server.py', 622, 'python').
project_file('mcp-webui/tests/test_mcp_webui.py', 12, 'python').
project_file('project.sh', 47, 'shell').
project_file('scripts/deploy.sh', 136, 'shell').
project_file('scripts/generate_demo_repos.sh', 397, 'shell').
project_file('scripts/refactor-last-repo.sh', 313, 'shell').
project_file('scripts/test.sh', 405, 'shell').
project_file('semcod_mcp/__init__.py', 4, 'python').
project_file('semcod_mcp/analyze.py', 106, 'python').
project_file('semcod_mcp/cli.py', 133, 'python').
project_file('semcod_mcp/deinit_cmd.py', 138, 'python').
project_file('semcod_mcp/doctor.py', 117, 'python').
project_file('semcod_mcp/init_cmd.py', 177, 'python').
project_file('semcod_mcp/merge.py', 217, 'python').
project_file('semcod_mcp/paths.py', 71, 'python').
project_file('semcod_mcp/templates.py', 163, 'python').
project_file('semcod_mcp/validate.py', 102, 'python').
project_file('tests/__init__.py', 2, 'python').
project_file('tests/test_deinit.py', 74, 'python').
project_file('tests/test_init.py', 71, 'python').
project_file('tests/test_merge.py', 77, 'python').
project_file('tree.sh', 2, 'shell').

% ── Python Functions ─────────────────────────────────────
python_function('dashboard/server.py', 'main', 0, 2, 3).
python_function('env2mcp/env2mcp/cli.py', 'cmd_github_login', 1, 4, 5).
python_function('env2mcp/env2mcp/cli.py', 'cmd_github_status', 1, 11, 8).
python_function('env2mcp/env2mcp/cli.py', 'cmd_github_logout', 1, 7, 8).
python_function('env2mcp/env2mcp/cli.py', 'cmd_github_repos', 1, 5, 5).
python_function('env2mcp/env2mcp/cli.py', 'cmd_env_show', 1, 6, 9).
python_function('env2mcp/env2mcp/cli.py', 'cmd_env_set', 1, 2, 4).
python_function('env2mcp/env2mcp/cli.py', 'cmd_env_get', 1, 7, 7).
python_function('env2mcp/env2mcp/cli.py', 'main', 1, 2, 9).
python_function('env2mcp/env2mcp/config.py', 'load_env', 1, 1, 1).
python_function('env2mcp/env2mcp/config.py', 'save_env', 2, 1, 1).
python_function('env2mcp/env2mcp/github_cli.py', 'get_github_token', 1, 5, 5).
python_function('env2mcp/env2mcp/github_cli.py', 'configure_github', 2, 14, 14).
python_function('env2mcp/tests/test_env2mcp.py', 'test_import', 0, 1, 0).
python_function('env2mcp/tests/test_env2mcp.py', 'test_format_value_token_no_quotes', 0, 3, 2).
python_function('env2mcp/tests/test_env2mcp.py', 'test_format_value_no_double_quote_wrap', 0, 3, 3).
python_function('env2mcp/tests/test_env2mcp.py', 'test_format_value_spaces_quoted', 0, 2, 2).
python_function('env2mcp/tests/test_env2mcp.py', 'test_format_value_empty', 0, 2, 2).
python_function('env2mcp/tests/test_env2mcp.py', 'test_format_value_numeric', 0, 2, 2).
python_function('env2mcp/tests/test_env2mcp.py', 'test_save_load_roundtrip', 1, 7, 5).
python_function('gh2mcp/gh2mcp/cli.py', '_cmd_status', 1, 1, 3).
python_function('gh2mcp/gh2mcp/cli.py', '_cmd_sync', 1, 2, 4).
python_function('gh2mcp/gh2mcp/cli.py', '_cmd_agent', 1, 3, 4).
python_function('gh2mcp/gh2mcp/cli.py', 'build_parser', 0, 1, 5).
python_function('gh2mcp/gh2mcp/cli.py', 'main', 1, 2, 5).
python_function('gh2mcp/gh2mcp/server.py', '_periodic_sync', 0, 2, 2).
python_function('gh2mcp/gh2mcp/server.py', 'on_startup', 0, 3, 4).
python_function('gh2mcp/gh2mcp/server.py', 'on_shutdown', 0, 2, 2).
python_function('gh2mcp/gh2mcp/server.py', 'health', 0, 1, 1).
python_function('gh2mcp/gh2mcp/server.py', 'status', 1, 1, 3).
python_function('gh2mcp/gh2mcp/server.py', 'sync_token', 1, 1, 2).
python_function('gh2mcp/gh2mcp/server.py', 'set_org', 1, 1, 2).
python_function('gh2mcp/gh2mcp/server.py', 'list_orgs', 1, 1, 2).
python_function('gh2mcp/gh2mcp/server.py', 'last_pushed_repo', 1, 1, 2).
python_function('gh2mcp/gh2mcp/server.py', 'recent_repos', 1, 1, 2).
python_function('gh2mcp/tests/test_gh2mcp.py', 'test_sync_token_saves_from_env_and_reads_back', 2, 9, 9).
python_function('gh2mcp/tests/test_gh2mcp.py', 'test_sync_token_reads_from_env_file_when_env_missing', 2, 6, 6).
python_function('gh2mcp/tests/test_gh2mcp.py', 'test_sync_token_force_gh_cli_does_not_fallback_to_env_or_file', 2, 4, 5).
python_function('gh2mcp/tests/test_gh2mcp.py', 'test_set_org_defaults_to_gh_username', 2, 4, 4).
python_function('gh2mcp/tests/test_gh2mcp.py', 'test_list_orgs_and_repos', 2, 5, 4).
python_function('gh2mcp/tests/test_gh2mcp.py', 'test_get_last_pushed_repo_selects_latest', 2, 4, 4).
python_function('gh2mcp/tests/test_gh2mcp.py', 'test_get_last_pushed_repo_success', 2, 5, 5).
python_function('gh2mcp/tests/test_gh2mcp.py', 'test_get_last_pushed_repo_no_repos', 2, 3, 5).
python_function('gh2mcp/tests/test_gh2mcp.py', 'test_get_recent_repos_sorts_across_user_and_orgs', 2, 7, 4).
python_function('gh2mcp/tests/test_gh2mcp.py', 'test_get_recent_repos_owner_only', 2, 5, 4).
python_function('git2mcp/examples/01_sync_and_commit.py', 'main', 0, 1, 9).
python_function('git2mcp/examples/02_fragment_sync_to_skills.py', 'main', 0, 1, 12).
python_function('git2mcp/examples/03_agent_git2mcp.py', 'main', 0, 4, 8).
python_function('git2mcp/examples/04_dry_run_vs_execute.py', 'run', 1, 3, 5).
python_function('git2mcp/examples/04_dry_run_vs_execute.py', 'main', 0, 1, 7).
python_function('git2mcp/examples/05_local_iterate.py', 'main', 0, 5, 13).
python_function('git2mcp/tests/test_git2mcp.py', '_load_proxy_app', 2, 2, 5).
python_function('git2mcp/tests/test_git2mcp.py', '_create_sample_repo_source', 1, 1, 2).
python_function('git2mcp/tests/test_git2mcp.py', 'test_git_proxy_e2e_sync_export_commit_and_tests', 1, 18, 10).
python_function('git2mcp/tests/test_git2mcp.py', 'test_git_proxy_local_operations', 1, 17, 6).
python_function('git2mcp/tests/test_git2mcp.py', 'test_git_proxy_e2e_commit_and_reset', 1, 7, 6).
python_function('git2mcp/tests/test_git2mcp.py', 'test_git_proxy_e2e_push_to_bare_remote', 1, 10, 18).
python_function('llm-agent/agent.py', 'main', 0, 2, 10).
python_function('llm-agent/agent_git2mcp.py', 'main', 0, 1, 12).
python_function('llm-agent/agent_standalone.py', 'main', 0, 2, 13).
python_function('llm-agent/tests/test_llm_agent.py', 'test_placeholder', 0, 2, 0).
python_function('llm-agent/tests/test_llm_agent.py', 'test_import', 0, 1, 0).
python_function('mcp-docs/server.py', '_markdown_to_html', 1, 1, 1).
python_function('mcp-docs/server.py', '_page', 2, 1, 1).
python_function('mcp-docs/server.py', '_safe_doc_path', 1, 4, 6).
python_function('mcp-docs/server.py', 'health', 0, 1, 1).
python_function('mcp-docs/server.py', 'list_docs', 0, 3, 9).
python_function('mcp-docs/server.py', 'index', 0, 4, 10).
python_function('mcp-docs/server.py', 'render_doc', 1, 1, 6).
python_function('mcp-docs/tests/test_mcp_docs.py', 'test_placeholder', 0, 2, 0).
python_function('mcp-docs/tests/test_mcp_docs.py', 'test_import', 0, 1, 0).
python_function('mcp-gateway/gateway_chat.py', '_audit', 1, 1, 1).
python_function('mcp-gateway/gateway_chat.py', 'run_chat_workflow', 1, 43, 22).
python_function('mcp-gateway/gateway_chat.py', 'handle_chat_completions', 2, 31, 28).
python_function('mcp-gateway/gateway_dispatch.py', 'dispatch_skill', 19, 19, 21).
python_function('mcp-gateway/gateway_gh2mcp.py', '_gateway_hooks', 0, 1, 0).
python_function('mcp-gateway/gateway_gh2mcp.py', 'is_github_configured', 0, 1, 2).
python_function('mcp-gateway/gateway_gh2mcp.py', 'get_default_github_repo', 0, 7, 4).
python_function('mcp-gateway/gateway_gh2mcp.py', 'sync_github_token_via_gh2mcp', 0, 3, 6).
python_function('mcp-gateway/gateway_gh2mcp.py', 'set_default_org_via_gh2mcp', 1, 3, 6).
python_function('mcp-gateway/gateway_gh2mcp.py', 'list_recent_repos_via_gh2mcp', 3, 2, 6).
python_function('mcp-gateway/gateway_gh2mcp.py', 'list_orgs_via_gh2mcp', 1, 2, 6).
python_function('mcp-gateway/gateway_gh2mcp.py', 'gh2mcp_status_via_gh2mcp', 0, 2, 5).
python_function('mcp-gateway/gateway_gh2mcp.py', 'last_pushed_repo_via_gh2mcp', 2, 2, 6).
python_function('mcp-gateway/gateway_gh2mcp.py', 'is_github_auth_error', 1, 3, 2).
python_function('mcp-gateway/gateway_gh2mcp.py', 'github_auth_recovery_message', 1, 1, 1).
python_function('mcp-gateway/gateway_gh2mcp.py', 'resolve_repo_id_template', 1, 14, 12).
python_function('mcp-gateway/gateway_gh2mcp.py', 'save_github_token_via_env2mcp', 2, 4, 4).
python_function('mcp-gateway/gateway_gh2mcp.py', 'repo_owner', 1, 4, 2).
python_function('mcp-gateway/gateway_gh2mcp.py', 'run_github_qa', 3, 9, 12).
python_function('mcp-gateway/gateway_github.py', 'normalize_repo_url', 1, 3, 2).
python_function('mcp-gateway/gateway_github.py', 'github_repo_from_url', 1, 9, 9).
python_function('mcp-gateway/gateway_github.py', 'is_github_token_save_command', 2, 15, 7).
python_function('mcp-gateway/gateway_github.py', 'is_github_token_sync_command', 2, 11, 8).
python_function('mcp-gateway/gateway_github.py', 'extract_org_from_text', 2, 9, 8).
python_function('mcp-gateway/gateway_github.py', 'is_org_set_command', 1, 9, 5).
python_function('mcp-gateway/gateway_github.py', 'is_org_list_command', 1, 13, 5).
python_function('mcp-gateway/gateway_github.py', 'is_repo_list_command', 1, 23, 4).
python_function('mcp-gateway/gateway_github.py', 'extract_repo_list_limit', 3, 3, 5).
python_function('mcp-gateway/gateway_github.py', 'load_env_file_values', 1, 11, 8).
python_function('mcp-gateway/gateway_github.py', 'runtime_github_token', 0, 4, 3).
python_function('mcp-gateway/gateway_github.py', 'save_github_token', 1, 6, 9).
python_function('mcp-gateway/gateway_github.py', 'inject_github_token', 1, 9, 5).
python_function('mcp-gateway/gateway_github.py', 'redact_repo_url', 1, 6, 4).
python_function('mcp-gateway/gateway_github.py', 'default_draft_name', 1, 2, 3).
python_function('mcp-gateway/gateway_github.py', 'default_pr_title', 2, 4, 4).
python_function('mcp-gateway/gateway_github.py', 'default_pr_body', 3, 1, 1).
python_function('mcp-gateway/gateway_github.py', 'create_github_pr', 8, 3, 5).
python_function('mcp-gateway/gateway_jobs.py', 'job_storage_key', 1, 1, 0).
python_function('mcp-gateway/gateway_jobs.py', 'get_state_redis_client', 0, 4, 2).
python_function('mcp-gateway/gateway_jobs.py', 'get_rq_redis_client', 0, 4, 2).
python_function('mcp-gateway/gateway_jobs.py', 'get_queue', 0, 5, 2).
python_function('mcp-gateway/gateway_jobs.py', 'save_job', 2, 3, 4).
python_function('mcp-gateway/gateway_jobs.py', 'load_job', 1, 5, 5).
python_function('mcp-gateway/gateway_jobs.py', 'update_job', 1, 2, 4).
python_function('mcp-gateway/gateway_jobs.py', 'queue_workflow_job', 2, 2, 3).
python_function('mcp-gateway/gateway_jobs.py', 'execute_dispatch_job', 2, 3, 6).
python_function('mcp-gateway/gateway_prompt.py', 'message_content_to_text', 1, 14, 5).
python_function('mcp-gateway/gateway_prompt.py', 'parse_prompt_context', 1, 8, 6).
python_function('mcp-gateway/gateway_prompt.py', 'parse_bool', 2, 4, 2).
python_function('mcp-gateway/gateway_prompt.py', 'normalize_command_text', 1, 1, 4).
python_function('mcp-gateway/gateway_prompt.py', 'extract_github_token_from_text', 1, 2, 2).
python_function('mcp-gateway/gateway_prompt.py', 'extract_repo_template_expression', 1, 3, 3).
python_function('mcp-gateway/gateway_prompt.py', 'is_last_pushed_repo_template', 1, 15, 3).
python_function('mcp-gateway/gateway_prompt.py', 'extract_owner_from_repo_template', 1, 4, 3).
python_function('mcp-gateway/gateway_prompt.py', 'strip_url_suffix', 1, 1, 1).
python_function('mcp-gateway/gateway_prompt.py', 'parse_tool_intent', 2, 23, 12).
python_function('mcp-gateway/gateway_render.py', 'summary_text', 2, 9, 3).
python_function('mcp-gateway/gateway_render.py', 'render_repo_selection_text', 1, 4, 2).
python_function('mcp-gateway/gateway_render.py', 'render_system_text', 1, 27, 6).
python_function('mcp-gateway/gateway_render.py', 'render_analyze_text', 1, 14, 6).
python_function('mcp-gateway/gateway_render.py', 'render_queued_text', 1, 6, 3).
python_function('mcp-gateway/gateway_render.py', 'render_refactor_text', 1, 17, 9).
python_function('mcp-gateway/gateway_render.py', 'file_fence_lang', 1, 4, 4).
python_function('mcp-gateway/gateway_render.py', 'is_markdown_path', 1, 1, 2).
python_function('mcp-gateway/gateway_render.py', 'render_tool_text', 1, 40, 11).
python_function('mcp-gateway/gateway_render.py', 'render_github_qa_text', 1, 8, 4).
python_function('mcp-gateway/gateway_render.py', 'render_chat_content', 1, 13, 11).
python_function('mcp-gateway/gateway_render.py', 'build_commit_changes', 2, 1, 1).
python_function('mcp-gateway/gateway_render.py', 'render_tools_list_text', 1, 11, 4).
python_function('mcp-gateway/gateway_skills.py', 'expect_json', 2, 3, 3).
python_function('mcp-gateway/gateway_skills.py', 'is_tools_list_command', 1, 6, 3).
python_function('mcp-gateway/gateway_skills.py', 'fetch_tools_list', 0, 2, 3).
python_function('mcp-gateway/gateway_skills.py', 'run_skills_tool', 6, 7, 5).
python_function('mcp-gateway/gateway_skills.py', 'ask_openrouter_github_qa', 2, 12, 8).
python_function('mcp-gateway/gateway_skills.py', 'enrich_analysis_with_file_metrics', 3, 13, 5).
python_function('mcp-gateway/gateway_skills.py', 'run_skills_analysis', 5, 4, 5).
python_function('mcp-gateway/gateway_tenants.py', 'load_tenants', 0, 5, 5).
python_function('mcp-gateway/gateway_tenants.py', 'get_redis_client', 0, 4, 1).
python_function('mcp-gateway/gateway_tenants.py', 'track_repo_usage', 3, 3, 7).
python_function('mcp-gateway/gateway_tenants.py', 'get_last_used_repo', 1, 8, 6).
python_function('mcp-gateway/gateway_tenants.py', 'get_most_used_repo', 1, 8, 5).
python_function('mcp-gateway/gateway_tenants.py', 'get_preferred_repo', 1, 2, 2).
python_function('mcp-gateway/gateway_tenants.py', 'find_tenant_by_key', 1, 3, 2).
python_function('mcp-gateway/gateway_tenants.py', 'authenticate', 1, 4, 7).
python_function('mcp-gateway/gateway_tenants.py', 'audit', 1, 1, 5).
python_function('mcp-gateway/server.py', 'health', 0, 1, 3).
python_function('mcp-gateway/server.py', 'list_models', 1, 2, 3).
python_function('mcp-gateway/server.py', 'chat_completions', 2, 1, 3).
python_function('mcp-gateway/server.py', 'get_job', 2, 2, 4).
python_function('mcp-gateway/server.py', 'stream_job', 2, 2, 8).
python_function('mcp-gateway/server.py', 'audit_tail', 2, 4, 7).
python_function('mcp-gateway/server.py', '_ask_openrouter_github_qa', 2, 1, 1).
python_function('mcp-gateway/test_gateway_token_command.py', '_extract_sse_data', 1, 3, 4).
python_function('mcp-gateway/test_gateway_token_command.py', '_authorized_client', 0, 1, 1).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_is_github_token_sync_command', 2, 2, 3).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_is_github_token_sync_command_false_if_explicit_token_value', 0, 2, 2).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_is_github_token_save_command', 2, 2, 3).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_extract_github_token_from_text', 0, 2, 1).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_is_org_set_command', 2, 2, 2).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_is_org_list_command', 2, 2, 2).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_is_repo_list_command', 2, 2, 2).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_extract_repo_list_limit_defaults_and_bounds', 0, 5, 1).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_extract_org_from_text', 0, 5, 1).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_sync_github_token_via_gh2mcp_success_note', 1, 4, 3).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_sync_github_token_via_gh2mcp_failure_note', 1, 5, 4).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_extract_repo_template_expression', 0, 3, 1).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_is_last_pushed_repo_template', 2, 2, 2).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_resolve_repo_id_template_last_pushed', 1, 5, 3).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_resolve_repo_id_template_last_pushed_repo_url_in_meta', 1, 8, 4).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_resolve_repo_id_template_unsupported', 0, 1, 3).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_is_github_auth_error', 2, 2, 2).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_github_auth_recovery_message_has_three_options', 0, 6, 2).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_resolve_repo_id_template_auto_recovers_on_auth_error', 1, 4, 5).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_resolve_repo_id_template_auth_error_with_failed_recovery_raises_helpful_message', 1, 4, 5).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_resolve_repo_id_template_non_auth_error_does_not_trigger_recovery', 1, 3, 6).
python_function('mcp-gateway/test_gateway_token_command.py', '_compute_effective_repo_url', 2, 4, 1).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_effective_repo_url_explicit_repo_url_wins', 1, 2, 4).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_effective_repo_url_falls_back_to_resolved', 1, 2, 4).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_effective_repo_url_both_none', 0, 3, 1).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_effective_repo_url_no_template_resolution', 0, 2, 1).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_render_chat_content_analyze_human_readable', 0, 4, 2).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_render_chat_content_refactor_human_readable', 0, 5, 2).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_render_chat_content_system_human_readable', 0, 3, 1).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_render_chat_content_system_recent_repos_human_readable', 0, 4, 1).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_render_chat_content_queued_human_readable', 0, 4, 1).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_is_repo_list_command', 2, 2, 2).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_extract_repo_list_limit', 2, 2, 2).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_summary_text_redsl_engine', 0, 8, 1).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_summary_text_mcp_skills_engine', 0, 4, 1).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_stream_job_not_found_returns_404', 1, 2, 4).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_stream_job_emits_status_updates_and_done', 1, 6, 7).
python_function('mcp-gateway/test_gateway_token_command.py', 'test_stream_job_emits_failure_with_error', 1, 6, 7).
python_function('mcp-gateway/test_github_qa.py', '_authorized_client', 0, 1, 1).
python_function('mcp-gateway/test_github_qa.py', 'test_render_chat_content_github_qa', 0, 3, 1).
python_function('mcp-gateway/test_github_qa.py', 'test_run_github_qa_missing_openrouter_key', 1, 4, 3).
python_function('mcp-gateway/test_github_qa.py', 'test_chat_completions_github_qa_model', 1, 4, 5).
python_function('mcp-gateway/test_github_qa.py', 'test_models_include_github_qa', 0, 4, 4).
python_function('mcp-gateway/test_tool_intent.py', 'test_parse_tool_intent_recognizes_tool_and_repo', 4, 5, 2).
python_function('mcp-gateway/test_tool_intent.py', 'test_parse_tool_intent_returns_none_for_non_tool_prompts', 1, 2, 2).
python_function('mcp-gateway/test_tool_intent.py', 'test_parse_tool_intent_uses_prompt_ctx_repo_id', 0, 4, 1).
python_function('mcp-gateway/test_tool_intent.py', 'test_render_tool_text_includes_artifacts_and_status', 0, 10, 1).
python_function('mcp-gateway/test_tool_intent.py', 'test_render_tool_text_handles_failure', 0, 4, 1).
python_function('mcp-gateway/test_tool_intent.py', 'test_render_chat_content_dispatches_tool_skill', 0, 3, 1).
python_function('mcp-gateway/test_tool_intent.py', 'test_force_tool_skill_with_no_intent_returns_helpful_error', 0, 3, 2).
python_function('mcp-gateway/tests/test_mcp_gateway.py', 'test_placeholder', 0, 2, 0).
python_function('mcp-gateway/tests/test_mcp_gateway.py', 'test_import', 0, 1, 0).
python_function('mcp-gateway/worker.py', 'main', 0, 2, 4).
python_function('mcp-git-proxy/server.py', 'health', 0, 1, 1).
python_function('mcp-git-proxy/server.py', 'list_repos', 0, 1, 2).
python_function('mcp-git-proxy/server.py', 'sync_repo', 1, 2, 4).
python_function('mcp-git-proxy/server.py', 'export_fragments', 1, 2, 4).
python_function('mcp-git-proxy/server.py', 'export_package', 1, 2, 4).
python_function('mcp-git-proxy/server.py', 'import_package', 1, 1, 9).
python_function('mcp-git-proxy/server.py', 'commit', 2, 2, 4).
python_function('mcp-git-proxy/server.py', 'push', 2, 2, 4).
python_function('mcp-git-proxy/server.py', 'reset', 2, 2, 4).
python_function('mcp-git-proxy/server.py', 'worktree_write', 2, 2, 4).
python_function('mcp-git-proxy/server.py', 'worktree_read', 2, 3, 4).
python_function('mcp-git-proxy/server.py', 'worktree_diff', 2, 2, 4).
python_function('mcp-git-proxy/server.py', 'patch_apply', 2, 2, 4).
python_function('mcp-git-proxy/server.py', 'stage', 2, 2, 4).
python_function('mcp-git-proxy/server.py', 'stash_save', 2, 2, 4).
python_function('mcp-git-proxy/server.py', 'stash_pop', 1, 2, 4).
python_function('mcp-git-proxy/server.py', 'branch_draft', 2, 2, 4).
python_function('mcp-git-proxy/server.py', 'checkpoint_create', 2, 2, 4).
python_function('mcp-git-proxy/server.py', 'checkpoint_restore', 2, 3, 4).
python_function('mcp-git-proxy/server.py', 'run_tests', 2, 2, 6).
python_function('mcp-git-proxy/server.py', 'github_create_repo', 1, 9, 15).
python_function('mcp-git-proxy/server.py', 'sync_pull', 2, 7, 8).
python_function('mcp-git-proxy/tests/test_mcp_git_proxy.py', 'test_placeholder', 0, 2, 0).
python_function('mcp-git-proxy/tests/test_mcp_git_proxy.py', 'test_import', 0, 1, 0).
python_function('mcp-skills/code_analysis.py', '_should_skip_path', 1, 2, 1).
python_function('mcp-skills/code_analysis.py', 'compute_repo_file_metrics', 2, 15, 14).
python_function('mcp-skills/code_analysis.py', 'detect_repo_patterns', 1, 10, 14).
python_function('mcp-skills/code_analysis.py', 'build_maintainability_recommendations', 1, 24, 7).
python_function('mcp-skills/code_analysis.py', 'merge_recommendations', 2, 9, 6).
python_function('mcp-skills/code_analysis.py', 'recommendations_payload', 3, 5, 3).
python_function('mcp-skills/mcp_parse.py', 'parse_tool_result', 1, 3, 1).
python_function('mcp-skills/redsl_runner.py', 'run_redsl_refactor', 3, 14, 9).
python_function('mcp-skills/server.py', 'health', 0, 1, 2).
python_function('mcp-skills/server.py', 'sync_repo', 1, 2, 4).
python_function('mcp-skills/server.py', 'analyze_code_structure', 1, 2, 6).
python_function('mcp-skills/server.py', 'compute_metrics', 1, 2, 6).
python_function('mcp-skills/server.py', 'detect_patterns', 1, 2, 6).
python_function('mcp-skills/server.py', 'recommend_refactoring', 1, 2, 6).
python_function('mcp-skills/server.py', 'redsl_refactor', 1, 9, 16).
python_function('mcp-skills/server.py', 'list_tools_endpoint', 0, 2, 3).
python_function('mcp-skills/server.py', 'run_tool_endpoint', 1, 1, 2).
python_function('mcp-skills/server.py', 'main', 0, 2, 5).
python_function('mcp-skills/server.py', '_run_tool_against_repo', 1, 1, 1).
python_function('mcp-skills/test_code_analysis.py', 'test_compute_repo_file_metrics_returns_largest_files', 1, 5, 3).
python_function('mcp-skills/test_code_analysis.py', 'test_build_maintainability_recommendations_targets_large_files', 1, 5, 2).
python_function('mcp-skills/test_code_analysis.py', 'test_merge_recommendations_prefers_concrete_targets', 0, 3, 2).
python_function('mcp-skills/test_tools_run.py', 'server_module', 1, 2, 9).
python_function('mcp-skills/test_tools_run.py', 'test_derive_repo_id_from_url', 1, 5, 1).
python_function('mcp-skills/test_tools_run.py', 'test_supported_tools_registry_has_expected_entries', 1, 2, 2).
python_function('mcp-skills/test_tools_run.py', 'test_collect_output_files_reads_small_text', 2, 6, 3).
python_function('mcp-skills/test_tools_run.py', 'test_run_tool_against_repo_unsupported', 1, 3, 3).
python_function('mcp-skills/test_tools_run.py', 'test_run_tool_against_repo_happy_path', 3, 9, 9).
python_function('mcp-skills/test_tools_run.py', 'test_run_tool_against_repo_install_fails', 3, 4, 7).
python_function('mcp-skills/tests/test_mcp_skills.py', 'test_placeholder', 0, 2, 0).
python_function('mcp-skills/tests/test_mcp_skills.py', 'test_import', 0, 1, 0).
python_function('mcp-skills/tool_run.py', '_truncate_text', 2, 3, 3).
python_function('mcp-skills/tool_run.py', '_ensure_tool_installed', 4, 10, 6).
python_function('mcp-skills/tool_run.py', '_inject_github_token', 1, 5, 2).
python_function('mcp-skills/tool_run.py', '_git_clone_or_update', 3, 10, 12).
python_function('mcp-skills/tool_run.py', 'derive_repo_id_from_url', 1, 9, 5).
python_function('mcp-skills/tool_run.py', 'collect_output_files', 2, 9, 11).
python_function('mcp-skills/tool_run.py', 'run_tool_against_repo', 2, 37, 30).
python_function('mcp-webui/server.py', 'gateway_headers', 0, 1, 0).
python_function('mcp-webui/server.py', 'index', 1, 3, 6).
python_function('mcp-webui/server.py', 'repos_page', 1, 2, 4).
python_function('mcp-webui/server.py', 'repos_sync', 3, 1, 4).
python_function('mcp-webui/server.py', 'diff_page', 2, 5, 6).
python_function('mcp-webui/server.py', 'skills_page', 1, 1, 2).
python_function('mcp-webui/server.py', 'skills_run', 4, 4, 6).
python_function('mcp-webui/server.py', 'playground', 1, 1, 2).
python_function('mcp-webui/server.py', '_resolve_github_token', 0, 7, 4).
python_function('mcp-webui/server.py', '_read_gh2mcp_status', 0, 4, 3).
python_function('mcp-webui/server.py', '_get_github_config', 0, 16, 10).
python_function('mcp-webui/server.py', 'github_page', 1, 2, 5).
python_function('mcp-webui/server.py', 'github_configure', 3, 9, 11).
python_function('mcp-webui/server.py', 'github_fetch_token_from_cli', 1, 16, 15).
python_function('mcp-webui/server.py', '_github_page_ctx', 1, 2, 4).
python_function('mcp-webui/server.py', '_normalize_github_url', 1, 6, 4).
python_function('mcp-webui/server.py', 'github_clone', 4, 6, 12).
python_function('mcp-webui/server.py', 'github_create_repo', 5, 4, 9).
python_function('mcp-webui/server.py', 'github_sync', 3, 4, 8).
python_function('mcp-webui/tests/test_mcp_webui.py', 'test_placeholder', 0, 2, 0).
python_function('mcp-webui/tests/test_mcp_webui.py', 'test_import', 0, 1, 0).
python_function('semcod_mcp/analyze.py', 'run_analyze', 1, 12, 13).
python_function('semcod_mcp/cli.py', 'main', 0, 1, 2).
python_function('semcod_mcp/cli.py', 'init_cmd', 6, 4, 9).
python_function('semcod_mcp/cli.py', 'deinit_cmd', 4, 2, 7).
python_function('semcod_mcp/cli.py', 'doctor_cmd', 1, 6, 10).
python_function('semcod_mcp/cli.py', 'validate_cmd', 1, 4, 7).
python_function('semcod_mcp/cli.py', 'analyze_cmd', 3, 4, 7).
python_function('semcod_mcp/deinit_cmd.py', '_deinit_mcp_json', 1, 8, 7).
python_function('semcod_mcp/deinit_cmd.py', 'run_deinit', 1, 15, 15).
python_function('semcod_mcp/deinit_cmd.py', 'print_deinit_result', 1, 5, 1).
python_function('semcod_mcp/doctor.py', '_http_ok', 3, 4, 2).
python_function('semcod_mcp/doctor.py', 'run_doctor', 1, 11, 19).
python_function('semcod_mcp/init_cmd.py', '_touch_text', 2, 5, 4).
python_function('semcod_mcp/init_cmd.py', '_init_mcp_json', 2, 5, 7).
python_function('semcod_mcp/init_cmd.py', 'run_init', 1, 14, 23).
python_function('semcod_mcp/init_cmd.py', 'print_init_result', 1, 5, 1).
python_function('semcod_mcp/merge.py', 'load_json', 1, 4, 6).
python_function('semcod_mcp/merge.py', 'save_json', 2, 2, 3).
python_function('semcod_mcp/merge.py', 'merge_mcp_servers', 3, 5, 5).
python_function('semcod_mcp/merge.py', 'merge_continue_models', 2, 10, 7).
python_function('semcod_mcp/merge.py', 'merge_vscode_settings', 2, 4, 3).
python_function('semcod_mcp/merge.py', '_mcp_json_is_empty', 1, 3, 3).
python_function('semcod_mcp/merge.py', '_continue_json_is_empty', 1, 3, 3).
python_function('semcod_mcp/merge.py', 'remove_mcp_server', 2, 4, 5).
python_function('semcod_mcp/merge.py', 'remove_continue_models', 2, 8, 5).
python_function('semcod_mcp/merge.py', 'remove_vscode_settings', 2, 4, 2).
python_function('semcod_mcp/merge.py', 'write_json_or_delete', 2, 5, 3).
python_function('semcod_mcp/merge.py', 'delete_file', 1, 3, 2).
python_function('semcod_mcp/paths.py', 'expand', 1, 1, 3).
python_function('semcod_mcp/paths.py', 'detect_stack_path', 1, 10, 5).
python_function('semcod_mcp/paths.py', 'infer_repo_id', 1, 5, 5).
python_function('semcod_mcp/paths.py', 'gateway_url', 1, 1, 1).
python_function('semcod_mcp/paths.py', 'default_api_key', 0, 1, 1).
python_function('semcod_mcp/templates.py', 'mcp_server_block', 1, 1, 1).
python_function('semcod_mcp/templates.py', 'continue_models', 2, 1, 0).
python_function('semcod_mcp/templates.py', 'vscode_settings_snippet', 0, 1, 2).
python_function('semcod_mcp/templates.py', 'cursor_rule_text', 2, 3, 0).
python_function('semcod_mcp/templates.py', 'manifest_data', 4, 2, 8).
python_function('semcod_mcp/templates.py', '_manifest_compare_keys', 1, 2, 2).
python_function('semcod_mcp/templates.py', 'write_manifest', 2, 8, 8).
python_function('semcod_mcp/templates.py', 'read_manifest', 1, 3, 3).
python_function('semcod_mcp/validate.py', '_validate_mcp_json', 3, 13, 8).
python_function('semcod_mcp/validate.py', 'run_validate', 1, 13, 13).
python_function('tests/test_deinit.py', '_make_stack', 1, 1, 2).
python_function('tests/test_deinit.py', 'test_deinit_dry_run_leaves_files', 1, 5, 7).
python_function('tests/test_deinit.py', 'test_deinit_removes_init_artifacts', 1, 6, 5).
python_function('tests/test_deinit.py', 'test_deinit_preserves_other_mcp_servers', 1, 2, 8).
python_function('tests/test_deinit.py', 'test_deinit_idempotent_second_run', 1, 3, 4).
python_function('tests/test_init.py', 'test_init_dry_run_writes_nothing', 1, 4, 8).
python_function('tests/test_init.py', 'test_init_merges_cursor_mcp', 1, 4, 8).
python_function('tests/test_init.py', 'test_init_idempotent_second_run_no_duplicates', 1, 8, 9).
python_function('tests/test_merge.py', 'test_merge_mcp_servers_adds_without_touching_existing', 0, 4, 2).
python_function('tests/test_merge.py', 'test_merge_mcp_servers_skips_when_different_without_force', 0, 3, 2).
python_function('tests/test_merge.py', 'test_merge_continue_models_by_title', 0, 3, 3).
python_function('tests/test_merge.py', 'test_merge_vscode_settings_non_destructive', 0, 3, 1).
python_function('tests/test_merge.py', 'test_remove_mcp_server_preserves_other_servers', 0, 5, 2).
python_function('tests/test_merge.py', 'test_remove_mcp_server_deletes_empty_doc', 0, 3, 2).
python_function('tests/test_merge.py', 'test_remove_continue_models_by_title', 0, 5, 3).
python_function('tests/test_merge.py', 'test_remove_vscode_settings_keeps_unrelated_keys', 0, 3, 2).

% ── Python Classes ───────────────────────────────────────
python_class('dashboard/server.py', 'DashboardHandler').
python_method('DashboardHandler', 'end_headers', 0, 1, 3).
python_method('DashboardHandler', 'do_GET', 0, 8, 13).
python_method('DashboardHandler', 'serve_file', 1, 2, 10).
python_method('DashboardHandler', 'send_json', 1, 1, 7).
python_method('DashboardHandler', 'get_content_type', 1, 1, 1).
python_method('DashboardHandler', 'get_status', 0, 5, 7).
python_method('DashboardHandler', 'get_analyses', 0, 4, 6).
python_method('DashboardHandler', 'get_analysis', 1, 3, 4).
python_method('DashboardHandler', 'get_repos', 0, 5, 8).
python_class('dashboard/server.py', 'TCPServer').
python_class('env2mcp/env2mcp/config.py', 'EnvConfig').
python_method('EnvConfig', '__init__', 1, 1, 2).
python_method('EnvConfig', '_load', 0, 11, 7).
python_method('EnvConfig', 'get', 2, 2, 2).
python_method('EnvConfig', 'set', 2, 1, 0).
python_method('EnvConfig', 'remove', 1, 1, 1).
python_method('EnvConfig', '_format_value', 2, 8, 6).
python_method('EnvConfig', 'save', 1, 20, 12).
python_method('EnvConfig', '__contains__', 1, 2, 0).
python_method('EnvConfig', '__getitem__', 1, 2, 2).
python_method('EnvConfig', '__setitem__', 2, 1, 1).
python_method('EnvConfig', 'items', 0, 3, 3).
python_class('env2mcp/env2mcp/github_cli.py', 'GitHubCLI').
python_method('GitHubCLI', '__init__', 0, 1, 0).
python_method('GitHubCLI', 'is_available', 0, 3, 1).
python_method('GitHubCLI', 'get_auth_status', 0, 14, 8).
python_method('GitHubCLI', 'get_token', 0, 4, 3).
python_method('GitHubCLI', 'get_user', 0, 4, 3).
python_method('GitHubCLI', 'login', 2, 7, 2).
python_method('GitHubCLI', 'logout', 1, 5, 3).
python_method('GitHubCLI', 'list_repos', 2, 5, 4).
python_method('GitHubCLI', 'clone_url', 1, 4, 1).
python_class('gh2mcp/gh2mcp/server.py', 'SyncTokenRequest').
python_class('gh2mcp/gh2mcp/server.py', 'SetOrgRequest').
python_class('gh2mcp/gh2mcp/server.py', 'ListOrgsRequest').
python_class('gh2mcp/gh2mcp/server.py', 'LastPushedRepoRequest').
python_class('gh2mcp/gh2mcp/server.py', 'RecentReposRequest').
python_class('gh2mcp/gh2mcp/sync.py', 'GitHubTokenSyncService').
python_method('GitHubTokenSyncService', '__init__', 1, 1, 1).
python_method('GitHubTokenSyncService', 'get_status', 1, 6, 7).
python_method('GitHubTokenSyncService', 'set_org', 1, 6, 7).
python_method('GitHubTokenSyncService', 'list_orgs_and_repos', 1, 8, 10).
python_method('GitHubTokenSyncService', 'get_last_pushed_repo', 2, 23, 15).
python_method('GitHubTokenSyncService', 'get_recent_repos', 3, 32, 18).
python_method('GitHubTokenSyncService', 'sync_token', 2, 20, 9).
python_class('gh2mcp/tests/test_gh2mcp.py', '_GhUnavailable').
python_method('_GhUnavailable', 'is_available', 0, 1, 0).
python_method('_GhUnavailable', 'get_token', 0, 1, 0).
python_method('_GhUnavailable', 'get_user', 0, 1, 0).
python_class('gh2mcp/tests/test_gh2mcp.py', '_GhUserRepos').
python_method('_GhUserRepos', 'is_available', 0, 1, 0).
python_method('_GhUserRepos', 'get_token', 0, 1, 0).
python_method('_GhUserRepos', 'get_user', 0, 1, 0).
python_method('_GhUserRepos', 'list_repos', 2, 1, 0).
python_class('gh2mcp/tests/test_gh2mcp.py', '_ProcResult').
python_method('_ProcResult', '__init__', 3, 1, 0).
python_class('gh2mcp/tests/test_gh2mcp.py', '_GhAvailableUser').
python_method('_GhAvailableUser', 'is_available', 0, 1, 0).
python_method('_GhAvailableUser', 'get_token', 0, 1, 0).
python_method('_GhAvailableUser', 'get_user', 0, 1, 0).
python_class('gh2mcp/tests/test_gh2mcp.py', '_GhNoToken').
python_method('_GhNoToken', 'is_available', 0, 1, 0).
python_method('_GhNoToken', 'get_token', 0, 1, 0).
python_method('_GhNoToken', 'get_user', 0, 1, 0).
python_class('git2mcp/git2mcp/client.py', 'Git2MCPClient').
python_method('Git2MCPClient', '__init__', 2, 1, 1).
python_method('Git2MCPClient', '_request', 3, 4, 7).
python_method('Git2MCPClient', 'health', 0, 1, 1).
python_method('Git2MCPClient', 'list_repos', 0, 1, 1).
python_method('Git2MCPClient', 'sync_repo', 4, 1, 1).
python_method('Git2MCPClient', 'export_package', 2, 1, 1).
python_method('Git2MCPClient', 'commit_changes', 5, 1, 1).
python_method('Git2MCPClient', 'run_tests', 2, 1, 1).
python_method('Git2MCPClient', 'push', 3, 1, 1).
python_method('Git2MCPClient', 'reset', 3, 1, 1).
python_method('Git2MCPClient', 'worktree_write', 4, 1, 1).
python_method('Git2MCPClient', 'worktree_read', 3, 1, 1).
python_method('Git2MCPClient', 'worktree_diff', 2, 1, 1).
python_method('Git2MCPClient', 'patch_apply', 3, 1, 1).
python_method('Git2MCPClient', 'stage', 2, 1, 1).
python_method('Git2MCPClient', 'stash_save', 2, 1, 1).
python_method('Git2MCPClient', 'stash_pop', 1, 1, 1).
python_method('Git2MCPClient', 'branch_draft', 3, 1, 1).
python_method('Git2MCPClient', 'checkpoint_create', 2, 1, 1).
python_method('Git2MCPClient', 'checkpoint_restore', 2, 1, 1).
python_class('git2mcp/git2mcp/proxy.py', 'GitProxyManager').
python_method('GitProxyManager', '__init__', 2, 1, 2).
python_method('GitProxyManager', '_repo_path', 1, 1, 0).
python_method('GitProxyManager', '_ensure_parent', 1, 1, 1).
python_method('GitProxyManager', '_allow_local_repo_url', 1, 9, 9).
python_method('GitProxyManager', 'list_repos', 0, 3, 5).
python_method('GitProxyManager', 'sync_repo', 4, 12, 21).
python_method('GitProxyManager', 'export_package', 2, 6, 16).
python_method('GitProxyManager', 'export_fragments', 3, 9, 12).
python_method('GitProxyManager', 'commit_changes', 5, 5, 12).
python_method('GitProxyManager', 'push', 3, 7, 9).
python_method('GitProxyManager', 'worktree_write', 4, 3, 11).
python_method('GitProxyManager', 'worktree_read', 3, 3, 8).
python_method('GitProxyManager', 'worktree_diff', 2, 3, 5).
python_method('GitProxyManager', 'patch_apply', 3, 5, 7).
python_method('GitProxyManager', 'stage', 2, 4, 5).
python_method('GitProxyManager', 'stash_save', 2, 3, 6).
python_method('GitProxyManager', 'stash_pop', 1, 3, 6).
python_method('GitProxyManager', 'branch_draft', 3, 4, 6).
python_method('GitProxyManager', 'checkpoint_create', 2, 5, 10).
python_method('GitProxyManager', 'checkpoint_restore', 2, 6, 9).
python_method('GitProxyManager', 'reset', 3, 3, 6).
python_class('llm-agent/agent.py', 'AnalysisResult').
python_class('llm-agent/agent.py', 'RefactoringAgent').
python_method('RefactoringAgent', '__init__', 0, 1, 1).
python_method('RefactoringAgent', 'connect_skills', 2, 2, 6).
python_method('RefactoringAgent', 'connect_git_mcp', 2, 2, 7).
python_method('RefactoringAgent', 'analyze_repository', 2, 3, 4).
python_method('RefactoringAgent', 'generate_refactoring_plan', 1, 4, 4).
python_method('RefactoringAgent', '_build_refactoring_prompt', 1, 2, 2).
python_method('RefactoringAgent', '_call_openai', 1, 2, 4).
python_method('RefactoringAgent', '_call_ollama', 1, 2, 6).
python_method('RefactoringAgent', '_mock_llm_response', 1, 3, 4).
python_method('RefactoringAgent', '_mock_llm_response_from_prompt', 1, 1, 1).
python_method('RefactoringAgent', 'execute_refactoring_workflow', 3, 3, 4).
python_method('RefactoringAgent', 'close', 0, 3, 3).
python_class('llm-agent/agent_git2mcp.py', 'AnalysisResult').
python_class('llm-agent/agent_git2mcp.py', 'CachedCodeAnalyzer').
python_method('CachedCodeAnalyzer', '__init__', 1, 1, 2).
python_method('CachedCodeAnalyzer', '_repo_path', 1, 1, 0).
python_method('CachedCodeAnalyzer', 'import_package', 2, 6, 14).
python_method('CachedCodeAnalyzer', 'compute_metrics', 2, 15, 13).
python_method('CachedCodeAnalyzer', 'detect_patterns', 1, 8, 14).
python_method('CachedCodeAnalyzer', 'recommend_refactoring', 2, 8, 4).
python_class('llm-agent/agent_git2mcp.py', 'Git2MCPRefactoringAgent').
python_method('Git2MCPRefactoringAgent', '__init__', 1, 1, 3).
python_method('Git2MCPRefactoringAgent', 'sync_and_cache_repo', 4, 1, 5).
python_method('Git2MCPRefactoringAgent', 'analyze', 1, 1, 4).
python_method('Git2MCPRefactoringAgent', 'generate_plan', 1, 5, 7).
python_method('Git2MCPRefactoringAgent', 'build_commit_changes', 1, 1, 2).
python_method('Git2MCPRefactoringAgent', 'execute', 7, 4, 9).
python_class('llm-agent/agent_standalone.py', 'AnalysisResult').
python_class('llm-agent/agent_standalone.py', 'LocalCodeAnalyzer').
python_method('LocalCodeAnalyzer', '__init__', 1, 1, 1).
python_method('LocalCodeAnalyzer', 'analyze_code_structure', 2, 11, 9).
python_method('LocalCodeAnalyzer', 'compute_metrics_for_repo', 2, 15, 13).
python_method('LocalCodeAnalyzer', 'detect_code_patterns', 2, 15, 13).
python_method('LocalCodeAnalyzer', 'recommend_refactoring', 2, 14, 6).
python_class('llm-agent/agent_standalone.py', 'RefactoringAgent').
python_method('RefactoringAgent', '__init__', 1, 1, 2).
python_method('RefactoringAgent', 'analyze_repository', 2, 2, 6).
python_method('RefactoringAgent', 'generate_refactoring_plan', 1, 3, 4).
python_method('RefactoringAgent', '_build_refactoring_prompt', 1, 2, 2).
python_method('RefactoringAgent', '_call_openai_sync', 1, 2, 5).
python_method('RefactoringAgent', '_mock_llm_response', 1, 3, 4).
python_method('RefactoringAgent', '_mock_llm_response_from_prompt', 1, 1, 1).
python_method('RefactoringAgent', 'execute_refactoring_workflow', 3, 3, 4).
python_class('mcp-gateway/gateway_models.py', 'ChatMessage').
python_class('mcp-gateway/gateway_models.py', 'ChatCompletionRequest').
python_class('mcp-gateway/test_gateway_token_command.py', '_FakeResponse').
python_method('_FakeResponse', '__init__', 2, 1, 1).
python_method('_FakeResponse', 'json', 0, 1, 0).
python_class('mcp-gateway/test_gateway_token_command.py', '_FakeAsyncClient').
python_method('_FakeAsyncClient', '__init__', 0, 1, 0).
python_method('_FakeAsyncClient', '__aenter__', 0, 1, 0).
python_method('_FakeAsyncClient', '__aexit__', 3, 1, 0).
python_method('_FakeAsyncClient', 'post', 2, 2, 2).
python_method('_FakeAsyncClient', 'get', 1, 1, 1).
python_class('mcp-git-proxy/server.py', 'SyncRepoRequest').
python_class('mcp-git-proxy/server.py', 'ExportPackageRequest').
python_class('mcp-git-proxy/server.py', 'ExportFragmentsRequest').
python_class('mcp-git-proxy/server.py', 'CommitRequest').
python_class('mcp-git-proxy/server.py', 'PushRequest').
python_class('mcp-git-proxy/server.py', 'RunTestsRequest').
python_class('mcp-git-proxy/server.py', 'ResetRequest').
python_class('mcp-git-proxy/server.py', 'ImportPackageRequest').
python_class('mcp-git-proxy/server.py', 'WorktreeWriteRequest').
python_class('mcp-git-proxy/server.py', 'WorktreeReadRequest').
python_class('mcp-git-proxy/server.py', 'WorktreeDiffRequest').
python_class('mcp-git-proxy/server.py', 'PatchApplyRequest').
python_class('mcp-git-proxy/server.py', 'StageRequest').
python_class('mcp-git-proxy/server.py', 'StashSaveRequest').
python_class('mcp-git-proxy/server.py', 'BranchDraftRequest').
python_class('mcp-git-proxy/server.py', 'CheckpointCreateRequest').
python_class('mcp-git-proxy/server.py', 'CheckpointRestoreRequest').
python_class('mcp-git-proxy/server.py', 'SyncPullRequest').
python_class('mcp-git-proxy/server.py', 'CreateGithubRepoRequest').
python_class('mcp-skills/http_models.py', 'SyncRepoRequest').
python_class('mcp-skills/http_models.py', 'AnalyzeStructureRequest').
python_class('mcp-skills/http_models.py', 'RepoMetricsRequest').
python_class('mcp-skills/http_models.py', 'PatternDetectionRequest').
python_class('mcp-skills/http_models.py', 'RecommendRefactoringRequest').
python_class('mcp-skills/http_models.py', 'RedslRefactorRequest').
python_class('mcp-skills/http_models.py', 'ToolRunRequest').
python_class('mcp-skills/server.py', 'MCPSkillsServer').
python_method('MCPSkillsServer', '__init__', 1, 2, 5).
python_method('MCPSkillsServer', '_sync_from_git_proxy', 2, 15, 23).
python_method('MCPSkillsServer', '_setup_handlers', 0, 1, 2).
python_method('MCPSkillsServer', '_handle_list_tools', 0, 1, 3).
python_method('MCPSkillsServer', '_handle_call_tool', 2, 7, 8).
python_method('MCPSkillsServer', '_analyze_code_structure', 1, 13, 14).
python_method('MCPSkillsServer', '_compute_metrics_for_repo', 1, 3, 8).
python_method('MCPSkillsServer', '_detect_code_patterns', 1, 2, 7).
python_method('MCPSkillsServer', '_sync_repo_tool', 1, 2, 5).
python_method('MCPSkillsServer', '_recommend_refactoring', 1, 2, 10).
python_method('MCPSkillsServer', 'run', 0, 1, 5).
python_class('semcod_mcp/analyze.py', 'AnalyzeReport').
python_class('semcod_mcp/deinit_cmd.py', 'DeinitResult').
python_method('DeinitResult', 'changed', 0, 6, 2).
python_class('semcod_mcp/doctor.py', 'Check').
python_class('semcod_mcp/doctor.py', 'DoctorReport').
python_method('DoctorReport', 'healthy', 0, 3, 2).
python_method('DoctorReport', 'add', 3, 1, 2).
python_class('semcod_mcp/init_cmd.py', 'InitResult').
python_method('InitResult', 'changed', 0, 6, 1).
python_class('semcod_mcp/validate.py', 'ValidationIssue').
python_class('semcod_mcp/validate.py', 'ValidationReport').
python_method('ValidationReport', 'ok', 0, 2, 1).
python_method('ValidationReport', 'error', 2, 1, 2).
python_method('ValidationReport', 'warn', 2, 1, 2).

% ── Dependencies ─────────────────────────────────────────

% ── Makefile Targets ─────────────────────────────────────
makefile_target('SHELL', '').
makefile_target('PORTS', '').
makefile_target('COMPOSE', '').
makefile_target('COMPOSE_PROD', '').
makefile_target('PROFILES', '').
makefile_target('help', '').
makefile_target('kill-ports', '').
makefile_target('start', '').
makefile_target('stop', '').
makefile_target('restart', '').
makefile_target('up', '').
makefile_target('down', '').
makefile_target('logs', '').
makefile_target('ps', '').
makefile_target('build', '').
makefile_target('rebuild', '').
makefile_target('smoke', '').
makefile_target('ansible-e2e', '').
makefile_target('ansible-gh2mcp', '').
makefile_target('ansible-github-qa', '').
makefile_target('reload-gateway', '').
makefile_target('ansible-tools-e2e', '').
makefile_target('reload-skills', '').
makefile_target('ansible-github-test', '').
makefile_target('gh2mcp-status', '').
makefile_target('pytest', '').
makefile_target('test', '').
makefile_target('prod-up', '').
makefile_target('prod-down', '').
makefile_target('clean', '').
makefile_target('install-env2mcp', '').
makefile_target('setup-github', '').
makefile_target('generate-demo-repos', '').
makefile_target('generate-demo-repos-github', '').

% ── Taskfile Tasks ───────────────────────────────────────

% ── Environment Variables ────────────────────────────────
env_variable('LLM_PROVIDER', 'openrouter-lite', 'LLM Provider: openrouter-lite, mock, openai, ollama').
env_variable('OPENROUTER_API_KEY', '*(not set)*', '').
env_variable('LLM_MODEL', 'openrouter/x-ai/grok-code-fast-1', 'LLM_MODEL=openrouter/qwen/qwen3-coder-next').
env_variable('OPENAI_API_KEY', 'sk-...', 'OpenAI API Key (wymagane dla LLM_PROVIDER=openai)').
env_variable('GITHUB_PAT', 'ghp_...', 'Uzyskaj token przez: make setup-github lub env2mcp github login').
env_variable('GITHUB_USER', 'your-username', '').
env_variable('GH2MCP_SYNC_ON_START', 'true', 'gh2mcp Agent (docker) - synchronizacja tokenu z gh CLI do .env przy starcie').
env_variable('GH2MCP_SYNC_INTERVAL', '0', '').
env_variable('GIT_PROXY_URL', 'http://mcp-git-proxy:8080', 'MCP Git Proxy').
env_variable('WEBUI_API_KEY', 'sk-mcp-default-dev-key', 'MCP Gateway (OpenAI-compatible) - klucz tenanta z mcp-gateway/tenants/*.yaml').
env_variable('OPENWEBUI_AUTH', 'False', 'OpenWebUI (zostaw False dla lokalnego dev, True dla produkcji)').
env_variable('REPOS_PATH', './repos', 'Ścieżki repozytoriów').
env_variable('OUTPUT_PATH', './output', '').
env_variable('PORT_OPENWEBUI', '3000', 'Porty publiczne usług (host:kontener)').
env_variable('PORT_GH2MCP', '8079', '').
env_variable('PORT_GIT_PROXY', '8081', '').
env_variable('PORT_DASHBOARD', '8085', '').
env_variable('PORT_WEBUI', '8092', '').
env_variable('PORT_DOCS', '8093', '').
env_variable('PORT_GATEWAY', '9000', '').
env_variable('REDIS_URL', 'redis://redis:6379/0', 'Redis').
env_variable('OPENWEBUI_URL', 'http://localhost:3000/', 'URL OpenWebUI (używany przez mcp-docs do linku w UI)').
env_variable('ENABLE_MERMAID', 'true', 'OpenWebUI - renderowanie artefaktów i Markdown').
env_variable('ENABLE_LATEX', 'true', '').
env_variable('ENABLE_ARTIFACTS', 'true', '').
env_variable('COLLAPSE_CODE_BLOCKS', 'false', '').
env_variable('ENABLE_CODE_EXECUTION', 'false', '').
env_variable('DEFAULT_LOCALE', 'pl-PL', '').

% ── TestQL Scenarios ─────────────────────────────────────

% ── Semantic Facts from SUMD.md ──────────────────────────
sumd_declared_file('app.doql.less', 'doql').
sumd_declared_file('project/map.toon.yaml', 'analysis').
sumd_declared_file('project/logic.pl', 'analysis').
sumd_declared_file('project/calls.toon.yaml', 'analysis').
sumd_interface('api', '').
sumd_interface('mcp', 'stdio').
sumd_interface('mcp', '').
sumd_interface('web', '').
sumd_workflow('kill-ports', 'manual').
sumd_workflow_step('kill-ports', 1, 'for p in $(PORTS)').
sumd_workflow_step('kill-ports', 2, 'cids=$$(docker ps --filter "publish=$$p" -q)').
sumd_workflow_step('kill-ports', 3, 'if [ -n "$$cids" ]').
sumd_workflow_step('kill-ports', 4, 'echo "stopping containers binding port $$p: $$cids"').
sumd_workflow_step('kill-ports', 5, 'docker stop $$cids >/dev/null || true').
sumd_workflow_step('kill-ports', 6, 'fi').
sumd_workflow_step('kill-ports', 7, 'pids=$$(ss -lntp 2>/dev/null | grep -E ":$$p[[:space:]]" | grep -oE \'pid=[0-9]+\' | cut -d= -f2 | sort -u)').
sumd_workflow_step('kill-ports', 8, 'if [ -n "$$pids" ]').
sumd_workflow_step('kill-ports', 9, 'echo "killing pids on port $$p: $$pids"').
sumd_workflow_step('kill-ports', 10, 'for pid in $$pids').
sumd_workflow_step('kill-ports', 11, 'sleep 1').
sumd_workflow_step('kill-ports', 12, 'for pid in $$pids').
sumd_workflow_step('kill-ports', 13, 'fi').
sumd_workflow_step('kill-ports', 14, 'done').
sumd_workflow('start', 'manual').
sumd_workflow_step('start', 1, 'echo "Pruning orphaned containers to avoid name conflicts..."').
sumd_workflow_step('start', 2, 'for c in mcp-redis mcp-git-proxy gh2mcp-agent mcp-skills-server llm-agent mcp-gateway mcp-gateway-worker mcp-webui mcp-docs openwebui mcp-dashboard').
sumd_workflow_step('start', 3, 'docker rm -f $$c >/dev/null 2>&1 || true').
sumd_workflow_step('start', 4, 'done').
sumd_workflow_step('start', 5, 'GH_TOKEN_VALUE=$$(gh auth token 2>/dev/null || true)').
sumd_workflow_step('start', 6, 'if [ -n "$$GH_TOKEN_VALUE" ]').
sumd_workflow_step('start', 7, '$(COMPOSE) $(PROFILES) build').
sumd_workflow_step('start', 8, 'GH_TOKEN_VALUE=$$(gh auth token 2>/dev/null || true)').
sumd_workflow_step('start', 9, 'if [ -n "$$GH_TOKEN_VALUE" ]').
sumd_workflow_step('start', 10, '$(COMPOSE) $(PROFILES) up -d').
sumd_workflow_step('start', 11, '$(MAKE) smoke').
sumd_workflow_step('start', 12, 'echo ""').
sumd_workflow_step('start', 13, 'echo "MCP Skills stack started:"').
sumd_workflow_step('start', 14, 'echo "  OpenWebUI:  http://localhost:$(PORT_OPENWEBUI)"').
sumd_workflow_step('start', 15, 'echo "  MCP WebUI:  http://localhost:$(PORT_WEBUI)"').
sumd_workflow_step('start', 16, 'echo "  MCP Docs:   http://localhost:$(PORT_DOCS)"').
sumd_workflow_step('start', 17, 'echo "  Gateway:    http://localhost:$(PORT_GATEWAY)"').
sumd_workflow_step('start', 18, 'echo "  Dashboard:  http://localhost:$(PORT_DASHBOARD)"').
sumd_workflow_step('start', 19, 'echo "  Git Proxy:  http://localhost:$(PORT_GIT_PROXY)"').
sumd_workflow('stop', 'manual').
sumd_workflow_step('stop', 1, '$(COMPOSE) $(PROFILES) down --remove-orphans').
sumd_workflow('restart', 'manual').
sumd_workflow('up', 'manual').
sumd_workflow_step('up', 1, '$(COMPOSE) $(PROFILES) up -d').
sumd_workflow('down', 'manual').
sumd_workflow('logs', 'manual').
sumd_workflow_step('logs', 1, '$(COMPOSE) $(PROFILES) logs -f --tail=200').
sumd_workflow('ps', 'manual').
sumd_workflow_step('ps', 1, '$(COMPOSE) $(PROFILES) ps').
sumd_workflow('build', 'manual').
sumd_workflow_step('build', 1, '$(COMPOSE) $(PROFILES) build').
sumd_workflow('rebuild', 'manual').
sumd_workflow_step('rebuild', 1, '$(COMPOSE) $(PROFILES) build --no-cache').
sumd_workflow('smoke', 'manual').
sumd_workflow_step('smoke', 1, 'echo "--- gateway /health ---"').
sumd_workflow_step('smoke', 2, 'echo "--- gh2mcp /health ---"').
sumd_workflow_step('smoke', 3, 'echo "--- mcp-docs /health ---"').
sumd_workflow_step('smoke', 4, 'echo "--- gateway /v1/models (no auth) ---"').
sumd_workflow('ansible-e2e', 'manual').
sumd_workflow_step('ansible-e2e', 1, 'ansible-playbook -i ansible/inventory.ini ansible/e2e-docker-stack.yml').
sumd_workflow('ansible-gh2mcp', 'manual').
sumd_workflow_step('ansible-gh2mcp', 1, 'ansible-playbook -i ansible/inventory.ini ansible/e2e-gh2mcp.yml').
sumd_workflow('ansible-github-qa', 'manual').
sumd_workflow_step('ansible-github-qa', 1, 'ansible-playbook -i ansible/inventory.ini ansible/e2e-github-qa.yml').
sumd_workflow('reload-gateway', 'manual').
sumd_workflow_step('reload-gateway', 1, 'GH_TOKEN_VALUE=$$(gh auth token 2>/dev/null || true)').
sumd_workflow_step('reload-gateway', 2, 'if [ -n "$$GH_TOKEN_VALUE" ]').
sumd_workflow_step('reload-gateway', 3, '$(COMPOSE) $(PROFILES) up -d --build --remove-orphans mcp-gateway mcp-gateway-worker gh2mcp-agent').
sumd_workflow_step('reload-gateway', 4, 'echo "mcp-gateway + mcp-gateway-worker + gh2mcp-agent rebuilt and restarted (GH_TOKEN preserved)"').
sumd_workflow('ansible-tools-e2e', 'manual').
sumd_workflow_step('ansible-tools-e2e', 1, 'ansible-playbook -i ansible/inventory.ini ansible/e2e-tools.yml').
sumd_workflow('reload-skills', 'manual').
sumd_workflow_step('reload-skills', 1, '$(COMPOSE) $(PROFILES) up -d --build --remove-orphans mcp-skills').
sumd_workflow_step('reload-skills', 2, 'echo "mcp-skills rebuilt and restarted"').
sumd_workflow('ansible-github-test', 'manual').
sumd_workflow_step('ansible-github-test', 1, 'ansible-playbook -i ansible/inventory.ini ansible/test-github-integration.yml').
sumd_workflow('gh2mcp-status', 'manual').
sumd_workflow_step('gh2mcp-status', 1, 'echo "--- gh2mcp /health ---"').
sumd_workflow_step('gh2mcp-status', 2, 'echo "--- gh2mcp /status ---"').
sumd_workflow('pytest', 'manual').
sumd_workflow_step('pytest', 1, 'python3 -m pytest -q git2mcp/tests/test_git2mcp.py').
sumd_workflow_step('pytest', 2, 'cd mcp-gateway && python3 -m pytest -q').
sumd_workflow_step('pytest', 3, 'cd gh2mcp && python3 -m pytest -q').
sumd_workflow_step('pytest', 4, 'cd mcp-skills && SKILLS_REPO_BASE=/tmp/mcp-skills-test python3 -m pytest -q').
sumd_workflow('test', 'manual').
sumd_workflow_step('test', 1, 'bash scripts/test.sh').
sumd_workflow_step('test', 2, '$(MAKE) ansible-github-qa').
sumd_workflow_step('test', 3, '$(MAKE) ansible-tools-e2e').
sumd_workflow('prod-up', 'manual').
sumd_workflow_step('prod-up', 1, '$(COMPOSE_PROD) $(PROFILES) up -d --build').
sumd_workflow('prod-down', 'manual').
sumd_workflow_step('prod-down', 1, '$(COMPOSE_PROD) $(PROFILES) down --remove-orphans').
sumd_workflow('clean', 'manual').
sumd_workflow_step('clean', 1, '$(COMPOSE) $(PROFILES) down -v --remove-orphans').
sumd_workflow('install-env2mcp', 'manual').
sumd_workflow_step('install-env2mcp', 1, 'pip install -e ./env2mcp').
sumd_workflow('setup-github', 'manual').
sumd_workflow_step('setup-github', 1, 'env2mcp setup-github').
sumd_workflow('generate-demo-repos', 'manual').
sumd_workflow_step('generate-demo-repos', 1, 'bash scripts/generate_demo_repos.sh').
sumd_workflow('generate-demo-repos-github', 'manual').
sumd_workflow_step('generate-demo-repos-github', 1, 'GH_DEMO_PROVIDER=github bash scripts/generate_demo_repos.sh').
sumd_deploy_target('docker_compose').
sumd_deploy_compose_file('docker-compose.yml').
```

## Call Graph

*189 nodes · 214 edges · 38 modules · CC̄=4.5*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `chat_completions` *(in mcp-gateway.server)* | 31 ⚠ | 0 | 114 | **114** |
| `run_tool_against_repo` *(in mcp-skills.tool_run)* | 37 ⚠ | 2 | 80 | **82** |
| `render_tool_text` *(in mcp-gateway.gateway_render)* | 40 ⚠ | 1 | 80 | **81** |
| `handle_chat_completions` *(in mcp-gateway.gateway_chat)* | 31 ⚠ | 0 | 69 | **69** |
| `print` *(in scripts.test)* | 0 | 64 | 0 | **64** |
| `render_refactor_text` *(in mcp-gateway.gateway_render)* | 17 ⚠ | 1 | 51 | **52** |
| `render_system_text` *(in mcp-gateway.gateway_render)* | 27 ⚠ | 1 | 45 | **46** |
| `run_chat_workflow` *(in mcp-gateway.gateway_chat)* | 43 ⚠ | 2 | 43 | **45** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/semcod/mcp
# generated in 0.09s
# nodes: 189 | edges: 214 | modules: 38
# CC̄=4.5

HUBS[20]:
  mcp-gateway.server.chat_completions
    CC=31  in:0  out:114  total:114
  mcp-skills.tool_run.run_tool_against_repo
    CC=37  in:2  out:80  total:82
  mcp-gateway.gateway_render.render_tool_text
    CC=40  in:1  out:80  total:81
  mcp-gateway.gateway_chat.handle_chat_completions
    CC=31  in:0  out:69  total:69
  scripts.test.print
    CC=0  in:64  out:0  total:64
  mcp-gateway.gateway_render.render_refactor_text
    CC=17  in:1  out:51  total:52
  mcp-gateway.gateway_render.render_system_text
    CC=27  in:1  out:45  total:46
  mcp-gateway.gateway_chat.run_chat_workflow
    CC=43  in:2  out:43  total:45
  mcp-gateway.gateway_dispatch.dispatch_skill
    CC=19  in:3  out:41  total:44
  mcp-skills.server.redsl_refactor
    CC=9  in:0  out:44  total:44
  mcp-skills.server.MCPSkillsServer._sync_from_git_proxy
    CC=15  in:0  out:39  total:39
  semcod_mcp.doctor.run_doctor
    CC=11  in:1  out:38  total:39
  gh2mcp.gh2mcp.sync.GitHubTokenSyncService.get_recent_repos
    CC=32  in:0  out:38  total:38
  semcod_mcp.init_cmd.run_init
    CC=14  in:1  out:37  total:38
  mcp-skills.code_analysis.build_maintainability_recommendations
    CC=24  in:2  out:34  total:36
  semcod_mcp.deinit_cmd.run_deinit
    CC=15  in:1  out:33  total:34
  mcp-webui.server.github_fetch_token_from_cli
    CC=16  in:0  out:32  total:32
  mcp-gateway.gateway_render.render_analyze_text
    CC=14  in:1  out:30  total:31
  env2mcp.env2mcp.github_cli.configure_github
    CC=14  in:1  out:29  total:30
  mcp-gateway.server._resolve_repo_id_template
    CC=14  in:1  out:28  total:29

MODULES:
  dashboard.server  [1 funcs]
    main  CC=2  out:10
  env2mcp.env2mcp.cli  [7 funcs]
    cmd_env_get  CC=7  out:10
    cmd_env_set  CC=2  out:5
    cmd_env_show  CC=6  out:12
    cmd_github_login  CC=4  out:9
    cmd_github_logout  CC=7  out:14
    cmd_github_repos  CC=5  out:12
    cmd_github_status  CC=11  out:22
  env2mcp.env2mcp.config  [1 funcs]
    set  CC=1  out:0
  env2mcp.env2mcp.github_cli  [1 funcs]
    configure_github  CC=14  out:29
  gh2mcp.gh2mcp.cli  [5 funcs]
    _cmd_agent  CC=3  out:6
    _cmd_status  CC=1  out:3
    _cmd_sync  CC=2  out:4
    build_parser  CC=1  out:13
    main  CC=2  out:5
  gh2mcp.gh2mcp.server  [2 funcs]
    _periodic_sync  CC=2  out:2
    on_startup  CC=3  out:4
  gh2mcp.gh2mcp.sync  [1 funcs]
    get_recent_repos  CC=32  out:38
  git2mcp.examples.01_sync_and_commit  [1 funcs]
    main  CC=1  out:18
  git2mcp.examples.02_fragment_sync_to_skills  [1 funcs]
    main  CC=1  out:15
  git2mcp.examples.03_agent_git2mcp  [1 funcs]
    main  CC=4  out:19
  llm-agent.agent  [1 funcs]
    main  CC=2  out:16
  llm-agent.agent_standalone  [1 funcs]
    main  CC=2  out:21
  mcp-docs.server  [5 funcs]
    _markdown_to_html  CC=1  out:1
    _page  CC=1  out:1
    _safe_doc_path  CC=4  out:9
    index  CC=4  out:11
    render_doc  CC=1  out:6
  mcp-gateway.gateway_chat  [2 funcs]
    handle_chat_completions  CC=31  out:69
    run_chat_workflow  CC=43  out:43
  mcp-gateway.gateway_dispatch  [1 funcs]
    dispatch_skill  CC=19  out:41
  mcp-gateway.gateway_gh2mcp  [13 funcs]
    get_default_github_repo  CC=7  out:7
    gh2mcp_status_via_gh2mcp  CC=2  out:11
    is_github_auth_error  CC=3  out:2
    is_github_configured  CC=1  out:2
    last_pushed_repo_via_gh2mcp  CC=2  out:12
    list_orgs_via_gh2mcp  CC=2  out:10
    list_recent_repos_via_gh2mcp  CC=2  out:11
    repo_owner  CC=4  out:2
    resolve_repo_id_template  CC=14  out:28
    run_github_qa  CC=9  out:16
  mcp-gateway.gateway_github  [15 funcs]
    create_github_pr  CC=3  out:14
    extract_org_from_text  CC=9  out:9
    extract_repo_list_limit  CC=3  out:5
    github_repo_from_url  CC=9  out:10
    inject_github_token  CC=9  out:6
    is_github_token_save_command  CC=15  out:7
    is_github_token_sync_command  CC=11  out:9
    is_org_list_command  CC=13  out:7
    is_org_set_command  CC=9  out:6
    is_repo_list_command  CC=23  out:4
  mcp-gateway.gateway_jobs  [9 funcs]
    execute_dispatch_job  CC=3  out:15
    get_queue  CC=5  out:2
    get_rq_redis_client  CC=4  out:2
    get_state_redis_client  CC=4  out:2
    job_storage_key  CC=1  out:0
    load_job  CC=5  out:6
    queue_workflow_job  CC=2  out:3
    save_job  CC=3  out:4
    update_job  CC=2  out:4
  mcp-gateway.gateway_prompt  [8 funcs]
    extract_github_token_from_text  CC=2  out:2
    extract_owner_from_repo_template  CC=4  out:3
    extract_repo_template_expression  CC=3  out:3
    is_last_pushed_repo_template  CC=15  out:3
    normalize_command_text  CC=1  out:5
    parse_prompt_context  CC=8  out:10
    parse_tool_intent  CC=23  out:17
    strip_url_suffix  CC=1  out:1
  mcp-gateway.gateway_render  [7 funcs]
    render_analyze_text  CC=14  out:30
    render_chat_content  CC=13  out:16
    render_queued_text  CC=6  out:7
    render_refactor_text  CC=17  out:51
    render_system_text  CC=27  out:45
    render_tool_text  CC=40  out:80
    summary_text  CC=9  out:24
  mcp-gateway.gateway_skills  [5 funcs]
    ask_openrouter_github_qa  CC=12  out:15
    enrich_analysis_with_file_metrics  CC=13  out:12
    expect_json  CC=3  out:4
    is_tools_list_command  CC=6  out:8
    run_skills_analysis  CC=4  out:16
  mcp-gateway.gateway_tenants  [7 funcs]
    authenticate  CC=4  out:8
    find_tenant_by_key  CC=3  out:2
    get_last_used_repo  CC=8  out:6
    get_most_used_repo  CC=8  out:5
    get_preferred_repo  CC=2  out:2
    get_redis_client  CC=4  out:1
    track_repo_usage  CC=3  out:8
  mcp-gateway.server  [18 funcs]
    _get_default_github_repo  CC=7  out:7
    _get_last_used_repo  CC=8  out:6
    _get_most_used_repo  CC=8  out:5
    _get_preferred_repo  CC=2  out:2
    _get_redis_client  CC=4  out:1
    _gh2mcp_status_via_gh2mcp  CC=2  out:11
    _is_github_auth_error  CC=3  out:2
    _is_github_configured  CC=1  out:2
    _last_pushed_repo_via_gh2mcp  CC=2  out:12
    _list_recent_repos_via_gh2mcp  CC=2  out:11
  mcp-skills.code_analysis  [6 funcs]
    _should_skip_path  CC=2  out:1
    build_maintainability_recommendations  CC=24  out:34
    compute_repo_file_metrics  CC=15  out:23
    detect_repo_patterns  CC=10  out:18
    merge_recommendations  CC=9  out:13
    recommendations_payload  CC=5  out:9
  mcp-skills.mcp_parse  [1 funcs]
    parse_tool_result  CC=3  out:1
  mcp-skills.server  [11 funcs]
    _compute_metrics_for_repo  CC=3  out:12
    _detect_code_patterns  CC=2  out:10
    _recommend_refactoring  CC=2  out:15
    _sync_from_git_proxy  CC=15  out:39
    _run_tool_against_repo  CC=1  out:1
    analyze_code_structure  CC=2  out:6
    compute_metrics  CC=2  out:6
    detect_patterns  CC=2  out:6
    recommend_refactoring  CC=2  out:6
    redsl_refactor  CC=9  out:44
  mcp-skills.tool_run  [6 funcs]
    _ensure_tool_installed  CC=10  out:11
    _git_clone_or_update  CC=10  out:19
    _inject_github_token  CC=5  out:3
    _truncate_text  CC=3  out:4
    collect_output_files  CC=9  out:17
    run_tool_against_repo  CC=37  out:80
  mcp-webui.server  [12 funcs]
    _get_github_config  CC=16  out:15
    _github_page_ctx  CC=2  out:4
    _normalize_github_url  CC=6  out:5
    _read_gh2mcp_status  CC=4  out:3
    _resolve_github_token  CC=7  out:6
    gateway_headers  CC=1  out:0
    github_clone  CC=6  out:17
    github_create_repo  CC=4  out:18
    github_fetch_token_from_cli  CC=16  out:32
    github_page  CC=2  out:6
  scripts.test  [1 funcs]
    print  CC=0  out:0
  semcod_mcp.analyze  [1 funcs]
    run_analyze  CC=12  out:22
  semcod_mcp.cli  [5 funcs]
    analyze_cmd  CC=4  out:10
    deinit_cmd  CC=2  out:9
    doctor_cmd  CC=6  out:12
    init_cmd  CC=4  out:14
    validate_cmd  CC=4  out:8
  semcod_mcp.deinit_cmd  [3 funcs]
    _deinit_mcp_json  CC=8  out:7
    print_deinit_result  CC=5  out:4
    run_deinit  CC=15  out:33
  semcod_mcp.doctor  [3 funcs]
    add  CC=1  out:2
    _http_ok  CC=4  out:2
    run_doctor  CC=11  out:38
  semcod_mcp.init_cmd  [3 funcs]
    _init_mcp_json  CC=5  out:8
    print_init_result  CC=5  out:4
    run_init  CC=14  out:37
  semcod_mcp.merge  [11 funcs]
    _continue_json_is_empty  CC=3  out:3
    _mcp_json_is_empty  CC=3  out:3
    delete_file  CC=3  out:2
    load_json  CC=4  out:6
    merge_mcp_servers  CC=5  out:8
    merge_vscode_settings  CC=4  out:5
    remove_continue_models  CC=8  out:9
    remove_mcp_server  CC=4  out:6
    remove_vscode_settings  CC=4  out:3
    save_json  CC=2  out:3
  semcod_mcp.paths  [5 funcs]
    default_api_key  CC=1  out:2
    detect_stack_path  CC=10  out:10
    expand  CC=1  out:3
    gateway_url  CC=1  out:2
    infer_repo_id  CC=5  out:6
  semcod_mcp.templates  [6 funcs]
    _manifest_compare_keys  CC=2  out:6
    manifest_data  CC=2  out:10
    mcp_server_block  CC=1  out:1
    read_manifest  CC=3  out:3
    vscode_settings_snippet  CC=1  out:2
    write_manifest  CC=8  out:10
  semcod_mcp.validate  [2 funcs]
    _validate_mcp_json  CC=13  out:23
    run_validate  CC=13  out:24

EDGES:
  dashboard.server.main → scripts.test.print
  mcp-docs.server.index → mcp-docs.server._page
  mcp-docs.server.render_doc → mcp-docs.server._safe_doc_path
  mcp-docs.server.render_doc → mcp-docs.server._markdown_to_html
  mcp-docs.server.render_doc → mcp-docs.server._page
  gh2mcp.gh2mcp.cli._cmd_status → scripts.test.print
  gh2mcp.gh2mcp.cli._cmd_sync → scripts.test.print
  gh2mcp.gh2mcp.cli._cmd_agent → scripts.test.print
  gh2mcp.gh2mcp.cli.main → gh2mcp.gh2mcp.cli.build_parser
  gh2mcp.gh2mcp.server.on_startup → gh2mcp.gh2mcp.server._periodic_sync
  gh2mcp.gh2mcp.sync.GitHubTokenSyncService.get_recent_repos → env2mcp.env2mcp.config.EnvConfig.set
  mcp-gateway.gateway_render.render_tool_text → env2mcp.env2mcp.config.EnvConfig.set
  mcp-gateway.gateway_render.render_chat_content → mcp-gateway.gateway_render.render_system_text
  mcp-gateway.gateway_render.render_chat_content → mcp-gateway.gateway_render.render_queued_text
  mcp-gateway.gateway_render.render_chat_content → mcp-gateway.gateway_render.render_analyze_text
  mcp-gateway.gateway_render.render_chat_content → mcp-gateway.gateway_render.render_refactor_text
  mcp-gateway.gateway_render.render_chat_content → mcp-gateway.gateway_render.render_tool_text
  llm-agent.agent_standalone.main → scripts.test.print
  llm-agent.agent.main → scripts.test.print
  mcp-skills.tool_run._ensure_tool_installed → mcp-skills.tool_run._truncate_text
  mcp-skills.tool_run._git_clone_or_update → mcp-skills.tool_run._inject_github_token
  mcp-skills.tool_run._git_clone_or_update → mcp-skills.tool_run._truncate_text
  mcp-skills.tool_run.collect_output_files → env2mcp.env2mcp.config.EnvConfig.set
  mcp-skills.tool_run.run_tool_against_repo → mcp-skills.tool_run._ensure_tool_installed
  mcp-skills.tool_run.run_tool_against_repo → mcp-skills.tool_run.collect_output_files
  mcp-skills.code_analysis.compute_repo_file_metrics → mcp-skills.code_analysis._should_skip_path
  mcp-skills.code_analysis.detect_repo_patterns → mcp-skills.code_analysis._should_skip_path
  mcp-skills.code_analysis.build_maintainability_recommendations → env2mcp.env2mcp.config.EnvConfig.set
  mcp-skills.code_analysis.build_maintainability_recommendations → semcod_mcp.doctor.DoctorReport.add
  mcp-skills.code_analysis.merge_recommendations → env2mcp.env2mcp.config.EnvConfig.set
  mcp-skills.server.MCPSkillsServer._sync_from_git_proxy → env2mcp.env2mcp.config.EnvConfig.set
  mcp-skills.server.MCPSkillsServer._compute_metrics_for_repo → mcp-skills.code_analysis.compute_repo_file_metrics
  mcp-skills.server.MCPSkillsServer._detect_code_patterns → mcp-skills.code_analysis.detect_repo_patterns
  mcp-skills.server.MCPSkillsServer._recommend_refactoring → mcp-skills.code_analysis.build_maintainability_recommendations
  mcp-skills.server.MCPSkillsServer._recommend_refactoring → mcp-skills.code_analysis.recommendations_payload
  mcp-skills.server.analyze_code_structure → mcp-skills.mcp_parse.parse_tool_result
  mcp-skills.server.compute_metrics → mcp-skills.mcp_parse.parse_tool_result
  mcp-skills.server.detect_patterns → mcp-skills.mcp_parse.parse_tool_result
  mcp-skills.server.recommend_refactoring → mcp-skills.mcp_parse.parse_tool_result
  mcp-skills.server.redsl_refactor → mcp-skills.code_analysis.compute_repo_file_metrics
  mcp-skills.server.redsl_refactor → mcp-skills.code_analysis.build_maintainability_recommendations
  mcp-skills.server.redsl_refactor → mcp-skills.code_analysis.merge_recommendations
  mcp-skills.server.run_tool_endpoint → mcp-skills.tool_run.run_tool_against_repo
  mcp-skills.server._run_tool_against_repo → mcp-skills.tool_run.run_tool_against_repo
  env2mcp.env2mcp.cli.cmd_github_login → env2mcp.env2mcp.github_cli.configure_github
  env2mcp.env2mcp.cli.cmd_github_login → scripts.test.print
  env2mcp.env2mcp.cli.cmd_github_status → scripts.test.print
  env2mcp.env2mcp.cli.cmd_github_logout → scripts.test.print
  env2mcp.env2mcp.cli.cmd_github_repos → scripts.test.print
  env2mcp.env2mcp.cli.cmd_env_show → scripts.test.print
```

## Intent

Initialize semcod MCP stack integration for Cursor, VS Code, Claude and other IDEs — init, doctor, validate, analyze.
