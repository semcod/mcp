"""Shared repo metrics and refactoring recommendations for mcp-skills."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from analysis_recommendations import (
    _make_adder,
    add_avg_file_size_recommendation,
    add_dense_function_recommendations,
    add_large_file_recommendations,
    add_structure_recommendations,
)

DEFAULT_EXTENSIONS = (".py", ".js", ".ts", ".tsx", ".jsx")
SKIP_DIR_NAMES = {".git", "__pycache__", ".venv", "node_modules", ".mypy_cache"}


def _should_skip_path(file_path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in file_path.parts)


def compute_repo_file_metrics(
    repo_path: Path,
    extensions: list[str] | None = None,
) -> dict[str, Any]:
    """Scan repo on disk and return aggregate metrics including largest_files."""
    if extensions is None:
        extensions = list(DEFAULT_EXTENSIONS)

    if not repo_path.is_dir():
        return {"error": f"Repo path does not exist: {repo_path}"}

    file_metrics: list[dict[str, Any]] = []
    total_lines = 0
    total_imports = 0
    total_functions = 0
    total_classes = 0

    for ext in extensions:
        for file_path in repo_path.rglob(f"*{ext}"):
            if _should_skip_path(file_path):
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            lines = content.splitlines()
            line_count = len(lines)
            imports = sum(
                1
                for line in lines
                if line.strip().startswith("import ") or line.strip().startswith("from ")
            )
            functions = sum(1 for line in lines if line.strip().startswith("def "))
            classes = sum(1 for line in lines if line.strip().startswith("class "))

            total_lines += line_count
            total_imports += imports
            total_functions += functions
            total_classes += classes
            file_metrics.append(
                {
                    "path": str(file_path.relative_to(repo_path)),
                    "lines": line_count,
                    "imports": imports,
                    "functions": functions,
                    "classes": classes,
                }
            )

    file_metrics.sort(key=lambda item: item["lines"], reverse=True)
    file_count = len(file_metrics)

    return {
        "file_count": file_count,
        "total_lines": total_lines,
        "total_imports": total_imports,
        "total_functions": total_functions,
        "total_classes": total_classes,
        "avg_lines_per_file": total_lines // file_count if file_count else 0,
        "largest_files": file_metrics[:10],
    }


def detect_repo_patterns(repo_path: Path) -> dict[str, Any]:
    """Detect large/complex files for pattern reporting."""
    large_files: list[dict[str, Any]] = []
    high_complexity: list[dict[str, Any]] = []
    import_map: dict[str, int] = {}

    if not repo_path.is_dir():
        return {
            "large_files_count": 0,
            "high_complexity_count": 0,
            "large_files": [],
            "high_complexity": [],
            "common_imports": [],
        }

    for file_path in repo_path.rglob("*.py"):
        if _should_skip_path(file_path):
            continue
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        rel_path = str(file_path.relative_to(repo_path))
        line_count = len(lines)
        if line_count > 500:
            large_files.append({"path": rel_path, "lines": line_count})
        if line_count > 300:
            high_complexity.append({"path": rel_path, "indicator": f"{line_count} lines"})

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                import_map[stripped] = import_map.get(stripped, 0) + 1

    common_imports = sorted(import_map.items(), key=lambda item: item[1], reverse=True)[:10]
    return {
        "large_files_count": len(large_files),
        "high_complexity_count": len(high_complexity),
        "large_files": large_files[:5],
        "high_complexity": high_complexity[:5],
        "common_imports": common_imports,
    }


def build_maintainability_recommendations(
    metrics: dict[str, Any],
    *,
    repo_id: str,
    goal: str = "maintainability",
) -> list[dict[str, Any]]:
    """Build concrete file-targeted recommendations from repo metrics."""
    recommendations: list[dict[str, Any]] = []
    seen_targets: set[str] = set()
    add = _make_adder(recommendations, seen_targets)

    if goal in {"maintainability", "modularity", "performance"}:
        add_large_file_recommendations(metrics, add)
        add_dense_function_recommendations(metrics, add)

    add_structure_recommendations(metrics, add)
    add_avg_file_size_recommendation(metrics, recommendations, add)
    return recommendations


def merge_recommendations(
    primary: list[dict[str, Any]],
    supplemental: list[dict[str, Any]],
    *,
    max_items: int = 15,
) -> list[dict[str, Any]]:
    """Merge recommendation lists; prefer concrete file targets over 'general'."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    def key(rec: dict[str, Any]) -> str:
        return f"{rec.get('type')}::{rec.get('target')}"

    for rec in primary + supplemental:
        target = str(rec.get("target") or "general")
        if target == "general":
            continue
        k = key(rec)
        if k in seen:
            continue
        seen.add(k)
        merged.append(rec)

    for rec in primary + supplemental:
        target = str(rec.get("target") or "general")
        if target != "general":
            continue
        k = key(rec)
        if k in seen:
            continue
        seen.add(k)
        merged.append(rec)

    return merged[:max_items]


def recommendations_payload(
    repo_id: str,
    metrics: dict[str, Any],
    recommendations: list[dict[str, Any]],
    *,
    goal: str = "maintainability",
) -> dict[str, Any]:
    return {
        "repo_id": repo_id,
        "goal": goal,
        "summary": {
            "total_recommendations": len(recommendations),
            "high_priority": sum(1 for r in recommendations if r.get("priority") == "high"),
            "medium_priority": sum(1 for r in recommendations if r.get("priority") == "medium"),
        },
        "recommendations": recommendations,
        "metrics_summary": {
            "total_files": metrics.get("file_count"),
            "total_lines": metrics.get("total_lines"),
            "avg_lines_per_file": metrics.get("avg_lines_per_file"),
            "largest_files": metrics.get("largest_files", [])[:5],
        },
    }
