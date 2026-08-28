# Autonomiczny Agent Refaktoryzacji MCP

SUMD - Structured Unified Markdown Descriptor for AI-aware project refactorization

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Workflows](#workflows)
- [Call Graph](#call-graph)
- [Refactoring Analysis](#refactoring-analysis)
- [Intent](#intent)

## Metadata

- **name**: `mcp`
- **version**: `0.0.0`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: Makefile, app.doql.less, goal.yaml, .env.example, docker-compose.yml, project/(5 analysis files)

## Architecture

```
SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)
```

### DOQL Application Declaration (`app.doql.less`)

```less markpact:doql path=app.doql.less
// LESS format — define @variables here as needed

app {
  name: mcp;
  version: 0.1.0;
}

database[name="redis"] {
  type: redis;
  url: env.REDIS_URL;
}

interface[type="api"] {
  type: rest;
  framework: fastapi;
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
  step-1: run cmd=GH_TOKEN_VALUE=$$(gh auth token 2>/dev/null || true); \;
  step-2: run cmd=if [ -n "$$GH_TOKEN_VALUE" ]; then export GH_TOKEN="$$GH_TOKEN_VALUE"; fi; \;
  step-3: run cmd=$(COMPOSE) $(PROFILES) build;
  step-4: run cmd=GH_TOKEN_VALUE=$$(gh auth token 2>/dev/null || true); \;
  step-5: run cmd=if [ -n "$$GH_TOKEN_VALUE" ]; then export GH_TOKEN="$$GH_TOKEN_VALUE"; fi; \;
  step-6: run cmd=$(COMPOSE) $(PROFILES) up -d;
  step-7: run cmd=$(MAKE) smoke;
  step-8: run cmd=echo "";
  step-9: run cmd=echo "MCP Skills stack started:";
  step-10: run cmd=echo "  OpenWebUI:  http://localhost:$(PORT_OPENWEBUI)";
  step-11: run cmd=echo "  MCP WebUI:  http://localhost:$(PORT_WEBUI)";
  step-12: run cmd=echo "  MCP Docs:   http://localhost:$(PORT_DOCS)";
  step-13: run cmd=echo "  Gateway:    http://localhost:$(PORT_GATEWAY)";
  step-14: run cmd=echo "  Dashboard:  http://localhost:$(PORT_DASHBOARD)";
  step-15: run cmd=echo "  Git Proxy:  http://localhost:$(PORT_GIT_PROXY)";
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

deploy {
  target: docker-compose;
  compose_file: docker-compose.yml;
  ansible: true;
}

environment[name="local"] {
  runtime: docker-compose;
  env_file: .env;
}

environment[name="prod"] {
  runtime: docker-compose;
}
```

## Workflows

## Call Graph

*119 nodes · 129 edges · 17 modules · CC̄=3.7*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `chat_completions` *(in mcp-gateway.server)* | 31 ⚠ | 0 | 114 | **114** |
| `_render_tool_text` *(in mcp-gateway.server)* | 40 ⚠ | 1 | 80 | **81** |
| `_run_tool_against_repo` *(in mcp-skills.server)* | 37 ⚠ | 1 | 80 | **81** |
| `print` *(in scripts.test)* | 0 | 64 | 0 | **64** |
| `_render_refactor_text` *(in mcp-gateway.server)* | 17 ⚠ | 1 | 51 | **52** |
| `_render_system_text` *(in mcp-gateway.server)* | 27 ⚠ | 1 | 45 | **46** |
| `dispatch_skill` *(in mcp-gateway.server)* | 19 ⚠ | 2 | 41 | **43** |
| `_sync_from_git_proxy` *(in mcp-skills.server.MCPSkillsServer)* | 15 ⚠ | 0 | 39 | **39** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/semcod/mcp
# nodes: 119 | edges: 129 | modules: 17
# CC̄=3.7

HUBS[20]:
  mcp-gateway.server.chat_completions
    CC=31  in:0  out:114  total:114
  mcp-gateway.server._render_tool_text
    CC=40  in:1  out:80  total:81
  mcp-skills.server._run_tool_against_repo
    CC=37  in:1  out:80  total:81
  scripts.test.print
    CC=0  in:64  out:0  total:64
  mcp-gateway.server._render_refactor_text
    CC=17  in:1  out:51  total:52
  mcp-gateway.server._render_system_text
    CC=27  in:1  out:45  total:46
  mcp-gateway.server.dispatch_skill
    CC=19  in:2  out:41  total:43
  mcp-skills.server.MCPSkillsServer._sync_from_git_proxy
    CC=15  in:0  out:39  total:39
  gh2mcp.gh2mcp.sync.GitHubTokenSyncService.get_recent_repos
    CC=32  in:0  out:38  total:38
  mcp-webui.server.github_fetch_token_from_cli
    CC=16  in:0  out:32  total:32
  env2mcp.env2mcp.github_cli.configure_github
    CC=14  in:1  out:29  total:30
  mcp-gateway.server._resolve_repo_id_template
    CC=14  in:1  out:28  total:29
  mcp-gateway.server._summary_text
    CC=9  in:1  out:24  total:25
  mcp-gateway.server._render_analyze_text
    CC=10  in:1  out:23  total:24
  env2mcp.env2mcp.cli.cmd_github_status
    CC=11  in:0  out:22  total:22
  mcp-webui.server._get_github_config
    CC=16  in:7  out:15  total:22
  mcp-gateway.server._expect_json
    CC=3  in:18  out:4  total:22
  llm-agent.agent_standalone.main
    CC=2  in:0  out:21  total:21
  mcp-gateway.server._render_chat_content
    CC=13  in:4  out:16  total:20
  git2mcp.examples.03_agent_git2mcp.main
    CC=4  in:0  out:19  total:19

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
  mcp-gateway.server  [66 funcs]
    _ask_openrouter_github_qa  CC=12  out:15
    _create_github_pr  CC=3  out:14
    _expect_json  CC=3  out:4
    _extract_github_token_from_text  CC=2  out:2
    _extract_org_from_text  CC=9  out:9
    _extract_owner_from_repo_template  CC=4  out:3
    _extract_repo_template_expression  CC=3  out:3
    _get_default_github_repo  CC=7  out:7
    _get_last_used_repo  CC=8  out:6
    _get_most_used_repo  CC=8  out:5
  mcp-skills.server  [12 funcs]
    _sync_from_git_proxy  CC=15  out:39
    _collect_output_files  CC=9  out:17
    _ensure_tool_installed  CC=10  out:11
    _git_clone_or_update  CC=10  out:16
    _parse_tool_result  CC=3  out:1
    _run_tool_against_repo  CC=37  out:80
    _truncate_text  CC=3  out:4
    analyze_code_structure  CC=2  out:6
    compute_metrics  CC=2  out:6
    detect_patterns  CC=2  out:6
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

EDGES:
  dashboard.server.main → scripts.test.print
  llm-agent.agent_standalone.main → scripts.test.print
  llm-agent.agent.main → scripts.test.print
  git2mcp.examples.03_agent_git2mcp.main → scripts.test.print
  git2mcp.examples.02_fragment_sync_to_skills.main → scripts.test.print
  git2mcp.examples.01_sync_and_commit.main → scripts.test.print
  gh2mcp.gh2mcp.sync.GitHubTokenSyncService.get_recent_repos → env2mcp.env2mcp.config.EnvConfig.set
  mcp-docs.server.index → mcp-docs.server._page
  mcp-docs.server.render_doc → mcp-docs.server._safe_doc_path
  mcp-docs.server.render_doc → mcp-docs.server._markdown_to_html
  mcp-docs.server.render_doc → mcp-docs.server._page
  env2mcp.env2mcp.github_cli.configure_github → scripts.test.print
  env2mcp.env2mcp.cli.cmd_github_login → env2mcp.env2mcp.github_cli.configure_github
  env2mcp.env2mcp.cli.cmd_github_login → scripts.test.print
  env2mcp.env2mcp.cli.cmd_github_status → scripts.test.print
  env2mcp.env2mcp.cli.cmd_github_logout → scripts.test.print
  env2mcp.env2mcp.cli.cmd_github_repos → scripts.test.print
  env2mcp.env2mcp.cli.cmd_env_show → scripts.test.print
  env2mcp.env2mcp.cli.cmd_env_set → scripts.test.print
  env2mcp.env2mcp.cli.cmd_env_get → scripts.test.print
  gh2mcp.gh2mcp.cli._cmd_status → scripts.test.print
  gh2mcp.gh2mcp.cli._cmd_sync → scripts.test.print
  gh2mcp.gh2mcp.cli._cmd_agent → scripts.test.print
  gh2mcp.gh2mcp.cli.main → gh2mcp.gh2mcp.cli.build_parser
  mcp-webui.server.index → mcp-webui.server.gateway_headers
  mcp-webui.server._get_github_config → mcp-webui.server._resolve_github_token
  mcp-webui.server._get_github_config → mcp-webui.server._read_gh2mcp_status
  mcp-webui.server.github_page → mcp-webui.server._get_github_config
  mcp-webui.server.github_fetch_token_from_cli → mcp-webui.server._get_github_config
  mcp-webui.server._github_page_ctx → mcp-webui.server._get_github_config
  mcp-webui.server.github_clone → mcp-webui.server._normalize_github_url
  mcp-webui.server.github_clone → mcp-webui.server._resolve_github_token
  mcp-webui.server.github_clone → mcp-webui.server._get_github_config
  mcp-webui.server.github_create_repo → mcp-webui.server._resolve_github_token
  mcp-webui.server.github_create_repo → mcp-webui.server._get_github_config
  mcp-webui.server.github_sync → mcp-webui.server._get_github_config
  gh2mcp.gh2mcp.server.on_startup → gh2mcp.gh2mcp.server._periodic_sync
  mcp-skills.server.MCPSkillsServer._sync_from_git_proxy → env2mcp.env2mcp.config.EnvConfig.set
  mcp-skills.server._ensure_tool_installed → mcp-skills.server._truncate_text
  mcp-skills.server._git_clone_or_update → mcp-skills.server._truncate_text
  mcp-skills.server._collect_output_files → env2mcp.env2mcp.config.EnvConfig.set
  mcp-skills.server._run_tool_against_repo → mcp-skills.server._ensure_tool_installed
  mcp-skills.server._run_tool_against_repo → mcp-skills.server._collect_output_files
  mcp-skills.server.analyze_code_structure → mcp-skills.server._parse_tool_result
  mcp-skills.server.compute_metrics → mcp-skills.server._parse_tool_result
  mcp-skills.server.detect_patterns → mcp-skills.server._parse_tool_result
  mcp-skills.server.recommend_refactoring → mcp-skills.server._parse_tool_result
  mcp-skills.server.run_tool_endpoint → mcp-skills.server._run_tool_against_repo
  mcp-gateway.server._track_repo_usage → mcp-gateway.server._get_redis_client
  mcp-gateway.server._get_last_used_repo → mcp-gateway.server._get_redis_client
```

## Refactoring Analysis

*Pre-refactoring snapshot — use this section to identify targets. Generated from `project/` toon files.*

### Call Graph & Complexity (`project/calls.toon.yaml`)

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/semcod/mcp
# nodes: 119 | edges: 129 | modules: 17
# CC̄=3.7

HUBS[20]:
  mcp-gateway.server.chat_completions
    CC=31  in:0  out:114  total:114
  mcp-gateway.server._render_tool_text
    CC=40  in:1  out:80  total:81
  mcp-skills.server._run_tool_against_repo
    CC=37  in:1  out:80  total:81
  scripts.test.print
    CC=0  in:64  out:0  total:64
  mcp-gateway.server._render_refactor_text
    CC=17  in:1  out:51  total:52
  mcp-gateway.server._render_system_text
    CC=27  in:1  out:45  total:46
  mcp-gateway.server.dispatch_skill
    CC=19  in:2  out:41  total:43
  mcp-skills.server.MCPSkillsServer._sync_from_git_proxy
    CC=15  in:0  out:39  total:39
  gh2mcp.gh2mcp.sync.GitHubTokenSyncService.get_recent_repos
    CC=32  in:0  out:38  total:38
  mcp-webui.server.github_fetch_token_from_cli
    CC=16  in:0  out:32  total:32
  env2mcp.env2mcp.github_cli.configure_github
    CC=14  in:1  out:29  total:30
  mcp-gateway.server._resolve_repo_id_template
    CC=14  in:1  out:28  total:29
  mcp-gateway.server._summary_text
    CC=9  in:1  out:24  total:25
  mcp-gateway.server._render_analyze_text
    CC=10  in:1  out:23  total:24
  env2mcp.env2mcp.cli.cmd_github_status
    CC=11  in:0  out:22  total:22
  mcp-webui.server._get_github_config
    CC=16  in:7  out:15  total:22
  mcp-gateway.server._expect_json
    CC=3  in:18  out:4  total:22
  llm-agent.agent_standalone.main
    CC=2  in:0  out:21  total:21
  mcp-gateway.server._render_chat_content
    CC=13  in:4  out:16  total:20
  git2mcp.examples.03_agent_git2mcp.main
    CC=4  in:0  out:19  total:19

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
  mcp-gateway.server  [66 funcs]
    _ask_openrouter_github_qa  CC=12  out:15
    _create_github_pr  CC=3  out:14
    _expect_json  CC=3  out:4
    _extract_github_token_from_text  CC=2  out:2
    _extract_org_from_text  CC=9  out:9
    _extract_owner_from_repo_template  CC=4  out:3
    _extract_repo_template_expression  CC=3  out:3
    _get_default_github_repo  CC=7  out:7
    _get_last_used_repo  CC=8  out:6
    _get_most_used_repo  CC=8  out:5
  mcp-skills.server  [12 funcs]
    _sync_from_git_proxy  CC=15  out:39
    _collect_output_files  CC=9  out:17
    _ensure_tool_installed  CC=10  out:11
    _git_clone_or_update  CC=10  out:16
    _parse_tool_result  CC=3  out:1
    _run_tool_against_repo  CC=37  out:80
    _truncate_text  CC=3  out:4
    analyze_code_structure  CC=2  out:6
    compute_metrics  CC=2  out:6
    detect_patterns  CC=2  out:6
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

EDGES:
  dashboard.server.main → scripts.test.print
  llm-agent.agent_standalone.main → scripts.test.print
  llm-agent.agent.main → scripts.test.print
  git2mcp.examples.03_agent_git2mcp.main → scripts.test.print
  git2mcp.examples.02_fragment_sync_to_skills.main → scripts.test.print
  git2mcp.examples.01_sync_and_commit.main → scripts.test.print
  gh2mcp.gh2mcp.sync.GitHubTokenSyncService.get_recent_repos → env2mcp.env2mcp.config.EnvConfig.set
  mcp-docs.server.index → mcp-docs.server._page
  mcp-docs.server.render_doc → mcp-docs.server._safe_doc_path
  mcp-docs.server.render_doc → mcp-docs.server._markdown_to_html
  mcp-docs.server.render_doc → mcp-docs.server._page
  env2mcp.env2mcp.github_cli.configure_github → scripts.test.print
  env2mcp.env2mcp.cli.cmd_github_login → env2mcp.env2mcp.github_cli.configure_github
  env2mcp.env2mcp.cli.cmd_github_login → scripts.test.print
  env2mcp.env2mcp.cli.cmd_github_status → scripts.test.print
  env2mcp.env2mcp.cli.cmd_github_logout → scripts.test.print
  env2mcp.env2mcp.cli.cmd_github_repos → scripts.test.print
  env2mcp.env2mcp.cli.cmd_env_show → scripts.test.print
  env2mcp.env2mcp.cli.cmd_env_set → scripts.test.print
  env2mcp.env2mcp.cli.cmd_env_get → scripts.test.print
  gh2mcp.gh2mcp.cli._cmd_status → scripts.test.print
  gh2mcp.gh2mcp.cli._cmd_sync → scripts.test.print
  gh2mcp.gh2mcp.cli._cmd_agent → scripts.test.print
  gh2mcp.gh2mcp.cli.main → gh2mcp.gh2mcp.cli.build_parser
  mcp-webui.server.index → mcp-webui.server.gateway_headers
  mcp-webui.server._get_github_config → mcp-webui.server._resolve_github_token
  mcp-webui.server._get_github_config → mcp-webui.server._read_gh2mcp_status
  mcp-webui.server.github_page → mcp-webui.server._get_github_config
  mcp-webui.server.github_fetch_token_from_cli → mcp-webui.server._get_github_config
  mcp-webui.server._github_page_ctx → mcp-webui.server._get_github_config
  mcp-webui.server.github_clone → mcp-webui.server._normalize_github_url
  mcp-webui.server.github_clone → mcp-webui.server._resolve_github_token
  mcp-webui.server.github_clone → mcp-webui.server._get_github_config
  mcp-webui.server.github_create_repo → mcp-webui.server._resolve_github_token
  mcp-webui.server.github_create_repo → mcp-webui.server._get_github_config
  mcp-webui.server.github_sync → mcp-webui.server._get_github_config
  gh2mcp.gh2mcp.server.on_startup → gh2mcp.gh2mcp.server._periodic_sync
  mcp-skills.server.MCPSkillsServer._sync_from_git_proxy → env2mcp.env2mcp.config.EnvConfig.set
  mcp-skills.server._ensure_tool_installed → mcp-skills.server._truncate_text
  mcp-skills.server._git_clone_or_update → mcp-skills.server._truncate_text
  mcp-skills.server._collect_output_files → env2mcp.env2mcp.config.EnvConfig.set
  mcp-skills.server._run_tool_against_repo → mcp-skills.server._ensure_tool_installed
  mcp-skills.server._run_tool_against_repo → mcp-skills.server._collect_output_files
  mcp-skills.server.analyze_code_structure → mcp-skills.server._parse_tool_result
  mcp-skills.server.compute_metrics → mcp-skills.server._parse_tool_result
  mcp-skills.server.detect_patterns → mcp-skills.server._parse_tool_result
  mcp-skills.server.recommend_refactoring → mcp-skills.server._parse_tool_result
  mcp-skills.server.run_tool_endpoint → mcp-skills.server._run_tool_against_repo
  mcp-gateway.server._track_repo_usage → mcp-gateway.server._get_redis_client
  mcp-gateway.server._get_last_used_repo → mcp-gateway.server._get_redis_client
```

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 87f 15354L | python:29,yaml:23,txt:8,shell:7,yml:7,toml:3,ini:1 | 2026-05-03
# CC̄=3.7 | critical:22/422 | dups:0 | cycles:0

HEALTH[20]:
  🔴 GOD   mcp-skills/server.py = 1462L, 8 classes, 29m, max CC=37
  🟡 CC    compute_metrics_for_repo CC=15 (limit:15)
  🟡 CC    detect_code_patterns CC=15 (limit:15)
  🟡 CC    compute_metrics CC=15 (limit:15)
  🟡 CC    get_last_pushed_repo CC=23 (limit:15)
  🟡 CC    get_recent_repos CC=32 (limit:15)
  🟡 CC    sync_token CC=20 (limit:15)
  🟡 CC    save CC=20 (limit:15)
  🟡 CC    _get_github_config CC=16 (limit:15)
  🟡 CC    github_fetch_token_from_cli CC=16 (limit:15)
  🟡 CC    _sync_from_git_proxy CC=15 (limit:15)
  🟡 CC    _compute_metrics_for_repo CC=15 (limit:15)
  🟡 CC    _recommend_refactoring CC=15 (limit:15)
  🟡 CC    _run_tool_against_repo CC=37 (limit:15)
  🟡 CC    _is_last_pushed_repo_template CC=15 (limit:15)
  🟡 CC    _is_github_token_save_command CC=15 (limit:15)
  🟡 CC    _is_repo_list_command CC=23 (limit:15)
  🟡 CC    parse_tool_intent CC=23 (limit:15)
  🟡 CC    _render_system_text CC=27 (limit:15)
  🟡 CC    _render_refactor_text CC=17 (limit:15)

REFACTOR[2]:
  1. split mcp-skills/server.py  (god module)
  2. split 19 high-CC methods  (CC>15)

PIPELINES[211]:
  [1] Src [end_headers]: end_headers
      PURITY: 100% pure
  [2] Src [do_GET]: do_GET
      PURITY: 100% pure
  [3] Src [serve_file]: serve_file
      PURITY: 100% pure
  [4] Src [send_json]: send_json
      PURITY: 100% pure
  [5] Src [get_content_type]: get_content_type
      PURITY: 100% pure

LAYERS:
  mcp-skills/                     CC̄=7.2    ←in:0  →out:2
  │ !! server                    1462L  8C   29m  CC=37     ←0
  │ requirements.txt             5L  0C    0m  CC=0.0    ←0
  │ Dockerfile                   0L  0C    0m  CC=0.0    ←0
  │
  mcp-gateway/                    CC̄=6.8    ←in:0  →out:8  !! split
  │ !! server                    2908L  2C   86m  CC=40     ←1
  │ worker                      18L  0C    1m  CC=2      ←0
  │ default.yaml                16L  0C    0m  CC=0.0    ←0
  │ requirements.txt             9L  0C    0m  CC=0.0    ←0
  │ Dockerfile                   0L  0C    0m  CC=0.0    ←0
  │
  gh2mcp/                         CC̄=5.4    ←in:0  →out:0
  │ !! sync                       430L  1C    7m  CC=32     ←0
  │ server                     110L  5C   10m  CC=3      ←0
  │ cli                         68L  0C    5m  CC=3      ←0
  │ pyproject.toml              52L  0C    0m  CC=0.0    ←0
  │ goal.yaml                    4L  0C    0m  CC=0.0    ←0
  │ __init__                     4L  0C    0m  CC=0.0    ←0
  │ Dockerfile                   0L  0C    0m  CC=0.0    ←0
  │
  env2mcp/                        CC̄=5.0    ←in:0  →out:0
  │ github_cli                 330L  1C   11m  CC=14     ←1
  │ cli                        252L  0C    8m  CC=11     ←0
  │ !! config                     134L  1C   12m  CC=20     ←3
  │ pyproject.toml              68L  0C    0m  CC=0.0    ←0
  │ __init__                    13L  0C    0m  CC=0.0    ←0
  │
  mcp-webui/                      CC̄=4.9    ←in:0  →out:0
  │ !! server                     621L  0C   19m  CC=16     ←0
  │ requirements.txt             5L  0C    0m  CC=0.0    ←0
  │ Dockerfile                   0L  0C    0m  CC=0.0    ←0
  │
  llm-agent/                      CC̄=4.0    ←in:0  →out:10  !! split
  │ !! agent_standalone           540L  3C   14m  CC=15     ←0
  │ agent                      375L  2C   13m  CC=4      ←0
  │ !! agent_git2mcp              361L  3C   13m  CC=15     ←0
  │ requirements.txt             5L  0C    0m  CC=0.0    ←0
  │ Dockerfile                   0L  0C    0m  CC=0.0    ←0
  │
  dashboard/                      CC̄=3.2    ←in:0  →out:8  !! split
  │ server                     189L  2C   10m  CC=8      ←0
  │ Dockerfile                   0L  0C    0m  CC=0.0    ←0
  │
  git2mcp/                        CC̄=2.6    ←in:0  →out:0
  │ proxy                      437L  1C   21m  CC=12     ←0
  │ 05_local_iterate           126L  0C    1m  CC=5      ←0
  │ planfile.yaml              123L  0C    0m  CC=0.0    ←0
  │ 04_dry_run_vs_execute      115L  0C    2m  CC=3      ←0
  │ client                     104L  1C   20m  CC=4      ←0
  │ prefact.yaml                91L  0C    0m  CC=0.0    ←0
  │ 02_fragment_sync_to_skills    68L  0C    1m  CC=1      ←0
  │ 01_sync_and_commit          62L  0C    1m  CC=1      ←0
  │ pyproject.toml              57L  0C    0m  CC=0.0    ←0
  │ 03_agent_git2mcp            55L  0C    1m  CC=4      ←0
  │ generated-from-pytests.testql.toon.yaml    55L  0C    0m  CC=0.0    ←0
  │ prompt.txt                  49L  0C    0m  CC=0.0    ←0
  │ project.sh                  47L  0C    0m  CC=0.0    ←0
  │ analysis.toon.yaml          43L  0C    0m  CC=0.0    ←0
  │ evolution.toon.yaml         39L  0C    0m  CC=0.0    ←0
  │ project.toon.yaml           39L  0C    0m  CC=0.0    ←0
  │ map.toon.yaml               33L  0C    4m  CC=0.0    ←0
  │ calls.yaml                  29L  0C    0m  CC=0.0    ←0
  │ generated-api-integration.testql.toon.yaml    18L  0C    0m  CC=0.0    ←0
  │ duplication.toon.yaml        9L  0C    0m  CC=0.0    ←0
  │ calls.toon.yaml              9L  0C    0m  CC=0.0    ←0
  │ proxy                        3L  0C    0m  CC=0.0    ←0
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │ client                       3L  0C    0m  CC=0.0    ←0
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │
  mcp-git-proxy/                  CC̄=2.5    ←in:0  →out:0
  │ server                     443L  19C   22m  CC=9      ←0
  │ requirements.txt             4L  0C    0m  CC=0.0    ←0
  │ Dockerfile                   0L  0C    0m  CC=0.0    ←0
  │
  mcp-docs/                       CC̄=2.1    ←in:0  →out:0
  │ server                     273L  0C    7m  CC=4      ←0
  │ requirements.txt             3L  0C    0m  CC=0.0    ←0
  │ Dockerfile                   0L  0C    0m  CC=0.0    ←0
  │
  scripts/                        CC̄=0.0    ←in:64  →out:0
  │ test.sh                    404L  1C   14m  CC=0.0    ←12
  │ generate_demo_repos.sh     396L  0C   18m  CC=0.0    ←0
  │ refactor-last-repo.sh      312L  0C   12m  CC=0.0    ←0
  │ deploy.sh                  135L  0C    7m  CC=0.0    ←0
  │
  project/                        CC̄=0.0    ←in:0  →out:0
  │ calls.yaml                 316L  0C    0m  CC=0.0    ←0
  │ map.toon.yaml              191L  0C   52m  CC=0.0    ←0
  │ analysis.toon.yaml         120L  0C    0m  CC=0.0    ←0
  │ evolution.toon.yaml         73L  0C    0m  CC=0.0    ←0
  │ calls.toon.yaml             66L  0C    0m  CC=0.0    ←0
  │ duplication.toon.yaml       62L  0C    0m  CC=0.0    ←0
  │ project.toon.yaml           51L  0C    0m  CC=0.0    ←0
  │ prompt.txt                  49L  0C    0m  CC=0.0    ←0
  │
  ansible/                        CC̄=0.0    ←in:0  →out:0
  │ !! e2e-gh2mcp.yml             520L  0C    1m  CC=0.0    ←0
  │ e2e-tools.yml              285L  0C    0m  CC=0.0    ←0
  │ e2e-github-qa.yml          232L  0C    0m  CC=0.0    ←0
  │ test-github-integration.yml   189L  0C    0m  CC=0.0    ←0
  │ e2e-docker-stack.yml       172L  0C    0m  CC=0.0    ←0
  │ inventory.ini                2L  0C    0m  CC=0.0    ←0
  │
  ./                              CC̄=0.0    ←in:0  →out:0
  │ !! goal.yaml                  510L  0C    0m  CC=0.0    ←0
  │ planfile.yaml              461L  0C    0m  CC=0.0    ←0
  │ docker-compose.yml         313L  0C    0m  CC=0.0    ←0
  │ prefact.yaml                91L  0C    0m  CC=0.0    ←0
  │ project.sh                  47L  0C    0m  CC=0.0    ←0
  │ docker-compose.prod.yml     34L  0C    0m  CC=0.0    ←0
  │ tree.sh                      1L  0C    0m  CC=0.0    ←0
  │ Makefile                     0L  0C    0m  CC=0.0    ←0
  │
  ── zero ──
     Makefile                                  0L
     dashboard/Dockerfile                      0L
     gh2mcp/Dockerfile                         0L
     llm-agent/Dockerfile                      0L
     mcp-docs/Dockerfile                       0L
     mcp-gateway/Dockerfile                    0L
     mcp-git-proxy/Dockerfile                  0L
     mcp-skills/Dockerfile                     0L
     mcp-webui/Dockerfile                      0L

COUPLING:
                             scripts   env2mcp.env2mcp         llm-agent         dashboard  git2mcp.examples       mcp-gateway     gh2mcp.gh2mcp        mcp-skills
           scripts                ──               ←34               ←10                ←8                ←8                                  ←4                    hub
   env2mcp.env2mcp                34                ──                                                                      ←8                ←1                ←2  hub
         llm-agent                10                                  ──                                                                                            !! fan-out
         dashboard                 8                                                    ──                                                                          !! fan-out
  git2mcp.examples                 8                                                                      ──                                                        !! fan-out
       mcp-gateway                                   8                                                                      ──                                      !! fan-out
     gh2mcp.gh2mcp                 4                 1                                                                                        ──                  
        mcp-skills                                   2                                                                                                          ──
  CYCLES: none
  HUB: scripts/ (fan-in=64)
  HUB: env2mcp.env2mcp/ (fan-in=11)
  SMELL: mcp-gateway/ fan-out=8 → split needed
  SMELL: dashboard/ fan-out=8 → split needed
  SMELL: git2mcp.examples/ fan-out=8 → split needed
  SMELL: env2mcp.env2mcp/ fan-out=34 → split needed
  SMELL: llm-agent/ fan-out=10 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 6 groups | 32f 8868L | 2026-05-03

SUMMARY:
  files_scanned: 32
  total_lines:   8868
  dup_groups:    6
  dup_fragments: 16
  saved_lines:   98
  scan_ms:       7442

HOTSPOTS[5] (files with most duplication):
  llm-agent/agent.py  dup=41L  groups=2  frags=2  (0.5%)
  llm-agent/agent_standalone.py  dup=41L  groups=2  frags=2  (0.5%)
  mcp-skills/server.py  dup=32L  groups=1  frags=4  (0.4%)
  mcp-git-proxy/server.py  dup=30L  groups=2  frags=6  (0.3%)
  mcp-gateway/server.py  dup=26L  groups=1  frags=2  (0.3%)

DUPLICATES[6] (ranked by impact):
  [aea4a7a9526a2ad3]   EXAC  _mock_llm_response  L=30 N=2 saved=30 sim=1.00
      llm-agent/agent.py:232-261  (_mock_llm_response)
      llm-agent/agent_standalone.py:405-434  (_mock_llm_response)
  [467fd96667a253a0]   STRU  analyze_code_structure  L=8 N=4 saved=24 sim=1.00
      mcp-skills/server.py:1288-1295  (analyze_code_structure)
      mcp-skills/server.py:1299-1306  (compute_metrics)
      mcp-skills/server.py:1310-1317  (detect_patterns)
      mcp-skills/server.py:1321-1328  (recommend_refactoring)
  [d7672c451ace4405]   STRU  worktree_diff  L=5 N=4 saved=15 sim=1.00
      mcp-git-proxy/server.py:230-234  (worktree_diff)
      mcp-git-proxy/server.py:246-250  (stage)
      mcp-git-proxy/server.py:254-258  (stash_save)
      mcp-git-proxy/server.py:278-282  (checkpoint_create)
  [bf41aa98652b1a64]   STRU  _get_state_redis_client  L=13 N=2 saved=13 sim=1.00
      mcp-gateway/server.py:2013-2025  (_get_state_redis_client)
      mcp-gateway/server.py:2028-2040  (_get_rq_redis_client)
  [5865906155183adc]   EXAC  _mock_llm_response_from_prompt  L=11 N=2 saved=11 sim=1.00
      llm-agent/agent.py:263-273  (_mock_llm_response_from_prompt)
      llm-agent/agent_standalone.py:436-446  (_mock_llm_response_from_prompt)
  [796eb26d67b6a889]   STRU  push  L=5 N=2 saved=5 sim=1.00
      mcp-git-proxy/server.py:196-200  (push)
      mcp-git-proxy/server.py:270-274  (branch_draft)

REFACTOR[6] (ranked by priority):
  [1] ○ extract_class      → llm-agent/utils/_mock_llm_response.py
      WHY: 2 occurrences of 30-line block across 2 files — saves 30 lines
      FILES: llm-agent/agent.py, llm-agent/agent_standalone.py
  [2] ○ extract_function   → mcp-skills/utils/analyze_code_structure.py
      WHY: 4 occurrences of 8-line block across 1 files — saves 24 lines
      FILES: mcp-skills/server.py
  [3] ○ extract_function   → mcp-git-proxy/utils/worktree_diff.py
      WHY: 4 occurrences of 5-line block across 1 files — saves 15 lines
      FILES: mcp-git-proxy/server.py
  [4] ○ extract_function   → mcp-gateway/utils/_get_state_redis_client.py
      WHY: 2 occurrences of 13-line block across 1 files — saves 13 lines
      FILES: mcp-gateway/server.py
  [5] ○ extract_class      → llm-agent/utils/_mock_llm_response_from_prompt.py
      WHY: 2 occurrences of 11-line block across 2 files — saves 11 lines
      FILES: llm-agent/agent.py, llm-agent/agent_standalone.py
  [6] ○ extract_function   → mcp-git-proxy/utils/push.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: mcp-git-proxy/server.py

QUICK_WINS[5] (low risk, high savings — do first):
  [1] extract_class      saved=30L  → llm-agent/utils/_mock_llm_response.py
      FILES: agent.py, agent_standalone.py
  [2] extract_function   saved=24L  → mcp-skills/utils/analyze_code_structure.py
      FILES: server.py
  [3] extract_function   saved=15L  → mcp-git-proxy/utils/worktree_diff.py
      FILES: server.py
  [4] extract_function   saved=13L  → mcp-gateway/utils/_get_state_redis_client.py
      FILES: server.py
  [5] extract_class      saved=11L  → llm-agent/utils/_mock_llm_response_from_prompt.py
      FILES: agent.py, agent_standalone.py

EFFORT_ESTIMATE (total ≈ 3.3h):
  medium _mock_llm_response                  saved=30L  ~60min
  medium analyze_code_structure              saved=24L  ~48min
  medium worktree_diff                       saved=15L  ~30min
  easy   _get_state_redis_client             saved=13L  ~26min
  easy   _mock_llm_response_from_prompt      saved=11L  ~22min
  easy   push                                saved=5L  ~10min

METRICS-TARGET:
  dup_groups:  6 → 0
  saved_lines: 98 lines recoverable
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 365 func | 21f | 2026-05-03

NEXT[10] (ranked by impact):
  [1] !! SPLIT           mcp-gateway/server.py
      WHY: 2908L, 2 classes, max CC=40
      EFFORT: ~4h  IMPACT: 116320

  [2] !! SPLIT           mcp-skills/server.py
      WHY: 1462L, 8 classes, max CC=37
      EFFORT: ~4h  IMPACT: 54094

  [3] !! SPLIT-FUNC      chat_completions  CC=31  fan=56
      WHY: CC=31 exceeds 15
      EFFORT: ~1h  IMPACT: 1736

  [4] !! SPLIT-FUNC      _run_tool_against_repo  CC=37  fan=41
      WHY: CC=37 exceeds 15
      EFFORT: ~1h  IMPACT: 1517

  [5] !! SPLIT-FUNC      GitHubTokenSyncService.get_recent_repos  CC=32  fan=24
      WHY: CC=32 exceeds 15
      EFFORT: ~1h  IMPACT: 768

  [6] !! SPLIT-FUNC      _render_tool_text  CC=40  fan=15
      WHY: CC=40 exceeds 15
      EFFORT: ~1h  IMPACT: 600

  [7] !  SPLIT-FUNC      dispatch_skill  CC=19  fan=26
      WHY: CC=19 exceeds 15
      EFFORT: ~1h  IMPACT: 494

  [8] !  SPLIT-FUNC      MCPSkillsServer._sync_from_git_proxy  CC=15  fan=30
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 450

  [9] !  SPLIT-FUNC      GitHubTokenSyncService.get_last_pushed_repo  CC=23  fan=18
      WHY: CC=23 exceeds 15
      EFFORT: ~1h  IMPACT: 414

  [10] !  SPLIT-FUNC      parse_tool_intent  CC=23  fan=16
      WHY: CC=23 exceeds 15
      EFFORT: ~1h  IMPACT: 368


RISKS[3]:
  ⚠ Splitting mcp-gateway/server.py may break 86 import paths
  ⚠ Splitting mcp-skills/server.py may break 29 import paths
  ⚠ Splitting mcp-gateway/test_gateway_token_command.py may break 0 import paths

METRICS-TARGET:
  CC̄:          4.2 → ≤2.9
  max-CC:      40 → ≤20
  god-modules: 5 → 0
  high-CC(≥15): 22 → ≤11
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
  prev CC̄=3.4 → now CC̄=4.2
```

## Intent

Autonomiczny Agent Refaktoryzacji MCP
