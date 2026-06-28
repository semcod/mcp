"""Markdown helpers for refactor skill chat responses."""

from __future__ import annotations

from typing import Any


def render_refactor_execution(execution: dict[str, Any]) -> list[str]:
    lines = [
        "",
        "## Status wykonania",
        f"- Committed: `{str(bool(execution.get('committed'))).lower()}`",
    ]

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

    return lines
