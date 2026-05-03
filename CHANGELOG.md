# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

