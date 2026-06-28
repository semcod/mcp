# Autonomiczny Agent Refaktoryzacji MCP

SUMD - Structured Unified Markdown Descriptor for AI-aware project refactorization

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Workflows](#workflows)
- [Dependencies](#dependencies)
- [Call Graph](#call-graph)
- [Refactoring Analysis](#refactoring-analysis)
- [Intent](#intent)

## Metadata

- **name**: `semcod-mcp`
- **version**: `0.1.4`
- **python_requires**: `>=3.10`
- **license**: Apache-2.0
- **ai_model**: `openrouter/qwen/qwen3-coder-next`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: pyproject.toml, Makefile, app.doql.less, goal.yaml, .env.example, docker-compose.yml, project/(5 analysis files)

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

## Workflows

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

## Refactoring Analysis

*Pre-refactoring snapshot — use this section to identify targets. Generated from `project/` toon files.*

### Call Graph & Complexity (`project/calls.toon.yaml`)

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

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 101f 18254L | python:56,yaml:9,yml:7,shell:7,txt:6,toml:4,json:2,ini:1 | 2026-06-18
# generated in 0.02s
# CC̅=4.5 | critical:25/446 | dups:0 | cycles:0

HEALTH[20]:
  🟡 CC    get_last_pushed_repo CC=23 (limit:15)
  🟡 CC    get_recent_repos CC=32 (limit:15)
  🟡 CC    sync_token CC=20 (limit:15)
  🟡 CC    render_system_text CC=27 (limit:15)
  🟡 CC    render_refactor_text CC=17 (limit:15)
  🟡 CC    render_tool_text CC=40 (limit:15)
  🟡 CC    compute_metrics_for_repo CC=15 (limit:15)
  🟡 CC    detect_code_patterns CC=15 (limit:15)
  🟡 CC    compute_metrics CC=15 (limit:15)
  🟡 CC    run_tool_against_repo CC=37 (limit:15)
  🟡 CC    compute_repo_file_metrics CC=15 (limit:15)
  🟡 CC    build_maintainability_recommendations CC=24 (limit:15)
  🟡 CC    _sync_from_git_proxy CC=15 (limit:15)
  🟡 CC    save CC=20 (limit:15)
  🟡 CC    _get_github_config CC=16 (limit:15)
  🟡 CC    github_fetch_token_from_cli CC=16 (limit:15)
  🟡 CC    run_deinit CC=15 (limit:15)
  🟡 CC    is_github_token_save_command CC=15 (limit:15)
  🟡 CC    is_repo_list_command CC=23 (limit:15)
  🟡 CC    run_chat_workflow CC=43 (limit:15)

REFACTOR[1]:
  1. split 20 high-CC methods  (CC>15)

PIPELINES[225]:
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
  [6] Src [get_status]: get_status
      PURITY: 100% pure
  [7] Src [get_analyses]: get_analyses
      PURITY: 100% pure
  [8] Src [get_analysis]: get_analysis
      PURITY: 100% pure
  [9] Src [get_repos]: get_repos
      PURITY: 100% pure
  [10] Src [main]: main → print
      PURITY: 100% pure
  [11] Src [health]: health
      PURITY: 100% pure
  [12] Src [list_repos]: list_repos
      PURITY: 100% pure
  [13] Src [sync_repo]: sync_repo
      PURITY: 100% pure
  [14] Src [export_fragments]: export_fragments
      PURITY: 100% pure
  [15] Src [export_package]: export_package
      PURITY: 100% pure
  [16] Src [import_package]: import_package
      PURITY: 100% pure
  [17] Src [commit]: commit
      PURITY: 100% pure
  [18] Src [push]: push
      PURITY: 100% pure
  [19] Src [reset]: reset
      PURITY: 100% pure
  [20] Src [worktree_write]: worktree_write
      PURITY: 100% pure
  [21] Src [worktree_read]: worktree_read
      PURITY: 100% pure
  [22] Src [worktree_diff]: worktree_diff
      PURITY: 100% pure
  [23] Src [patch_apply]: patch_apply
      PURITY: 100% pure
  [24] Src [stage]: stage
      PURITY: 100% pure
  [25] Src [stash_save]: stash_save
      PURITY: 100% pure
  [26] Src [stash_pop]: stash_pop
      PURITY: 100% pure
  [27] Src [branch_draft]: branch_draft
      PURITY: 100% pure
  [28] Src [checkpoint_create]: checkpoint_create
      PURITY: 100% pure
  [29] Src [checkpoint_restore]: checkpoint_restore
      PURITY: 100% pure
  [30] Src [run_tests]: run_tests
      PURITY: 100% pure
  [31] Src [github_create_repo]: github_create_repo
      PURITY: 100% pure
  [32] Src [sync_pull]: sync_pull
      PURITY: 100% pure
  [33] Src [health]: health
      PURITY: 100% pure
  [34] Src [list_docs]: list_docs
      PURITY: 100% pure
  [35] Src [index]: index → _page
      PURITY: 100% pure
  [36] Src [render_doc]: render_doc → _safe_doc_path
      PURITY: 100% pure
  [37] Src [_cmd_status]: _cmd_status → print
      PURITY: 100% pure
  [38] Src [_cmd_sync]: _cmd_sync → print
      PURITY: 100% pure
  [39] Src [_cmd_agent]: _cmd_agent → print
      PURITY: 100% pure
  [40] Src [main]: main → build_parser
      PURITY: 100% pure
  [41] Src [on_startup]: on_startup → _periodic_sync
      PURITY: 100% pure
  [42] Src [on_shutdown]: on_shutdown
      PURITY: 100% pure
  [43] Src [health]: health
      PURITY: 100% pure
  [44] Src [status]: status
      PURITY: 100% pure
  [45] Src [sync_token]: sync_token
      PURITY: 100% pure
  [46] Src [set_org]: set_org
      PURITY: 100% pure
  [47] Src [list_orgs]: list_orgs
      PURITY: 100% pure
  [48] Src [last_pushed_repo]: last_pushed_repo
      PURITY: 100% pure
  [49] Src [recent_repos]: recent_repos
      PURITY: 100% pure
  [50] Src [__init__]: __init__
      PURITY: 100% pure

LAYERS:
  mcp-gateway/                    CC̄=6.8    ←in:0  →out:9  !! split
  │ !! server                    1206L  2C   29m  CC=31     ←1
  │ !! gateway_chat               563L  0C    2m  CC=43     ←0
  │ !! gateway_render             502L  0C   13m  CC=40     ←3
  │ !! gateway_github             432L  0C   18m  CC=23     ←3
  │ gateway_gh2mcp             398L  0C   14m  CC=14     ←1
  │ !! gateway_prompt             271L  0C   10m  CC=23     ←5
  │ gateway_skills             263L  0C    7m  CC=13     ←3
  │ !! gateway_dispatch           248L  0C    1m  CC=19     ←3
  │ gateway_jobs               175L  0C    9m  CC=5      ←2
  │ gateway_tenants            141L  0C    9m  CC=8      ←1
  │ gateway_config              56L  0C    0m  CC=0.0    ←0
  │ gateway_models              34L  2C    0m  CC=0.0    ←0
  │ worker                      18L  0C    1m  CC=2      ←0
  │ default.yaml                16L  0C    0m  CC=0.0    ←0
  │ Dockerfile                  15L  0C    0m  CC=0.0    ←0
  │ requirements.txt             9L  0C    0m  CC=0.0    ←0
  │
  mcp-skills/                     CC̄=6.5    ←in:0  →out:10  !! split
  │ !! server                     691L  1C   22m  CC=15     ←0
  │ !! tool_run                   388L  0C    7m  CC=37     ←1
  │ !! code_analysis              282L  0C    6m  CC=24     ←1
  │ tools_registry             150L  0C    0m  CC=0.0    ←0
  │ redsl_runner                71L  0C    1m  CC=14     ←1
  │ http_models                 60L  7C    0m  CC=0.0    ←0
  │ Dockerfile                  37L  0C    0m  CC=0.0    ←0
  │ mcp_parse                   18L  0C    1m  CC=3      ←1
  │ requirements.txt             5L  0C    0m  CC=0.0    ←0
  │
  gh2mcp/                         CC̄=5.4    ←in:0  →out:0
  │ !! sync                       430L  1C    7m  CC=32     ←0
  │ server                     110L  5C   10m  CC=3      ←0
  │ cli                         68L  0C    5m  CC=3      ←0
  │ pyproject.toml              52L  0C    0m  CC=0.0    ←0
  │ Dockerfile                  18L  0C    0m  CC=0.0    ←0
  │ goal.yaml                    4L  0C    0m  CC=0.0    ←0
  │ __init__                     4L  0C    0m  CC=0.0    ←0
  │
  env2mcp/                        CC̄=5.1    ←in:0  →out:0
  │ github_cli                 330L  1C   11m  CC=14     ←1
  │ cli                        252L  0C    8m  CC=11     ←0
  │ !! config                     158L  1C   13m  CC=20     ←11
  │ pyproject.toml              68L  0C    0m  CC=0.0    ←0
  │ __init__                    13L  0C    0m  CC=0.0    ←0
  │
  semcod_mcp/                     CC̄=5.0    ←in:6  →out:3
  │ merge                      216L  0C   12m  CC=10     ←4
  │ init_cmd                   176L  1C    4m  CC=14     ←1
  │ templates                  162L  0C    8m  CC=8      ←4
  │ !! deinit_cmd                 137L  1C    3m  CC=15     ←1
  │ cli                        132L  0C    6m  CC=6      ←0
  │ doctor                     116L  2C    3m  CC=11     ←2
  │ analyze                    105L  1C    1m  CC=12     ←1
  │ validate                   101L  2C    4m  CC=13     ←1
  │ paths                       70L  0C    5m  CC=10     ←6
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │
  mcp-webui/                      CC̄=4.9    ←in:0  →out:0
  │ !! server                     621L  0C   19m  CC=16     ←0
  │ Dockerfile                  15L  0C    0m  CC=0.0    ←0
  │ requirements.txt             5L  0C    0m  CC=0.0    ←0
  │
  llm-agent/                      CC̄=4.0    ←in:0  →out:10  !! split
  │ !! agent_standalone           540L  3C   14m  CC=15     ←0
  │ agent                      375L  2C   13m  CC=4      ←0
  │ !! agent_git2mcp              361L  3C   13m  CC=15     ←0
  │ Dockerfile                  10L  0C    0m  CC=0.0    ←0
  │ requirements.txt             5L  0C    0m  CC=0.0    ←0
  │
  dashboard/                      CC̄=3.2    ←in:0  →out:8  !! split
  │ server                     189L  2C   10m  CC=8      ←0
  │ Dockerfile                  10L  0C    0m  CC=0.0    ←0
  │
  git2mcp/                        CC̄=2.9    ←in:0  →out:0
  │ proxy                      437L  1C   21m  CC=12     ←0
  │ 05_local_iterate           126L  0C    1m  CC=5      ←0
  │ planfile.yaml              123L  0C    0m  CC=0.0    ←0
  │ 04_dry_run_vs_execute      115L  0C    2m  CC=3      ←0
  │ client                     104L  1C   20m  CC=4      ←0
  │ 02_fragment_sync_to_skills    68L  0C    1m  CC=1      ←0
  │ 01_sync_and_commit          62L  0C    1m  CC=1      ←0
  │ pyproject.toml              57L  0C    0m  CC=0.0    ←0
  │ 03_agent_git2mcp            55L  0C    1m  CC=4      ←0
  │ generated-from-pytests.testql.toon.yaml    55L  0C    0m  CC=0.0    ←0
  │ project.sh                  47L  0C    0m  CC=0.0    ←0
  │ generated-api-integration.testql.toon.yaml    18L  0C    0m  CC=0.0    ←0
  │ proxy                        3L  0C    0m  CC=0.0    ←0
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │ client                       3L  0C    0m  CC=0.0    ←0
  │ __init__                     3L  0C    0m  CC=0.0    ←0
  │
  mcp-git-proxy/                  CC̄=2.5    ←in:0  →out:0
  │ server                     443L  19C   22m  CC=9      ←0
  │ Dockerfile                  18L  0C    0m  CC=0.0    ←0
  │ requirements.txt             4L  0C    0m  CC=0.0    ←0
  │
  mcp-docs/                       CC̄=2.1    ←in:0  →out:0
  │ server                     273L  0C    7m  CC=4      ←0
  │ Dockerfile                  14L  0C    0m  CC=0.0    ←0
  │ requirements.txt             3L  0C    0m  CC=0.0    ←0
  │
  scripts/                        CC̄=0.0    ←in:64  →out:0
  │ test.sh                    404L  1C   14m  CC=0.0    ←12
  │ generate_demo_repos.sh     396L  0C   18m  CC=0.0    ←0
  │ refactor-last-repo.sh      312L  0C   12m  CC=0.0    ←0
  │ deploy.sh                  135L  0C    7m  CC=0.0    ←0
  │
  ./                              CC̄=0.0    ←in:0  →out:0
  │ !! planfile.yaml             1319L  0C    0m  CC=0.0    ←0
  │ !! goal.yaml                  528L  0C    0m  CC=0.0    ←0
  │ docker-compose.yml         325L  0C    0m  CC=0.0    ←0
  │ Makefile                   197L  0C    0m  CC=0.0    ←0
  │ prefact.yaml                91L  0C    0m  CC=0.0    ←0
  │ pyproject.toml              64L  0C    0m  CC=0.0    ←0
  │ project.sh                  47L  0C    0m  CC=0.0    ←0
  │ docker-compose.prod.yml     34L  0C    0m  CC=0.0    ←0
  │ .semcod-mcp.yaml            15L  0C    0m  CC=0.0    ←0
  │ tree.sh                      1L  0C    0m  CC=0.0    ←0
  │
  examples/                       CC̄=0.0    ←in:0  →out:0
  │ continue-config.snippet.json    25L  0C    0m  CC=0.0    ←0
  │ claude-desktop-mcp.json     22L  0C    0m  CC=0.0    ←0
  │
  ansible/                        CC̄=0.0    ←in:0  →out:0
  │ !! e2e-gh2mcp.yml             520L  0C    0m  CC=0.0    ←0
  │ e2e-tools.yml              285L  0C    0m  CC=0.0    ←0
  │ e2e-github-qa.yml          232L  0C    0m  CC=0.0    ←0
  │ test-github-integration.yml   189L  0C    0m  CC=0.0    ←0
  │ e2e-docker-stack.yml       172L  0C    0m  CC=0.0    ←0
  │ inventory.ini                2L  0C    0m  CC=0.0    ←0
  │

COUPLING:
                             scripts   env2mcp.env2mcp         llm-agent        mcp-skills       mcp-gateway        semcod_mcp         dashboard  git2mcp.examples     gh2mcp.gh2mcp
           scripts                ──               ←34               ←10                                                                      ←8                ←8                ←4  hub
   env2mcp.env2mcp                34                ──                                  ←4                ←9                ←3                                                    ←1  hub
         llm-agent                10                                  ──                                                                                                              !! fan-out
        mcp-skills                                   4                                  ──                                   6                                                        !! fan-out
       mcp-gateway                                   9                                                    ──                                                                          !! fan-out
        semcod_mcp                                   3                                  ←6                                  ──                                                        hub
         dashboard                 8                                                                                                          ──                                      !! fan-out
  git2mcp.examples                 8                                                                                                                            ──                    !! fan-out
     gh2mcp.gh2mcp                 4                 1                                                                                                                            ──
  CYCLES: none
  HUB: semcod_mcp/ (fan-in=6)
  HUB: scripts/ (fan-in=64)
  HUB: env2mcp.env2mcp/ (fan-in=17)
  SMELL: mcp-gateway/ fan-out=9 → split needed
  SMELL: mcp-skills/ fan-out=10 → split needed
  SMELL: dashboard/ fan-out=8 → split needed
  SMELL: env2mcp.env2mcp/ fan-out=34 → split needed
  SMELL: git2mcp.examples/ fan-out=8 → split needed
  SMELL: llm-agent/ fan-out=10 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 7 groups | 59f 10680L | 2026-06-18

SUMMARY:
  files_scanned: 59
  total_lines:   10680
  dup_groups:    7
  dup_fragments: 18
  saved_lines:   107
  scan_ms:       4447

HOTSPOTS[7] (files with most duplication):
  llm-agent/agent.py  dup=41L  groups=2  frags=2  (0.4%)
  llm-agent/agent_standalone.py  dup=41L  groups=2  frags=2  (0.4%)
  mcp-skills/server.py  dup=32L  groups=1  frags=4  (0.3%)
  mcp-git-proxy/server.py  dup=30L  groups=2  frags=6  (0.3%)
  mcp-gateway/gateway_jobs.py  dup=26L  groups=1  frags=2  (0.2%)
  semcod_mcp/deinit_cmd.py  dup=9L  groups=1  frags=1  (0.1%)
  semcod_mcp/init_cmd.py  dup=9L  groups=1  frags=1  (0.1%)

DUPLICATES[7] (ranked by impact):
  [aea4a7a9526a2ad3]   EXAC  _mock_llm_response  L=30 N=2 saved=30 sim=1.00
      llm-agent/agent.py:232-261  (_mock_llm_response)
      llm-agent/agent_standalone.py:405-434  (_mock_llm_response)
  [467fd96667a253a0]   STRU  analyze_code_structure  L=8 N=4 saved=24 sim=1.00
      mcp-skills/server.py:504-511  (analyze_code_structure)
      mcp-skills/server.py:515-522  (compute_metrics)
      mcp-skills/server.py:526-533  (detect_patterns)
      mcp-skills/server.py:537-544  (recommend_refactoring)
  [d7672c451ace4405]   STRU  worktree_diff  L=5 N=4 saved=15 sim=1.00
      mcp-git-proxy/server.py:230-234  (worktree_diff)
      mcp-git-proxy/server.py:246-250  (stage)
      mcp-git-proxy/server.py:254-258  (stash_save)
      mcp-git-proxy/server.py:278-282  (checkpoint_create)
  [bf41aa98652b1a64]   STRU  get_state_redis_client  L=13 N=2 saved=13 sim=1.00
      mcp-gateway/gateway_jobs.py:32-44  (get_state_redis_client)
      mcp-gateway/gateway_jobs.py:47-59  (get_rq_redis_client)
  [5865906155183adc]   EXAC  _mock_llm_response_from_prompt  L=11 N=2 saved=11 sim=1.00
      llm-agent/agent.py:263-273  (_mock_llm_response_from_prompt)
      llm-agent/agent_standalone.py:436-446  (_mock_llm_response_from_prompt)
  [29f85044e563198e]   STRU  print_deinit_result  L=9 N=2 saved=9 sim=1.00
      semcod_mcp/deinit_cmd.py:129-137  (print_deinit_result)
      semcod_mcp/init_cmd.py:168-176  (print_init_result)
  [796eb26d67b6a889]   STRU  push  L=5 N=2 saved=5 sim=1.00
      mcp-git-proxy/server.py:196-200  (push)
      mcp-git-proxy/server.py:270-274  (branch_draft)

REFACTOR[7] (ranked by priority):
  [1] ○ extract_class      → llm-agent/utils/_mock_llm_response.py
      WHY: 2 occurrences of 30-line block across 2 files — saves 30 lines
      FILES: llm-agent/agent.py, llm-agent/agent_standalone.py
  [2] ○ extract_function   → mcp-skills/utils/analyze_code_structure.py
      WHY: 4 occurrences of 8-line block across 1 files — saves 24 lines
      FILES: mcp-skills/server.py
  [3] ○ extract_function   → mcp-git-proxy/utils/worktree_diff.py
      WHY: 4 occurrences of 5-line block across 1 files — saves 15 lines
      FILES: mcp-git-proxy/server.py
  [4] ○ extract_function   → mcp-gateway/utils/get_state_redis_client.py
      WHY: 2 occurrences of 13-line block across 1 files — saves 13 lines
      FILES: mcp-gateway/gateway_jobs.py
  [5] ○ extract_class      → llm-agent/utils/_mock_llm_response_from_prompt.py
      WHY: 2 occurrences of 11-line block across 2 files — saves 11 lines
      FILES: llm-agent/agent.py, llm-agent/agent_standalone.py
  [6] ○ extract_function   → semcod_mcp/utils/print_deinit_result.py
      WHY: 2 occurrences of 9-line block across 2 files — saves 9 lines
      FILES: semcod_mcp/deinit_cmd.py, semcod_mcp/init_cmd.py
  [7] ○ extract_function   → mcp-git-proxy/utils/push.py
      WHY: 2 occurrences of 5-line block across 1 files — saves 5 lines
      FILES: mcp-git-proxy/server.py

QUICK_WINS[6] (low risk, high savings — do first):
  [1] extract_class      saved=30L  → llm-agent/utils/_mock_llm_response.py
      FILES: agent.py, agent_standalone.py
  [2] extract_function   saved=24L  → mcp-skills/utils/analyze_code_structure.py
      FILES: server.py
  [3] extract_function   saved=15L  → mcp-git-proxy/utils/worktree_diff.py
      FILES: server.py
  [4] extract_function   saved=13L  → mcp-gateway/utils/get_state_redis_client.py
      FILES: gateway_jobs.py
  [5] extract_class      saved=11L  → llm-agent/utils/_mock_llm_response_from_prompt.py
      FILES: agent.py, agent_standalone.py
  [6] extract_function   saved=9L  → semcod_mcp/utils/print_deinit_result.py
      FILES: deinit_cmd.py, init_cmd.py

EFFORT_ESTIMATE (total ≈ 3.6h):
  medium _mock_llm_response                  saved=30L  ~60min
  medium analyze_code_structure              saved=24L  ~48min
  medium worktree_diff                       saved=15L  ~30min
  easy   get_state_redis_client              saved=13L  ~26min
  easy   _mock_llm_response_from_prompt      saved=11L  ~22min
  easy   print_deinit_result                 saved=9L  ~18min
  easy   push                                saved=5L  ~10min

METRICS-TARGET:
  dup_groups:  7 → 0
  saved_lines: 107 lines recoverable
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 389 func | 40f | 2026-06-18
# generated in 0.00s

NEXT[10] (ranked by impact):
  [1] !! SPLIT           mcp-gateway/server.py
      WHY: 1206L, 2 classes, max CC=31
      EFFORT: ~4h  IMPACT: 37386

  [2] !! SPLIT           mcp-skills/server.py
      WHY: 691L, 1 classes, max CC=15
      EFFORT: ~4h  IMPACT: 10365

  [3] !! SPLIT-FUNC      chat_completions  CC=31  fan=56
      WHY: CC=31 exceeds 15
      EFFORT: ~1h  IMPACT: 1736

  [4] !! SPLIT-FUNC      run_tool_against_repo  CC=37  fan=41
      WHY: CC=37 exceeds 15
      EFFORT: ~1h  IMPACT: 1517

  [5] !! SPLIT-FUNC      run_chat_workflow  CC=43  fan=26
      WHY: CC=43 exceeds 15
      EFFORT: ~1h  IMPACT: 1118

  [6] !! SPLIT-FUNC      handle_chat_completions  CC=31  fan=32
      WHY: CC=31 exceeds 15
      EFFORT: ~1h  IMPACT: 992

  [7] !! SPLIT-FUNC      GitHubTokenSyncService.get_recent_repos  CC=32  fan=24
      WHY: CC=32 exceeds 15
      EFFORT: ~1h  IMPACT: 768

  [8] !! SPLIT-FUNC      render_tool_text  CC=40  fan=15
      WHY: CC=40 exceeds 15
      EFFORT: ~1h  IMPACT: 600

  [9] !  SPLIT-FUNC      dispatch_skill  CC=19  fan=26
      WHY: CC=19 exceeds 15
      EFFORT: ~1h  IMPACT: 494

  [10] !  SPLIT-FUNC      MCPSkillsServer._sync_from_git_proxy  CC=15  fan=30
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 450


RISKS[3]:
  ⚠ Splitting planfile.yaml may break 0 import paths
  ⚠ Splitting mcp-gateway/server.py may break 29 import paths
  ⚠ Splitting mcp-skills/server.py may break 22 import paths

METRICS-TARGET:
  CC̄:          5.1 → ≤3.6
  max-CC:      43 → ≤20
  god-modules: 9 → 0
  high-CC(≥15): 25 → ≤12
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
  prev CC̄=5.0 → now CC̄=5.1
```

## Intent

Initialize semcod MCP stack integration for Cursor, VS Code, Claude and other IDEs — init, doctor, validate, analyze.
