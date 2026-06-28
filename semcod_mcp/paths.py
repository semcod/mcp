"""Path detection and repo metadata."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

MANIFEST_NAME = ".semcod-mcp.yaml"
DEFAULT_STACK_CANDIDATES = (
    "~/github/semcod/mcp",
    "~/github/wronai/mcp",
)


def expand(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def detect_stack_path(explicit: str | None = None) -> Path | None:
    if explicit:
        p = expand(explicit)
        return p if (p / "docker-compose.yml").is_file() else None

    env = os.getenv("SEMCOD_MCP_STACK")
    if env:
        p = expand(env)
        if (p / "docker-compose.yml").is_file():
            return p

    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / "docker-compose.yml").is_file() and (parent / "mcp-gateway").is_dir():
            return parent

    for candidate in DEFAULT_STACK_CANDIDATES:
        p = expand(candidate)
        if (p / "docker-compose.yml").is_file():
            return p
    return None


def infer_repo_id(project_dir: Path) -> str | None:
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=project_dir,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    url = url.removesuffix(".git")
    if url.startswith("git@"):
        # git@github.com:org/repo
        part = url.split(":", 1)[-1]
        return part if "/" in part else None
    if "github.com/" in url:
        return url.split("github.com/", 1)[-1]
    return None


def gateway_url(stack_path: Path | None) -> str:
    port = os.getenv("PORT_GATEWAY", "9000")
    return os.getenv("SEMCOD_MCP_GATEWAY_URL", f"http://localhost:{port}/v1")


def default_api_key() -> str:
    return os.getenv("SEMCOD_MCP_API_KEY", os.getenv("WEBUI_API_KEY", "sk-mcp-default-dev-key"))


def container_source_path(project_dir: Path, stack_path: Path | None) -> str | None:
    """Map host project dir to git-proxy mount (compose: ..:/host-semcod:ro).

    Example: ~/github/semcod/mcp → /host-semcod/mcp (live working tree, no commit).
    """
    if stack_path is None:
        return None
    project_dir = project_dir.resolve()
    stack_path = stack_path.resolve()
    host_root = stack_path.parent
    try:
        rel = project_dir.relative_to(host_root)
        return f"/host-semcod/{rel.as_posix()}"
    except ValueError:
        pass
    host_repos = stack_path / "repos"
    try:
        rel = project_dir.relative_to(host_repos.resolve())
        return f"/host-repos/{rel.as_posix()}"
    except ValueError:
        return None
