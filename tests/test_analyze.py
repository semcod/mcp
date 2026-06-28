"""Tests for semcod-mcp analyze and container source path mapping."""

from __future__ import annotations

from pathlib import Path

from semcod_mcp.analyze import _format_analyze_result
from semcod_mcp.paths import container_source_path


def test_container_source_path_maps_semcod_sibling():
    stack = Path("/home/tom/github/semcod/mcp")
    project = Path("/home/tom/github/semcod/nlp2cmd")
    assert container_source_path(project, stack) == "/host-semcod/nlp2cmd"


def test_container_source_path_maps_stack_itself():
    stack = Path("/home/tom/github/semcod/mcp")
    assert container_source_path(stack, stack) == "/host-semcod/mcp"


def test_format_analyze_result_includes_largest_files():
    text = _format_analyze_result(
        {
            "repo_id": "semcod/mcp",
            "analysis": {
                "metrics": {
                    "file_count": 10,
                    "total_lines": 1000,
                    "largest_files": [{"path": "mcp-gateway/server.py", "lines": 228}],
                },
                "recommendations": {
                    "recommendations": [
                        {
                            "priority": "high",
                            "target": "foo.py",
                            "suggested_action": "split_module",
                        }
                    ]
                },
            },
        }
    )
    assert "mcp-gateway/server.py" in text
    assert "228" in text
    assert "split_module" in text
