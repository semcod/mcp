"""Markdown renderers for mcp-gateway chat responses."""

from __future__ import annotations

import json
from typing import Any

from render_tools import (
    file_fence_lang,
    is_markdown_path,
    render_tool_text,
    render_tools_list_text,
)
from render_refactor_actions import render_refactor_execution
from render_system_actions import render_list_orgs_and_repos, render_list_recent_repos

__all__ = [
    "build_commit_changes",
    "file_fence_lang",
    "is_markdown_path",
    "render_analyze_text",
    "render_chat_content",
    "render_github_qa_text",
    "render_queued_text",
    "render_refactor_text",
    "render_repo_selection_text",
    "render_system_text",
    "render_tool_text",
    "render_tools_list_text",
    "summary_text",
]

def summary_text(analysis: dict[str, Any], user_request: str) -> str:
    metrics = analysis.get("metrics", {})
    recs = analysis.get("recommendations", {}).get("recommendations", [])
    engine = analysis.get("engine", "mcp-skills")
    redsl_raw = analysis.get("redsl_raw", {})
    lines = [
        "# MCP Refactoring Summary",
        "",
        f"Request: {user_request}",
        f"Engine: {engine}",
        f"Files: {metrics.get('file_count', 0)}",
        f"Total lines: {metrics.get('total_lines', 0)}",
    ]
    if engine == "redsl":
        avg_cc = metrics.get("avg_complexity", 0.0)
        critical = metrics.get("critical_count", 0)
        alerts = metrics.get("alerts_count", 0)
        if avg_cc:
            lines.append(f"Avg complexity (CC): {avg_cc}")
        if critical:
            lines.append(f"Critical hotspots: {critical}")
        if alerts:
            lines.append(f"Alerts: {alerts}")
        decisions_count = redsl_raw.get("decisions_count", 0)
        lines.append(f"redsl decisions: {decisions_count}")
    lines += ["", "## Suggested actions"]
    if recs:
        for rec in recs[:10]:
            priority = rec.get("priority", "medium")
            target = rec.get("target", "general")
            action = rec.get("suggested_action", "review")
            reason = rec.get("reason", "")
            score = rec.get("redsl_score")
            score_str = f" (score={score:.2f})" if score is not None else ""
            lines.append(f"- [{priority}] `{target}`: {action}{score_str}")
            if reason:
                lines.append(f"  > {reason}")
    else:
        lines.append("- No automatic recommendations generated.")
    return "\n".join(lines) + "\n"


def render_repo_selection_text(repo_selection: dict[str, Any] | None) -> list[str]:
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


def render_system_text(result: dict[str, Any]) -> str:
    github = result.get("github") or {}
    action = github.get("action") or "system-action"
    success = bool(github.get("success"))
    status = "✅" if success else "⚠️"

    lines = [f"{status} Operacja systemowa: `{action}`"]

    if action == "list-recent-github-repos":
        lines.extend(render_list_recent_repos(github))
    elif action == "list-github-orgs-and-repos":
        lines.extend(render_list_orgs_and_repos(github))

    if github.get("org"):
        lines.append(f"- Organizacja domyślna: `{github.get('org')}`")
    if github.get("repo"):
        lines.append(f"- Repo: `{github.get('repo')}`")
    if github.get("note"):
        lines.append(f"- Info: {github.get('note')}")
    if github.get("error"):
        lines.append(f"- Błąd: {github.get('error')}")
    return "\n".join(lines)


def render_analyze_text(result: dict[str, Any]) -> str:
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

    largest = metrics.get("largest_files") or []
    if largest:
        lines.append("")
        lines.append("## Największe pliki")
        for item in largest[:5]:
            lines.append(
                f"- `{item.get('path', '?')}` — {item.get('lines', '?')} linii"
            )

    lines.extend(render_repo_selection_text(result.get("repo_selection")))

    lines.append("")
    lines.append("## Proponowane etapy")
    if recommendations:
        for idx, rec in enumerate(recommendations[:7], start=1):
            priority = rec.get("priority", "medium")
            target = rec.get("target", "general")
            action = rec.get("suggested_action", "review")
            reason = rec.get("reason", "")
            line = f"{idx}. **[{priority}] `{target}`** — {action}"
            if reason:
                line += f" ({reason})"
            lines.append(line)
    else:
        lines.append("1. Brak automatycznych rekomendacji — sprawdź metryki i wzorce.")

    note = result.get("note")
    if note:
        lines.append("")
        lines.append(f"_Info: {note}_")
    return "\n".join(lines)


def render_queued_text(result: dict[str, Any]) -> str:
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


def render_refactor_text(result: dict[str, Any]) -> str:
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

    lines.extend(render_repo_selection_text(result.get("repo_selection")))

    if summary:
        lines.append("")
        lines.append("## Podsumowanie planu")
        lines.append(summary)

    lines.extend(render_refactor_execution(execution))

    if not execute_commit:
        lines.append("")
        lines.append("_Tryb plan-only: nic nie zostało zapisane ani wypchnięte._")

    note = result.get("note")
    if note:
        lines.append("")
        lines.append(f"_Info: {note}_")
    return "\n".join(lines)


def render_github_qa_text(result: dict[str, Any]) -> str:
    answer = (result.get("answer") or "").strip()
    if not answer:
        answer = "⚠️ Brak odpowiedzi z GitHub Q&A."

    lines = [answer]
    llm = result.get("llm") or {}
    llm_model = llm.get("model")
    if llm_model:
        state = "used" if llm.get("used") else "fallback"
        lines.append("")
        lines.append(f"_GitHub Q&A: model=`{llm_model}`, state=`{state}`_")

    error = result.get("error")
    if error and error not in answer:
        lines.append("")
        lines.append(f"⚠️ {error}")
    return "\n".join(lines)


def render_chat_content(result: dict[str, Any]) -> str:
    if not isinstance(result, dict):
        return str(result)

    if result.get("error") and not result.get("skill"):
        return f"❌ Błąd workflow: {result.get('error')}"

    skill = result.get("skill")
    if skill == "system":
        return render_system_text(result)
    if skill == "queued":
        return render_queued_text(result)
    if skill == "analyze":
        return render_analyze_text(result)
    if skill == "refactor":
        return render_refactor_text(result)
    if skill == "tool":
        return render_tool_text(result.get("tool_result") or result)
    if skill == "tools_list":
        return render_tools_list_text(result.get("tools_list") or result)
    if skill == "github_qa":
        return render_github_qa_text(result)

    return json.dumps(result, ensure_ascii=False)


def build_commit_changes(plan_payload: dict[str, Any], summary_md: str) -> list[dict[str, str]]:
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


# Re-exported from render_tools.py (see module docstring at top).

