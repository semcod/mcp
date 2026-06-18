"""semcod-mcp deinit — remove IDE configuration added by init."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

from semcod_mcp.merge import (
    delete_file,
    load_json,
    remove_continue_models,
    remove_mcp_server,
    remove_vscode_settings,
    write_json_or_delete,
)
from semcod_mcp.paths import MANIFEST_NAME
from semcod_mcp.templates import (
    CONTINUE_MODEL_TITLES,
    CURSOR_RULE_NAME,
    SERVER_NAME,
    VSCODE_SETTING_KEYS,
)

console = Console()


@dataclass
class DeinitResult:
    project_dir: Path
    messages: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return any(
            "removed:" in m
            or m.startswith("deleted:")
            or m.startswith("would delete:")
            or m.startswith("updated:")
            or m.startswith("would update:")
            for m in self.messages
        )


def _deinit_mcp_json(path: Path, *, dry_run: bool) -> list[str]:
    if not path.is_file():
        return [f"skipped: {path} (not found)"]

    merged, msgs = remove_mcp_server(load_json(path), SERVER_NAME)
    prefix = str(path)
    if any(m.startswith("removed:") for m in msgs):
        action = write_json_or_delete(path, merged, dry_run=dry_run)
        if action in ("deleted", "would delete"):
            return [f"{action}: {path}"] + [f"{prefix}: {m}" for m in msgs]
        return [f"{action}: {path}"] + [f"{prefix}: {m}" for m in msgs]
    return [f"{prefix}: {m}" for m in msgs]


def run_deinit(
    project_dir: Path,
    *,
    global_config: bool = False,
    dry_run: bool = False,
    skip_continue: bool = False,
) -> DeinitResult:
    project_dir = project_dir.resolve()
    result = DeinitResult(project_dir=project_dir)

    for cfg_path in (
        project_dir / ".cursor" / "mcp.json",
        project_dir / ".vscode" / "mcp.json",
        project_dir / ".windsurf" / "mcp.json",
    ):
        result.messages.extend(_deinit_mcp_json(cfg_path, dry_run=dry_run))

    rule_path = project_dir / ".cursor" / "rules" / CURSOR_RULE_NAME
    rule_action = delete_file(rule_path, dry_run=dry_run)
    if rule_action == "skipped":
        result.messages.append(f"skipped: {rule_path} (not found)")
    else:
        result.messages.append(f"{rule_action}: {rule_path}")

    vscode_settings = project_dir / ".vscode" / "settings.json"
    if vscode_settings.is_file():
        merged, s_msgs = remove_vscode_settings(
            load_json(vscode_settings),
            frozenset(VSCODE_SETTING_KEYS),
        )
        if any(m.startswith("removed:") for m in s_msgs):
            action = write_json_or_delete(vscode_settings, merged, dry_run=dry_run)
            result.messages.append(f"{action}: {vscode_settings}")
        result.messages.extend([f"{vscode_settings}: {m}" for m in s_msgs])
    else:
        result.messages.append(f"skipped: {vscode_settings} (not found)")

    if not skip_continue:
        continue_cfg = project_dir / ".continue" / "config.json"
        if continue_cfg.is_file():
            merged, c_msgs = remove_continue_models(
                load_json(continue_cfg),
                frozenset(CONTINUE_MODEL_TITLES),
            )
            if any(m.startswith("removed:") for m in c_msgs):
                action = write_json_or_delete(continue_cfg, merged, dry_run=dry_run)
                result.messages.append(f"{action}: {continue_cfg}")
            result.messages.extend([f"{continue_cfg}: {m}" for m in c_msgs])
        else:
            result.messages.append(f"skipped: {continue_cfg} (not found)")

    if global_config:
        home = Path.home()
        for cfg_path in (
            home / ".cursor" / "mcp.json",
            home / ".config" / "Claude" / "claude_desktop_config.json",
        ):
            result.messages.extend(_deinit_mcp_json(cfg_path, dry_run=dry_run))

    manifest_path = project_dir / MANIFEST_NAME
    manifest_action = delete_file(manifest_path, dry_run=dry_run)
    if manifest_action == "skipped":
        result.messages.append(f"skipped: {manifest_path} (not found)")
    else:
        result.messages.append(f"{manifest_action}: {manifest_path}")

    return result


def print_deinit_result(result: DeinitResult) -> None:
    console.print(f"[bold]Project:[/bold] {result.project_dir}")
    for line in result.messages:
        if "unchanged" in line or "skipped" in line:
            console.print(f"  [dim]{line}[/dim]")
        else:
            console.print(f"  [green]{line}[/green]")
    if not result.changed:
        console.print("[dim]Nothing to remove — semcod-mcp not initialized here.[/dim]")
