import json
from pathlib import Path

from semcod_mcp.init_cmd import run_init
from semcod_mcp.paths import MANIFEST_NAME
from semcod_mcp.templates import SERVER_NAME
from semcod_mcp.validate import run_validate


def test_init_dry_run_writes_nothing(tmp_path: Path):
    stack = tmp_path / "stack"
    stack.mkdir()
    (stack / "docker-compose.yml").write_text("services: {}\n")
    (stack / "mcp-gateway").mkdir()

    project = tmp_path / "project"
    project.mkdir()
    (project / ".cursor").mkdir(parents=True)
    existing = {"mcpServers": {"custom": {"command": "keep"}}}
    (project / ".cursor" / "mcp.json").write_text(json.dumps(existing))

    result = run_init(project, stack_path=stack, dry_run=True)
    assert not (project / MANIFEST_NAME).exists()
    # original untouched
    assert json.loads((project / ".cursor" / "mcp.json").read_text()) == existing
    assert any("added" in m or "unchanged" in m for m in result.messages)


def test_init_merges_cursor_mcp(tmp_path: Path):
    stack = tmp_path / "stack"
    stack.mkdir()
    (stack / "docker-compose.yml").write_text("services: {}\n")
    (stack / "mcp-gateway").mkdir()

    project = tmp_path / "project"
    project.mkdir()

    run_init(project, stack_path=stack, dry_run=False)
    data = json.loads((project / ".cursor" / "mcp.json").read_text())
    assert SERVER_NAME in data["mcpServers"]
    assert (project / MANIFEST_NAME).is_file()

    report = run_validate(project)
    assert report.ok or all(i.level != "error" for i in report.issues)
