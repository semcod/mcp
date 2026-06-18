"""Markdown renderers for mcp-gateway chat responses."""

from __future__ import annotations

import json
from typing import Any

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
        user = github.get("user")
        if user:
            lines.append(f"- Użytkownik: `{user}`")
        lines.append(f"- Liczba repo: `{github.get('count', 0)}`")
        repos = github.get("repos") or []
        if repos:
            lines.append("")
            lines.append("## Ostatnio aktywne repo")
            for idx, repo in enumerate(repos, start=1):
                slug = repo.get("nameWithOwner") or "?"
                pushed_at = repo.get("pushedAt") or "?"
                url = repo.get("url")
                lines.append(f"{idx}. `{slug}` — `{pushed_at}`")
                if url:
                    lines.append(f"   - {url}")

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


_FENCE_LANG_MAP: dict[str, str] = {
    ".py": "python",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".md": "markdown",
    ".mmd": "mermaid",
    ".mermaid": "mermaid",
    ".less": "less",
    ".css": "css",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".sql": "sql",
    ".html": "html",
    ".htm": "html",
    ".xml": "xml",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".tf": "hcl",
    ".hcl": "hcl",
    ".ini": "ini",
    ".env": "bash",
    ".dockerfile": "dockerfile",
    ".toon": "yaml",
    ".doql": "less",
    ".planfile": "yaml",
    ".diff": "diff",
    ".patch": "diff",
}

# File names (basename) that have a known language.
_FENCE_NAME_MAP: dict[str, str] = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
    "taskfile.yml": "yaml",
    "taskfile.yaml": "yaml",
    ".env": "bash",
    ".env.example": "bash",
    "cargo.toml": "toml",
    "pyproject.toml": "toml",
    "package.json": "json",
    "composer.json": "json",
}


def file_fence_lang(path: str) -> str:
    p = path.lower()
    basename = p.rsplit("/", 1)[-1]
    if basename in _FENCE_NAME_MAP:
        return _FENCE_NAME_MAP[basename]
    for ext, lang in _FENCE_LANG_MAP.items():
        if p.endswith(ext):
            return lang
    return ""


def is_markdown_path(path: str) -> bool:
    return path.lower().endswith(".md")


def render_tool_text(result: dict[str, Any]) -> str:
    """Render result of /tools/run into a Markdown chat reply."""
    tool = result.get("tool") or "?"
    repo_id = result.get("repo_id") or "?"
    repo_url = result.get("repo_url")
    returncode = result.get("returncode")
    ok = bool(result.get("ok"))
    status = "✅" if ok else "❌"
    lines = [f"# {status} `{tool}` na `{repo_id}`"]
    if result.get("tool_description"):
        lines.append(f"_{result['tool_description']}_")
    if repo_url:
        lines.append(f"- Źródło: {repo_url}")

    sync = result.get("sync") or {}
    if sync:
        lines.append(
            f"- Klonowanie: `{sync.get('strategy', '?')}` "
            f"(action=`{sync.get('action', '-')}`, ok=`{str(bool(sync.get('ok'))).lower()}`)"
        )
        if sync.get("error"):
            lines.append(f"  - Błąd sync: {sync['error']}")

    install = result.get("install") or {}
    if install:
        avail = install.get("available")
        installed_now = install.get("installed_now")
        bin_path = install.get("binary_path")
        lines.append(
            f"- Instalacja: available=`{str(bool(avail)).lower()}`, "
            f"installed_now=`{str(bool(installed_now)).lower()}`"
            + (f", path=`{bin_path}`" if bin_path else "")
        )
        if install.get("pip_stderr"):
            lines.append(f"  - pip stderr (skrót): `{install['pip_stderr'][:300]}`")
        if install.get("error"):
            lines.append(f"  - Błąd instalacji: {install['error']}")

    cmd = result.get("command") or []
    if cmd:
        lines.append(f"- Komenda: `{' '.join(cmd)}`")
    if returncode is not None:
        lines.append(f"- returncode: `{returncode}`")

    if result.get("error"):
        lines.append("")
        lines.append(f"⚠️ {result['error']}")

    stdout = (result.get("stdout") or "").strip()
    stderr = (result.get("stderr") or "").strip()
    if stdout:
        lines.append("")
        lines.append("## stdout")
        lines.append("```")
        lines.append(stdout[:6000])
        lines.append("```")
    if stderr:
        lines.append("")
        lines.append("## stderr")
        lines.append("```")
        lines.append(stderr[:3000])
        lines.append("```")

    summary_files = result.get("summary_files") or []
    output_files = result.get("output_files") or []

    primary = summary_files or output_files
    rendered_paths: set[str] = set()
    if primary:
        lines.append("")
        lines.append("## Wygenerowane artefakty")
    for entry in primary:
        path = entry.get("path") or "?"
        rendered_paths.add(path)
        size = entry.get("size") or 0
        truncated = entry.get("truncated")
        lines.append(f"### `{path}` ({size} B{', truncated' if truncated else ''})")
        content = entry.get("content")
        if content is None:
            lines.append("_binary file_")
            continue
        text = content[:16000]
        if is_markdown_path(path):
            # Render Markdown files directly — avoid nested fences.
            # Replace any 3-backtick fences with 4-backtick fences to prevent
            # collision with the outer code block, then just output raw.
            lines.append(text)
        else:
            lang = file_fence_lang(path)
            # Use 4-backtick fence so inner 3-backtick fences don't break rendering.
            fence_open = f"````{lang}" if lang else "````"
            lines.append(fence_open)
            lines.append(text)
            lines.append("````")

    extra = [e for e in output_files if (e.get("path") or "?") not in rendered_paths]
    if extra:
        lines.append("")
        lines.append("## Pozostałe pliki wyjściowe")
        for entry in extra:
            path = entry.get("path") or "?"
            size = entry.get("size") or 0
            lines.append(f"- `{path}` ({size} B)")

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


def render_tools_list_text(result: dict[str, Any]) -> str:
    """Render /tools/list result as Markdown."""
    if not result.get("ok"):
        return f"⚠️ Nie udało się pobrać listy narzędzi: {result.get('error')}"
    tools = result.get("tools") or []
    lines = [f"## Dostępne narzędzia semcod ({len(tools)})\n"]
    for t in tools:
        name = t.get("tool", "?")
        desc = t.get("description") or ""
        cmd = t.get("binary", name)
        sub = t.get("default_subcommand") or ""
        args = " ".join(t.get("default_args") or [])
        invocation = f"`{cmd}{' ' + sub if sub else ''}{' ' + args if args else ''}`"
        lines.append(f"- **{name}** — {desc}")
        lines.append(f"  Domyślne wywołanie: {invocation}")
        if t.get("key_outputs"):
            lines.append(f"  Pliki wyjściowe: {', '.join(f'`{o}`' for o in t['key_outputs'][:3])}")
    lines.append("")
    lines.append("_Użycie: `wygeneruj <narzędzie> dla <owner/repo>`_")
    return "\n".join(lines)

