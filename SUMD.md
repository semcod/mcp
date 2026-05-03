# Autonomiczny Agent Refaktoryzacji MCP

Autonomiczny Agent Refaktoryzacji MCP

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Environment Variables (`.env.example`)](#environment-variables-envexample)
- [Release Management (`goal.yaml`)](#release-management-goalyaml)
- [Code Analysis](#code-analysis)
- [Call Graph](#call-graph)
- [Intent](#intent)

## Metadata

- **name**: `mcp`
- **version**: `0.0.0`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: app.doql.less, goal.yaml, .env.example, docker-compose.yml, project/(2 analysis files)

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

interface[type="api"] {
  type: rest;
  framework: fastapi;
}

integration[name="github"] {
  type: scm;
}

deploy {
  target: docker-compose;
  compose_file: docker-compose.yml;
}

environment[name="local"] {
  runtime: docker-compose;
  env_file: .env;
}

environment[name="prod"] {
  runtime: docker-compose;
}
```

## Configuration

```yaml
project:
  name: mcp
  version: 0.0.0
  env: local
```

## Deployment

```bash markpact:run
pip install mcp

# development install
pip install -e .[dev]
```

### Docker Compose (`docker-compose.yml`)

- **mcp-git-proxy** image=`{'context': '.', 'dockerfile': 'mcp-git-proxy/Dockerfile'}` ports: `8081:8080`
- **mcp-skills** image=`./mcp-skills`
- **llm-agent** image=`./llm-agent`
- **mcp-gateway** image=`{'context': '.', 'dockerfile': 'mcp-gateway/Dockerfile'}` ports: `9000:9000`
- **mcp-webui** image=`{'context': '.', 'dockerfile': 'mcp-webui/Dockerfile'}` ports: `8092:8090`
- **openwebui** image=`ghcr.io/open-webui/open-webui:main` ports: `3000:8080`
- **dashboard** image=`./dashboard` ports: `8085:8080`

## Environment Variables (`.env.example`)

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openrouter-lite` | LLM Provider: openrouter-lite, mock, openai, ollama |
| `OPENROUTER_API_KEY` | `*(not set)*` |  |
| `LLM_MODEL` | `openrouter/x-ai/grok-code-fast-1` | LLM_MODEL=openrouter/qwen/qwen3-coder-next |
| `OPENAI_API_KEY` | `sk-...` | OpenAI API Key (wymagane dla LLM_PROVIDER=openai) |
| `GITHUB_PAT` | `ghp_...` | GitHub Personal Access Token (dla MCP Git Server) |
| `GITHUB_ORG` | `your-org` |  |
| `GIT_PROXY_URL` | `http://mcp-git-proxy:8080` | MCP Git Proxy |
| `REPOS_PATH` | `./repos` | Ścieżki repozytoriów |
| `OUTPUT_PATH` | `./output` |  |

## Release Management (`goal.yaml`)

- **versioning**: `semver`
- **commits**: `conventional` scope=`mcp`
- **changelog**: `keep-a-changelog`
- **build strategies**: `python`, `nodejs`, `rust`
- **version files**: `VERSION`, `pyproject.toml:version`, `venv/lib/python3.13/site-packages/cryptography/__init__.py:__version__`

## Code Analysis

### `project/map.toon.yaml`

```toon markpact:analysis path=project/map.toon.yaml
# mcp | 35f 4849L | python:28,shell:5,less:2 | 2026-05-03
# stats: 63 func | 33 cls | 35 mod | CC̄=2.8 | critical:3 | cycles:0
# alerts[5]: CC test_git_proxy_e2e_sync_export_commit_and_tests=18; CC test_git_proxy_local_operations=17; CC test_git_proxy_e2e_push_to_bare_remote=10; CC test_git_proxy_e2e_commit_and_reset=7; CC dispatch_skill=7
# hotspots[5]: chat_completions fan=20; test_git_proxy_e2e_push_to_bare_remote fan=18; main fan=13; main fan=13; main fan=12
# evolution: baseline
# Keys: M=modules, D=details, i=imports, e=exports, c=classes, f=functions, m=methods
M[35]:
  app.doql.less,30
  dashboard/server.py,190
  git2mcp/__init__.py,4
  git2mcp/app.doql.less,22
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
  mcp-gateway/server.py,239
  mcp-git-proxy/server.py,299
  mcp-skills/server.py,640
  mcp-webui/server.py,128
  project.sh,47
  repos/test/another-project/app.py,7
  repos/test/push-seed/app.py,3
  repos/test/sample-project/main.py,33
  repos/test/sample-project/module_1.py,8
  repos/test/sample-project/module_2.py,8
  repos/test/sample-project/module_3.py,8
  repos/test/sample-project/module_4.py,8
  repos/test/sample-project/module_5.py,8
  scripts/deploy.sh,128
  scripts/test.sh,398
  tree.sh,2
D:
  dashboard/server.py:
    e: main,DashboardHandler,TCPServer
    DashboardHandler: end_headers(0),do_GET(0),serve_file(1),send_json(1),get_content_type(1),get_status(0),get_analyses(0),get_analysis(1),get_repos(0)  # Custom HTTP handler for dashboard
    TCPServer:
    main()
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
  mcp-gateway/server.py:
    e: load_tenants,find_tenant_by_key,authenticate,audit,health,list_models,chat_completions,dispatch_skill,get_job,audit_tail,ChatMessage,ChatCompletionRequest
    ChatMessage:
    ChatCompletionRequest:
    load_tenants()
    find_tenant_by_key(api_key)
    authenticate(authorization)
    audit(event)
    health()
    list_models(_)
    chat_completions(req;tenant)
    dispatch_skill(skill;tenant;req;user_msg)
    get_job(job_id;_)
    audit_tail(limit;_)
  mcp-git-proxy/server.py:
    e: health,list_repos,sync_repo,export_fragments,export_package,import_package,commit,push,reset,worktree_write,worktree_read,worktree_diff,patch_apply,stage,stash_save,stash_pop,branch_draft,checkpoint_create,checkpoint_restore,run_tests,SyncRepoRequest,ExportPackageRequest,ExportFragmentsRequest,CommitRequest,PushRequest,RunTestsRequest,ResetRequest,ImportPackageRequest,WorktreeWriteRequest,WorktreeReadRequest,WorktreeDiffRequest,PatchApplyRequest,StageRequest,StashSaveRequest,BranchDraftRequest,CheckpointCreateRequest,CheckpointRestoreRequest
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
  mcp-skills/server.py:
    e: main,MCPSkillsServer
    MCPSkillsServer: __init__(1),_sync_from_git_proxy(2),_setup_handlers(0),_handle_list_tools(0),_handle_call_tool(2),_analyze_code_structure(1),_compute_metrics_for_repo(1),_detect_code_patterns(1),_sync_repo_tool(1),_recommend_refactoring(1),run(0)  # Serwer MCP Skills z narzędziami do analizy kodu
    main()
  mcp-webui/server.py:
    e: gateway_headers,index,repos_page,repos_sync,diff_page,skills_page,skills_run,playground
    gateway_headers()
    index(request)
    repos_page(request)
    repos_sync(repo_id;source_path;branch)
    diff_page(request;repo_id)
    skills_page(request)
    skills_run(model;prompt;repo_id;source_path)
    playground(request)
  repos/test/another-project/app.py:
    e: build_payload
    build_payload(value)
  repos/test/push-seed/app.py:
    e: add
    add(a;b)
  repos/test/sample-project/main.py:
    e: main,DataProcessor
    DataProcessor: __init__(1),process(1),_transform(1)  # Main data processor class
    main()
  repos/test/sample-project/module_1.py:
    e: function_1
    function_1(data)
  repos/test/sample-project/module_2.py:
    e: function_2
    function_2(data)
  repos/test/sample-project/module_3.py:
    e: function_3
    function_3(data)
  repos/test/sample-project/module_4.py:
    e: function_4
    function_4(data)
  repos/test/sample-project/module_5.py:
    e: function_5
    function_5(data)
```

## Call Graph

*13 nodes · 9 edges · 9 modules · CC̄=2.9*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `print` *(in scripts.test)* | 0 | 26 | 0 | **26** |
| `chat_completions` *(in mcp-gateway.server)* | 6 | 0 | 26 | **26** |
| `main` *(in llm-agent.agent_standalone)* | 2 | 0 | 21 | **21** |
| `main` *(in git2mcp.examples.03_agent_git2mcp)* | 4 | 0 | 19 | **19** |
| `main` *(in git2mcp.examples.01_sync_and_commit)* | 1 | 0 | 18 | **18** |
| `main` *(in llm-agent.agent)* | 2 | 0 | 16 | **16** |
| `main` *(in git2mcp.examples.02_fragment_sync_to_skills)* | 1 | 0 | 15 | **15** |
| `main` *(in dashboard.server)* | 2 | 0 | 10 | **10** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/semcod/mcp
# nodes: 13 | edges: 9 | modules: 9
# CC̄=2.9

HUBS[20]:
  scripts.test.print
    CC=0  in:26  out:0  total:26
  mcp-gateway.server.chat_completions
    CC=6  in:0  out:26  total:26
  llm-agent.agent_standalone.main
    CC=2  in:0  out:21  total:21
  git2mcp.examples.03_agent_git2mcp.main
    CC=4  in:0  out:19  total:19
  git2mcp.examples.01_sync_and_commit.main
    CC=1  in:0  out:18  total:18
  llm-agent.agent.main
    CC=2  in:0  out:16  total:16
  git2mcp.examples.02_fragment_sync_to_skills.main
    CC=1  in:0  out:15  total:15
  dashboard.server.main
    CC=2  in:0  out:10  total:10
  mcp-webui.server.index
    CC=3  in:0  out:10  total:10
  mcp-gateway.server.authenticate
    CC=4  in:0  out:8  total:8
  mcp-gateway.server.audit
    CC=1  in:1  out:5  total:6
  mcp-gateway.server.find_tenant_by_key
    CC=3  in:1  out:2  total:3
  mcp-webui.server.gateway_headers
    CC=1  in:2  out:0  total:2

MODULES:
  dashboard.server  [1 funcs]
    main  CC=2  out:10
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
  mcp-gateway.server  [4 funcs]
    audit  CC=1  out:5
    authenticate  CC=4  out:8
    chat_completions  CC=6  out:26
    find_tenant_by_key  CC=3  out:2
  mcp-webui.server  [2 funcs]
    gateway_headers  CC=1  out:0
    index  CC=3  out:10
  scripts.test  [1 funcs]
    print  CC=0  out:0

EDGES:
  git2mcp.examples.02_fragment_sync_to_skills.main → scripts.test.print
  mcp-webui.server.index → mcp-webui.server.gateway_headers
  git2mcp.examples.03_agent_git2mcp.main → scripts.test.print
  git2mcp.examples.01_sync_and_commit.main → scripts.test.print
  dashboard.server.main → scripts.test.print
  llm-agent.agent.main → scripts.test.print
  llm-agent.agent_standalone.main → scripts.test.print
  mcp-gateway.server.authenticate → mcp-gateway.server.find_tenant_by_key
  mcp-gateway.server.chat_completions → mcp-gateway.server.audit
```

## Intent

Autonomiczny Agent Refaktoryzacji MCP
