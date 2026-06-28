"""Tool run / tools-list Markdown renderers for mcp-gateway chat."""

from __future__ import annotations

from typing import Any

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


def _append_sync_and_install(lines: list[str], result: dict[str, Any]) -> None:
    sync = result.get("sync") or {}
    if sync:
        lines.append(
            f"- Klonowanie: `{sync.get('strategy', '?')}` "
            f"(action=`{sync.get('action', '-')}`, ok=`{str(bool(sync.get('ok'))).lower()}`)"
        )
        if sync.get("error"):
            lines.append(f"  - Błąd sync: {sync['error']}")

    install = result.get("install") or {}
    if not install:
        return
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


def _append_stdio(lines: list[str], result: dict[str, Any]) -> None:
    stdout = (result.get("stdout") or "").strip()
    stderr = (result.get("stderr") or "").strip()
    if stdout:
        lines.extend(["", "## stdout", "```", stdout[:6000], "```"])
    if stderr:
        lines.extend(["", "## stderr", "```", stderr[:3000], "```"])


def _append_artifact_entry(lines: list[str], entry: dict[str, Any]) -> str:
    path = entry.get("path") or "?"
    size = entry.get("size") or 0
    truncated = entry.get("truncated")
    lines.append(f"### `{path}` ({size} B{', truncated' if truncated else ''})")
    content = entry.get("content")
    if content is None:
        lines.append("_binary file_")
        return path
    text = content[:16000]
    if is_markdown_path(path):
        lines.append(text)
        return path
    lang = file_fence_lang(path)
    fence_open = f"````{lang}" if lang else "````"
    lines.extend([fence_open, text, "````"])
    return path


def _append_artifacts(lines: list[str], result: dict[str, Any]) -> None:
    summary_files = result.get("summary_files") or []
    output_files = result.get("output_files") or []
    primary = summary_files or output_files
    rendered_paths: set[str] = set()
    if primary:
        lines.extend(["", "## Wygenerowane artefakty"])
    for entry in primary:
        rendered_paths.add(_append_artifact_entry(lines, entry))

    extra = [e for e in output_files if (e.get("path") or "?") not in rendered_paths]
    if not extra:
        return
    lines.extend(["", "## Pozostałe pliki wyjściowe"])
    for entry in extra:
        path = entry.get("path") or "?"
        size = entry.get("size") or 0
        lines.append(f"- `{path}` ({size} B)")


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

    _append_sync_and_install(lines, result)

    cmd = result.get("command") or []
    if cmd:
        lines.append(f"- Komenda: `{' '.join(cmd)}`")
    if returncode is not None:
        lines.append(f"- returncode: `{returncode}`")

    if result.get("error"):
        lines.extend(["", f"⚠️ {result['error']}"])

    _append_stdio(lines, result)
    _append_artifacts(lines, result)
    return "\n".join(lines)


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
    lines.extend(["", "_Użycie: `wygeneruj <narzędzie> dla <owner/repo>`_"])
    return "\n".join(lines)
