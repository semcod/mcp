"""gh2mcp-agent HTTP client, repo templates, and GitHub Q&A."""

from __future__ import annotations

from typing import Any

import httpx

from gateway_config import GH2MCP_URL, LLM_MODEL
import gateway_config
from gateway_github import (
    extract_github_token_from_text,
    runtime_github_token,
    save_github_token,
)
from gateway_prompt import (
    extract_owner_from_repo_template,
    extract_repo_template_expression,
    is_last_pushed_repo_template,
    normalize_command_text,
)
from gateway_skills import ask_openrouter_github_qa, expect_json


def _gateway_hooks():
    """Late import so tests can monkeypatch `server._last_pushed_repo_via_gh2mcp` etc."""
    import server as gateway

    return gateway


def is_github_configured() -> bool:
    return bool(runtime_github_token())


async def get_default_github_repo() -> dict[str, str] | None:
    if not is_github_configured() or not GH2MCP_URL:
        return None
    try:
        resolved = await last_pushed_repo_via_gh2mcp(owner=None, limit=10)
        if resolved.get("success") and resolved.get("repo"):
            repo_id = str(resolved["repo"])
            repo_url = str(resolved.get("repo_url") or f"https://github.com/{repo_id}.git")
            return {"repo_id": repo_id, "repo_url": repo_url}
    except Exception:
        pass
    return None


async def sync_github_token_via_gh2mcp() -> dict[str, Any]:
    if not GH2MCP_URL:
        raise ValueError("GH2MCP_URL is not configured")

    async with httpx.AsyncClient(timeout=20.0) as client:
        sync_response = await client.post(
            f"{GH2MCP_URL}/sync/token",
            json={"force_gh_cli": True, "include_token": False},
        )
        sync_data = await expect_json(sync_response, "gh2mcp sync token")

        status_response = await client.get(f"{GH2MCP_URL}/status")
        status_data = await expect_json(status_response, "gh2mcp status")

    success = bool(sync_data.get("success"))
    if success:
        note = "Token synchronized via gh2mcp-agent (/sync/token) and saved to /app/.env for MCP services."
    else:
        note = (
            "Token sync via gh2mcp-agent failed; current token status is shown from /status. "
            "Run 'gh auth login' on host and restart stack with 'make restart'."
        )

    return {
        "action": "sync-github-token-from-gh-cli",
        "success": success,
        "method": "gh auth token",
        "source": sync_data.get("source"),
        "error": sync_data.get("error"),
        "github": {
            "configured": bool(status_data.get("configured")),
            "token_hint": status_data.get("token_hint"),
            "user": status_data.get("user"),
        },
        "note": note,
    }


async def set_default_org_via_gh2mcp(org: str | None) -> dict[str, Any]:
    if not GH2MCP_URL:
        raise ValueError("GH2MCP_URL is not configured")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{GH2MCP_URL}/org/set",
            json={"org": org},
        )
        data = await expect_json(response, "gh2mcp set org")

    return {
        "action": "set-default-github-org",
        "success": bool(data.get("success")),
        "org": data.get("org"),
        "error": data.get("error"),
        "note": data.get("note") or "Default org updated via gh2mcp/env2mcp.",
    }


async def list_recent_repos_via_gh2mcp(
    limit: int = 10,
    owner: str | None = None,
    include_orgs: bool = True,
) -> dict[str, Any]:
    if not GH2MCP_URL:
        raise ValueError("GH2MCP_URL is not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GH2MCP_URL}/repo/recent",
            json={"limit": limit, "owner": owner, "include_orgs": include_orgs},
        )
        data = await expect_json(response, "gh2mcp recent repos")

    return {
        "action": "list-recent-github-repos",
        "success": bool(data.get("success")),
        "error": data.get("error"),
        "user": data.get("user"),
        "count": data.get("count"),
        "repos": data.get("repos", []),
        "owners_checked": data.get("owners_checked", []),
        "note": "Recent repositories listed via gh2mcp (gh CLI, pushedAt desc).",
    }


async def list_orgs_via_gh2mcp(repos_limit: int = 30) -> dict[str, Any]:
    if not GH2MCP_URL:
        raise ValueError("GH2MCP_URL is not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GH2MCP_URL}/org/list",
            json={"repos_limit": repos_limit},
        )
        data = await expect_json(response, "gh2mcp list orgs")

    return {
        "action": "list-github-orgs-and-repos",
        "success": bool(data.get("success")),
        "error": data.get("error"),
        "user": data.get("user"),
        "org_count": data.get("org_count"),
        "orgs": data.get("orgs", []),
        "note": "Organizations and repositories listed via gh2mcp (gh CLI).",
    }


async def gh2mcp_status_via_gh2mcp() -> dict[str, Any]:
    if not GH2MCP_URL:
        raise ValueError("GH2MCP_URL is not configured")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{GH2MCP_URL}/status")
        data = await expect_json(response, "gh2mcp status")

    return {
        "action": "github-status",
        "success": bool(data.get("configured")),
        "error": data.get("error"),
        "configured": bool(data.get("configured")),
        "user": data.get("user"),
        "token_hint": data.get("token_hint"),
    }


async def last_pushed_repo_via_gh2mcp(owner: str | None = None, limit: int = 100) -> dict[str, Any]:
    if not GH2MCP_URL:
        raise ValueError("GH2MCP_URL is not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GH2MCP_URL}/repo/last-pushed",
            json={"owner": owner, "limit": limit},
        )
        data = await expect_json(response, "gh2mcp last pushed repo")

    return {
        "action": "resolve-last-pushed-repo",
        "success": bool(data.get("success")),
        "error": data.get("error"),
        "owner": data.get("owner"),
        "repo": data.get("repo"),
        "repo_url": data.get("repo_url"),
        "pushed_at": data.get("pushed_at"),
        "source": data.get("source"),
    }


_GH_AUTH_ERROR_HINTS = (
    "401",
    "requires authentication",
    "gh auth login",
    "no token",
    "bad credentials",
    "could not resolve to a user",
)


def is_github_auth_error(error_text: str | None) -> bool:
    if not error_text:
        return False
    needle = error_text.lower()
    return any(hint in needle for hint in _GH_AUTH_ERROR_HINTS)


def github_auth_recovery_message(original_error: str) -> str:
    return (
        "❌ GitHub odrzucił żądanie (auth error): "
        f"{original_error.strip()}\n\n"
        "🔧 Spróbowano automatycznie odświeżyć token przez gh2mcp (`gh auth token`) i zapisać "
        "do `.env` przez env2mcp, ale to nie pomogło.\n\n"
        "Wybierz jedną z opcji:\n"
        "1) **W czacie podaj token bezpośrednio:**\n"
        "   `Zapisz token github do .env: ghp_xxx...`\n"
        "2) **Zaloguj się przez gh CLI na hoście, potem odśwież w czacie:**\n"
        "   `gh auth login` → `Pobierz token github`\n"
        "3) **Z terminala:**\n"
        "   `env2mcp env set GITHUB_PAT ghp_xxx` → `make reload-gateway`\n\n"
        "Po zapisaniu tokenu spróbuj ponownie ten sam prompt."
    )


async def resolve_repo_id_template(repo_value: str) -> tuple[str, dict[str, Any] | None]:
    expression = extract_repo_template_expression(repo_value)
    if not expression:
        return repo_value, None

    if is_last_pushed_repo_template(expression):
        owner = extract_owner_from_repo_template(expression)
        gw = _gateway_hooks()
        resolved = await gw._last_pushed_repo_via_gh2mcp(owner=owner, limit=100)

        if (
            (not resolved.get("success") or not resolved.get("repo"))
            and is_github_auth_error(resolved.get("error"))
        ):
            try:
                sync = await gw._sync_github_token_via_gh2mcp()
            except Exception as exc:  # noqa: BLE001
                sync = {"success": False, "error": str(exc)}

            if sync.get("success"):
                resolved = await gw._last_pushed_repo_via_gh2mcp(owner=owner, limit=100)

            if not resolved.get("success") or not resolved.get("repo"):
                raise ValueError(
                    github_auth_recovery_message(resolved.get("error") or "unknown error")
                )

        if not resolved.get("success") or not resolved.get("repo"):
            raise ValueError(
                "Repo template resolution failed for last pushed GitHub repository: "
                f"{resolved.get('error') or 'unknown error'}"
            )
        selected_repo = str(resolved["repo"]).strip()
        return selected_repo, {
            "strategy": "last_pushed_repo_from_github",
            "input": repo_value,
            "resolved_repo_id": selected_repo,
            "owner": resolved.get("owner"),
            "repo_url": resolved.get("repo_url"),
            "pushed_at": resolved.get("pushed_at"),
            "source": resolved.get("source"),
        }

    raise ValueError(
        "Unsupported Repo template. Supported example: {{show last pushed repo from github}}"
    )


def save_github_token_via_env2mcp(user_msg: str, prompt_ctx: dict[str, str]) -> dict[str, Any]:
    token = prompt_ctx.get("github_token") or extract_github_token_from_text(user_msg)
    if not token:
        return {
            "action": "save-github-token-to-env",
            "success": False,
            "error": "No token value found. Use: 'Zapisz token github do .env: ghp_xxx'",
            "github": {
                "configured": False,
                "token_hint": None,
                "user": None,
            },
            "note": "Provide a GitHub token value in the command.",
        }

    try:
        saved = save_github_token(token)
        return {
            "action": "save-github-token-to-env",
            "success": True,
            "method": "env2mcp.EnvConfig",
            "error": None,
            "github": {
                "configured": True,
                "token_hint": token[:8] + "...",
                "user": saved.get("github_user"),
                "env_file": saved.get("env_file"),
            },
            "note": "Token saved via env2mcp to .env as GITHUB_PAT.",
        }
    except Exception as exc:
        return {
            "action": "save-github-token-to-env",
            "success": False,
            "error": str(exc),
            "github": {
                "configured": False,
                "token_hint": None,
                "user": None,
            },
            "note": "env2mcp could not save token to .env.",
        }


def repo_owner(repo_id: str | None) -> str | None:
    if not repo_id or "/" not in repo_id:
        return None
    return repo_id.split("/", 1)[0].strip() or None


async def run_github_qa(
    user_request: str,
    repo_id: str | None = None,
    repo_url: str | None = None,
) -> dict[str, Any]:
    owner = repo_owner(repo_id)
    github_context: dict[str, Any] = {
        "repo_id_hint": repo_id,
        "repo_url_hint": repo_url,
    }
    gw = _gateway_hooks()

    try:
        github_context["status"] = await gw._gh2mcp_status_via_gh2mcp()
    except Exception as exc:
        github_context["status"] = {"success": False, "error": str(exc)}

    try:
        github_context["recent_repos"] = await gw._list_recent_repos_via_gh2mcp(
            limit=10,
            owner=owner,
            include_orgs=owner is None,
        )
    except Exception as exc:
        github_context["recent_repos"] = {"success": False, "error": str(exc)}

    wants_orgs = bool(
        {"organizacja", "organizacje", "organization", "organizations", "org", "orgs"}
        & set(normalize_command_text(user_request).split())
    )
    if wants_orgs:
        try:
            github_context["orgs"] = await gw._list_orgs_via_gh2mcp(repos_limit=10)
        except Exception as exc:
            github_context["orgs"] = {"success": False, "error": str(exc)}

    llm = await gw._ask_openrouter_github_qa(user_request, github_context)
    if not llm.get("ok"):
        error = str(llm.get("error") or "unknown llm error")
        if "OPENROUTER_API_KEY" in error or (
            "OpenRouter HTTP 401" in error and not gateway_config.OPENROUTER_API_KEY
        ):
            answer = (
                "⚠️ GitHub Q&A wymaga `OPENROUTER_API_KEY`. "
                "Ustaw klucz w `.env` i zrestartuj gateway (`make reload-gateway`)."
            )
        else:
            answer = (
                "⚠️ Nie udało się pobrać odpowiedzi z OpenRouter. "
                "Sprawdź konfigurację LLM i spróbuj ponownie."
            )
        return {
            "skill": "github_qa",
            "ok": False,
            "repo_id": repo_id,
            "repo_url": repo_url,
            "question": user_request,
            "answer": answer,
            "error": error,
            "github_context": github_context,
            "llm": {
                "provider": "openrouter",
                "model": LLM_MODEL,
                "used": False,
            },
        }

    return {
        "skill": "github_qa",
        "ok": True,
        "repo_id": repo_id,
        "repo_url": repo_url,
        "question": user_request,
        "answer": llm.get("answer") or "",
        "github_context": github_context,
        "llm": {
            "provider": "openrouter",
            "model": LLM_MODEL,
            "used": True,
        },
    }
