"""semcod-mcp validate — local config validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from semcod_mcp.merge import load_json
from semcod_mcp.paths import MANIFEST_NAME, detect_stack_path
from semcod_mcp.templates import SERVER_NAME, read_manifest


@dataclass
class ValidationIssue:
    level: str  # error | warning
    path: str
    message: str


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.level == "error" for i in self.issues)

    def error(self, path: str, message: str) -> None:
        self.issues.append(ValidationIssue("error", path, message))

    def warn(self, path: str, message: str) -> None:
        self.issues.append(ValidationIssue("warning", path, message))


def _validate_mcp_json(path: Path, report: ValidationReport, stack_path: Path | None) -> None:
    if not path.is_file():
        report.warn(str(path), "not found")
        return
    try:
        data = load_json(path)
    except (json.JSONDecodeError, ValueError) as exc:
        report.error(str(path), str(exc))
        return

    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        report.error(str(path), "mcpServers must be an object")
        return

    entry = servers.get(SERVER_NAME)
    if entry is None:
        report.warn(str(path), f"missing server {SERVER_NAME}")
        return

    args = entry.get("args") or []
    compose_flags = [a for a in args if str(a).endswith("docker-compose.yml")]
    if stack_path and compose_flags:
        if str(stack_path / "docker-compose.yml") not in [str(a) for a in compose_flags]:
            report.warn(str(path), "docker-compose path may not match detected stack")
    elif not compose_flags:
        report.warn(str(path), "no docker-compose.yml in args")


def run_validate(project_dir: Path) -> ValidationReport:
    project_dir = project_dir.resolve()
    report = ValidationReport()
    stack = detect_stack_path()

    manifest = read_manifest(project_dir)
    if manifest is None:
        report.warn(MANIFEST_NAME, "missing — run semcod-mcp init")
    else:
        m_stack = manifest.get("stack_path")
        if stack and m_stack and Path(m_stack).resolve() != stack.resolve():
            report.warn(MANIFEST_NAME, f"stack_path {m_stack} differs from detected {stack}")

    for rel in (
        ".cursor/mcp.json",
        ".vscode/mcp.json",
        ".windsurf/mcp.json",
    ):
        _validate_mcp_json(project_dir / rel, report, stack)

    continue_cfg = project_dir / ".continue" / "config.json"
    if continue_cfg.is_file():
        try:
            data = load_json(continue_cfg)
            models = data.get("models", [])
            titles = {m.get("title") for m in models if isinstance(m, dict)}
            for expected in ("semcod-mcp-analyze", "semcod-mcp-refactor"):
                if expected not in titles:
                    report.warn(str(continue_cfg), f"missing model {expected}")
        except (json.JSONDecodeError, ValueError) as exc:
            report.error(str(continue_cfg), str(exc))

    rule = project_dir / ".cursor" / "rules" / "semcod-mcp.mdc"
    if not rule.is_file():
        report.warn(str(rule), "cursor rule missing")

    return report
