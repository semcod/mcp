"""Tests for shared code analysis helpers."""

from __future__ import annotations

from pathlib import Path

from code_analysis import (
    build_maintainability_recommendations,
    compute_repo_file_metrics,
    merge_recommendations,
)


def test_compute_repo_file_metrics_returns_largest_files(tmp_path: Path):
    repo = tmp_path / "demo"
    pkg = repo / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "small.py").write_text("x = 1\n")
    (pkg / "large.py").write_text("def f():\n    pass\n" * 400)

    metrics = compute_repo_file_metrics(repo, [".py"])

    assert metrics["file_count"] == 2
    assert metrics["largest_files"]
    assert metrics["largest_files"][0]["path"] == "pkg/large.py"
    assert metrics["largest_files"][0]["lines"] > 500


def test_build_maintainability_recommendations_targets_large_files(tmp_path: Path):
    metrics = {
        "file_count": 2,
        "total_lines": 3000,
        "total_imports": 10,
        "total_functions": 40,
        "total_classes": 2,
        "avg_lines_per_file": 1500,
        "largest_files": [
            {"path": "mcp-gateway/server.py", "lines": 2908, "functions": 80, "classes": 0},
            {"path": "mcp-skills/server.py", "lines": 1482, "functions": 40, "classes": 1},
        ],
    }

    recs = build_maintainability_recommendations(metrics, repo_id="semcod/mcp")

    targets = {r["target"] for r in recs}
    assert "mcp-gateway/server.py" in targets
    assert "mcp-skills/server.py" in targets
    assert all(r["target"] != "general" for r in recs if r["type"] in {"split_module", "split_file"})


def test_merge_recommendations_prefers_concrete_targets():
    generic = [
        {
            "type": "extract_functions",
            "priority": "medium",
            "target": "general",
            "reason": "",
            "suggested_action": "extract_functions",
        }
    ]
    concrete = [
        {
            "type": "split_module",
            "priority": "high",
            "target": "mcp-gateway/server.py",
            "reason": "big",
            "suggested_action": "split_module",
        }
    ]

    merged = merge_recommendations(generic, concrete)

    assert merged[0]["target"] == "mcp-gateway/server.py"
    assert any(r["target"] == "general" for r in merged)
