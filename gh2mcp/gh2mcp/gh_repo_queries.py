"""Shared GitHub CLI repo-list helpers for gh2mcp."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from env2mcp import EnvConfig, GitHubCLI


def clamp_limit(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(minimum, min(parsed, maximum))


def resolve_owner(
    env_path,
    gh: GitHubCLI,
    owner: str | None,
) -> tuple[str | None, dict[str, Any] | None]:
    """Resolve GitHub owner from arg, env, or gh CLI. Returns (owner, error_payload)."""
    cfg = EnvConfig(env_path)
    resolved = (owner or "").strip()
    if not resolved:
        resolved = (cfg.get("GITHUB_ORG") or "").strip()
    if not resolved:
        resolved = (cfg.get("GITHUB_USER") or "").strip()
    if not resolved:
        resolved = (gh.get_user() or "").strip()
    if not resolved:
        return None, {
            "success": False,
            "error": "Unable to resolve GitHub owner (set GITHUB_ORG or pass owner)",
            "owner": None,
            "repo": None,
        }
    return resolved, None


def gh_repo_list(
    owner: str,
    limit: int,
    *,
    fields: str = "nameWithOwner,pushedAt,url",
    timeout: int = 30,
) -> tuple[list[dict[str, Any]], str | None]:
    """Run `gh repo list` and return (repos, error_message)."""
    try:
        proc = subprocess.run(
            ["gh", "repo", "list", owner, "-L", str(limit), "--json", fields],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception as exc:
        return [], f"gh repo list failed: {exc}"

    if proc.returncode != 0:
        return [], (proc.stderr or proc.stdout or "gh repo list failed").strip()

    try:
        repos = json.loads(proc.stdout) if proc.stdout.strip() else []
    except Exception:
        repos = []
    return repos, None


def fetch_user_org_logins() -> list[str]:
    try:
        proc = subprocess.run(
            ["gh", "api", "user/orgs"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        orgs = json.loads(proc.stdout) if proc.returncode == 0 and proc.stdout.strip() else []
    except Exception:
        orgs = []
    return [item.get("login") for item in orgs if isinstance(item, dict) and item.get("login")]


def collect_repos_for_owners(
    owners: list[str],
    limit: int,
    *,
    fields: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    candidates: list[dict[str, Any]] = []
    errors: list[str] = []
    for owner_name in owners:
        repos, err = gh_repo_list(owner_name, limit, fields=fields)
        if err:
            errors.append(f"{owner_name}: {err}")
            continue
        for item in repos:
            if not isinstance(item, dict):
                continue
            name_with_owner = item.get("nameWithOwner")
            if not name_with_owner:
                continue
            candidates.append({**item, "owner": owner_name})
    return candidates, errors


def dedupe_repos_by_slug(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    candidates.sort(key=lambda item: item.get("pushedAt") or "", reverse=True)
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        slug = str(item.get("nameWithOwner") or "")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        deduped.append(item)
        if len(deduped) >= limit:
            break
    return deduped


def newest_repo_with_slug(repos: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [item for item in repos if isinstance(item, dict) and item.get("nameWithOwner")]
    if not valid:
        return None
    valid.sort(key=lambda item: item.get("pushedAt") or "", reverse=True)
    return valid[0]


def resolve_github_token(
    env_path,
    gh: GitHubCLI,
    *,
    force_gh_cli: bool = False,
) -> tuple[str | None, str | None, dict[str, Any] | None]:
    """Return (token, source, error_payload)."""
    cfg = EnvConfig(env_path)
    token: str | None = None
    source: str | None = None

    if force_gh_cli:
        if not gh.is_available():
            return None, None, {
                "success": False,
                "configured": False,
                "error": "gh CLI not available",
                "source": None,
            }
        token = gh.get_token()
        if token:
            return token, "gh_cli", None
        return None, None, {
            "success": False,
            "configured": False,
            "error": "gh CLI has no token (run: gh auth login)",
            "source": None,
        }

    token = os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN")
    if token:
        return token, "env", None

    if gh.is_available():
        token = gh.get_token()
        if token:
            return token, "gh_cli", None

    token = cfg.get("GITHUB_PAT") or cfg.get("GITHUB_TOKEN")
    if token:
        return token, "env_file", None

    return None, None, {
        "success": False,
        "configured": False,
        "error": "Brak tokenu GitHub (env, gh CLI, .env)",
        "source": None,
    }

