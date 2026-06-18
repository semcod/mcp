"""Manifest and template generation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from semcod_mcp.paths import MANIFEST_NAME, default_api_key, gateway_url

SERVER_NAME = "semcod-mcp-skills"
CURSOR_RULE_NAME = "semcod-mcp.mdc"


def mcp_server_block(stack_path: Path) -> dict[str, Any]:
    compose = stack_path / "docker-compose.yml"
    return {
        "command": "docker",
        "args": [
            "compose",
            "-f",
            str(compose),
            "exec",
            "-T",
            "mcp-skills",
            "python",
            "server.py",
        ],
        "env": {
            "MCP_SKILLS_TRANSPORT": "stdio",
            "GIT_PROXY_URL": "http://mcp-git-proxy:8080",
            "SKILLS_REPO_BASE": "/skills-cache",
        },
    }


def continue_models(gw: str, api_key: str) -> list[dict[str, Any]]:
    base = {
        "provider": "openai",
        "apiBase": gw,
        "apiKey": api_key,
    }
    return [
        {**base, "title": "semcod-mcp-analyze", "model": "mcp-skills/analyze"},
        {**base, "title": "semcod-mcp-refactor", "model": "mcp-skills/refactor"},
        {**base, "title": "semcod-mcp-tool", "model": "mcp-skills/tool"},
    ]


def vscode_settings_snippet() -> dict[str, Any]:
    return {
        "semcod-mcp.gatewayUrl": gateway_url(None),
        "semcod-mcp.apiKey": default_api_key(),
    }


def cursor_rule_text(repo_id: str | None, stack_path: Path) -> str:
    repo_line = f"`{repo_id}`" if repo_id else "(auto from git remote)"
    return f"""---
description: semcod MCP quality pipeline — analyze before large refactors
globs:
  - "**/*"
---

# semcod MCP

Before non-trivial refactors in {repo_line}:

1. Run `semcod-mcp doctor` — stack must be healthy.
2. Use MCP server `semcod-mcp-skills` or gateway model `mcp-skills/analyze`.
3. After edits run `semcod-mcp validate` and local `pyqual run` if available.
4. Stack path: `{stack_path}`

Prompt template for gateway:

```
Repo: {repo_id or "org/repo"}
Branch: main
Execute: false
Zadanie: <opis zadania>
```
"""


def manifest_data(
    project_dir: Path,
    stack_path: Path,
    repo_id: str | None,
    ides: list[str],
) -> dict[str, Any]:
    return {
        "version": 1,
        "stack_path": str(stack_path),
        "gateway_url": gateway_url(stack_path),
        "api_key_env": "SEMCOD_MCP_API_KEY",
        "default_api_key": default_api_key(),
        "repo_id": repo_id,
        "project_dir": str(project_dir),
        "ides": sorted(set(ides)),
        "initialized_at": datetime.now(timezone.utc).isoformat(),
    }


def write_manifest(path: Path, data: dict[str, Any], *, dry_run: bool = False) -> None:
    if dry_run:
        return
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def read_manifest(project_dir: Path) -> dict[str, Any] | None:
    path = project_dir / MANIFEST_NAME
    if not path.is_file():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
