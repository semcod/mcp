import json
from pathlib import Path

from semcod_mcp.deinit_cmd import run_deinit
from semcod_mcp.init_cmd import run_init
from semcod_mcp.paths import MANIFEST_NAME
from semcod_mcp.templates import CURSOR_RULE_NAME, SERVER_NAME


def _make_stack(tmp_path: Path) -> Path:
    stack = tmp_path / "stack"
    stack.mkdir()
    (stack / "docker-compose.yml").write_text("services: {}\n")
    (stack / "mcp-gateway").mkdir()
    return stack


def test_deinit_dry_run_leaves_files(tmp_path: Path):
    stack = _make_stack(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    run_init(project, stack_path=stack, dry_run=False)
    assert (project / MANIFEST_NAME).is_file()

    result = run_deinit(project, dry_run=True)
    assert result.changed
    assert (project / MANIFEST_NAME).is_file()
    assert SERVER_NAME in json.loads((project / ".cursor" / "mcp.json").read_text())["mcpServers"]


def test_deinit_removes_init_artifacts(tmp_path: Path):
    stack = _make_stack(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    run_init(project, stack_path=stack, dry_run=False)
    run_deinit(project, dry_run=False)

    assert not (project / MANIFEST_NAME).exists()
    assert not (project / ".cursor" / "mcp.json").exists()
    assert not (project / ".cursor" / "rules" / CURSOR_RULE_NAME).exists()
    assert not (project / ".continue" / "config.json").exists()
    assert not (project / ".vscode" / "settings.json").exists()


def test_deinit_preserves_other_mcp_servers(tmp_path: Path):
    stack = _make_stack(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    (project / ".cursor").mkdir(parents=True)
    (project / ".cursor" / "mcp.json").write_text(
        json.dumps({"mcpServers": {"custom": {"command": "keep"}}})
    )

    run_init(project, stack_path=stack, dry_run=False)
    run_deinit(project, dry_run=False)

    data = json.loads((project / ".cursor" / "mcp.json").read_text())
    assert data == {"mcpServers": {"custom": {"command": "keep"}}}


def test_deinit_idempotent_second_run(tmp_path: Path):
    stack = _make_stack(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    run_init(project, stack_path=stack, dry_run=False)
    first = run_deinit(project, dry_run=False)
    assert first.changed

    second = run_deinit(project, dry_run=False)
    assert not second.changed
