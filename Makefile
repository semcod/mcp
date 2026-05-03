SHELL := /bin/bash

# Load port variables from .env (fallback to defaults)
ifneq (,$(wildcard .env))
  include .env
  export
endif

PORT_OPENWEBUI ?= 3000
PORT_GH2MCP    ?= 8079
PORT_GIT_PROXY ?= 8081
PORT_DASHBOARD ?= 8085
PORT_WEBUI     ?= 8092
PORT_DOCS      ?= 8093
PORT_GATEWAY   ?= 9000

PORTS := $(PORT_OPENWEBUI) $(PORT_GH2MCP) $(PORT_GIT_PROXY) $(PORT_DASHBOARD) $(PORT_WEBUI) $(PORT_DOCS) $(PORT_GATEWAY)

COMPOSE := docker-compose
COMPOSE_PROD := docker-compose -f docker-compose.yml -f docker-compose.prod.yml
PROFILES := --profile openwebui

.PHONY: help start stop restart kill-ports up down logs ps build rebuild test pytest smoke ansible-e2e ansible-gh2mcp ansible-github-qa ansible-github-test ansible-tools-e2e gh2mcp-status reload-gateway reload-skills clean prod-up prod-down setup-github install-env2mcp generate-demo-repos generate-demo-repos-github

help:
	@echo "MCP Skills - Makefile targets"
	@echo "  make start         - kill host ports, build and start full stack (with OpenWebUI)"
	@echo "  make stop          - stop all containers"
	@echo "  make restart       - stop + start"
	@echo "  make kill-ports    - free host ports: $(PORTS)"
	@echo "  make build         - build all images"
	@echo "  make rebuild       - build --no-cache"
	@echo "  make logs          - tail compose logs"
	@echo "  make ps            - list services"
	@echo "  make smoke         - basic curl smoke-test against gateway/webui"
	@echo "  make ansible-e2e   - run Ansible docker E2E (gateway/openwebui/prompts)"
	@echo "  make ansible-gh2mcp - run Ansible gh2mcp E2E (token/org/repo endpoints + chat commands)"
	@echo "  make ansible-github-qa - run Ansible GitHub Q&A E2E (github-qa model + /repo/recent)"
	@echo "  make reload-gateway - rebuild + restart mcp-gateway, mcp-gateway-worker and gh2mcp-agent (preserves GH_TOKEN)"
	@echo "  make test          - run pytest (all unit tests) + scripts/test.sh + ansible-github-qa E2E"
	@echo "  make pytest        - run pytest only"
	@echo "  make prod-up       - start production overlay"
	@echo "  make prod-down     - stop production overlay"
	@echo "  make clean         - down + remove volumes"
	@echo "  make install-env2mcp - install env2mcp package locally"
	@echo "  make setup-github  - configure GitHub authentication via env2mcp"
	@echo "  make generate-demo-repos - create and sync demo repos for use-cases"
	@echo "  make generate-demo-repos-github - force create/sync demo repos on GitHub via gh"
	@echo "  make ansible-github-test  - test GitHub token + create-repo via Ansible (requires GITHUB_PAT)"
	@echo "  make ansible-tools-e2e - run Ansible NLP tool routing E2E (mcp-skills /tools/list + gateway chat)"
	@echo "  make reload-skills  - rebuild + restart mcp-skills container"
	@echo "  make gh2mcp-status - show gh2mcp agent health and token status"
	@echo "  mcp-docs:         http://localhost:$(PORT_DOCS) (dokumentacja + playbooki chat)"
	@echo "  env vars for demo repos: GH_DEMO_PROVIDER=auto|github|local GH_DEMO_PREFIX=mcp-demo GH_DEMO_VISIBILITY=private|public"

kill-ports:
	@for p in $(PORTS); do \
		cids=$$(docker ps --filter "publish=$$p" -q); \
		if [ -n "$$cids" ]; then \
			echo "stopping containers binding port $$p: $$cids"; \
			docker stop $$cids >/dev/null || true; \
		fi; \
		pids=$$(ss -lntp 2>/dev/null | grep -E ":$$p[[:space:]]" | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u); \
		if [ -n "$$pids" ]; then \
			echo "killing pids on port $$p: $$pids"; \
			for pid in $$pids; do kill -TERM $$pid 2>/dev/null || true; done; \
			sleep 1; \
			for pid in $$pids; do kill -9 $$pid 2>/dev/null || true; done; \
		fi; \
	done

start: kill-ports
	@GH_TOKEN_VALUE=$$(gh auth token 2>/dev/null || true); \
	if [ -n "$$GH_TOKEN_VALUE" ]; then export GH_TOKEN="$$GH_TOKEN_VALUE"; fi; \
	$(COMPOSE) $(PROFILES) build
	@GH_TOKEN_VALUE=$$(gh auth token 2>/dev/null || true); \
	if [ -n "$$GH_TOKEN_VALUE" ]; then export GH_TOKEN="$$GH_TOKEN_VALUE"; fi; \
	$(COMPOSE) $(PROFILES) up -d
	@$(MAKE) smoke
	@echo ""
	@echo "MCP Skills stack started:"
	@echo "  OpenWebUI:  http://localhost:$(PORT_OPENWEBUI)"
	@echo "  MCP WebUI:  http://localhost:$(PORT_WEBUI)"
	@echo "  MCP Docs:   http://localhost:$(PORT_DOCS)"
	@echo "  Gateway:    http://localhost:$(PORT_GATEWAY)"
	@echo "  Dashboard:  http://localhost:$(PORT_DASHBOARD)"
	@echo "  Git Proxy:  http://localhost:$(PORT_GIT_PROXY)"

stop:
	$(COMPOSE) $(PROFILES) down --remove-orphans

restart: stop start

up:
	$(COMPOSE) $(PROFILES) up -d

down: stop

logs:
	$(COMPOSE) $(PROFILES) logs -f --tail=200

ps:
	$(COMPOSE) $(PROFILES) ps

build:
	$(COMPOSE) $(PROFILES) build

rebuild:
	$(COMPOSE) $(PROFILES) build --no-cache

smoke:
	@echo "--- gateway /health ---"; curl -fsS http://localhost:$(PORT_GATEWAY)/health && echo
	@echo "--- gh2mcp /health ---"; curl -fsS http://localhost:$(PORT_GH2MCP)/health && echo
	@echo "--- mcp-docs /health ---"; curl -fsS http://localhost:$(PORT_DOCS)/health && echo
	@echo "--- gateway /v1/models (no auth) ---"; curl -s -o /dev/null -w '%{http_code}\n' http://localhost:$(PORT_GATEWAY)/v1/models
	@echo "--- gateway /v1/models (auth) ---"; curl -fsS -H "Authorization: Bearer $${WEBUI_API_KEY:-sk-mcp-default-dev-key}" http://localhost:$(PORT_GATEWAY)/v1/models | python3 -m json.tool | head -20
	@echo "--- mcp-skills /health (container) ---"; $(COMPOSE) $(PROFILES) exec -T mcp-skills python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=5).status)"
	@echo "--- mcp-skills /tools/list (container) ---"; $(COMPOSE) $(PROFILES) exec -T mcp-skills python -c "import urllib.request, json; r=urllib.request.urlopen('http://127.0.0.1:8080/tools/list', timeout=5); d=json.loads(r.read()); print('tools:', len(d.get('tools',[])))" && echo OK || echo 'SKIP (tools not ready)'
	@echo "--- mcp-webui / (wait for 200) ---"; \
	code=""; \
	for i in {1..30}; do \
		code=$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:$(PORT_WEBUI)/ || true); \
		if [ "$$code" = "200" ]; then break; fi; \
		sleep 1; \
	done; \
	echo "$$code"; \
	[ "$$code" = "200" ]

ansible-e2e:
	ansible-playbook -i ansible/inventory.ini ansible/e2e-docker-stack.yml

ansible-gh2mcp:
	ansible-playbook -i ansible/inventory.ini ansible/e2e-gh2mcp.yml

ansible-github-qa:
	ansible-playbook -i ansible/inventory.ini ansible/e2e-github-qa.yml

reload-gateway:
	@GH_TOKEN_VALUE=$$(gh auth token 2>/dev/null || true); \
	if [ -n "$$GH_TOKEN_VALUE" ]; then export GH_TOKEN="$$GH_TOKEN_VALUE"; fi; \
	$(COMPOSE) $(PROFILES) up -d --build --remove-orphans mcp-gateway mcp-gateway-worker gh2mcp-agent
	@echo "mcp-gateway + mcp-gateway-worker + gh2mcp-agent rebuilt and restarted (GH_TOKEN preserved)"

ansible-tools-e2e:
	ansible-playbook -i ansible/inventory.ini ansible/e2e-tools.yml

reload-skills:
	$(COMPOSE) $(PROFILES) up -d --build --remove-orphans mcp-skills
	@echo "mcp-skills rebuilt and restarted"

ansible-github-test:
	ansible-playbook -i ansible/inventory.ini ansible/test-github-integration.yml

gh2mcp-status:
	@echo "--- gh2mcp /health ---"; curl -fsS http://localhost:$(PORT_GH2MCP)/health && echo
	@echo "--- gh2mcp /status ---"; curl -fsS http://localhost:$(PORT_GH2MCP)/status | python3 -m json.tool

pytest:
	python3 -m pytest -q git2mcp/tests/test_git2mcp.py
	cd mcp-gateway && python3 -m pytest -q
	cd gh2mcp && python3 -m pytest -q
	cd mcp-skills && SKILLS_REPO_BASE=/tmp/mcp-skills-test python3 -m pytest -q

test: pytest
	bash scripts/test.sh
	$(MAKE) ansible-github-qa
	$(MAKE) ansible-tools-e2e

prod-up: kill-ports
	$(COMPOSE_PROD) $(PROFILES) up -d --build

prod-down:
	$(COMPOSE_PROD) $(PROFILES) down --remove-orphans

clean:
	$(COMPOSE) $(PROFILES) down -v --remove-orphans

install-env2mcp:
	pip install -e ./env2mcp

setup-github: install-env2mcp
	@env2mcp setup-github

generate-demo-repos:
	bash scripts/generate_demo_repos.sh

generate-demo-repos-github:
	GH_DEMO_PROVIDER=github bash scripts/generate_demo_repos.sh
