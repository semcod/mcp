"""CLI entrypoint for semcod-mcp."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from semcod_mcp import __version__
from semcod_mcp.analyze import run_analyze
from semcod_mcp.doctor import run_doctor
from semcod_mcp.deinit_cmd import print_deinit_result, run_deinit
from semcod_mcp.init_cmd import print_init_result, run_init
from semcod_mcp.paths import detect_stack_path
from semcod_mcp.validate import run_validate

console = Console()


@click.group()
@click.version_option(__version__, prog_name="semcod-mcp")
def main() -> None:
    """semcod MCP — init/deinit IDE configs, doctor, validate, analyze."""


@main.command("init")
@click.argument("path", type=click.Path(path_type=Path), default=".")
@click.option("--stack-path", type=click.Path(path_type=Path), help="Path to semcod/mcp docker stack")
@click.option("--global", "global_config", is_flag=True, help="Also update ~/.cursor and Claude Desktop")
@click.option("--dry-run", is_flag=True, help="Show actions without writing files")
@click.option("--force", is_flag=True, help="Replace existing semcod-mcp entries")
@click.option("--skip-continue", is_flag=True, help="Skip .continue/config.json")
def init_cmd(
    path: Path,
    stack_path: Path | None,
    global_config: bool,
    dry_run: bool,
    force: bool,
    skip_continue: bool,
) -> None:
    """Initialize IDE/MCP configs in PATH (non-destructive merge)."""
    stack = stack_path or detect_stack_path()
    if stack is None:
        raise click.ClickException("MCP stack not found. Use --stack-path ~/github/semcod/mcp")

    result = run_init(
        path,
        stack_path=stack,
        global_config=global_config,
        dry_run=dry_run,
        force=force,
        skip_continue=skip_continue,
    )
    print_init_result(result)
    if dry_run:
        console.print("[yellow]Dry run — no files written.[/yellow]")


@main.command("deinit")
@click.argument("path", type=click.Path(path_type=Path), default=".")
@click.option("--global", "global_config", is_flag=True, help="Also remove from ~/.cursor and Claude Desktop")
@click.option("--dry-run", is_flag=True, help="Show actions without writing files")
@click.option("--skip-continue", is_flag=True, help="Skip .continue/config.json")
def deinit_cmd(
    path: Path,
    global_config: bool,
    dry_run: bool,
    skip_continue: bool,
) -> None:
    """Remove semcod-mcp IDE integration from PATH (preserves other MCP servers)."""
    result = run_deinit(
        path,
        global_config=global_config,
        dry_run=dry_run,
        skip_continue=skip_continue,
    )
    print_deinit_result(result)
    if dry_run:
        console.print("[yellow]Dry run — no files written.[/yellow]")


@main.command("doctor")
@click.argument("path", type=click.Path(path_type=Path), default=".")
def doctor_cmd(path: Path) -> None:
    """Check Docker stack, gateway API and local semcod-mcp config."""
    report = run_doctor(path)
    table = Table(title="semcod-mcp doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    for check in report.checks:
        status = "[green]OK[/green]" if check.ok else "[red]FAIL[/red]"
        if check.name.startswith("optional:") and not check.ok:
            status = "[yellow]WARN[/yellow]"
        table.add_row(check.name, status, check.detail)
    console.print(table)
    if not report.healthy:
        raise SystemExit(1)


@main.command("validate")
@click.argument("path", type=click.Path(path_type=Path), default=".")
def validate_cmd(path: Path) -> None:
    """Validate local IDE integration files."""
    report = run_validate(path)
    for issue in report.issues:
        color = "red" if issue.level == "error" else "yellow"
        console.print(f"[{color}]{issue.level.upper()}[/{color}] {issue.path}: {issue.message}")
    if not report.ok:
        raise SystemExit(1)
    console.print("[green]Validation passed.[/green]")


@main.command("analyze")
@click.argument("path", type=click.Path(path_type=Path), default=".")
@click.option("--task", default="Szybka analiza struktury i rekomendacje refaktoryzacji.")
@click.option("--execute", is_flag=True, help="Pass Execute: true to gateway")
@click.option(
    "--local",
    "local_tool",
    flag_value="code2llm",
    help="Analiza code2llm na working tree (bez gateway, bez commita)",
)
@click.option(
    "--no-source",
    is_flag=True,
    help="Nie przekazuj Source: /host-semcod/... (użyj tylko zsynchronizowanego repo)",
)
@click.option(
    "--async",
    "async_mode",
    is_flag=True,
    help="Kolejka Redis/RQ zamiast synchronicznego analyze",
)
@click.option("--timeout", default=120.0, show_default=True, help="Timeout HTTP / poll job (s)")
def analyze_cmd(
    path: Path,
    task: str,
    execute: bool,
    local_tool: str | None,
    no_source: bool,
    async_mode: bool,
    timeout: float,
) -> None:
    """Run gateway analysis for repo (live source_path) or local code2llm."""
    report = run_analyze(
        path,
        task=task,
        execute=execute,
        timeout=timeout,
        use_local_source=not no_source,
        sync_mode=not async_mode,
        local_tool=local_tool,
    )
    console.print(f"[bold]Repo:[/bold] {report.repo_id or '—'}  [bold]Mode:[/bold] {report.mode}")
    console.print(report.summary)
    for note in report.notes:
        console.print(f"  [dim]• {note}[/dim]")
    if not report.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
