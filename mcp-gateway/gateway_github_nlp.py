"""NLP detection for GitHub admin commands in mcp-gateway chat."""

from __future__ import annotations

import re

from gateway_prompt import extract_github_token_from_text, normalize_command_text

_REPO_WORDS = frozenset({
    "repo",
    "repos",
    "repozytorium",
    "repozytoria",
    "repozytoriow",
    "repozytoriów",
    "repositories",
})

_ORG_WORDS = frozenset({
    "org",
    "orgs",
    "organization",
    "organizations",
})

_LIST_WORDS = frozenset({
    "pokaz",
    "pokaż",
    "lista",
    "wylistuj",
    "list",
    "show",
})

_TOKEN_SYNC_INTENT_WORDS = frozenset({
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
})


def _words(user_msg: str) -> set[str]:
    normalized = normalize_command_text(user_msg)
    return set(normalized.split()) if normalized else set()


def _has_org_word(words: set[str]) -> bool:
    return any(word.startswith("organizac") for word in words) or bool(words & _ORG_WORDS)


def is_github_token_save_command(user_msg: str, prompt_ctx: dict[str, str]) -> bool:
    words = _words(user_msg)
    if not words:
        return False

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
    return bool(explicit_token_value and has_save_intent)


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
    has_intent = bool(words & _TOKEN_SYNC_INTENT_WORDS) or "gh auth token" in normalized
    return has_token and has_gh and has_intent


def is_org_set_command(user_msg: str) -> bool:
    words = _words(user_msg)
    has_org = _has_org_word(words)
    has_set = "ustaw" in words or "zmien" in words or "zmień" in words or "set" in words or "change" in words
    return has_org and has_set


def is_org_list_command(user_msg: str) -> bool:
    words = _words(user_msg)
    has_org = _has_org_word(words)
    has_repo = bool(words & _REPO_WORDS)
    has_list = bool(words & _LIST_WORDS)
    return has_org and has_list and (has_repo or "wszystkich" in words or "all" in words)


def is_repo_list_command(user_msg: str) -> bool:
    words = _words(user_msg)
    has_github = "github" in words or "gh" in words
    has_repo = bool(words & _REPO_WORDS)
    has_list = bool(words & _LIST_WORDS)
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
