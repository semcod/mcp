"""Focused handlers extracted from gateway chat workflow routing."""

from __future__ import annotations

from typing import Any

from gateway_gh2mcp import (
    get_default_github_repo,
    list_orgs_via_gh2mcp,
    list_recent_repos_via_gh2mcp,
    save_github_token_via_env2mcp,
    set_default_org_via_gh2mcp,
    sync_github_token_via_gh2mcp,
)
from gateway_github import extract_org_from_text, extract_repo_list_limit
from gateway_prompt import SUPPORTED_TOOL_NAMES
from gateway_skills import fetch_tools_list, is_tools_list_command, run_skills_tool
from gateway_tenants import track_repo_usage


def _system_result(tenant: dict, user_request: str, github: dict[str, Any]) -> dict[str, Any]:
    return {
        "skill": "system",
        "tenant": tenant["tenant_id"],
        "repo_id": None,
        "user_request": user_request,
        "github": github,
    }


async def handle_github_admin_commands(
    *,
    tenant: dict,
    user_msg: str,
    prompt_ctx: dict[str, str],
    user_request: str,
    org_set_command: bool,
    org_list_command: bool,
    repo_list_command: bool,
    token_save_command: bool,
    token_sync_command: bool,
) -> dict[str, Any] | None:
    if org_set_command:
        org_value = extract_org_from_text(user_msg, prompt_ctx)
        return _system_result(tenant, user_request, await set_default_org_via_gh2mcp(org_value))

    if org_list_command:
        return _system_result(tenant, user_request, await list_orgs_via_gh2mcp(repos_limit=30))

    if repo_list_command:
        limit = extract_repo_list_limit(user_msg, default=10, max_limit=30)
        return _system_result(tenant, user_request, await list_recent_repos_via_gh2mcp(limit=limit))

    if token_save_command:
        return _system_result(tenant, user_request, save_github_token_via_env2mcp(user_msg, prompt_ctx))

    if token_sync_command:
        try:
            result = await sync_github_token_via_gh2mcp()
        except Exception as exc:
            result = {
                "action": "sync-github-token-from-gh-cli",
                "success": False,
                "error": str(exc),
            }
        return _system_result(tenant, user_request, result)

    return None


async def handle_tools_list(
    *,
    tenant_id: str,
    user_msg: str,
    user_request: str,
    force_tool_skill: bool,
) -> dict[str, Any] | None:
    if not (is_tools_list_command(user_msg) or (force_tool_skill and is_tools_list_command(user_request))):
        return None
    tools_list = await fetch_tools_list()
    return {"skill": "tools_list", "tenant": tenant_id, "tools_list": tools_list}


async def handle_tool_intent(
    *,
    tenant: dict,
    tenant_id: str,
    tool_intent: dict[str, Any],
    repo_id_input: str | None,
    repo_url: str | None,
    user_request: str,
) -> dict[str, Any] | None:
    if tool_intent is None:
        return None

    if not tenant.get("features", {}).get("tool", True):
        return {
            "skill": "tool",
            "tenant": tenant_id,
            "tool_result": {
                "tool": tool_intent.get("tool"),
                "ok": False,
                "error": "Feature 'tool' not enabled for tenant.",
            },
        }

    if not tool_intent.get("tool"):
        return {
            "skill": "tool",
            "tenant": tenant_id,
            "tool_result": {
                "tool": None,
                "ok": False,
                "error": (
                    "Nie rozpoznałem nazwy narzędzia. Dostępne: "
                    + ", ".join(SUPPORTED_TOOL_NAMES)
                    + ". Przykład: 'wygeneruj sumd dla https://github.com/owner/repo'."
                ),
            },
        }

    tool_repo_url = tool_intent.get("repo_url") or repo_url
    tool_repo_id = tool_intent.get("repo_id") or repo_id_input
    if not tool_repo_id and not tool_repo_url:
        github_default = await get_default_github_repo()
        if github_default:
            tool_repo_id = github_default.get("repo_id")
            if not tool_repo_url:
                tool_repo_url = github_default.get("repo_url")

    if not tool_repo_id and not tool_repo_url:
        return {
            "skill": "tool",
            "tenant": tenant_id,
            "tool_result": {
                "tool": tool_intent.get("tool"),
                "ok": False,
                "error": "Brak repozytorium docelowego — podaj URL lub owner/repo.",
            },
        }

    try:
        tool_result = await run_skills_tool(
            tool=tool_intent["tool"],
            repo_id=tool_repo_id,
            repo_url=tool_repo_url,
            subcommand=tool_intent.get("subcommand"),
            args=tool_intent.get("args") or [],
        )
    except Exception as exc:
        tool_result = {
            "tool": tool_intent.get("tool"),
            "repo_id": tool_repo_id,
            "repo_url": tool_repo_url,
            "ok": False,
            "error": f"mcp-skills /tools/run failed: {exc}",
        }

    if tool_repo_id and tool_result.get("ok"):
        track_repo_usage(tenant_id, tool_repo_id, platform="github")

    return {
        "skill": "tool",
        "tenant": tenant_id,
        "repo_id": tool_repo_id,
        "user_request": user_request,
        "tool_result": tool_result,
    }
