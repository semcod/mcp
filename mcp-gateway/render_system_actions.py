"""Action-specific Markdown renderers for gateway system responses."""

from __future__ import annotations

from typing import Any


def render_list_recent_repos(github: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    user = github.get("user")
    if user:
        lines.append(f"- Użytkownik: `{user}`")
    lines.append(f"- Liczba repo: `{github.get('count', 0)}`")
    repos = github.get("repos") or []
    if not repos:
        return lines
    lines.append("")
    lines.append("## Ostatnio aktywne repo")
    for idx, repo in enumerate(repos, start=1):
        slug = repo.get("nameWithOwner") or "?"
        pushed_at = repo.get("pushedAt") or "?"
        url = repo.get("url")
        lines.append(f"{idx}. `{slug}` — `{pushed_at}`")
        if url:
            lines.append(f"   - {url}")
    return lines


def render_list_orgs_and_repos(github: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    user = github.get("user")
    if user:
        lines.append(f"- Użytkownik: `{user}`")
    lines.append(f"- Liczba organizacji: `{github.get('org_count', 0)}`")
    orgs = github.get("orgs") or []
    if not orgs:
        return lines
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
    return lines
