"""Run semcod CLI tools against materialized repos."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from http_models import ToolRunRequest

from tools_registry import SUPPORTED_TOOLS

_MAX_INLINE_FILE_BYTES = 64 * 1024
_MAX_STREAM_BYTES = 32 * 1024

# Cache of tools we've already attempted to install (avoid reinstall storm).
TOOL_INSTALL_CACHE: dict[str, dict[str, Any]] = {}


def _truncate_text(text: str, limit: int = _MAX_STREAM_BYTES) -> str:
    if not text:
        return ""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text
    truncated = encoded[:limit].decode("utf-8", errors="replace")
    return truncated + f"\n... [truncated, {len(encoded) - limit} more bytes]"


def _ensure_tool_installed(
    tool_name: str, package: str, binary: str, extra_pip_deps: list[str] | None = None
) -> dict[str, Any]:
    """Ensure a CLI tool binary is available, attempting `pip install <package>` if not."""
    cached = TOOL_INSTALL_CACHE.get(tool_name)
    if cached and cached.get("available"):
        # Still install extra_pip_deps if requested and not yet done.
        if extra_pip_deps and not cached.get("extra_deps_installed"):
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-cache-dir"] + extra_pip_deps,
                capture_output=True, text=True, timeout=120,
            )
            cached["extra_deps_installed"] = True
        return cached

    binary_path = shutil.which(binary)
    if binary_path:
        if extra_pip_deps:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-cache-dir"] + extra_pip_deps,
                capture_output=True, text=True, timeout=120,
            )
        info = {"available": True, "binary_path": binary_path, "installed_now": False, "extra_deps_installed": True}
        TOOL_INSTALL_CACHE[tool_name] = info
        return info

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-cache-dir", "--upgrade", package],
            capture_output=True,
            text=True,
            timeout=300,
        )
        installed_ok = proc.returncode == 0
        binary_path = shutil.which(binary)
        info: dict[str, Any] = {
            "available": bool(binary_path),
            "binary_path": binary_path,
            "installed_now": installed_ok,
            "pip_returncode": proc.returncode,
            "pip_stderr": _truncate_text(proc.stderr or "", 4 * 1024),
        }
    except subprocess.TimeoutExpired:
        info = {"available": False, "binary_path": None, "error": "pip install timeout"}
    except Exception as exc:
        info = {"available": False, "binary_path": None, "error": str(exc)}

    TOOL_INSTALL_CACHE[tool_name] = info
    return info


def _inject_github_token(url: str) -> str:
    """Embed GITHUB_PAT / GH_TOKEN into a GitHub HTTPS URL for auth."""
    token = os.getenv("GITHUB_PAT") or os.getenv("GH_TOKEN") or ""
    if not token:
        return url
    if "github.com" not in url:
        return url
    # https://github.com/... → https://<token>@github.com/...
    return url.replace("https://", f"https://{token}@", 1)


def _git_clone_or_update(repo_url: str, target_dir: Path, ref: str = "HEAD") -> dict[str, Any]:
    """Clone repo_url into target_dir, or fetch+reset if it already exists."""
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"
    authed_url = _inject_github_token(repo_url)

    def _clone_ok(proc: subprocess.CompletedProcess) -> bool:
        """git may exit 0 but print fatal on stderr for private repos."""
        if proc.returncode != 0:
            return False
        stderr = (proc.stderr or "").lower()
        return "fatal:" not in stderr and "error:" not in stderr

    if not (target_dir / ".git").exists():
        if target_dir.exists() and any(target_dir.iterdir()):
            shutil.rmtree(target_dir, ignore_errors=True)
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", authed_url, str(target_dir)],
            capture_output=True, text=True, timeout=300, env=env,
        )
        ok = _clone_ok(proc)
        return {
            "action": "clone",
            "ok": ok,
            "returncode": proc.returncode,
            "stderr": _truncate_text(proc.stderr or "", 4 * 1024),
        }

    fetch = subprocess.run(
        ["git", "-C", str(target_dir), "fetch", "--depth", "1", "origin"],
        capture_output=True, text=True, timeout=180, env=env,
    )
    if fetch.returncode != 0:
        return {
            "action": "fetch",
            "ok": False,
            "returncode": fetch.returncode,
            "stderr": _truncate_text(fetch.stderr or "", 4 * 1024),
        }
    target_ref = ref if ref and ref != "HEAD" else "FETCH_HEAD"
    reset = subprocess.run(
        ["git", "-C", str(target_dir), "reset", "--hard", target_ref],
        capture_output=True, text=True, timeout=120, env=env,
    )
    return {
        "action": "fetch+reset",
        "ok": reset.returncode == 0,
        "returncode": reset.returncode,
        "stderr": _truncate_text(reset.stderr or "", 4 * 1024),
    }


def derive_repo_id_from_url(repo_url: str) -> str:
    """Map https://github.com/owner/repo(.git) → 'owner/repo'."""
    cleaned = repo_url.strip()
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    cleaned = cleaned.rstrip("/")
    if "://" in cleaned:
        cleaned = cleaned.split("://", 1)[1]
    if "@" in cleaned and ":" in cleaned:
        # git@github.com:owner/repo style
        cleaned = cleaned.split(":", 1)[1]
    parts = [p for p in cleaned.split("/") if p]
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return cleaned or "anon/repo"


def collect_output_files(repo_path: Path, paths: list[str]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rel in paths:
        candidate = (repo_path / rel).resolve()
        try:
            candidate.relative_to(repo_path.resolve())
        except ValueError:
            continue
        if str(candidate) in seen:
            continue
        seen.add(str(candidate))
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            data = candidate.read_bytes()
        except Exception as exc:
            collected.append({"path": rel, "error": str(exc)})
            continue
        if len(data) == 0:
            continue
        truncated = len(data) > _MAX_INLINE_FILE_BYTES
        text: str | None
        try:
            text = data[: _MAX_INLINE_FILE_BYTES].decode("utf-8")
        except UnicodeDecodeError:
            text = None
        collected.append({
            "path": rel,
            "size": len(data),
            "truncated": truncated,
            "content": text,
            "binary": text is None,
        })
    return collected


async def run_tool_against_repo(request: ToolRunRequest, skills_server: Any) -> dict[str, Any]:
    tool_key = request.tool.strip().lower()
    spec = SUPPORTED_TOOLS.get(tool_key)
    if spec is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported tool '{request.tool}'. Known: {sorted(SUPPORTED_TOOLS)}",
        )

    repo_id = (request.repo_id or "").strip()
    if not repo_id and request.repo_url:
        repo_id = derive_repo_id_from_url(request.repo_url)
    if not repo_id:
        raise HTTPException(status_code=400, detail="repo_id or repo_url is required")

    base = Path(request.base_path or str(skills_server.repo_base))
    repo_path = base / repo_id

    # 1. Materialize the repo locally.
    sync_info: dict[str, Any] = {"strategy": None, "ok": False}
    if request.repo_url:
        sync_info = _git_clone_or_update(request.repo_url, repo_path, request.ref)
        sync_info["strategy"] = "git_clone"
    elif request.use_git_proxy:
        try:
            proxy_sync = await skills_server._sync_from_git_proxy(repo_id, request.ref)
            sync_info = {"strategy": "git_proxy", "ok": True, **proxy_sync}
        except Exception as exc:
            sync_info = {"strategy": "git_proxy", "ok": False, "error": str(exc)}

    if not sync_info.get("ok") and not repo_path.exists():
        return {
            "tool": tool_key,
            "repo_id": repo_id,
            "repo_url": request.repo_url,
            "sync": sync_info,
            "install": None,
            "command": None,
            "returncode": None,
            "ok": False,
            "error": "Failed to materialize repository (no clone/sync succeeded).",
        }

    # 2. Ensure binary available.
    install_info = _ensure_tool_installed(
        tool_key, spec["package"], spec["binary"], spec.get("extra_pip_deps")
    )
    if request.auto_install is False and not install_info.get("available"):
        install_info = {**install_info, "skipped": True}
    if not install_info.get("available"):
        return {
            "tool": tool_key,
            "repo_id": repo_id,
            "repo_url": request.repo_url,
            "sync": sync_info,
            "install": install_info,
            "command": None,
            "returncode": None,
            "ok": False,
            "error": f"Tool '{tool_key}' is not installed and auto_install failed.",
        }

    # 3. Build command.
    binary_path = install_info["binary_path"] or spec["binary"]
    cmd: list[str] = [binary_path]
    if request.subcommand:
        cmd.append(request.subcommand)
    elif spec.get("default_subcommand"):
        cmd.append(spec["default_subcommand"])
    if request.args:
        cmd.extend(str(a) for a in request.args)
    else:
        cmd.extend(spec.get("default_args", []))

    env = os.environ.copy()
    for key in ("OPENROUTER_API_KEY", "LLM_MODEL", "OPENAI_API_KEY", "GITHUB_TOKEN"):
        val = os.getenv(key)
        if val:
            env[key] = val
    env.update({k: str(v) for k, v in (request.env or {}).items()})

    loop = asyncio.get_event_loop()

    def _run() -> dict[str, Any]:
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=request.timeout,
                env=env,
            )
            return {
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": _truncate_text(proc.stdout or ""),
                "stderr": _truncate_text(proc.stderr or ""),
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "ok": False,
                "returncode": None,
                "stdout": _truncate_text(exc.stdout or "") if isinstance(exc.stdout, str) else "",
                "stderr": f"timeout after {request.timeout}s",
            }
        except FileNotFoundError as exc:
            return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc)}

    run_result = await loop.run_in_executor(None, _run)

    # 3b. Fallback: if main command failed and spec defines fallback_subcommand,
    # run fallback (e.g. sumd map), touch a project marker, then retry main command.
    if not run_result.get("ok") and spec.get("fallback_subcommand"):
        fb_cmd = [binary_path, spec["fallback_subcommand"]] + [str(a) for a in spec.get("fallback_args", [])]

        def _run_fallback(c: list[str] = fb_cmd) -> dict[str, Any]:
            try:
                p = subprocess.run(c, cwd=str(repo_path), capture_output=True, text=True, timeout=request.timeout, env=env)
                return {"ok": p.returncode == 0, "stdout": p.stdout or "", "stderr": p.stderr or ""}
            except Exception as exc:
                return {"ok": False, "stdout": "", "stderr": str(exc)}

        fb_result = await loop.run_in_executor(None, _run_fallback)
        # Touch key_outputs[0] as project marker so scan can find it.
        key_outputs = spec.get("key_outputs", [])
        if key_outputs:
            marker = repo_path / key_outputs[0]
            if not marker.exists():
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.touch()
        # Retry main command now that the marker exists.
        retry_result = await loop.run_in_executor(None, _run)
        combined_fb_stdout = (fb_result.get("stdout") or "").rstrip("\n") + "\n\n" + (retry_result.get("stdout") or "")
        run_result = {**retry_result, "stdout": combined_fb_stdout}

    post_stdout_parts: list[str] = []
    if run_result.get("ok") and spec.get("post_commands"):
        for post_args in spec["post_commands"]:
            post_cmd = [binary_path] + [str(a) for a in post_args]

            def _run_post(c: list[str] = post_cmd) -> dict[str, Any]:
                try:
                    p = subprocess.run(
                        c,
                        cwd=str(repo_path),
                        capture_output=True,
                        text=True,
                        timeout=request.timeout,
                        env=env,
                    )
                    return {"ok": p.returncode == 0, "stdout": p.stdout or "", "stderr": p.stderr or ""}
                except Exception as exc:
                    return {"ok": False, "stdout": "", "stderr": str(exc)}

            post_result = await loop.run_in_executor(None, _run_post)
            if post_result.get("stdout"):
                post_stdout_parts.append(post_result["stdout"])

    combined_stdout = run_result.get("stdout", "")
    if post_stdout_parts:
        combined_stdout = combined_stdout.rstrip("\n") + "\n\n" + "\n".join(post_stdout_parts)

    # 4. Collect well-known output files.
    output_files = collect_output_files(repo_path, list(spec.get("key_outputs", [])))
    summary_files = collect_output_files(repo_path, list(spec.get("summary_files", [])))

    return {
        "tool": tool_key,
        "tool_description": spec.get("description"),
        "repo_id": repo_id,
        "repo_url": request.repo_url,
        "repo_path": str(repo_path),
        "sync": sync_info,
        "install": install_info,
        "command": cmd,
        "returncode": run_result.get("returncode"),
        "ok": bool(run_result.get("ok")),
        "stdout": combined_stdout,
        "stderr": run_result.get("stderr", ""),
        "output_files": output_files,
        "summary_files": summary_files,
    }

