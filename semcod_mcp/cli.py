"""CLI entrypoint for semcod-mcp."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from semcod_mcp import __version__
from semcod_mcp.analyze import run_analyze
from semcod_mcp.doctor import run_doctor
from semcod_mcp.init_cmd import print_init_result, run_init
from semcod_mcp.paths import detect_stack_path
from semcod_mcp.validate import run_validate

console = Console()


@click.group()
@click.version_option(__version__, prog_name="semcod-mcp")
def main() -> None:
    """semcod MCP — init IDE configs, doctor, validate, analyze."""


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
def analyze_cmd(path: Path, task: str, execute: bool) -> None:
    """Run gateway analysis for repo (or local fallback summary)."""
    report = run_analyze(path, task=task, execute=execute)
    console.print(f"[bold]Repo:[/bold] {report.repo_id or '—'}  [bold]Mode:[/bold] {report.mode}")
    console.print(report.summary)
    for note in report.notes:
        console.print(f"  [dim]• {note}[/dim]")
    if not report.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
