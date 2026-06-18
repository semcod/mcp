"""GitHub NLP command detection and repo URL helpers for mcp-gateway."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from gateway_prompt import extract_github_token_from_text, normalize_command_text


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
