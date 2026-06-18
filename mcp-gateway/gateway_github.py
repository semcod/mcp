"""GitHub NLP command detection and repo URL helpers for mcp-gateway."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from gateway_config import GITHUB_API_URL, MCP_ENV_FILE
from gateway_prompt import extract_github_token_from_text, normalize_command_text

try:
    from env2mcp import EnvConfig, GitHubCLI

    ENV2MCP_AVAILABLE = True
except Exception:
    ENV2MCP_AVAILABLE = False


def normalize_repo_url(repo_url: str | None) -> str | None:
    if not repo_url:
        return None
    value = repo_url.strip()
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        return f"https://github.com/{value}.git"
    return value


def github_repo_from_url(repo_url: str | None) -> tuple[str, str] | None:
    normalized_url = normalize_repo_url(repo_url)
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


def is_github_token_save_command(user_msg: str, prompt_ctx: dict[str, str]) -> bool:
    normalized = normalize_command_text(user_msg)
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

    explicit_token_value = bool(prompt_ctx.get("github_token") or extract_github_token_from_text(user_msg))
    if has_save_intent and has_token_word and has_gh_word:
        return True
    if explicit_token_value and has_save_intent:
        return True
    return False


def is_github_token_sync_command(user_msg: str, prompt_ctx: dict[str, str]) -> bool:
    if prompt_ctx.get("github_token"):
        return False

    normalized = normalize_command_text(user_msg)
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


def extract_org_from_text(user_msg: str, prompt_ctx: dict[str, str]) -> str | None:
    repo_url = prompt_ctx.get("repo_url")
    if repo_url:
        normalized_repo = normalize_repo_url(repo_url)
        github_repo = github_repo_from_url(normalized_repo)
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


def is_org_set_command(user_msg: str) -> bool:
    normalized = normalize_command_text(user_msg)
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


def is_org_list_command(user_msg: str) -> bool:
    normalized = normalize_command_text(user_msg)
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


def is_repo_list_command(user_msg: str) -> bool:
    normalized = normalize_command_text(user_msg)
    words = set(normalized.split())

    has_github = "github" in words or "gh" in words
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
    has_list = (
        "pokaz" in words
        or "pokaż" in words
        or "lista" in words
        or "wylistuj" in words
        or "list" in words
        or "show" in words
    )
    has_last = "ostatnio" in words or "ostatnich" in words or "last" in words or "recent" in words
    has_edited = (
        "edytowanych" in words
        or "edytowane" in words
        or "edited" in words
        or "modified" in words
        or "updated" in words
        or "pushed" in words
    )

    return has_github and has_repo and has_list and (
        has_last or has_edited or "10" in user_msg or "pięć" in user_msg or "piec" in user_msg
    )


def extract_repo_list_limit(user_msg: str, default: int = 10, max_limit: int = 30) -> int:
    match = re.search(r"\b(\d{1,3})\b", user_msg)
    if not match:
        return default
    try:
        value = int(match.group(1))
    except Exception:
        return default
    return max(1, min(value, max_limit))


def load_env_file_values(env_path: Path) -> dict[str, str]:
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


def runtime_github_token() -> str:
    file_values = load_env_file_values(MCP_ENV_FILE)
    return (
        file_values.get("GITHUB_TOKEN")
        or file_values.get("GITHUB_PAT")
        or os.getenv("GITHUB_TOKEN", "")
        or os.getenv("GITHUB_PAT", "")
    )


def save_github_token(token: str) -> dict[str, Any]:
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


def inject_github_token(repo_url: str | None) -> str | None:
    if not repo_url:
        return repo_url
    parsed = urlparse(repo_url)
    if (parsed.scheme or "").lower() != "https":
        return repo_url
    if (parsed.hostname or "").lower() != "github.com":
        return repo_url
    if parsed.username:
        return repo_url

    token = runtime_github_token()
    if not token:
        return repo_url

    if parsed.port:
        netloc = f"{token}@{parsed.hostname}:{parsed.port}"
    else:
        netloc = f"{token}@{parsed.hostname}"
    return parsed._replace(netloc=netloc).geturl()


def redact_repo_url(repo_url: str | None) -> str | None:
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


def default_draft_name(repo_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]", "-", repo_id).strip("-")
    if not slug:
        slug = "repo"
    return f"{slug}-{uuid.uuid4().hex[:8]}"


def default_pr_title(repo_id: str, user_request: str) -> str:
    first = user_request.strip().splitlines()[0] if user_request.strip() else ""
    if not first:
        return f"mcp: refactor {repo_id}"
    if len(first) > 72:
        first = first[:69].rstrip() + "..."
    return f"mcp: {first}"


def default_pr_body(repo_id: str, user_request: str, base_branch: str) -> str:
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


async def create_github_pr(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str,
    draft: bool,
) -> dict[str, Any]:
    token = runtime_github_token()
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
