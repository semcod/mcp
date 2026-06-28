"""Clone or sync repositories before running semcod CLI tools."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from http_models import ToolRunRequest

from tool_common import truncate_text


def inject_github_token(url: str) -> str:
    """Embed GITHUB_PAT / GH_TOKEN into a GitHub HTTPS URL for auth."""
    token = os.getenv("GITHUB_PAT") or os.getenv("GH_TOKEN") or ""
    if not token or "github.com" not in url:
        return url
    return url.replace("https://", f"https://{token}@", 1)


def _clone_ok(proc: subprocess.CompletedProcess) -> bool:
    """git may exit 0 but print fatal on stderr for private repos."""
    if proc.returncode != 0:
        return False
    stderr = (proc.stderr or "").lower()
    return "fatal:" not in stderr and "error:" not in stderr


def git_clone_or_update(repo_url: str, target_dir: Path, ref: str = "HEAD") -> dict[str, Any]:
    """Clone repo_url into target_dir, or fetch+reset if it already exists."""
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"
    authed_url = inject_github_token(repo_url)

    if not (target_dir / ".git").exists():
        if target_dir.exists() and any(target_dir.iterdir()):
            shutil.rmtree(target_dir, ignore_errors=True)
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", authed_url, str(target_dir)],
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
        ok = _clone_ok(proc)
        return {
            "action": "clone",
            "ok": ok,
            "returncode": proc.returncode,
            "stderr": truncate_text(proc.stderr or "", 4 * 1024),
        }

    fetch = subprocess.run(
        ["git", "-C", str(target_dir), "fetch", "--depth", "1", "origin"],
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    if fetch.returncode != 0:
        return {
            "action": "fetch",
            "ok": False,
            "returncode": fetch.returncode,
            "stderr": truncate_text(fetch.stderr or "", 4 * 1024),
        }
    target_ref = ref if ref and ref != "HEAD" else "FETCH_HEAD"
    reset = subprocess.run(
        ["git", "-C", str(target_dir), "reset", "--hard", target_ref],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return {
        "action": "fetch+reset",
        "ok": reset.returncode == 0,
        "returncode": reset.returncode,
        "stderr": truncate_text(reset.stderr or "", 4 * 1024),
    }


async def materialize_repo(
    request: ToolRunRequest,
    skills_server: Any,
    repo_id: str,
    repo_path: Path,
) -> dict[str, Any]:
    """Clone, git-proxy sync, or verify an existing local repo path."""
    sync_info: dict[str, Any] = {"strategy": None, "ok": False}
    if request.repo_url:
        sync_info = git_clone_or_update(request.repo_url, repo_path, request.ref)
        sync_info["strategy"] = "git_clone"
    elif request.use_git_proxy:
        try:
            proxy_sync = await skills_server._sync_from_git_proxy(repo_id, request.ref)
            sync_info = {"strategy": "git_proxy", "ok": True, **proxy_sync}
        except Exception as exc:
            sync_info = {"strategy": "git_proxy", "ok": False, "error": str(exc)}

    if not sync_info.get("ok") and not repo_path.exists():
        return {
            "sync": sync_info,
            "error": "Failed to materialize repository (no clone/sync succeeded).",
        }
    return {"sync": sync_info}


def derive_repo_id_from_url(repo_url: str) -> str:
    """Map https://github.com/owner/repo(.git) → 'owner/repo'."""
    cleaned = repo_url.strip()
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    cleaned = cleaned.rstrip("/")
    if "://" in cleaned:
        cleaned = cleaned.split("://", 1)[1]
    if "@" in cleaned and ":" in cleaned:
        cleaned = cleaned.split(":", 1)[1]
    parts = [p for p in cleaned.split("/") if p]
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return cleaned or "anon/repo"


def resolve_repo_id(request: ToolRunRequest) -> str:
    repo_id = (request.repo_id or "").strip()
    if not repo_id and request.repo_url:
        repo_id = derive_repo_id_from_url(request.repo_url)
    if not repo_id:
        raise HTTPException(status_code=400, detail="repo_id or repo_url is required")
    return repo_id
