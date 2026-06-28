"""Recommendation rule helpers for code_analysis."""

from __future__ import annotations

from typing import Any, Callable


def _make_adder(
    recommendations: list[dict[str, Any]],
    seen_targets: set[str],
) -> Callable[[dict[str, Any]], None]:
    def add(rec: dict[str, Any]) -> None:
        target = str(rec.get("target") or "")
        if not target or target in seen_targets:
            return
        seen_targets.add(target)
        recommendations.append(rec)

    return add


def add_large_file_recommendations(metrics: dict[str, Any], add: Callable[[dict[str, Any]], None]) -> None:
    for file_info in metrics.get("largest_files", [])[:5]:
        lines = int(file_info.get("lines") or 0)
        path = str(file_info.get("path") or "")
        if not path:
            continue
        if lines > 1000:
            add({
                "type": "split_module",
                "priority": "high",
                "target": path,
                "reason": f"File has {lines} lines — split into route/handler modules",
                "suggested_action": "split_module",
            })
        elif lines > 500:
            add({
                "type": "split_file",
                "priority": "high",
                "target": path,
                "reason": f"File has {lines} lines — extract cohesive units",
                "suggested_action": "extract_functions",
            })


def add_dense_function_recommendations(metrics: dict[str, Any], add: Callable[[dict[str, Any]], None]) -> None:
    for file_info in metrics.get("largest_files", [])[:10]:
        lines = int(file_info.get("lines") or 0)
        path = str(file_info.get("path") or "")
        functions = int(file_info.get("functions") or 0)
        if path and lines > 300 and functions > 15:
            add({
                "type": "extract_functions",
                "priority": "medium",
                "target": path,
                "reason": f"{functions} functions in {lines} lines — extract helpers",
                "suggested_action": "extract_functions",
            })


def add_structure_recommendations(metrics: dict[str, Any], add: Callable[[dict[str, Any]], None]) -> None:
    if metrics.get("total_classes", 0) > 50 and metrics.get("file_count", 0) < 20:
        add({
            "type": "organize_classes",
            "priority": "medium",
            "target": "project_structure",
            "reason": "High class density — organize into packages",
            "suggested_action": "create_package_structure",
        })

    if metrics.get("total_imports", 0) > metrics.get("total_lines", 0) * 0.1:
        add({
            "type": "optimize_imports",
            "priority": "low",
            "target": "imports",
            "reason": "High import ratio — consider lazy imports",
            "suggested_action": "optimize_imports",
        })


def add_avg_file_size_recommendation(
    metrics: dict[str, Any],
    recommendations: list[dict[str, Any]],
    add: Callable[[dict[str, Any]], None],
) -> None:
    avg_lines = int(metrics.get("avg_lines_per_file") or 0)
    if avg_lines <= 300 or any(r.get("type") == "split_module" for r in recommendations):
        return
    top = (metrics.get("largest_files") or [{}])[0]
    top_path = top.get("path")
    if top_path:
        add({
            "type": "reduce_file_size",
            "priority": "medium",
            "target": str(top_path),
            "reason": f"Average file size is {avg_lines} lines — start with largest file",
            "suggested_action": "split_module",
        })
