"""semcod-mcp init — non-destructive IDE configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

from semcod_mcp.merge import (
    load_json,
    merge_continue_models,
    merge_mcp_servers,
    merge_vscode_settings,
    save_json,
)
from semcod_mcp.paths import MANIFEST_NAME, detect_stack_path, infer_repo_id
from semcod_mcp.templates import (
    CURSOR_RULE_NAME,
    SERVER_NAME,
    continue_models,
    cursor_rule_text,
    manifest_data,
    mcp_server_block,
    vscode_settings_snippet,
    write_manifest,
)

console = Console()


@dataclass
class InitResult:
    project_dir: Path
    messages: list[str] = field(default_factory=list)
    ides: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return any(
            "added:" in m
            or "replaced:" in m
            or "created:" in m
            or "wrote:" in m
            or "would write" in m
            for m in self.messages
        )


def _touch_text(path: Path, content: str, *, dry_run: bool, force: bool) -> list[str]:
    msgs: list[str] = []
    existed = path.is_file()
    if existed and not force:
        msgs.append(f"skipped: {path} (exists)")
        return msgs
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    action = "updated" if existed else "created"
    msgs.append(f"{action}: {path}")
    return msgs


def _init_mcp_json(path: Path, stack_path: Path, *, dry_run: bool, force: bool) -> list[str]:
    existing = load_json(path)
    merged, msgs = merge_mcp_servers(
        existing,
        SERVER_NAME,
        mcp_server_block(stack_path),
        force=force,
    )
    prefix = str(path)
    if any(m.startswith("added") or m.startswith("replaced") for m in msgs):
        save_json(path, merged, dry_run=dry_run)
    return [f"{prefix}: {m}" for m in msgs]


def run_init(
    project_dir: Path,
    *,
    stack_path: Path | None = None,
    global_config: bool = False,
    dry_run: bool = False,
    force: bool = False,
    skip_continue: bool = False,
) -> InitResult:
    stack = stack_path or detect_stack_path()
    if stack is None:
        raise SystemExit(
            "Cannot find semcod MCP stack (docker-compose.yml). "
            "Use --stack-path or set SEMCOD_MCP_STACK."
        )

    project_dir = project_dir.resolve()
    repo_id = infer_repo_id(project_dir)
    result = InitResult(project_dir=project_dir)

    # Project-level IDE configs
    targets: list[tuple[str, Path]] = [
        ("cursor", project_dir / ".cursor" / "mcp.json"),
        ("vscode", project_dir / ".vscode" / "mcp.json"),
        ("windsurf", project_dir / ".windsurf" / "mcp.json"),
    ]
    for ide, cfg_path in targets:
        result.messages.extend(_init_mcp_json(cfg_path, stack, dry_run=dry_run, force=force))
        result.ides.append(ide)

    # Cursor rule (only if missing unless force)
    rule_path = project_dir / ".cursor" / "rules" / CURSOR_RULE_NAME
    result.messages.extend(
        _touch_text(
            rule_path,
            cursor_rule_text(repo_id, stack),
            dry_run=dry_run,
            force=force,
        )
    )

    # VS Code settings snippet
    vscode_settings = project_dir / ".vscode" / "settings.json"
    merged_settings, s_msgs = merge_vscode_settings(
        load_json(vscode_settings),
        vscode_settings_snippet(),
    )
    if any(m.startswith("added") for m in s_msgs):
        save_json(vscode_settings, merged_settings, dry_run=dry_run)
    result.messages.extend([f"{vscode_settings}: {m}" for m in s_msgs])
    result.ides.append("vscode-settings")

    # Continue.dev (project-local if supported)
    if not skip_continue:
        from semcod_mcp.paths import default_api_key, gateway_url

        continue_cfg = project_dir / ".continue" / "config.json"
        merged_cont, c_msgs = merge_continue_models(
            load_json(continue_cfg),
            continue_models(gateway_url(stack), default_api_key()),
            force=force,
        )
        if any(m.startswith("added") or m.startswith("replaced") for m in c_msgs):
            save_json(continue_cfg, merged_cont, dry_run=dry_run)
        result.messages.extend([f"{continue_cfg}: {m}" for m in c_msgs])
        result.ides.append("continue")

    # Global user configs (optional)
    if global_config:
        home = Path.home()
        global_targets = [
            ("cursor-global", home / ".cursor" / "mcp.json"),
            ("claude-desktop", home / ".config" / "Claude" / "claude_desktop_config.json"),
        ]
        for ide, cfg_path in global_targets:
            result.messages.extend(_init_mcp_json(cfg_path, stack, dry_run=dry_run, force=force))
            result.ides.append(ide)

    manifest_path = project_dir / MANIFEST_NAME
    manifest_msg = write_manifest(
        manifest_path,
        manifest_data(project_dir, stack, repo_id, result.ides),
        dry_run=dry_run,
        force=force,
    )
    result.messages.append(f"{manifest_path}: {manifest_msg}")

    return result


def print_init_result(result: InitResult) -> None:
    console.print(f"[bold]Project:[/bold] {result.project_dir}")
    for line in result.messages:
        if "unchanged" in line or "skipped" in line:
            console.print(f"  [dim]{line}[/dim]")
        else:
            console.print(f"  [green]{line}[/green]")
    if not result.changed:
        console.print("[dim]Already initialized — no changes (idempotent).[/dim]")
