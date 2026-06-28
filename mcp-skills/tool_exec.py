"""Install semcod CLI tools and execute them against a materialized repo."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from http_models import ToolRunRequest

from tool_common import _MAX_INLINE_FILE_BYTES, truncate_text

TOOL_INSTALL_CACHE: dict[str, dict[str, Any]] = {}


def ensure_tool_installed(
    tool_name: str, package: str, binary: str, extra_pip_deps: list[str] | None = None
) -> dict[str, Any]:
    """Ensure a CLI tool binary is available, attempting `pip install <package>` if not."""
    cached = TOOL_INSTALL_CACHE.get(tool_name)
    if cached and cached.get("available"):
        if extra_pip_deps and not cached.get("extra_deps_installed"):
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-cache-dir"] + extra_pip_deps,
                capture_output=True,
                text=True,
                timeout=120,
            )
            cached["extra_deps_installed"] = True
        return cached

    binary_path = shutil.which(binary)
    if binary_path:
        if extra_pip_deps:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-cache-dir"] + extra_pip_deps,
                capture_output=True,
                text=True,
                timeout=120,
            )
        info = {
            "available": True,
            "binary_path": binary_path,
            "installed_now": False,
            "extra_deps_installed": True,
        }
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
            "pip_stderr": truncate_text(proc.stderr or "", 4 * 1024),
        }
    except subprocess.TimeoutExpired:
        info = {"available": False, "binary_path": None, "error": "pip install timeout"}
    except Exception as exc:
        info = {"available": False, "binary_path": None, "error": str(exc)}

    TOOL_INSTALL_CACHE[tool_name] = info
    return info


def build_tool_command(spec: dict[str, Any], install_info: dict[str, Any], request: ToolRunRequest) -> list[str]:
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
    return cmd


def build_tool_env(request: ToolRunRequest) -> dict[str, str]:
    env = os.environ.copy()
    for key in ("OPENROUTER_API_KEY", "LLM_MODEL", "OPENAI_API_KEY", "GITHUB_TOKEN"):
        val = os.getenv(key)
        if val:
            env[key] = val
    env.update({k: str(v) for k, v in (request.env or {}).items()})
    return env


def run_subprocess(cmd: list[str], repo_path: Path, env: dict[str, str], timeout: int) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": truncate_text(proc.stdout or ""),
            "stderr": truncate_text(proc.stderr or ""),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": truncate_text(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            "stderr": f"timeout after {timeout}s",
        }
    except FileNotFoundError as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc)}


async def run_in_executor(loop: asyncio.AbstractEventLoop, fn) -> dict[str, Any]:
    return await loop.run_in_executor(None, fn)


async def execute_with_fallback(
    loop: asyncio.AbstractEventLoop,
    spec: dict[str, Any],
    binary_path: str,
    repo_path: Path,
    cmd: list[str],
    env: dict[str, str],
    request: ToolRunRequest,
) -> dict[str, Any]:
    run_result = await run_in_executor(
        loop, lambda: run_subprocess(cmd, repo_path, env, request.timeout)
    )
    if run_result.get("ok") or not spec.get("fallback_subcommand"):
        return run_result

    fb_cmd = [binary_path, spec["fallback_subcommand"]] + [
        str(a) for a in spec.get("fallback_args", [])
    ]

    def _run_fallback() -> dict[str, Any]:
        try:
            p = subprocess.run(
                fb_cmd,
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=request.timeout,
                env=env,
            )
            return {"ok": p.returncode == 0, "stdout": p.stdout or "", "stderr": p.stderr or ""}
        except Exception as exc:
            return {"ok": False, "stdout": "", "stderr": str(exc)}

    fb_result = await run_in_executor(loop, _run_fallback)
    key_outputs = spec.get("key_outputs", [])
    if key_outputs:
        marker = repo_path / key_outputs[0]
        if not marker.exists():
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch()

    retry_result = await run_in_executor(
        loop, lambda: run_subprocess(cmd, repo_path, env, request.timeout)
    )
    combined_stdout = (fb_result.get("stdout") or "").rstrip("\n") + "\n\n" + (
        retry_result.get("stdout") or ""
    )
    return {**retry_result, "stdout": combined_stdout}


async def run_post_commands(
    loop: asyncio.AbstractEventLoop,
    spec: dict[str, Any],
    binary_path: str,
    repo_path: Path,
    env: dict[str, str],
    request: ToolRunRequest,
    run_result: dict[str, Any],
) -> str:
    combined_stdout = run_result.get("stdout", "")
    if not run_result.get("ok") or not spec.get("post_commands"):
        return combined_stdout

    post_stdout_parts: list[str] = []
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

        post_result = await run_in_executor(loop, _run_post)
        if post_result.get("stdout"):
            post_stdout_parts.append(post_result["stdout"])

    if post_stdout_parts:
        return combined_stdout.rstrip("\n") + "\n\n" + "\n".join(post_stdout_parts)
    return combined_stdout


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
            text = data[:_MAX_INLINE_FILE_BYTES].decode("utf-8")
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
