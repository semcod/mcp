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


async def _get_default_github_repo() -> str | None:
    """Pobiera domyślne repo z GitHub: ostatnio pushowane lub pierwsze z listy."""
    if not _is_github_configured() or not GH2MCP_URL:
        return None
    try:
        # Spróbuj pobrać ostatnio pushowane repo
        resolved = await _last_pushed_repo_via_gh2mcp(owner=None, limit=10)
        if resolved.get("success") and resolved.get("repo"):
            return resolved["repo"]
    except Exception:
        pass
    return None


PROMPT_FIELD_REGEX = {
    "repo_id": re.compile(r"^\s*Repo\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "repo_url": re.compile(r"^\s*Repo\s*URL\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "github_token": re.compile(r"^\s*(?:GitHub\s*Token|Github\s*Token|Token)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "source_path": re.compile(r"^\s*Source\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "branch": re.compile(r"^\s*Branch\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "task": re.compile(r"^\s*Zadanie\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "execute": re.compile(r"^\s*(?:Execute|Wykonaj)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "push": re.compile(r"^\s*(?:Push|Wypchnij)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "draft": re.compile(r"^\s*(?:Draft|Draft\s*branch)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "draft_name": re.compile(r"^\s*(?:Draft\s*name|Draft\s*branch\s*name)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "open_pr": re.compile(r"^\s*(?:PR|Pull\s*request|Open\s*PR)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "pr_title": re.compile(r"^\s*(?:PR\s*title|Pull\s*request\s*title)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "pr_body": re.compile(r"^\s*(?:PR\s*body|Pull\s*request\s*body)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "pr_base": re.compile(r"^\s*(?:PR\s*base|Pull\s*request\s*base)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "test_command": re.compile(r"^\s*(?:Test(?:\s*command)?|Testy)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "remote": re.compile(r"^\s*(?:Remote|Push\s*remote)\s*:\s*(.+?)\s*$", re.IGNORECASE),
}


def message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                elif item.get("type") == "text" and isinstance(item.get("content"), str):
                    parts.append(item["content"])
        return "\n".join(p for p in parts if p)
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"]
        if isinstance(content.get("content"), str):
            return content["content"]
    return str(content)


def parse_prompt_context(user_msg: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in user_msg.splitlines():
        for key, regex in PROMPT_FIELD_REGEX.items():
            match = regex.match(line)
            if match:
                parsed[key] = match.group(1).strip()
    # Jeśli repo_id nie zostało znalezione przez regex, spróbuj ekstrakcji owner/repo z tekstu
    if "repo_id" not in parsed:
        repo_match = GITHUB_REPO_SLUG_REGEX.search(user_msg)
        if repo_match:
            parsed["repo_id"] = repo_match.group(1).strip()
    return parsed


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "tak", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "nie", "off"}:
        return False
    return default


TOKEN_INLINE_REGEX = re.compile(r"(gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)", re.IGNORECASE)
REPO_TEMPLATE_REGEX = re.compile(r"^\s*\{\{\s*(.+?)\s*\}\}\s*$")
# Regex do rozpoznawania owner/repo bez 'Repo:' prefixu (np. semcod/code2schema)
GITHUB_REPO_SLUG_REGEX = re.compile(r"\b([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b")


def _normalize_command_text(text: str) -> str:
    cleaned = text.replace("*", " ")
    cleaned = re.sub(r"[^\w\sąćęłńóśźżĄĆĘŁŃÓŚŹŻ]", " ", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned, flags=re.UNICODE).strip().lower()
    return cleaned


def _extract_github_token_from_text(user_msg: str) -> str | None:
    match = TOKEN_INLINE_REGEX.search(user_msg)
    if match:
        return match.group(1)
    return None


def _extract_repo_template_expression(repo_value: str | None) -> str | None:
    if not repo_value:
        return None
    match = REPO_TEMPLATE_REGEX.match(repo_value)
    if not match:
        return None
    return match.group(1).strip()


def _is_last_pushed_repo_template(expression: str | None) -> bool:
    if not expression:
        return False
    normalized = _normalize_command_text(expression)
    if not normalized:
        return False

    words = set(normalized.split())
    has_repo = "repo" in words or "repozytorium" in words or "repozytorium" in words
    has_last = "last" in words or "ostatnio" in words or "ostatnie" in words or "najnowsze" in words
    has_push = "push" in words or "pushed" in words or "wypchniete" in words or "wypchnięte" in words
    has_github = "github" in words or "gh" in words
    return has_repo and has_last and has_push and has_github


def _extract_owner_from_repo_template(expression: str | None) -> str | None:
    if not expression:
        return None
    patterns = [
        r"(?:owner|org|organization|organizacja)\s*[:=]\s*([A-Za-z0-9_.-]+)",
        r"github\s+([A-Za-z0-9_.-]+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, expression, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _is_github_token_save_command(user_msg: str, prompt_ctx: dict[str, str]) -> bool:
    normalized = _normalize_command_text(user_msg)
    if not normalized:
        return False

    words = set(normalized.split())
    has_token_word = "token" in words
    has_gh_word = "github" in words or "gh" in words or "gihutb" in words
    has_save_intent = (
        "zapisz" in words
        or "save" in words
        or "zapisanie" in words
        or "set" in words
        or "env" in words
        or ".env" in user_msg.lower()
    )

    explicit_token_value = bool(prompt_ctx.get("github_token") or _extract_github_token_from_text(user_msg))
    if has_save_intent and has_token_word and has_gh_word:
        return True
    if explicit_token_value and has_save_intent:
        return True
    return False


def _extract_org_from_text(user_msg: str, prompt_ctx: dict[str, str]) -> str | None:
    repo_url = prompt_ctx.get("repo_url")
    if repo_url:
        normalized_repo = _normalize_repo_url(repo_url)
        github_repo = _github_repo_from_url(normalized_repo)
        if github_repo:
            return github_repo[0]
        if "/" in repo_url:
            owner = repo_url.split("/", 1)[0].strip()
            if owner and owner not in {"https:", "http:"}:
                return owner

    patterns = [
        r"(?:organizacj\w*\s+(?:github\s*[:=]?\s*)?(?:na\s+|to\s+)?)([A-Za-z0-9_.-]+)",
        r"(?:organizacj\w*\s*[:=]\s*)([A-Za-z0-9_.-]+)",
        r"(?:org(?:anization|s)?\s+(?:to\s+)?)([A-Za-z0-9_.-]+)",
        r"(?:org(?:anization)?\s*[:=]\s*)([A-Za-z0-9_.-]+)",
    ]
    blocked = {
        "github",
        "org",
        "orgs",
        "organization",
        "organizations",
        "organizacja",
        "organizacje",
        "na",
        "to",
    }
    for pattern in patterns:
        match = re.search(pattern, user_msg, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value.lower() in blocked:
                continue
            return value
    return None


def _is_org_set_command(user_msg: str) -> bool:
    normalized = _normalize_command_text(user_msg)
    words = set(normalized.split())
    has_org = any(word.startswith("organizac") for word in words) or any(
        token in words
        for token in {
            "org",
            "orgs",
            "organization",
            "organizations",
        }
    )
    has_set = "ustaw" in words or "zmien" in words or "zmień" in words or "set" in words or "change" in words
    return has_org and has_set


def _is_org_list_command(user_msg: str) -> bool:
    normalized = _normalize_command_text(user_msg)
    words = set(normalized.split())
    has_org = any(word.startswith("organizac") for word in words) or any(
        token in words
        for token in {
            "org",
            "orgs",
            "organization",
            "organizations",
        }
    )
    has_repo = any(
        token in words
        for token in {
            "repo",
            "repos",
            "repozytorium",
            "repozytoria",
            "repozytoriow",
            "repozytoriów",
            "repositories",
        }
    )
    has_list = "pokaz" in words or "pokaż" in words or "lista" in words or "wylistuj" in words or "list" in words
    return has_org and has_list and (has_repo or "wszystkich" in words or "all" in words)


def _is_github_token_sync_command(user_msg: str, prompt_ctx: dict[str, str]) -> bool:
    if prompt_ctx.get("github_token"):
        return False

    normalized = _normalize_command_text(user_msg)
    if not normalized:
        return False

    if normalized in {"github token", "token github", "token gh", "gh token"}:
        return True

    cleaned_user_msg = user_msg.replace("*", "").strip()
    if re.search(r"\bgithub\s+token\s*:\s*$", cleaned_user_msg, re.IGNORECASE):
        return True
    if re.search(r"\btoken\s*:\s*$", cleaned_user_msg, re.IGNORECASE):
        return True

    words = set(normalized.split())
    has_token = "token" in words
    has_gh = "github" in words or "gh" in words or "gihutb" in words
    intent_words = {
        "pobierz",
        "zaktualizuj",
        "aktualizuj",
        "uaktualnij",
        "pokaz",
        "pokaż",
        "show",
        "fetch",
        "get",
        "sync",
        "zsynchronizuj",
        "odswiez",
        "odśwież",
        "aktualny",
        "refresh",
        "update",
        "nowy",
        "najnowszy",
    }
    has_intent = bool(words & intent_words) or "gh auth token" in normalized
    return has_token and has_gh and has_intent


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


def _load_env_file_values(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        values[key] = value
    return values


def _runtime_github_token() -> str:
    file_values = _load_env_file_values(MCP_ENV_FILE)
    return (
        file_values.get("GITHUB_TOKEN")
        or file_values.get("GITHUB_PAT")
        or os.getenv("GITHUB_TOKEN", "")
        or os.getenv("GITHUB_PAT", "")
    )


def _save_github_token(token: str) -> dict[str, Any]:
    cleaned = token.strip()
    if not cleaned:
        raise ValueError("GitHub token is empty")
    if not ENV2MCP_AVAILABLE:
        raise ValueError("env2mcp is not available in mcp-gateway")

    cfg = EnvConfig(MCP_ENV_FILE)
    cfg["GITHUB_PAT"] = cleaned
    cfg.remove("GITHUB_TOKEN")

    github_user: str | None = None
    try:
        gh = GitHubCLI()
        if gh.is_available():
            os.environ["GITHUB_TOKEN"] = cleaned
            github_user = gh.get_user()
            if github_user:
                cfg["GITHUB_USER"] = github_user
    except Exception:
        github_user = None

    cfg.save()
    return {
        "configured": True,
        "env_file": str(MCP_ENV_FILE),
        "github_user": github_user,
    }


def _normalize_repo_url(repo_url: str | None) -> str | None:
    if not repo_url:
        return None
    value = repo_url.strip()
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        return f"https://github.com/{value}.git"
    return value


def _inject_github_token(repo_url: str | None) -> str | None:
    if not repo_url:
        return repo_url
    parsed = urlparse(repo_url)
    if (parsed.scheme or "").lower() != "https":
        return repo_url
    if (parsed.hostname or "").lower() != "github.com":
        return repo_url
    if parsed.username:
        return repo_url

    token = _runtime_github_token()
    if not token:
        return repo_url

    if parsed.port:
        netloc = f"{token}@{parsed.hostname}:{parsed.port}"
    else:
        netloc = f"{token}@{parsed.hostname}"
    return parsed._replace(netloc=netloc).geturl()


def _redact_repo_url(repo_url: str | None) -> str | None:
    if not repo_url:
        return repo_url
    try:
        parsed = urlparse(repo_url)
        if parsed.scheme and parsed.netloc and "@" in parsed.netloc:
            netloc = parsed.netloc.split("@", 1)[1]
            return parsed._replace(netloc=netloc).geturl()
    except Exception:
        pass
    return repo_url


def _default_draft_name(repo_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]", "-", repo_id).strip("-")
    if not slug:
        slug = "repo"
    return f"{slug}-{uuid.uuid4().hex[:8]}"


def _github_repo_from_url(repo_url: str | None) -> tuple[str, str] | None:
    normalized_url = _normalize_repo_url(repo_url)
    if not normalized_url:
        return None

    value = normalized_url.strip()
    if value.startswith("git@github.com:"):
        path = value.split(":", 1)[1]
    else:
        parsed = urlparse(value)
        host = parsed.hostname or ""
        if host.lower() != "github.com":
            return None
        path = parsed.path.lstrip("/")

    if path.endswith(".git"):
        path = path[:-4]

    parts = [p for p in path.split("/") if p]
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def _default_pr_title(repo_id: str, user_request: str) -> str:
    first = user_request.strip().splitlines()[0] if user_request.strip() else ""
    if not first:
        return f"mcp: refactor {repo_id}"
    if len(first) > 72:
        first = first[:69].rstrip() + "..."
    return f"mcp: {first}"


def _default_pr_body(repo_id: str, user_request: str, base_branch: str) -> str:
    return "\n".join(
        [
            "## MCP automated refactor request",
            "",
            f"- Repo: `{repo_id}`",
            f"- Base branch: `{base_branch}`",
            "",
            "### User task",
            user_request,
            "",
            "Generated by mcp-gateway.",
        ]
    )


async def _create_github_pr(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str,
    draft: bool,
) -> dict[str, Any]:
    token = _runtime_github_token()
    if not token:
        raise ValueError("GitHub token not configured (set GITHUB_TOKEN or GITHUB_PAT)")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    payload = {
        "title": title,
        "head": head_branch,
        "base": base_branch,
        "body": body,
        "draft": draft,
    }
    response = await client.post(
        f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls",
        headers=headers,
        json=payload,
    )
    if response.status_code not in {200, 201}:
        raise ValueError(f"create PR failed: {response.status_code} {response.text}")

    data = response.json()
    return {
        "number": data.get("number"),
        "title": data.get("title"),
        "url": data.get("html_url"),
        "state": data.get("state"),
        "draft": data.get("draft"),
        "head": data.get("head", {}).get("ref"),
        "base": data.get("base", {}).get("ref"),
    }


def _summary_text(analysis: dict[str, Any], user_request: str) -> str:
    metrics = analysis.get("metrics", {})
    recs = analysis.get("recommendations", {}).get("recommendations", [])
    lines = [
        "# MCP Refactoring Summary",
        "",
        f"Request: {user_request}",
        f"Files: {metrics.get('file_count', 0)}",
        f"Total lines: {metrics.get('total_lines', 0)}",
        "",
        "## Suggested actions",
    ]
    if recs:
        for rec in recs[:5]:
            lines.append(f"- [{rec.get('priority', 'medium')}] {rec.get('target', 'general')}: {rec.get('suggested_action', 'review')}" )
    else:
        lines.append("- No automatic recommendations generated.")
    return "\n".join(lines) + "\n"


def _render_repo_selection_text(repo_selection: dict[str, Any] | None) -> list[str]:
    if not repo_selection:
        return []
    lines = ["", "## Wybrane repo (auto-resolve)"]
    lines.append(f"- Strategia: `{repo_selection.get('strategy', '?')}`")
    lines.append(f"- Wejście: `{repo_selection.get('input', '?')}`")
    lines.append(f"- Repo: `{repo_selection.get('resolved_repo_id', '?')}`")
    if repo_selection.get("owner"):
        lines.append(f"- Owner: `{repo_selection.get('owner')}`")
    if repo_selection.get("pushed_at"):
        lines.append(f"- Last push: `{repo_selection.get('pushed_at')}`")
    return lines


def _render_system_text(result: dict[str, Any]) -> str:
    github = result.get("github") or {}
    action = github.get("action") or "system-action"
    success = bool(github.get("success"))
    status = "✅" if success else "⚠️"

    lines = [f"{status} Operacja systemowa: `{action}`"]

    if action == "list-github-orgs-and-repos":
        user = github.get("user")
        if user:
            lines.append(f"- Użytkownik: `{user}`")
        lines.append(f"- Liczba organizacji: `{github.get('org_count', 0)}`")
        orgs = github.get("orgs") or []
        if orgs:
            lines.append("")
            lines.append("## Organizacje i repo")
            for org in orgs[:8]:
                org_name = org.get("name") or "?"
                org_type = org.get("type") or "org"
                repo_count = org.get("repo_count", 0)
                lines.append(f"- `{org_name}` ({org_type}, repo: {repo_count})")
                repos = org.get("repos") or []
                if repos:
                    preview = ", ".join(f"`{r}`" for r in repos[:5])
                    suffix = " ..." if len(repos) > 5 else ""
                    lines.append(f"  - {preview}{suffix}")

    if github.get("org"):
        lines.append(f"- Organizacja domyślna: `{github.get('org')}`")
    if github.get("repo"):
        lines.append(f"- Repo: `{github.get('repo')}`")
    if github.get("note"):
        lines.append(f"- Info: {github.get('note')}")
    if github.get("error"):
        lines.append(f"- Błąd: {github.get('error')}")
    return "\n".join(lines)


def _render_analyze_text(result: dict[str, Any]) -> str:
    repo_id = result.get("repo_id") or "?"
    branch = result.get("branch") or "main"
    analysis = result.get("analysis") or {}
    metrics = analysis.get("metrics") or {}
    recommendations = (analysis.get("recommendations") or {}).get("recommendations") or []

    lines = [
        f"# Analiza repo `{repo_id}`",
        "",
        f"- Branch: `{branch}`",
        f"- Pliki: `{metrics.get('file_count', '?')}`",
        f"- Linie: `{metrics.get('total_lines', '?')}`",
    ]

    lines.extend(_render_repo_selection_text(result.get("repo_selection")))

    lines.append("")
    lines.append("## Proponowane etapy")
    if recommendations:
        for idx, rec in enumerate(recommendations[:7], start=1):
            priority = rec.get("priority", "medium")
            target = rec.get("target", "general")
            action = rec.get("suggested_action", "review")
            lines.append(f"{idx}. **[{priority}] {target}** — {action}")
    else:
        lines.append("1. Brak automatycznych rekomendacji — sprawdź metryki i wzorce.")

    note = result.get("note")
    if note:
        lines.append("")
        lines.append(f"_Info: {note}_")
    return "\n".join(lines)


def _render_queued_text(result: dict[str, Any]) -> str:
    job_id = result.get("job_id") or "?"
    status = result.get("status") or "queued"
    repo_id = result.get("repo_id") or "?"
    branch = result.get("branch") or "main"
    lines = [
        f"⏳ Zadanie zakolejkowane: `{job_id}`",
        f"- Repo: `{repo_id}`",
        f"- Branch: `{branch}`",
        f"- Status: `{status}`",
        f"- Podgląd: `GET /jobs/{job_id}`",
    ]
    note = result.get("note")
    if note:
        lines.append(f"- Info: {note}")
    return "\n".join(lines)


def _render_refactor_text(result: dict[str, Any]) -> str:
    repo_id = result.get("repo_id") or "?"
    branch = result.get("branch") or "main"
    base_branch = result.get("base_branch") or "main"
    execution = result.get("execution") or {}
    execute_commit = bool(execution.get("execute_commit"))
    summary = ((result.get("plan_preview") or {}).get("summary") or "").strip()

    lines = [
        f"# Plan refaktoryzacji `{repo_id}`",
        "",
        f"- Branch roboczy: `{branch}`",
        f"- Branch bazowy: `{base_branch}`",
        f"- Execute: `{str(execute_commit).lower()}`",
    ]

    lines.extend(_render_repo_selection_text(result.get("repo_selection")))

    if summary:
        lines.append("")
        lines.append("## Podsumowanie planu")
        lines.append(summary)

    lines.append("")
    lines.append("## Status wykonania")
    lines.append(f"- Committed: `{str(bool(execution.get('committed'))).lower()}`")

    tests = execution.get("tests") or {}
    if tests:
        lines.append(f"- Tests ok: `{str(bool(tests.get('ok'))).lower()}`")

    lines.append(f"- Pushed: `{str(bool(execution.get('pushed'))).lower()}`")

    draft_branch = (execution.get("draft_branch") or {}).get("branch")
    if draft_branch:
        lines.append(f"- Draft branch: `{draft_branch}`")

    pr = execution.get("pull_request") or {}
    if pr.get("url"):
        lines.append(f"- PR: {pr.get('url')}")
    elif pr.get("reason"):
        lines.append(f"- PR: pominięto ({pr.get('reason')})")

    if not execute_commit:
        lines.append("")
        lines.append("_Tryb plan-only: nic nie zostało zapisane ani wypchnięte._")

    note = result.get("note")
    if note:
        lines.append("")
        lines.append(f"_Info: {note}_")
    return "\n".join(lines)


def _render_chat_content(result: dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return str(result)

    if result.get("error"):
        return f"❌ Błąd workflow: {result.get('error')}"

    skill = result.get("skill")
    if skill == "system":
        return _render_system_text(result)
    if skill == "queued":
        return _render_queued_text(result)
    if skill == "analyze":
        return _render_analyze_text(result)
    if skill == "refactor":
        return _render_refactor_text(result)

    return json.dumps(result, ensure_ascii=False)


def _build_commit_changes(plan_payload: dict[str, Any], summary_md: str) -> list[dict[str, str]]:
    return [
        {
            "path": ".mcp/refactor-plan.json",
            "content": json.dumps(plan_payload, indent=2, ensure_ascii=False),
            "mode": "update",
        },
        {
            "path": ".mcp/refactor-summary.md",
            "content": summary_md,
            "mode": "update",
        },
    ]


async def _expect_json(response: httpx.Response, action: str) -> dict[str, Any]:
    if response.status_code != 200:
        raise ValueError(f"{action} failed: {response.status_code} {response.text}")
    data = response.json()
    if isinstance(data, dict):
        return data
    raise ValueError(f"{action} returned non-object payload")


async def _run_skills_analysis(client: httpx.AsyncClient, repo_id: str) -> dict[str, Any]:
    sync_res = await _expect_json(
        await client.post(f"{SKILLS_URL}/sync", json={"repo_id": repo_id, "ref": "HEAD"}),
        "skills sync",
    )
    metrics = await _expect_json(
        await client.post(f"{SKILLS_URL}/analyze/metrics", json={"repo_id": repo_id}),
        "skills metrics",
    )
    patterns = await _expect_json(
        await client.post(f"{SKILLS_URL}/analyze/patterns", json={"repo_id": repo_id}),
        "skills patterns",
    )
    recommendations = await _expect_json(
        await client.post(
            f"{SKILLS_URL}/refactor/recommend",
            json={"repo_id": repo_id, "goal": "maintainability"},
        ),
        "skills recommendations",
    )
    return {
        "sync": sync_res,
        "metrics": metrics,
        "patterns": patterns,
        "recommendations": recommendations,
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
SKILL_MODELS = {
    "mcp-skills/refactor": {
        "description": "Autonomous refactoring loop using git2mcp + mcp-skills",
        "skill": "refactor",
    },
    "mcp-skills/analyze": {
        "description": "Static analysis & metrics through mcp-skills",
        "skill": "analyze",
    },
}


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


# In-memory job store (MVP; Redis/Postgres in stage 5)
JOBS: dict[str, dict] = {}
_REDIS_STATE_CLIENT: Any | None = None
_REDIS_RQ_CLIENT: Any | None = None
_RQ_QUEUE: Any | None = None


def _job_storage_key(job_id: str) -> str:
    return f"mcp:job:{job_id}"


def _get_state_redis_client() -> Any | None:
    global _REDIS_STATE_CLIENT
    if not RQ_AVAILABLE:
        return None
    if _REDIS_STATE_CLIENT is not None:
        return _REDIS_STATE_CLIENT
    try:
        _REDIS_STATE_CLIENT = Redis.from_url(REDIS_URL, decode_responses=True)
        _REDIS_STATE_CLIENT.ping()
        return _REDIS_STATE_CLIENT
    except Exception:
        _REDIS_STATE_CLIENT = None
        return None


def _get_rq_redis_client() -> Any | None:
    global _REDIS_RQ_CLIENT
    if not RQ_AVAILABLE:
        return None
    if _REDIS_RQ_CLIENT is not None:
        return _REDIS_RQ_CLIENT
    try:
        _REDIS_RQ_CLIENT = Redis.from_url(REDIS_URL, decode_responses=False)
        _REDIS_RQ_CLIENT.ping()
        return _REDIS_RQ_CLIENT
    except Exception:
        _REDIS_RQ_CLIENT = None
        return None


def _get_queue() -> Any | None:
    global _RQ_QUEUE
    if not MCP_ASYNC_ENABLED:
        return None
    if not RQ_AVAILABLE:
        return None
    if _RQ_QUEUE is not None:
        return _RQ_QUEUE
    redis_client = _get_rq_redis_client()
    if redis_client is None:
        return None
    _RQ_QUEUE = Queue(name=RQ_QUEUE_NAME, connection=redis_client, default_timeout=900)
    return _RQ_QUEUE


def _save_job(job_id: str, payload: dict[str, Any]) -> None:
    JOBS[job_id] = payload
    redis_client = _get_state_redis_client()
    if redis_client is None:
        return
    try:
        redis_client.setex(
            _job_storage_key(job_id),
            JOB_TTL_SECONDS,
            json.dumps(payload, ensure_ascii=False),
        )
    except Exception:
        return


def _load_job(job_id: str) -> dict[str, Any] | None:
    redis_client = _get_state_redis_client()
    if redis_client is not None:
        try:
            raw = redis_client.get(_job_storage_key(job_id))
            if raw:
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    JOBS[job_id] = payload
                    return payload
        except Exception:
            pass
    return JOBS.get(job_id)


def _update_job(job_id: str, **updates: Any) -> dict[str, Any]:
    current = _load_job(job_id) or {}
    current.update(updates)
    current["updated_at"] = time.time()
    _save_job(job_id, current)
    return current


def _queue_workflow_job(job_id: str, payload: dict[str, Any]) -> None:
    queue = _get_queue()
    if queue is None:
        raise RuntimeError("Async queue is unavailable (enable MCP_ASYNC_ENABLED and Redis/RQ)")
    queue.enqueue(
        "server.execute_dispatch_job",
        kwargs={"job_id": job_id, "payload": payload},
        job_id=job_id,
        result_ttl=JOB_TTL_SECONDS,
        failure_ttl=JOB_TTL_SECONDS,
    )


def execute_dispatch_job(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _update_job(job_id, status="analyzing", phase="analyzing", started_at=time.time())
    try:
        result = asyncio.run(
            dispatch_skill(
                skill=payload["skill"],
                tenant=payload["tenant"],
                repo_id=payload["repo_id"],
                repo_url=payload.get("repo_url"),
                github_token=payload.get("github_token"),
                source_path=payload.get("source_path"),
                branch=payload["branch"],
                user_request=payload["user_request"],
                execute_commit=payload["execute_commit"],
                push_after_tests=payload["push_after_tests"],
                create_draft_branch=payload["create_draft_branch"],
                draft_name=payload["draft_name"],
                open_pull_request=payload["open_pull_request"],
                pr_title=payload.get("pr_title"),
                pr_body=payload.get("pr_body"),
                pr_base=payload["pr_base"],
                test_command=payload["test_command"],
                push_remote=payload["push_remote"],
                job_id=job_id,
            )
        )
        repo_selection = payload.get("repo_selection")
        if repo_selection:
            result["repo_selection"] = repo_selection
        _update_job(
            job_id,
            status="done",
            phase="done",
            completed_at=time.time(),
            result=result,
        )
        return result
    except Exception as exc:
        _update_job(
            job_id,
            status="failed",
            phase="failed",
            completed_at=time.time(),
            error=str(exc),
        )
        raise


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
        nonlocal repo_id_input
        # Jeśli repo_id_input jest None, spróbuj pobrać domyślne z GitHub
        if not repo_id_input:
            github_default = await _get_default_github_repo()
            if github_default:
                repo_id_input = github_default
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

            content = _render_chat_content(result)
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
                                            "delta": {"content": f"\n\n{_render_chat_content(final_result)}"},
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
                                            "delta": {"content": f"\n\n{_render_chat_content(error_result)}"},
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
                "message": {"role": "assistant", "content": _render_chat_content(result)},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "job_id": job_id,
    }


async def dispatch_skill(
    skill: str,
    tenant: dict,
    repo_id: str,
    repo_url: str | None,
    github_token: str | None,
    source_path: str | None,
    branch: str,
    user_request: str,
    execute_commit: bool,
    push_after_tests: bool,
    create_draft_branch: bool,
    draft_name: str,
    open_pull_request: bool,
    pr_title: str | None,
    pr_body: str | None,
    pr_base: str,
    test_command: str,
    push_remote: str,
    job_id: str | None = None,
) -> dict:
    tenant_id = tenant["tenant_id"]
    github_config_result: dict[str, Any] | None = None
    if github_token:
        github_config_result = _save_github_token(github_token)

    if job_id:
        _update_job(job_id, status="analyzing", phase="analyzing")

    normalized_repo_url = _normalize_repo_url(repo_url)
    safe_repo_url = _redact_repo_url(normalized_repo_url)
    async with httpx.AsyncClient(timeout=300.0) as client:
        sync_payload: dict[str, Any] = {
            "repo_id": repo_id,
            "branch": branch,
        }
        if source_path:
            sync_payload["source_path"] = source_path
        if normalized_repo_url:
            sync_payload["repo_url"] = _inject_github_token(normalized_repo_url)

        sync = await _expect_json(
            await client.post(f"{GIT_PROXY_URL}/repos/sync", json=sync_payload),
            "git sync",
        )

        if skill == "analyze":
            analysis = await _run_skills_analysis(client, repo_id)
            return {
                "skill": "analyze",
                "tenant": tenant_id,
                "repo_id": repo_id,
                "repo_url": safe_repo_url,
                "user_request": user_request,
                "source_path": source_path,
                "branch": branch,
                "sync": sync,
                "github": github_config_result,
                "analysis": analysis,
                "note": "Analyze workflow executed through mcp-skills HTTP API.",
            }

        if skill == "refactor":
            if job_id:
                _update_job(job_id, status="refactoring", phase="refactoring")
            ckpt = await _expect_json(
                await client.post(
                f"{GIT_PROXY_URL}/repos/{repo_id}/checkpoint",
                json={"label": f"task-{uuid.uuid4().hex[:8]}"},
                ),
                "checkpoint create",
            )

            analysis = await _run_skills_analysis(client, repo_id)
            base_branch = branch
            working_branch = branch
            plan_payload: dict[str, Any] = {
                "repo_id": repo_id,
                "tenant": tenant_id,
                "branch": working_branch,
                "base_branch": base_branch,
                "repo_url": safe_repo_url,
                "source_path": source_path,
                "user_request": user_request,
                "generated_at": int(time.time()),
                "analysis": analysis,
            }
            summary_md = _summary_text(analysis, user_request)

            execution: dict[str, Any] = {
                "execute_commit": execute_commit,
                "push_after_tests": push_after_tests,
                "create_draft_branch": create_draft_branch,
                "draft_name": draft_name,
                "open_pull_request": open_pull_request,
                "pr_base": pr_base,
                "test_command": test_command,
                "remote": push_remote,
                "committed": False,
                "pushed": False,
            }

            if execute_commit:
                if create_draft_branch:
                    draft_result = await _expect_json(
                        await client.post(
                            f"{GIT_PROXY_URL}/repos/{repo_id}/branch/draft",
                            json={"name": draft_name, "base": base_branch},
                        ),
                        "draft branch create",
                    )
                    working_branch = draft_result.get("branch", working_branch)
                    plan_payload["branch"] = working_branch
                    execution["draft_branch"] = draft_result

                commit_payload = {
                    "message": f"chore(mcp): refactor plan for {repo_id} ({working_branch})",
                    "changes": _build_commit_changes(plan_payload, summary_md),
                    "author_name": "mcp-gateway-bot",
                    "author_email": "mcp-gateway@local",
                }
                commit_result = await _expect_json(
                    await client.post(f"{GIT_PROXY_URL}/repos/{repo_id}/commit", json=commit_payload),
                    "git commit",
                )
                if job_id:
                    _update_job(job_id, status="testing", phase="testing")
                tests_result = await _expect_json(
                    await client.post(
                        f"{GIT_PROXY_URL}/repos/{repo_id}/run-tests",
                        json={"command": test_command},
                    ),
                    "run tests",
                )
                execution.update(
                    {
                        "committed": True,
                        "commit": commit_result,
                        "tests": tests_result,
                    }
                )

                if push_after_tests:
                    if not tenant.get("features", {}).get("push", False):
                        execution["push"] = {
                            "skipped": True,
                            "reason": "Tenant push feature disabled",
                        }
                    elif not tests_result.get("ok"):
                        execution["push"] = {
                            "skipped": True,
                            "reason": "Tests failed",
                        }
                    else:
                        push_result = await _expect_json(
                            await client.post(
                                f"{GIT_PROXY_URL}/repos/{repo_id}/push",
                                json={"remote": push_remote, "branch": working_branch},
                            ),
                            "git push",
                        )
                        execution["push"] = push_result
                        execution["pushed"] = True

                if open_pull_request:
                    if not execution.get("pushed"):
                        execution["pull_request"] = {
                            "skipped": True,
                            "reason": "Push was not executed",
                        }
                    else:
                        github_repo = _github_repo_from_url(repo_url)
                        if not github_repo:
                            execution["pull_request"] = {
                                "skipped": True,
                                "reason": "Repo URL is not a GitHub URL",
                            }
                        else:
                            owner, repo_name = github_repo
                            pr_result = await _create_github_pr(
                                client=client,
                                owner=owner,
                                repo=repo_name,
                                head_branch=working_branch,
                                base_branch=pr_base,
                                title=pr_title or _default_pr_title(repo_id, user_request),
                                body=pr_body or _default_pr_body(repo_id, user_request, pr_base),
                                draft=True,
                            )
                            execution["pull_request"] = pr_result

            diff = await _expect_json(
                await client.post(
                    f"{GIT_PROXY_URL}/repos/{repo_id}/worktree/diff",
                    json={"staged": False},
                ),
                "worktree diff",
            )

            return {
                "skill": "refactor",
                "tenant": tenant_id,
                "repo_id": repo_id,
                "repo_url": safe_repo_url,
                "source_path": source_path,
                "branch": working_branch,
                "base_branch": base_branch,
                "user_request": user_request,
                "sync": sync,
                "github": github_config_result,
                "checkpoint": ckpt,
                "analysis": analysis,
                "plan_preview": {
                    "summary": summary_md,
                    "artifacts": [".mcp/refactor-plan.json", ".mcp/refactor-summary.md"],
                },
                "execution": execution,
                "current_diff": diff.get("diff", ""),
                "note": "Gateway orchestrates sync+analysis and optional commit/push via git-proxy.",
            }

    raise ValueError(f"Unknown skill: {skill}")


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
