# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.10] - 2026-06-18

### Fixed
- Fix unused-imports issues (ticket-d4b1ca36)
- Fix magic-numbers issues (ticket-b8f91c35)
- Fix string-concat issues (ticket-da3705cc)
- Fix unused-imports issues (ticket-cf1891cc)
- Fix magic-numbers issues (ticket-64b1437b)
- Fix smart-return-type issues (ticket-b824928c)
- Fix string-concat issues (ticket-a8af84e6)
- Fix unused-imports issues (ticket-2d0dea29)
- Fix magic-numbers issues (ticket-4ee2ec52)

## [0.1.10] - 2026-06-18

### Fixed
- Fix string-concat issues (ticket-83a4eb40)
- Fix unused-imports issues (ticket-f6029415)
- Fix magic-numbers issues (ticket-cd362bb4)
- Fix smart-return-type issues (ticket-4efce036)
- Fix unused-imports issues (ticket-d33e19b4)

## [0.1.12] - 2026-06-18

### Added
- **`docs/CURSOR_MCP_WORKFLOW.md`** — workflow Cursor Agent + MCP (reload, test, 3 fazy)
- **mcp-skills modules:** `tools_registry.py`, `tool_run.py`, `http_models.py`, `redsl_runner.py`, `mcp_parse.py`
- **mcp-gateway modules:** `gateway_config.py`, `gateway_render.py`

### Changed
- **mcp-skills/server.py** — ~1311→~690 linii (god module split)
- **mcp-gateway/server.py** — wydzielono config + render (~480 L)
- **`.cursor/rules/semcod-mcp.mdc`** — obowiązkowa analiza przed refactorem, validate po edycji
- Dokumentacja podlinkowana w [docs/README.md](docs/README.md)

## [0.1.11] - 2026-06-18

### Added
- **`mcp-skills/code_analysis.py`** — wspólne metryki repo (`largest_files`, rekomendacje z konkretnymi targetami)
- **`docs/README.md`** — spis dokumentacji z linkami krzyżowymi
- **`docs/GATEWAY_MODULE_SPLIT.md`** — plan podziału `mcp-gateway/server.py`

### Fixed
- **Analyze** — `largest_files` i konkretne ścieżki w rekomendacjach (redsl + enrich w gateway)
- **Docker** — mount `code_analysis.py` dla `mcp-skills`

### Changed
- Dokumentacja: [SEMCOD_MCP_CLI.md](docs/SEMCOD_MCP_CLI.md), [IDE_AND_AGENT_INTEGRATION.md](docs/IDE_AND_AGENT_INTEGRATION.md), [USAGE.md](docs/USAGE.md) — rejestry, hurtowe `init`, format wyniku analyze

## [0.1.10] - 2026-06-18

### Fixed
- Fix string-concat issues (ticket-6326f0c7)
- Fix unused-imports issues (ticket-b9c07cf9)
- Fix magic-numbers issues (ticket-37aea4c3)
- Fix string-concat issues (ticket-e1cf1da3)
- Fix unused-imports issues (ticket-eb821ff7)
- Fix magic-numbers issues (ticket-dacf30cb)
- Fix unused-imports issues (ticket-fb370ae2)
- Fix ai-boilerplate issues (ticket-5d0a4086)
- Fix unused-imports issues (ticket-ebaf86f2)
- Fix string-concat issues (ticket-849f75bc)
- Fix unused-imports issues (ticket-4ede378d)
- Fix unused-imports issues (ticket-b63499e5)
- Fix unused-imports issues (ticket-ed5bc004)
- Fix unused-imports issues (ticket-e70cd1db)
- Fix smart-return-type issues (ticket-b5301998)
- Fix smart-return-type issues (ticket-823d6733)

## [0.1.10] - 2026-05-03

### Fixed
- Fix relative-imports issues (ticket-3b8719c4)
- Fix relative-imports issues (ticket-0234b9a8)
- Fix string-concat issues (ticket-f0afb114)
- Fix unused-imports issues (ticket-e74f97d9)
- Fix magic-numbers issues (ticket-a9b9165f)
- Fix ai-boilerplate issues (ticket-76691dde)
- Fix smart-return-type issues (ticket-916374bd)
- Fix unused-imports issues (ticket-973be596)
- Fix relative-imports issues (ticket-5e131711)
- Fix relative-imports issues (ticket-8a24b190)
- Fix string-concat issues (ticket-d1919ee1)
- Fix unused-imports issues (ticket-bc72edc1)
- Fix magic-numbers issues (ticket-873af373)
- Fix llm-generated-code issues (ticket-88728fa9)
- Fix relative-imports issues (ticket-7655ac63)
- Fix unused-imports issues (ticket-1c169665)
- Fix magic-numbers issues (ticket-39ce0253)
- Fix ai-boilerplate issues (ticket-02a9c6cb)
- Fix string-concat issues (ticket-00451893)
- Fix unused-imports issues (ticket-fd256bd3)
- Fix magic-numbers issues (ticket-94df9f8e)
- Fix relative-imports issues (ticket-09cd63ff)
- Fix unused-imports issues (ticket-c23207aa)
- Fix magic-numbers issues (ticket-7c348e41)
- Fix smart-return-type issues (ticket-58aa280e)
- Fix unused-imports issues (ticket-c9e79ed1)
- Fix unused-imports issues (ticket-6e8ee29e)
- Fix magic-numbers issues (ticket-3c9aac83)
- Fix smart-return-type issues (ticket-a001ca2a)
- Fix unused-imports issues (ticket-eb4f0127)
- Fix llm-hallucinations issues (ticket-62b8e4ab)
- Fix smart-return-type issues (ticket-62aebf74)
- Fix string-concat issues (ticket-9589658a)
- Fix unused-imports issues (ticket-53cc4c9a)
- Fix unused-imports issues (ticket-4ba9e289)
- Fix ai-boilerplate issues (ticket-4e1f11b3)
- Fix string-concat issues (ticket-cf238806)
- Fix smart-return-type issues (ticket-8655bcaa)
- Fix unused-imports issues (ticket-c2cf30c6)
- Fix duplicate-imports issues (ticket-9bde2585)
- Fix string-concat issues (ticket-21e868b1)

## [0.1.10] - 2026-05-03

### Fixed
- Fix relative-imports issues (ticket-fdfba7d4)
- Fix smart-return-type issues (ticket-6313e5f3)
- Fix unused-imports issues (ticket-928c5400)
- Fix magic-numbers issues (ticket-b6593aec)
- Fix ai-boilerplate issues (ticket-fcba60ab)
- Fix relative-imports issues (ticket-d35d216a)
- Fix magic-numbers issues (ticket-45359d32)
- Fix string-concat issues (ticket-87699e4f)
- Fix unused-imports issues (ticket-2ddf582d)
- Fix magic-numbers issues (ticket-69f2c3b8)
- Fix ai-boilerplate issues (ticket-a6c471f1)
- Fix string-concat issues (ticket-92938213)
- Fix unused-imports issues (ticket-7e35be8b)
- Fix magic-numbers issues (ticket-5913b7f3)
- Fix string-concat issues (ticket-bb62a236)
- Fix unused-imports issues (ticket-40b916af)
- Fix magic-numbers issues (ticket-005461f1)
- Fix ai-boilerplate issues (ticket-a1fde1a4)
- Fix string-concat issues (ticket-db1f528c)
- Fix unused-imports issues (ticket-34d377d2)
- Fix magic-numbers issues (ticket-ad0519cd)
- Fix ai-boilerplate issues (ticket-7d10a462)
- Fix unused-imports issues (ticket-5f3404cc)
- Fix magic-numbers issues (ticket-e5772246)
- Fix unused-imports issues (ticket-7e98a837)
- Fix magic-numbers issues (ticket-ef188d05)
- Fix ai-boilerplate issues (ticket-ff0b426c)
- Fix smart-return-type issues (ticket-d2460285)
- Fix unused-imports issues (ticket-8364f04b)
- Fix magic-numbers issues (ticket-d4b8a8e5)
- Fix smart-return-type issues (ticket-b824928c)
- Fix string-concat issues (ticket-a8af84e6)
- Fix unused-imports issues (ticket-2d0dea29)
- Fix magic-numbers issues (ticket-4ee2ec52)

## [Unreleased]

## [0.1.3] - 2026-06-18

### Docs
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md

### Other
- Update app.doql.less
- Update env2mcp/env2mcp/__init__.py
- Update gh2mcp/gh2mcp/__init__.py
- Update mcp-gateway/gateway_github.py
- Update mcp-gateway/gateway_prompt.py
- Update mcp-gateway/server.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/calls.toon.yaml
- ... and 6 more files

## [0.1.2] - 2026-06-18

### Docs
- Update CHANGELOG.md
- Update README.md
- Update REFACTORING_PLAN.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update docs/CURSOR_MCP_WORKFLOW.md
- Update docs/GATEWAY_MODULE_SPLIT.md
- Update docs/IDE_AND_AGENT_INTEGRATION.md
- Update docs/PRODUCT.md
- ... and 6 more files

### Test
- Update tests/test_deinit.py
- Update tests/test_merge.py

### Other
- Update .gitignore
- Update .semcod-mcp.yaml
- Update app.doql.less
- Update env2mcp/env2mcp/__init__.py
- Update gh2mcp/gh2mcp/__init__.py
- Update mcp-gateway/Dockerfile
- Update mcp-gateway/gateway_config.py
- Update mcp-gateway/gateway_render.py
- Update mcp-gateway/server.py
- Update mcp-skills/Dockerfile
- ... and 31 more files

## [0.1.1] - 2026-06-18

### Docs
- Update CHANGELOG.md
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update project/README.md
- Update project/context.md

### Other
- Update .continue/config.json
- Update .cursor/mcp.json
- Update .cursor/rules/semcod-mcp.mdc
- Update .semcod-mcp.yaml
- Update .vscode/mcp.json
- Update .vscode/settings.json
- Update .windsurf/mcp.json
- Update VERSION
- Update app.doql.less
- Update env2mcp/VERSION
- ... and 38 more files

## [0.0.7] - 2026-05-03

### Docs
- Update env2mcp/CHANGELOG.md

### Other
- Update .dockerignore
- Update Makefile
- Update env2mcp/VERSION
- Update env2mcp/env2mcp/config.py
- Update env2mcp/tests/test_env2mcp.py
- Update mcp-git-proxy/Dockerfile
- Update mcp-skills/Dockerfile
- Update mcp-skills/server.py

## [0.0.6] - 2026-05-03

### Docs
- Update CHANGELOG.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update TODO/1.md
- Update TODO/2.md
- Update TODO/3.md
- Update project/README.md
- Update project/context.md

### Other
- Update app.doql.less
- Update env2mcp/env2mcp/config.py
- Update mcp-gateway/conftest.py
- Update mcp-gateway/server.py
- Update mcp-skills/conftest.py
- Update mcp-skills/server.py
- Update mcp-skills/test_tools_run.py
- Update mcp-webui/templates/base.html
- Update mcp-webui/templates/playground.html
- Update mcp-webui/templates/skills.html
- ... and 20 more files

## [0.0.5] - 2026-05-03

### Docs
- Update docs/CHAT_PLAYBOOKS.md

### Other
- Update Makefile
- Update ansible/e2e-docker-stack.yml
- Update ansible/e2e-gh2mcp.yml
- Update ansible/e2e-github-qa.yml
- Update ansible/e2e-tools.yml
- Update ansible/test-github-integration.yml
- Update gh2mcp/gh2mcp/server.py
- Update gh2mcp/gh2mcp/sync.py
- Update gh2mcp/tests/test_gh2mcp.py
- Update mcp-docs/server.py
- ... and 8 more files

## [0.0.4] - 2026-05-03

### Docs
- Update README.md
- Update docs/CHAT_PLAYBOOKS.md

### Other
- Update Makefile
- Update mcp-gateway/server.py

## [0.0.3] - 2026-05-03

## [0.2.0] - 2026-05-03

### Added
- **MCP Gateway** - OpenAI-compatible HTTP shim with SSE streaming, multi-tenant auth, audit logging
- **MCP WebUI** - FastAPI + HTMX admin panel at port 8092
- **OpenWebUI Integration** - Full OpenAI-compatible API integration for end users
- **HTTP API for MCP Skills** - FastAPI endpoints for sync, analyze, refactor (/sync, /analyze/*, /refactor/recommend)
- **New git2mcp Local Operations** - worktree read/write/diff, patch apply, stash, checkpoint, draft branches
- **Makefile** - Complete lifecycle management (start, stop, smoke, kill-ports, prod-up)
- **Multi-tenant Support** - YAML-based tenant configs with API keys, quotas, feature flags
- **Healthchecks** - Docker Compose service health checks with dependency conditions
- **Ansible E2E Tests** - ansible/e2e-docker-stack.yml for automated integration testing
- **GitHub Page** - WebUI page for GitHub configuration

### Changed
- mcp-skills server now runs HTTP by default (MCP_SKILLS_TRANSPORT=http)
- Enhanced gateway prompt parsing for Repo/Source/Branch/Execute/Push/Test/Remote/Zadanie fields
- Full refactor workflow: sync → analyze → commit → test → push (when Execute=true and Push=true)

### Security
- Bearer token authentication for all gateway endpoints
- Path traversal protection in worktree operations
- Per-tenant feature flags (push can be disabled per tenant)

## [0.0.2] - 2026-05-03

### Docs
- Update README.md

### Other
- Update dashboard/Dockerfile
- Update dashboard/index.html
- Update dashboard/server.py
- Update output/test_sample-project_analysis.json
- Update scripts/deploy.sh

## [0.0.1] - 2026-05-03

### Docs
- Update README.md
- Update TODO/1.md
- Update TODO/2.md
- Update TODO/3.md

### Other
- Update .env.example
- Update .gitignore
- Update llm-agent/Dockerfile
- Update llm-agent/agent.py
- Update llm-agent/agent_standalone.py
- Update llm-agent/requirements.txt
- Update mcp-skills/Dockerfile
- Update mcp-skills/requirements.txt
- Update mcp-skills/server.py
- Update output/test_sample-project_analysis.json
- ... and 8 more files

