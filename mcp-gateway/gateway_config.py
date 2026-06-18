"""Environment configuration and skill model registry for mcp-gateway."""

from __future__ import annotations

import os
from pathlib import Path

TENANTS_DIR = Path(os.getenv("MCP_TENANTS_DIR", "/app/tenants"))
AUDIT_LOG = Path(os.getenv("MCP_AUDIT_LOG", "/audit/audit.jsonl"))
GIT_PROXY_URL = os.getenv("GIT_PROXY_URL", "http://mcp-git-proxy:8080")
SKILLS_URL = os.getenv("SKILLS_URL", "http://mcp-skills:8080")
GH2MCP_URL = os.getenv("GH2MCP_URL", "http://gh2mcp-agent:8079")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "openrouter/x-ai/grok-code-fast-1")
MCP_ENV_FILE = Path(os.getenv("MCP_ENV_FILE", "/app/.env"))
GITHUB_PAT = os.getenv("GITHUB_PAT", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API_URL = os.getenv("GITHUB_API_URL", "https://api.github.com")
MCP_ASYNC_ENABLED = os.getenv("MCP_ASYNC_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
    "tak",
    "on",
}
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
RQ_QUEUE_NAME = os.getenv("RQ_QUEUE_NAME", "mcp-jobs")
JOB_POLL_INTERVAL_SECONDS = 1.0
JOB_TTL_SECONDS = 86400
REPO_USAGE_TTL_SECONDS = 604800  # 7 dni - TTL dla historii użycia repozytoriów
MAX_REPO_HISTORY = 20  # Maksymalna liczba repozytoriów w historii


SKILL_MODELS = {
    "mcp-skills/refactor": {
        "description": "Autonomous refactoring loop using git2mcp + mcp-skills",
        "skill": "refactor",
    },
    "mcp-skills/analyze": {
        "description": "Static analysis & metrics through mcp-skills",
        "skill": "analyze",
    },
    "mcp-skills/tool": {
        "description": (
            "Run any semcod CLI tool (sumd, code2llm, code2docs, code2logic, "
            "redsl, redup, pyqual, domd, vallm, regix, regres, code2schema, "
            "clickmd, algitex) on a target repo. Routed by NLP intent."
        ),
        "skill": "tool",
    },
    "mcp-skills/github-qa": {
        "description": "General GitHub Q&A using gh2mcp context + OpenRouter LLM synthesis.",
        "skill": "github_qa",
    },
}
