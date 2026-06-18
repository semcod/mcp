"""Prompt parsing and NLP tool-intent detection for mcp-gateway."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

PROMPT_FIELD_REGEX = {
    "repo_id": re.compile(r"^\s*Repo\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "repo_url": re.compile(r"^\s*Repo\s*URL\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "github_token": re.compile(
        r"^\s*(?:GitHub\s*Token|Github\s*Token|Token)\s*:\s*(.+?)\s*$", re.IGNORECASE
    ),
    "source_path": re.compile(r"^\s*Source\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "branch": re.compile(r"^\s*Branch\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "task": re.compile(r"^\s*Zadanie\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "execute": re.compile(r"^\s*(?:Execute|Wykonaj)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "push": re.compile(r"^\s*(?:Push|Wypchnij)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "draft": re.compile(r"^\s*(?:Draft|Draft\s*branch)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "draft_name": re.compile(
        r"^\s*(?:Draft\s*name|Draft\s*branch\s*name)\s*:\s*(.+?)\s*$", re.IGNORECASE
    ),
    "open_pr": re.compile(r"^\s*(?:PR|Pull\s*request|Open\s*PR)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "pr_title": re.compile(
        r"^\s*(?:PR\s*title|Pull\s*request\s*title)\s*:\s*(.+?)\s*$", re.IGNORECASE
    ),
    "pr_body": re.compile(
        r"^\s*(?:PR\s*body|Pull\s*request\s*body)\s*:\s*(.+?)\s*$", re.IGNORECASE
    ),
    "pr_base": re.compile(
        r"^\s*(?:PR\s*base|Pull\s*request\s*base)\s*:\s*(.+?)\s*$", re.IGNORECASE
    ),
    "test_command": re.compile(
        r"^\s*(?:Test(?:\s*command)?|Testy)\s*:\s*(.+?)\s*$", re.IGNORECASE
    ),
    "remote": re.compile(r"^\s*(?:Remote|Push\s*remote)\s*:\s*(.+?)\s*$", re.IGNORECASE),
}

TOKEN_INLINE_REGEX = re.compile(
    r"(gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)", re.IGNORECASE
)
REPO_TEMPLATE_REGEX = re.compile(r"^\s*\{\{\s*(.+?)\s*\}\}\s*$")
GITHUB_REPO_SLUG_REGEX = re.compile(r"\b([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b")

SUPPORTED_TOOL_NAMES: tuple[str, ...] = (
    "sumd",
    "code2llm",
    "code2docs",
    "code2logic",
    "code2schema",
    "redsl",
    "redup",
    "regres",
    "regix",
    "vallm",
    "pyqual",
    "domd",
    "clickmd",
    "algitex",
)

_TOOL_INTENT_VERBS = {
    "wygeneruj",
    "generuj",
    "wygenerujesz",
    "uruchom",
    "uruchommy",
    "odpal",
    "odpalmy",
    "zrob",
    "zrób",
    "wykonaj",
    "stwórz",
    "stworz",
    "run",
    "execute",
    "generate",
    "build",
    "make",
    "analyze",
    "analyse",
    "analizuj",
    "przeanalizuj",
    "scan",
    "skanuj",
    "zeskanuj",
    "lint",
    "validate",
    "waliduj",
}

_REPO_URL_REGEX = re.compile(
    r"https?://(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org)/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+"
    r"(?:\.git)?",
    re.IGNORECASE,
)


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
    if "repo_id" not in parsed:
        stripped = user_msg.strip()
        if REPO_TEMPLATE_REGEX.match(stripped):
            parsed["repo_id"] = stripped

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


def normalize_command_text(text: str) -> str:
    cleaned = text.replace("*", " ")
    cleaned = re.sub(r"[^\w\sąćęłńóśźżĄĆĘŁŃÓŚŹŻ]", " ", cleaned, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned, flags=re.UNICODE).strip().lower()
    return cleaned


def extract_github_token_from_text(user_msg: str) -> str | None:
    match = TOKEN_INLINE_REGEX.search(user_msg)
    if match:
        return match.group(1)
    return None


def extract_repo_template_expression(repo_value: str | None) -> str | None:
    if not repo_value:
        return None
    match = REPO_TEMPLATE_REGEX.match(repo_value)
    if not match:
        return None
    return match.group(1).strip()


def is_last_pushed_repo_template(expression: str | None) -> bool:
    if not expression:
        return False
    normalized = normalize_command_text(expression)
    if not normalized:
        return False

    words = set(normalized.split())
    has_repo = "repo" in words or "repozytorium" in words or "repozytorium" in words
    has_last = "last" in words or "ostatnio" in words or "ostatnie" in words or "najnowsze" in words
    has_push = "push" in words or "pushed" in words or "wypchniete" in words or "wypchnięte" in words
    has_github = "github" in words or "gh" in words
    return has_repo and has_last and has_push and has_github


def extract_owner_from_repo_template(expression: str | None) -> str | None:
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


def strip_url_suffix(url: str) -> str:
    return url.rstrip(".,;:!?)")


def parse_tool_intent(user_msg: str, prompt_ctx: dict[str, str] | None = None) -> dict[str, Any] | None:
    """Detect requests like 'wygeneruj sumd dla <URL>' / 'run code2llm on owner/repo'."""
    if not user_msg:
        return None
    text = user_msg.strip()
    if not text:
        return None

    normalized = normalize_command_text(text)
    words = normalized.split()
    if not words:
        return None

    tool_name: str | None = None
    tool_idx: int = -1
    for idx, word in enumerate(words):
        if word in SUPPORTED_TOOL_NAMES:
            tool_name = word
            tool_idx = idx
            break

    if tool_name is None:
        return None

    has_verb = any(w in _TOOL_INTENT_VERBS for w in words[: tool_idx + 1])
    is_first_word = tool_idx == 0
    repo_url_match = _REPO_URL_REGEX.search(text)
    repo_url = strip_url_suffix(repo_url_match.group(0)) if repo_url_match else None

    if not (has_verb or is_first_word or repo_url):
        return None

    repo_id: str | None = None
    if prompt_ctx:
        repo_id = prompt_ctx.get("repo_id")

    if not repo_id and not repo_url:
        slug_match = re.search(
            r"\b([A-Za-z0-9][A-Za-z0-9_.\-]*)/([A-Za-z0-9][A-Za-z0-9_.\-]*)\b",
            text,
        )
        if slug_match:
            repo_id = f"{slug_match.group(1)}/{slug_match.group(2)}"

    if not repo_id and repo_url:
        try:
            parsed = urlparse(repo_url)
            parts = [p for p in parsed.path.strip("/").split("/") if p]
            if len(parts) >= 2:
                last = parts[1]
                if last.endswith(".git"):
                    last = last[:-4]
                repo_id = f"{parts[0]}/{last}"
        except Exception:
            pass

    return {
        "tool": tool_name,
        "repo_url": repo_url,
        "repo_id": repo_id,
        "subcommand": None,
        "args": [],
    }
