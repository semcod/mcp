"""Run semcod CLI tools against materialized repos."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from http_models import ToolRunRequest

from tool_exec import (
    TOOL_INSTALL_CACHE,
    build_tool_command,
    build_tool_env,
    collect_output_files,
    ensure_tool_installed,
    execute_with_fallback,
    run_post_commands,
)
from tool_materialize import derive_repo_id_from_url, materialize_repo, resolve_repo_id
from tools_registry import SUPPORTED_TOOLS

__all__ = [
    "TOOL_INSTALL_CACHE",
    "collect_output_files",
    "derive_repo_id_from_url",
    "run_tool_against_repo",
]


async def run_tool_against_repo(request: ToolRunRequest, skills_server: Any) -> dict[str, Any]:
    tool_key = request.tool.strip().lower()
    spec = SUPPORTED_TOOLS.get(tool_key)
    if spec is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported tool '{request.tool}'. Known: {sorted(SUPPORTED_TOOLS)}",
        )

    repo_id = resolve_repo_id(request)
    base = Path(request.base_path or str(skills_server.repo_base))
    repo_path = base / repo_id

    materialized = await materialize_repo(request, skills_server, repo_id, repo_path)
    sync_info = materialized["sync"]
    if materialized.get("error"):
        return {
            "tool": tool_key,
            "repo_id": repo_id,
            "repo_url": request.repo_url,
            "sync": sync_info,
            "install": None,
            "command": None,
            "returncode": None,
            "ok": False,
            "error": materialized["error"],
        }

    install_info = ensure_tool_installed(
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

    cmd = build_tool_command(spec, install_info, request)
    env = build_tool_env(request)
    loop = asyncio.get_event_loop()
    binary_path = install_info["binary_path"] or spec["binary"]

    run_result = await execute_with_fallback(loop, spec, binary_path, repo_path, cmd, env, request)
    combined_stdout = await run_post_commands(
        loop, spec, binary_path, repo_path, env, request, run_result
    )

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
