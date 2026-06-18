"""mcp-gateway: OpenAI-compatible HTTP shim for MCP skills + git2mcp.

Responsibilities:
- public entrypoint for OpenWebUI / external clients
- Bearer auth + tenant routing (tenants/*.yaml)
- /v1/models -> registered MCP skills
- /v1/chat/completions -> dispatches to skill workflow, streams SSE
- /jobs/* -> async job inspection
- /audit -> JSONL audit log writer
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

try:
    from redis import Redis
    from rq import Queue

    RQ_AVAILABLE = True
except Exception:
    Redis = None
    Queue = None
    RQ_AVAILABLE = False

try:
    from env2mcp import EnvConfig, GitHubCLI

    ENV2MCP_AVAILABLE = True
except Exception:
    ENV2MCP_AVAILABLE = False


from gateway_config import (
    AUDIT_LOG,
    GH2MCP_URL,
    GIT_PROXY_URL,
    GITHUB_API_URL,
    GITHUB_PAT,
    GITHUB_TOKEN,
    JOB_POLL_INTERVAL_SECONDS,
    JOB_TTL_SECONDS,
    LLM_MODEL,
    MAX_REPO_HISTORY,
    MCP_ASYNC_ENABLED,
    MCP_ENV_FILE,
    OPENROUTER_API_KEY,
    REDIS_URL,
    REPO_USAGE_TTL_SECONDS,
    RQ_QUEUE_NAME,
    SKILL_MODELS,
    SKILLS_URL,
    TENANTS_DIR,
)
from gateway_render import (
    build_commit_changes,
    render_analyze_text,
    render_chat_content,
    render_github_qa_text,
    render_queued_text,
    render_refactor_text,
    render_system_text,
    render_tool_text,
    render_tools_list_text,
    summary_text,
)
from gateway_github import (
    default_draft_name as _default_draft_name,
    extract_org_from_text as _extract_org_from_text,
    extract_repo_list_limit as _extract_repo_list_limit,
    github_repo_from_url as _github_repo_from_url,
    is_github_token_save_command as _is_github_token_save_command,
    is_github_token_sync_command as _is_github_token_sync_command,
    is_org_list_command as _is_org_list_command,
    is_org_set_command as _is_org_set_command,
    is_repo_list_command as _is_repo_list_command,
    normalize_repo_url as _normalize_repo_url,
    runtime_github_token as _runtime_github_token,
    save_github_token as _save_github_token,
)
from gateway_dispatch import dispatch_skill
from gateway_jobs import (
    execute_dispatch_job,
    get_rq_redis_client as _get_rq_redis_client,
    load_job as _load_job,
    queue_workflow_job as _queue_workflow_job,
    save_job as _save_job,
    update_job as _update_job,
)
from gateway_prompt import (
    SUPPORTED_TOOL_NAMES,
    extract_github_token_from_text as _extract_github_token_from_text,
    extract_owner_from_repo_template as _extract_owner_from_repo_template,
    extract_repo_template_expression as _extract_repo_template_expression,
    is_last_pushed_repo_template as _is_last_pushed_repo_template,
    message_content_to_text,
    normalize_command_text as _normalize_command_text,
    parse_bool,
    parse_prompt_context,
    parse_tool_intent,
)
from gateway_skills import (
    ask_openrouter_github_qa as _ask_openrouter_github_qa,
    expect_json as _expect_json,
    fetch_tools_list as _fetch_tools_list,
    is_tools_list_command as _is_tools_list_command,
    run_skills_tool as _run_skills_tool,
)

def load_tenants() -> dict[str, dict]:
    tenants: dict[str, dict] = {}
    if not TENANTS_DIR.exists():
        return tenants
    for path in TENANTS_DIR.glob("*.yaml"):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        tenant_id = data.get("tenant_id") or path.stem
        tenants[tenant_id] = data
    return tenants


def _get_redis_client() -> Redis | None:
    """Zwraca klienta Redis jeśli dostępny, w przeciwnym razie None."""
    if not RQ_AVAILABLE or not REDIS_URL:
        return None
    try:
        return Redis.from_url(REDIS_URL, decode_responses=True)
    except Exception:
        return None


def _track_repo_usage(tenant_id: str, repo_id: str, platform: str = "github") -> None:
    """Zapisuje użycie repozytorium w Redis dla celów śledzenia."""
    redis = _get_redis_client()
    if not redis:
        return
    try:
        # Klucz: mcp:repo_usage:{tenant_id}
        key = f"mcp:repo_usage:{tenant_id}"
        timestamp = int(time.time())
        # Zapisz jako hash: repo_id -> {timestamp, platform, count}
        redis.hset(key, repo_id, json.dumps({"timestamp": timestamp, "platform": platform, "count": 1}))
        # Aktualizuj licznik użycia
        redis.hincrby(f"mcp:repo_count:{tenant_id}", repo_id, 1)
        # Ustaw TTL
        redis.expire(key, REPO_USAGE_TTL_SECONDS)
        redis.expire(f"mcp:repo_count:{tenant_id}", REPO_USAGE_TTL_SECONDS)
    except Exception:
        pass


def _get_last_used_repo(tenant_id: str) -> str | None:
    """Zwraca ostatnio używane repozytorium dla danego tenantu."""
    redis = _get_redis_client()
    if not redis:
        return None
    try:
        key = f"mcp:repo_usage:{tenant_id}"
        if not redis.exists(key):
            return None
        # Pobierz wszystkie repozytoria i znajdź najnowsze
        repos = redis.hgetall(key)
        if not repos:
            return None
        latest_repo = None
        latest_timestamp = 0
        for repo_id, data_str in repos.items():
            try:
                data = json.loads(data_str)
                timestamp = data.get("timestamp", 0)
                if timestamp > latest_timestamp:
                    latest_timestamp = timestamp
                    latest_repo = repo_id
            except Exception:
                continue
        return latest_repo
    except Exception:
        return None


def _get_most_used_repo(tenant_id: str) -> str | None:
    """Zwraca najczęściej używane repozytorium dla danego tenantu."""
    redis = _get_redis_client()
    if not redis:
        return None
    try:
        key = f"mcp:repo_count:{tenant_id}"
        if not redis.exists(key):
            return None
        # Pobierz wszystkie liczniki i znajdź największy
        counts = redis.hgetall(key)
        if not counts:
            return None
        most_used_repo = None
        max_count = 0
        for repo_id, count_str in counts.items():
            try:
                count = int(count_str)
                if count > max_count:
                    max_count = count
                    most_used_repo = repo_id
            except Exception:
                continue
        return most_used_repo
    except Exception:
        return None


def _get_preferred_repo(tenant_id: str) -> str | None:
    """Zwraca preferowane repozytorium: ostatnio używane lub najczęściej używane."""
    # Priorytet: ostatnio używane > najczęściej używane > None
    return _get_last_used_repo(tenant_id) or _get_most_used_repo(tenant_id)


def _is_github_configured() -> bool:
    """Sprawdza czy GitHub jest skonfigurowany (token dostępny)."""
    return bool(_runtime_github_token())


async def _get_default_github_repo() -> dict[str, str] | None:
    """Pobiera domyślne repo z GitHub wraz z repo_url."""
    if not _is_github_configured() or not GH2MCP_URL:
        return None
    try:
        # Spróbuj pobrać ostatnio pushowane repo.
        resolved = await _last_pushed_repo_via_gh2mcp(owner=None, limit=10)
        if resolved.get("success") and resolved.get("repo"):
            repo_id = str(resolved["repo"])
            repo_url = str(resolved.get("repo_url") or f"https://github.com/{repo_id}.git")
            return {"repo_id": repo_id, "repo_url": repo_url}
    except Exception:
        pass
    return None


async def _sync_github_token_via_gh2mcp() -> dict[str, Any]:
    if not GH2MCP_URL:
        raise ValueError("GH2MCP_URL is not configured")

    async with httpx.AsyncClient(timeout=20.0) as client:
        sync_response = await client.post(
            f"{GH2MCP_URL}/sync/token",
            json={"force_gh_cli": True, "include_token": False},
        )
        sync_data = await _expect_json(sync_response, "gh2mcp sync token")

        status_response = await client.get(f"{GH2MCP_URL}/status")
        status_data = await _expect_json(status_response, "gh2mcp status")

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


async def _set_default_org_via_gh2mcp(org: str | None) -> dict[str, Any]:
    if not GH2MCP_URL:
        raise ValueError("GH2MCP_URL is not configured")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{GH2MCP_URL}/org/set",
            json={"org": org},
        )
        data = await _expect_json(response, "gh2mcp set org")

    return {
        "action": "set-default-github-org",
        "success": bool(data.get("success")),
        "org": data.get("org"),
        "error": data.get("error"),
        "note": data.get("note") or "Default org updated via gh2mcp/env2mcp.",
    }


async def _list_recent_repos_via_gh2mcp(
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
        data = await _expect_json(response, "gh2mcp recent repos")

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


async def _list_orgs_via_gh2mcp(repos_limit: int = 30) -> dict[str, Any]:
    if not GH2MCP_URL:
        raise ValueError("GH2MCP_URL is not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GH2MCP_URL}/org/list",
            json={"repos_limit": repos_limit},
        )
        data = await _expect_json(response, "gh2mcp list orgs")

    return {
        "action": "list-github-orgs-and-repos",
        "success": bool(data.get("success")),
        "error": data.get("error"),
        "user": data.get("user"),
        "org_count": data.get("org_count"),
        "orgs": data.get("orgs", []),
        "note": "Organizations and repositories listed via gh2mcp (gh CLI).",
    }


async def _gh2mcp_status_via_gh2mcp() -> dict[str, Any]:
    if not GH2MCP_URL:
        raise ValueError("GH2MCP_URL is not configured")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{GH2MCP_URL}/status")
        data = await _expect_json(response, "gh2mcp status")

    return {
        "action": "github-status",
        "success": bool(data.get("configured")),
        "error": data.get("error"),
        "configured": bool(data.get("configured")),
        "user": data.get("user"),
        "token_hint": data.get("token_hint"),
    }


async def _last_pushed_repo_via_gh2mcp(owner: str | None = None, limit: int = 100) -> dict[str, Any]:
    if not GH2MCP_URL:
        raise ValueError("GH2MCP_URL is not configured")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{GH2MCP_URL}/repo/last-pushed",
            json={"owner": owner, "limit": limit},
        )
        data = await _expect_json(response, "gh2mcp last pushed repo")

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


def _is_github_auth_error(error_text: str | None) -> bool:
    if not error_text:
        return False
    needle = error_text.lower()
    return any(hint in needle for hint in _GH_AUTH_ERROR_HINTS)


def _github_auth_recovery_message(original_error: str) -> str:
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


async def _resolve_repo_id_template(repo_value: str) -> tuple[str, dict[str, Any] | None]:
    expression = _extract_repo_template_expression(repo_value)
    if not expression:
        return repo_value, None

    if _is_last_pushed_repo_template(expression):
        owner = _extract_owner_from_repo_template(expression)
        resolved = await _last_pushed_repo_via_gh2mcp(owner=owner, limit=100)

        # Auto-recovery: detect GitHub auth errors and try to refresh token via gh2mcp.
        if (
            (not resolved.get("success") or not resolved.get("repo"))
            and _is_github_auth_error(resolved.get("error"))
        ):
            try:
                sync = await _sync_github_token_via_gh2mcp()
            except Exception as exc:  # noqa: BLE001
                sync = {"success": False, "error": str(exc)}

            if sync.get("success"):
                # Retry once with fresh token.
                resolved = await _last_pushed_repo_via_gh2mcp(owner=owner, limit=100)

            if not resolved.get("success") or not resolved.get("repo"):
                raise ValueError(
                    _github_auth_recovery_message(resolved.get("error") or "unknown error")
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


def _save_github_token_via_env2mcp(user_msg: str, prompt_ctx: dict[str, str]) -> dict[str, Any]:
    token = prompt_ctx.get("github_token") or _extract_github_token_from_text(user_msg)
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
        saved = _save_github_token(token)
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


def _repo_owner(repo_id: str | None) -> str | None:
    if not repo_id or "/" not in repo_id:
        return None
    return repo_id.split("/", 1)[0].strip() or None


async def _run_github_qa(
    user_request: str,
    repo_id: str | None = None,
    repo_url: str | None = None,
) -> dict[str, Any]:
    owner = _repo_owner(repo_id)
    github_context: dict[str, Any] = {
        "repo_id_hint": repo_id,
        "repo_url_hint": repo_url,
    }

    try:
        github_context["status"] = await _gh2mcp_status_via_gh2mcp()
    except Exception as exc:
        github_context["status"] = {"success": False, "error": str(exc)}

    try:
        github_context["recent_repos"] = await _list_recent_repos_via_gh2mcp(
            limit=10,
            owner=owner,
            include_orgs=owner is None,
        )
    except Exception as exc:
        github_context["recent_repos"] = {"success": False, "error": str(exc)}

    wants_orgs = bool(
        {"organizacja", "organizacje", "organization", "organizations", "org", "orgs"}
        & set(_normalize_command_text(user_request).split())
    )
    if wants_orgs:
        try:
            github_context["orgs"] = await _list_orgs_via_gh2mcp(repos_limit=10)
        except Exception as exc:
            github_context["orgs"] = {"success": False, "error": str(exc)}

    llm = await _ask_openrouter_github_qa(user_request, github_context)
    if not llm.get("ok"):
        error = str(llm.get("error") or "unknown llm error")
        if "OPENROUTER_API_KEY" in error:
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


TENANTS = load_tenants()


def find_tenant_by_key(api_key: str) -> dict | None:
    for tenant in TENANTS.values():
        if api_key in tenant.get("api_keys", []):
            return tenant
    return None


def authenticate(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    api_key = authorization.split(" ", 1)[1].strip()
    tenant = find_tenant_by_key(api_key)
    if not tenant:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return tenant


def audit(event: dict) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    event = {**event, "ts": time.time()}
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# Models exposed via OpenAI-compatible API (MCP skills as "models")
class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    async_mode: bool | None = None
    repo_id: str | None = None
    repo_url: str | None = None
    github_token: str | None = None
    source_path: str | None = None
    branch: str = "main"
    execute: bool | None = None
    push: bool | None = None
    draft: bool | None = None
    draft_name: str | None = None
    open_pr: bool | None = None
    pr_title: str | None = None
    pr_body: str | None = None
    pr_base: str | None = None
    test_command: str | None = None
    remote: str | None = None


app = FastAPI(title="mcp-gateway", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "mcp-gateway", "tenants": list(TENANTS.keys())}


@app.get("/v1/models")
def list_models(_: dict = Depends(authenticate)):
    return {
        "object": "list",
        "data": [
            {"id": model_id, "object": "model", "owned_by": "mcp-skills", **meta}
            for model_id, meta in SKILL_MODELS.items()
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest, tenant: dict = Depends(authenticate)):
    if req.model not in SKILL_MODELS:
        raise HTTPException(status_code=404, detail=f"Unknown model: {req.model}")

    skill = SKILL_MODELS[req.model]["skill"]
    if not tenant.get("features", {}).get(skill, False):
        raise HTTPException(status_code=403, detail=f"Feature '{skill}' not enabled for tenant")

    job_id = uuid.uuid4().hex
    _save_job(
        job_id,
        {
            "status": "pending",
            "tenant": tenant["tenant_id"],
            "skill": skill,
            "created_at": time.time(),
        },
    )
    audit({"event": "chat_completions", "tenant": tenant["tenant_id"], "model": req.model, "job_id": job_id})

    user_msg = next(
        (message_content_to_text(m.content) for m in reversed(req.messages) if m.role == "user"),
        "",
    )
    prompt_ctx = parse_prompt_context(user_msg)
    token_save_command = _is_github_token_save_command(user_msg, prompt_ctx)
    token_sync_command = _is_github_token_sync_command(user_msg, prompt_ctx)
    org_set_command = _is_org_set_command(user_msg)
    org_list_command = _is_org_list_command(user_msg)
    repo_list_command = _is_repo_list_command(user_msg)
    tool_intent = parse_tool_intent(user_msg, prompt_ctx)
    # If the user explicitly chose the tool model but provided no recognizable
    # intent, we still want to surface a helpful error in chat instead of falling
    # through to refactor/analyze.
    force_tool_skill = skill == "tool"
    if force_tool_skill and tool_intent is None:
        # Allow the runner to render an instructive message.
        tool_intent = {"tool": None, "repo_url": None, "repo_id": None, "args": []}

    tenant_id = tenant["tenant_id"]
    # Priorytet: jawne repo_id > repo_id z promptu > ostatnio/najczęściej używane > GitHub ostatnio pushowane > domyślne
    preferred_repo = _get_preferred_repo(tenant_id)
    repo_id_input = req.repo_id or prompt_ctx.get("repo_id") or preferred_repo
    repo_url = req.repo_url or prompt_ctx.get("repo_url")
    github_token = req.github_token or prompt_ctx.get("github_token")
    source_path = req.source_path or prompt_ctx.get("source_path")
    branch = req.branch
    if branch == "main" and prompt_ctx.get("branch"):
        branch = prompt_ctx["branch"]

    user_request = prompt_ctx.get("task") or user_msg
    execute_commit = req.execute if req.execute is not None else parse_bool(prompt_ctx.get("execute"), default=False)
    push_after_tests = req.push if req.push is not None else parse_bool(prompt_ctx.get("push"), default=False)
    create_draft_branch = req.draft if req.draft is not None else parse_bool(prompt_ctx.get("draft"), default=push_after_tests)
    draft_name_input = req.draft_name or prompt_ctx.get("draft_name")
    open_pull_request = req.open_pr if req.open_pr is not None else parse_bool(prompt_ctx.get("open_pr"), default=push_after_tests)
    pr_title = req.pr_title or prompt_ctx.get("pr_title")
    pr_body = req.pr_body or prompt_ctx.get("pr_body")
    pr_base = req.pr_base or prompt_ctx.get("pr_base") or branch
    test_command = req.test_command or prompt_ctx.get("test_command") or "python3 -m compileall -q ."
    push_remote = req.remote or prompt_ctx.get("remote") or "origin"
    async_mode = MCP_ASYNC_ENABLED if req.async_mode is None else req.async_mode

    async def runner() -> dict:
        nonlocal repo_id_input, repo_url
        # Dla analyze/refactor wymagamy repo; spróbuj pobrać domyślne z GitHub.
        if skill in {"analyze", "refactor"} and not repo_id_input:
            github_default = await _get_default_github_repo()
            if github_default:
                repo_id_input = github_default["repo_id"]
                if not repo_url:
                    repo_url = github_default.get("repo_url")
            else:
                repo_id_input = f"{tenant_id}/default"
        
        if org_set_command:
            org_value = _extract_org_from_text(user_msg, prompt_ctx)
            result = await _set_default_org_via_gh2mcp(org_value)
            return {
                "skill": "system",
                "tenant": tenant["tenant_id"],
                "repo_id": None,
                "user_request": user_request,
                "github": result,
            }

        if org_list_command:
            result = await _list_orgs_via_gh2mcp(repos_limit=30)
            return {
                "skill": "system",
                "tenant": tenant["tenant_id"],
                "repo_id": None,
                "user_request": user_request,
                "github": result,
            }

        if repo_list_command:
            limit = _extract_repo_list_limit(user_msg, default=10, max_limit=30)
            result = await _list_recent_repos_via_gh2mcp(limit=limit)
            return {
                "skill": "system",
                "tenant": tenant["tenant_id"],
                "repo_id": None,
                "user_request": user_request,
                "github": result,
            }

        if token_save_command:
            result = _save_github_token_via_env2mcp(user_msg, prompt_ctx)
            return {
                "skill": "system",
                "tenant": tenant["tenant_id"],
                "repo_id": None,
                "user_request": user_request,
                "github": result,
            }

        if token_sync_command:
            try:
                result = await _sync_github_token_via_gh2mcp()
                return {
                    "skill": "system",
                    "tenant": tenant["tenant_id"],
                    "repo_id": None,
                    "user_request": user_request,
                    "github": result,
                }
            except Exception as exc:
                return {
                    "skill": "system",
                    "tenant": tenant["tenant_id"],
                    "repo_id": None,
                    "user_request": user_request,
                    "github": {
                        "action": "sync-github-token-from-gh-cli",
                        "success": False,
                        "error": str(exc),
                    },
                }

        if skill == "github_qa":
            return await _run_github_qa(
                user_request=user_request,
                repo_id=repo_id_input,
                repo_url=repo_url,
            )

        # Lista dostępnych narzędzi
        if _is_tools_list_command(user_msg) or (force_tool_skill and _is_tools_list_command(user_request)):
            tools_list = await _fetch_tools_list()
            return {"skill": "tools_list", "tenant": tenant_id, "tools_list": tools_list}

        # NLP-routed tool execution (sumd / code2llm / redsl / ...)
        if tool_intent is not None:
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
                            + ". Przykład: 'wygeneruj sumd dla "
                            "https://github.com/owner/repo'."
                        ),
                    },
                }
            tool_repo_url = tool_intent.get("repo_url") or repo_url
            tool_repo_id = tool_intent.get("repo_id") or repo_id_input
            if not tool_repo_id and not tool_repo_url:
                github_default = await _get_default_github_repo()
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
                tool_result = await _run_skills_tool(
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
                _track_repo_usage(tenant_id, tool_repo_id, platform="github")
            return {
                "skill": "tool",
                "tenant": tenant_id,
                "repo_id": tool_repo_id,
                "user_request": user_request,
                "tool_result": tool_result,
            }

        try:
            resolved_repo_id, repo_selection = await _resolve_repo_id_template(repo_id_input)
            resolved_repo_url = (repo_selection or {}).get("repo_url") if not repo_url else None
            effective_repo_url = repo_url or resolved_repo_url
            draft_name = draft_name_input or _default_draft_name(resolved_repo_id)
            dispatch_payload = {
                "skill": skill,
                "tenant": tenant,
                "repo_id": resolved_repo_id,
                "repo_url": effective_repo_url,
                "github_token": github_token,
                "source_path": source_path,
                "branch": branch,
                "user_request": user_request,
                "execute_commit": execute_commit,
                "push_after_tests": push_after_tests,
                "create_draft_branch": create_draft_branch,
                "draft_name": draft_name,
                "open_pull_request": open_pull_request,
                "pr_title": pr_title,
                "pr_body": pr_body,
                "pr_base": pr_base,
                "test_command": test_command,
                "push_remote": push_remote,
                "repo_selection": repo_selection,
            }

            queue_error: str | None = None
            if async_mode and skill in {"analyze", "refactor"}:
                try:
                    _queue_workflow_job(job_id, dispatch_payload)
                    _update_job(
                        job_id,
                        status="queued",
                        phase="queued",
                        tenant=tenant["tenant_id"],
                        skill=skill,
                        repo_id=resolved_repo_id,
                        branch=branch,
                    )
                    return {
                        "skill": "queued",
                        "status": "queued",
                        "tenant": tenant["tenant_id"],
                        "repo_id": resolved_repo_id,
                        "branch": branch,
                        "job_id": job_id,
                        "note": "Workflow uruchomiony w tle (Redis/RQ worker).",
                    }
                except Exception as exc:
                    queue_error = str(exc)
                    _update_job(job_id, queue_error=queue_error)

            result = await dispatch_skill(
                skill=skill,
                tenant=tenant,
                repo_id=resolved_repo_id,
                repo_url=effective_repo_url,
                github_token=github_token,
                source_path=source_path,
                branch=branch,
                user_request=user_request,
                execute_commit=execute_commit,
                push_after_tests=push_after_tests,
                create_draft_branch=create_draft_branch,
                draft_name=draft_name,
                open_pull_request=open_pull_request,
                pr_title=pr_title,
                pr_body=pr_body,
                pr_base=pr_base,
                test_command=test_command,
                push_remote=push_remote,
                job_id=job_id,
            )
            if repo_selection:
                result["repo_selection"] = repo_selection
            if queue_error:
                fallback_note = (
                    "Queue unavailable; executed synchronously instead. "
                    f"Reason: {queue_error}"
                )
                existing_note = result.get("note")
                result["note"] = f"{existing_note} {fallback_note}" if existing_note else fallback_note
            # Śledź użycie repozytorium po udanej operacji
            if resolved_repo_id and not result.get("error"):
                _track_repo_usage(tenant_id, resolved_repo_id, platform="github")
            return result
        except Exception as exc:
            return {"error": str(exc)}

    completion_id = f"chatcmpl-{job_id}"
    created = int(time.time())

    if req.stream:
        async def event_stream():
            task = asyncio.create_task(runner())
            yield {
                "data": json.dumps(
                    {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": req.model,
                        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                    },
                    ensure_ascii=False,
                )
            }

            result = await task
            if result.get("skill") != "queued":
                _update_job(job_id, status="done", phase="done", result=result, completed_at=time.time())

            content = render_chat_content(result)
            yield {
                "data": json.dumps(
                    {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": req.model,
                        "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
                    },
                    ensure_ascii=False,
                )
            }

            if result.get("skill") == "queued":
                last_marker = "queued"
                while True:
                    await asyncio.sleep(JOB_POLL_INTERVAL_SECONDS)
                    state = _load_job(job_id) or {}
                    status = state.get("status") or "queued"
                    phase = state.get("phase") or status
                    marker = f"{status}:{phase}"
                    if marker != last_marker:
                        yield {
                            "data": json.dumps(
                                {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": req.model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {"content": f"\n\n_Status: `{phase}`_"},
                                            "finish_reason": None,
                                        }
                                    ],
                                },
                                ensure_ascii=False,
                            )
                        }
                        last_marker = marker
                    if status == "done":
                        final_result = state.get("result") or {
                            "error": "Job finished but no result payload",
                        }
                        yield {
                            "data": json.dumps(
                                {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": req.model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {"content": f"\n\n{render_chat_content(final_result)}"},
                                            "finish_reason": None,
                                        }
                                    ],
                                },
                                ensure_ascii=False,
                            )
                        }
                        break
                    if status == "failed":
                        error_result = {"error": state.get("error") or "Unknown background job error"}
                        yield {
                            "data": json.dumps(
                                {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": req.model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {"content": f"\n\n{render_chat_content(error_result)}"},
                                            "finish_reason": None,
                                        }
                                    ],
                                },
                                ensure_ascii=False,
                            )
                        }
                        break

            yield {
                "data": json.dumps(
                    {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": req.model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    },
                    ensure_ascii=False,
                )
            }
            yield {"data": "[DONE]"}
        return EventSourceResponse(event_stream())

    result = await runner()
    if result.get("skill") != "queued":
        _update_job(job_id, status="done", phase="done", result=result, completed_at=time.time())
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": render_chat_content(result)},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "job_id": job_id,
    }


@app.get("/jobs/{job_id}")
def get_job(job_id: str, _: dict = Depends(authenticate)):
    payload = _load_job(job_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return payload


@app.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str, _: dict = Depends(authenticate)):
    if _load_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_stream():
        last_marker = ""
        while True:
            state = _load_job(job_id) or {}
            status = state.get("status") or "pending"
            phase = state.get("phase") or status
            marker = f"{status}:{phase}:{state.get('updated_at')}"

            if marker != last_marker:
                payload = {
                    "job_id": job_id,
                    "status": status,
                    "phase": phase,
                    "updated_at": state.get("updated_at"),
                    "error": state.get("error"),
                }
                if status in {"done", "failed"}:
                    payload["result"] = state.get("result")
                yield {"data": json.dumps(payload, ensure_ascii=False)}
                last_marker = marker

            if status in {"done", "failed"}:
                break

            await asyncio.sleep(JOB_POLL_INTERVAL_SECONDS)

        yield {"data": "[DONE]"}

    return EventSourceResponse(event_stream())


@app.get("/audit/tail")
def audit_tail(limit: int = 100, _: dict = Depends(authenticate)):
    if not AUDIT_LOG.exists():
        return {"events": []}
    lines = AUDIT_LOG.read_text(encoding="utf-8").splitlines()[-limit:]
    return {"events": [json.loads(line) for line in lines if line.strip()]}


# Backward compatibility for tests
_summary_text = summary_text
_render_chat_content = render_chat_content
_render_analyze_text = render_analyze_text
_render_refactor_text = render_refactor_text
_render_tools_list_text = render_tools_list_text
_build_commit_changes = build_commit_changes
_render_system_text = render_system_text
_render_queued_text = render_queued_text
_render_tool_text = render_tool_text
_render_github_qa_text = render_github_qa_text
