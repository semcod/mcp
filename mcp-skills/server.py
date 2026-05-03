#!/usr/bin/env python3
"""
MCP Skills Server - Analiza kodu i metryki dla autonomicznej refaktoryzacji
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import StdioServerTransport
from mcp.types import (
    CallToolRequestParams,
    ListToolsResult,
    TextContent,
    Tool,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPSkillsServer:
    """Serwer MCP Skills z narzędziami do analizy kodu"""

    def __init__(self, repo_base: str = "/repos"):
        self.repo_base = Path(repo_base)
        self.server = Server("mcp-skills")
        self._setup_handlers()

    def _setup_handlers(self):
        """Konfiguracja handlerów MCP"""
        self.server.list_tools()(self._handle_list_tools)
        self.server.call_tool()(self._handle_call_tool)

    async def _handle_list_tools(self) -> ListToolsResult:
        """Lista dostępnych narzędzi"""
        tools = [
            Tool(
                name="analyze_code_structure",
                description="Analyze code structure of given repo paths. Returns line counts, import counts, and file previews.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_id": {
                            "type": "string",
                            "description": "Logical repo ID (e.g. 'my_org/repo')"
                        },
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of relative paths within repo"
                        },
                        "base_path": {
                            "type": "string",
                            "description": "Base path where repos are cloned",
                            "default": "/repos"
                        }
                    },
                    "required": ["repo_id", "paths"]
                }
            ),
            Tool(
                name="compute_metrics_for_repo",
                description="Compute high-level metrics for entire repo. Returns file count, total lines, total imports.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_id": {
                            "type": "string",
                            "description": "Logical repo ID, e.g. 'my_org/repo'"
                        },
                        "base_path": {
                            "type": "string",
                            "description": "Base path where repos are cloned",
                            "default": "/repos"
                        },
                        "extensions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "File extensions to analyze",
                            "default": [".py"]
                        }
                    },
                    "required": ["repo_id"]
                }
            ),
            Tool(
                name="detect_code_patterns",
                description="Detect common code patterns and anti-patterns in repo.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_id": {
                            "type": "string",
                            "description": "Logical repo ID"
                        },
                        "pattern_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Types of patterns to detect: 'complexity', 'duplication', 'imports', 'dependencies'",
                            "default": ["complexity", "imports"]
                        },
                        "base_path": {
                            "type": "string",
                            "description": "Base path where repos are cloned",
                            "default": "/repos"
                        }
                    },
                    "required": ["repo_id"]
                }
            ),
            Tool(
                name="recommend_refactoring",
                description="Generate refactoring recommendations based on code analysis.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_id": {
                            "type": "string",
                            "description": "Logical repo ID"
                        },
                        "target_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific paths to focus on"
                        },
                        "goal": {
                            "type": "string",
                            "description": "Refactoring goal: 'performance', 'maintainability', 'testability', 'modularity'",
                            "default": "maintainability"
                        },
                        "base_path": {
                            "type": "string",
                            "description": "Base path where repos are cloned",
                            "default": "/repos"
                        }
                    },
                    "required": ["repo_id"]
                }
            )
        ]
        return ListToolsResult(tools=tools)

    async def _handle_call_tool(self, name: str, arguments: dict) -> list:
        """Handler wywołań narzędzi"""
        logger.info(f"Tool call: {name} with arguments: {arguments}")

        try:
            if name == "analyze_code_structure":
                return await self._analyze_code_structure(arguments)
            elif name == "compute_metrics_for_repo":
                return await self._compute_metrics_for_repo(arguments)
            elif name == "detect_code_patterns":
                return await self._detect_code_patterns(arguments)
            elif name == "recommend_refactoring":
                return await self._recommend_refactoring(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            raise

    async def _analyze_code_structure(self, arguments: dict) -> list:
        """Analiza struktury kodu dla podanych ścieżek"""
        repo_id = arguments.get("repo_id")
        paths = arguments.get("paths", [])
        base_path = arguments.get("base_path", "/repos")

        if not repo_id or not paths:
            raise ValueError("repo_id and paths are required")

        repo_path = Path(base_path) / repo_id
        results = []

        for rel_path in paths:
            full_path = repo_path / rel_path
            if not full_path.exists():
                results.append({
                    "path": rel_path,
                    "exists": False,
                    "error": "File not found in repo"
                })
                continue

            try:
                with full_path.open("r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                lines = content.splitlines()
                line_count = len(lines)

                # Liczenie importów
                imports = []
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("import ") or stripped.startswith("from "):
                        imports.append(stripped)

                # Podstawowa analiza
                functions = [line for line in lines if line.strip().startswith("def ")]
                classes = [line for line in lines if line.strip().startswith("class ")]

                results.append({
                    "path": rel_path,
                    "exists": True,
                    "line_count": line_count,
                    "import_count": len(imports),
                    "function_count": len(functions),
                    "class_count": len(classes),
                    "imports": imports[:10],  # Pierwsze 10 importów
                    "preview": lines[:10],  # Pierwsze 10 linii
                })
            except Exception as e:
                results.append({
                    "path": rel_path,
                    "exists": True,
                    "error": str(e)
                })

        result_data = {
            "repo_id": repo_id,
            "path_analysis": results
        }

        return [TextContent(type="text", text=json.dumps(result_data, indent=2))]

    async def _compute_metrics_for_repo(self, arguments: dict) -> list:
        """Obliczanie metryk dla całego repozytorium"""
        repo_id = arguments.get("repo_id")
        base_path = arguments.get("base_path", "/repos")
        extensions = arguments.get("extensions", [".py"])

        if not repo_id:
            raise ValueError("repo_id is required")

        repo_path = Path(base_path) / repo_id

        if not repo_path.exists():
            return [TextContent(type="text", text=json.dumps({
                "error": f"Repo '{repo_id}' does not exist at {repo_path}"
            }))]

        total_files = 0
        total_lines = 0
        total_imports = 0
        total_functions = 0
        total_classes = 0

        file_metrics = []

        for ext in extensions:
            for file_path in repo_path.rglob(f"*{ext}"):
                if ".git" in str(file_path):
                    continue

                total_files += 1
                try:
                    with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    lines = content.splitlines()
                    line_count = len(lines)
                    total_lines += line_count

                    imports = sum(1 for line in lines
                                if line.strip().startswith("import ")
                                or line.strip().startswith("from "))
                    total_imports += imports

                    functions = sum(1 for line in lines
                                  if line.strip().startswith("def "))
                    total_functions += functions

                    classes = sum(1 for line in lines
                                if line.strip().startswith("class "))
                    total_classes += classes

                    # Relatywna ścieżka
                    rel_path = file_path.relative_to(repo_path)
                    file_metrics.append({
                        "path": str(rel_path),
                        "lines": line_count,
                        "imports": imports,
                        "functions": functions,
                        "classes": classes
                    })

                except Exception:
                    pass

        # Sortuj po liczbie linii (największe pliki pierwsze)
        file_metrics.sort(key=lambda x: x["lines"], reverse=True)

        metrics = {
            "repo_id": repo_id,
            "file_count": total_files,
            "total_lines": total_lines,
            "total_imports": total_imports,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "avg_lines_per_file": total_lines // total_files if total_files > 0 else 0,
            "largest_files": file_metrics[:10]  # Top 10 największych plików
        }

        return [TextContent(type="text", text=json.dumps(metrics, indent=2))]

    async def _detect_code_patterns(self, arguments: dict) -> list:
        """Wykrywanie wzorców kodu i antywzorców"""
        repo_id = arguments.get("repo_id")
        base_path = arguments.get("base_path", "/repos")
        pattern_types = arguments.get("pattern_types", ["complexity", "imports"])

        repo_path = Path(base_path) / repo_id

        if not repo_path.exists():
            return [TextContent(type="text", text=json.dumps({
                "error": f"Repo '{repo_id}' not found"
            }))]

        patterns = {
            "circular_imports": [],
            "unused_imports": [],
            "large_files": [],
            "high_complexity": [],
            "duplicate_code": []
        }

        all_imports = {}

        for file_path in repo_path.rglob("*.py"):
            if ".git" in str(file_path):
                continue

            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    lines = content.splitlines()

                rel_path = str(file_path.relative_to(repo_path))

                # Wykrywanie dużych plików (>500 linii)
                if len(lines) > 500:
                    patterns["large_files"].append({
                        "path": rel_path,
                        "lines": len(lines)
                    })

                # Zbieranie importów
                file_imports = []
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("import ") or stripped.startswith("from "):
                        file_imports.append(stripped)

                all_imports[rel_path] = file_imports

                # Wykrywanie złożoności (bazowe)
                if len(lines) > 300:
                    patterns["high_complexity"].append({
                        "path": rel_path,
                        "indicator": f"{len(lines)} lines"
                    })

            except Exception:
                pass

        # Analiza importów
        import_map = {}
        for path, imports in all_imports.items():
            for imp in imports:
                if imp not in import_map:
                    import_map[imp] = []
                import_map[imp].append(path)

        # Wyniki
        result = {
            "repo_id": repo_id,
            "patterns_detected": {
                "large_files_count": len(patterns["large_files"]),
                "high_complexity_count": len(patterns["high_complexity"]),
                "large_files": patterns["large_files"][:5],
                "high_complexity": patterns["high_complexity"][:5],
                "common_imports": sorted(
                    [(k, len(v)) for k, v in import_map.items()],
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            }
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def _recommend_refactoring(self, arguments: dict) -> list:
        """Generowanie rekomendacji refaktoryzacji"""
        repo_id = arguments.get("repo_id")
        target_paths = arguments.get("target_paths", [])
        goal = arguments.get("goal", "maintainability")
        base_path = arguments.get("base_path", "/repos")

        repo_path = Path(base_path) / repo_id

        if not repo_path.exists():
            return [TextContent(type="text", text=json.dumps({
                "error": f"Repo '{repo_id}' not found"
            }))]

        # Pobierz metryki
        metrics_args = {"repo_id": repo_id, "base_path": base_path}
        metrics_result = await self._compute_metrics_for_repo(metrics_args)
        metrics = json.loads(metrics_result[0].text)

        recommendations = []

        # Generuj rekomendacje na podstawie metryk i celu
        if goal in ["maintainability", "modularity"]:
            # Sprawdź duże pliki
            if metrics.get("largest_files"):
                for file_info in metrics["largest_files"][:3]:
                    if file_info["lines"] > 500:
                        recommendations.append({
                            "type": "split_file",
                            "priority": "high",
                            "target": file_info["path"],
                            "reason": f"File has {file_info['lines']} lines - consider splitting into smaller modules",
                            "suggested_action": "Extract classes/functions into separate files"
                        })

            # Sprawdź liczbę klas/funkcji
            if metrics.get("total_classes", 0) > 50 and metrics.get("file_count", 0) < 20:
                recommendations.append({
                    "type": "organize_classes",
                    "priority": "medium",
                    "target": "project_structure",
                    "reason": "High class density - consider organizing into packages",
                    "suggested_action": "Group related classes into subpackages"
                })

        if goal in ["performance", "maintainability"]:
            # Sprawdź importy
            if metrics.get("total_imports", 0) > metrics.get("total_lines", 0) * 0.1:
                recommendations.append({
                    "type": "optimize_imports",
                    "priority": "low",
                    "target": "imports",
                    "reason": "High import ratio - consider lazy imports or restructuring",
                    "suggested_action": "Use lazy imports in non-critical paths"
                })

        # Rekomendacje ogólne
        avg_lines = metrics.get("avg_lines_per_file", 0)
        if avg_lines > 300:
            recommendations.append({
                "type": "reduce_file_size",
                "priority": "medium",
                "target": "general",
                "reason": f"Average file size ({avg_lines} lines) is above recommended 300 lines",
                "suggested_action": "Follow single responsibility principle per file"
            })

        result = {
            "repo_id": repo_id,
            "goal": goal,
            "summary": {
                "total_recommendations": len(recommendations),
                "high_priority": sum(1 for r in recommendations if r.get("priority") == "high"),
                "medium_priority": sum(1 for r in recommendations if r.get("priority") == "medium")
            },
            "recommendations": recommendations,
            "metrics_summary": {
                "total_files": metrics.get("file_count"),
                "total_lines": metrics.get("total_lines"),
                "avg_lines_per_file": metrics.get("avg_lines_per_file")
            }
        }

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def run(self):
        """Uruchomienie serwera"""
        from mcp.server.stdio import stdio_server

        async with stdio_server(server=self.server) as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="mcp-skills",
                    server_version="0.1.0",
                    capabilities=self.server.get_capabilities()
                )
            )


async def main():
    server = MCPSkillsServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
