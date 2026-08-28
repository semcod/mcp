#!/usr/bin/env python3
"""
MCP Skills Server - Analiza kodu i metryki dla autonomicznej refaktoryzacji
"""

import asyncio
import base64
import json
import logging
import os
import shutil
import subprocess
import sys
import tarfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException

from mcp.server import Server
from mcp.server import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import (
    CallToolRequestParams,
    ListToolsResult,
    TextContent,
    Tool,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPSkillsServer:
    """Serwer MCP Skills z narzędziami do analizy kodu"""

    def __init__(self, repo_base: str = "/repos"):
        env_repo_base = os.getenv("SKILLS_REPO_BASE")
        self.repo_base = Path(env_repo_base or repo_base)
        self.git_proxy_url = os.getenv("GIT_PROXY_URL", "http://mcp-git-proxy:8080")
        self.repo_base.mkdir(parents=True, exist_ok=True)
        self.server = Server("mcp-skills")
        self._setup_handlers()

    async def _sync_from_git_proxy(self, repo_id: str, ref: str = "HEAD") -> Dict[str, Any]:
        target_repo = self.repo_base / repo_id
        target_repo.mkdir(parents=True, exist_ok=True)

        existing_files = {
            str(path.relative_to(target_repo)): path
            for path in target_repo.rglob("*")
            if path.is_file()
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                fragments_response = await client.post(
                    f"{self.git_proxy_url}/packages/export-fragments",
                    json={
                        "repo_id": repo_id,
                        "ref": ref,
                        "max_fragment_bytes": 200_000,
                    },
                )
                fragments_response.raise_for_status()
                fragments_payload = fragments_response.json()

                fragments = fragments_payload.get("fragments", [])
                if not fragments:
                    raise ValueError("No fragments in git proxy response")

                files_synced = 0
                files_updated = 0
                files_unchanged = 0
                incoming_paths: set[str] = set()
                for fragment in fragments:
                    for file_item in fragment.get("files", []):
                        rel_path = file_item.get("path")
                        content_b64 = file_item.get("content_b64")
                        if not rel_path or content_b64 is None:
                            continue
                        incoming_paths.add(rel_path)
                        file_path = target_repo / rel_path
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        incoming_bytes = base64.b64decode(content_b64)

                        if file_path.exists() and file_path.read_bytes() == incoming_bytes:
                            files_unchanged += 1
                        else:
                            file_path.write_bytes(incoming_bytes)
                            files_updated += 1
                        files_synced += 1

                files_deleted = 0
                for rel_path, existing_path in existing_files.items():
                    if rel_path not in incoming_paths and existing_path.exists():
                        existing_path.unlink()
                        files_deleted += 1

                return {
                    "repo_id": repo_id,
                    "target_path": str(target_repo),
                    "synced_ref": fragments_payload.get("ref", ref),
                    "transfer_mode": "fragments",
                    "fragment_count": fragments_payload.get("fragment_count", len(fragments)),
                    "files_synced": files_synced,
                    "files_updated": files_updated,
                    "files_unchanged": files_unchanged,
                    "files_deleted": files_deleted,
                }
            except Exception:
                response = await client.post(
                    f"{self.git_proxy_url}/packages/export",
                    json={"repo_id": repo_id, "ref": ref},
                )
                response.raise_for_status()
                payload = response.json()

                archive_b64 = payload.get("archive_b64")
                if not archive_b64:
                    raise ValueError("Missing archive_b64 in git proxy response")

                archive_bytes = base64.b64decode(archive_b64)
                with tarfile.open(fileobj=BytesIO(archive_bytes), mode="r:gz") as tar:
                    tar.extractall(target_repo)

                return {
                    "repo_id": repo_id,
                    "target_path": str(target_repo),
                    "synced_ref": payload.get("ref", ref),
                    "transfer_mode": "archive",
                }

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
                            "default": str(self.repo_base)
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
                            "default": str(self.repo_base)
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
                            "default": str(self.repo_base)
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
                            "default": str(self.repo_base)
                        }
                    },
                    "required": ["repo_id"]
                }
            ),
            Tool(
                name="sync_repo_from_git_proxy",
                description="Synchronize repository package from MCP Git Proxy into local skills cache.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_id": {
                            "type": "string",
                            "description": "Logical repo ID"
                        },
                        "ref": {
                            "type": "string",
                            "description": "Git ref (branch/tag/sha)",
                            "default": "HEAD"
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
            elif name == "sync_repo_from_git_proxy":
                return await self._sync_repo_tool(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            raise

    async def _analyze_code_structure(self, arguments: dict) -> list:
        """Analiza struktury kodu dla podanych ścieżek"""
        repo_id = arguments.get("repo_id")
        paths = arguments.get("paths", [])
        base_path = arguments.get("base_path", str(self.repo_base))

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
        base_path = arguments.get("base_path", str(self.repo_base))
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
        base_path = arguments.get("base_path", str(self.repo_base))
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

    async def _sync_repo_tool(self, arguments: dict) -> list:
        repo_id = arguments.get("repo_id")
        ref = arguments.get("ref", "HEAD")
        if not repo_id:
            raise ValueError("repo_id is required")

        sync_result = await self._sync_from_git_proxy(repo_id, ref)
        return [TextContent(type="text", text=json.dumps(sync_result, indent=2))]

    async def _recommend_refactoring(self, arguments: dict) -> list:
        """Generowanie rekomendacji refaktoryzacji"""
        repo_id = arguments.get("repo_id")
        target_paths = arguments.get("target_paths", [])
        goal = arguments.get("goal", "maintainability")
        base_path = arguments.get("base_path", str(self.repo_base))

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

        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="mcp-skills",
                    server_version="0.1.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    )
                )
            )


class SyncRepoRequest(BaseModel):
    repo_id: str
    ref: str = "HEAD"


class AnalyzeStructureRequest(BaseModel):
    repo_id: str
    paths: list[str]
    base_path: str | None = None


class RepoMetricsRequest(BaseModel):
    repo_id: str
    base_path: str | None = None
    extensions: list[str] = Field(default_factory=lambda: [".py"])


class PatternDetectionRequest(BaseModel):
    repo_id: str
    base_path: str | None = None
    pattern_types: list[str] = Field(default_factory=lambda: ["complexity", "imports"])


class RecommendRefactoringRequest(BaseModel):
    repo_id: str
    target_paths: list[str] = Field(default_factory=list)
    goal: str = "maintainability"
    base_path: str | None = None


class RedslRefactorRequest(BaseModel):
    repo_id: str
    max_actions: int = 10
    dry_run: bool = True
    execute: bool = False
    user_request: str = ""
    base_path: str | None = None


class ToolRunRequest(BaseModel):
    """Generic request to run a semcod CLI tool against a repo."""

    tool: str
    repo_id: str | None = None
    repo_url: str | None = None
    ref: str = "HEAD"
    subcommand: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    auto_install: bool = True
    timeout: int = 600
    base_path: str | None = None
    use_git_proxy: bool = True


# Registry of supported semcod CLI tools.
# Each entry describes how to invoke the tool against a repo directory.
SUPPORTED_TOOLS: dict[str, dict[str, Any]] = {
    "sumd": {
        "package": "sumd",
        "binary": "sumd",
        "description": "SUMD - Structured Unified Markdown Descriptor (project doc generator)",
        "default_subcommand": "scan",
        "default_args": [".", "--fix", "--workspace-mode", "--profile", "refactor"],
        "fallback_subcommand": "map",
        "fallback_args": ["."],
        "key_outputs": [
            "SUMD.md",
            "SUMR.md",
            "project/map.toon.yaml",
            "SUMR.json",
        ],
        "summary_files": ["SUMR.md", "SUMD.md", "project/map.toon.yaml"],
    },
    "code2llm": {
        "package": "code2llm",
        "binary": "code2llm",
        "description": "Static + dynamic code analyzer (TOON, call graphs, metrics)",
        "extra_pip_deps": ["psutil"],
        "default_subcommand": None,
        "default_args": [".", "-f", "toon", "-o", "code2llm_output"],
        "key_outputs": [
            "code2llm_output/map.toon.yaml",
            "code2llm_output/calls.yaml",
            "code2llm_output/analysis.toon.yaml",
        ],
        "summary_files": ["code2llm_output/map.toon.yaml"],
    },
    "code2docs": {
        "package": "code2docs",
        "binary": "code2docs",
        "description": "Auto-generate project documentation from source code",
        "default_subcommand": "generate",
        "default_args": ["."],
        "key_outputs": ["docs/index.md", "code2docs.yaml"],
        "summary_files": ["docs/index.md"],
    },
    "code2logic": {
        "package": "code2logic",
        "binary": "code2logic",
        "description": "Extract business logic and decision flow from code",
        "default_subcommand": None,
        "default_args": ["."],
        "key_outputs": [],
        "summary_files": [],
    },
    "code2schema": {
        "package": "code2schema",
        "binary": "code2schema",
        "description": "Infer JSON/SQL/OpenAPI schemas from code",
        "default_subcommand": None,
        "default_args": ["."],
        "key_outputs": [],
        "summary_files": [],
    },
    "redsl": {
        "package": "redsl",
        "binary": "redsl",
        "description": "reDSL - automated refactoring planner",
        "default_subcommand": "refactor",
        "default_args": [".", "-n", "10", "-f", "json", "--dry-run"],
        "key_outputs": [
            "redsl_refactor_plan.md",
            "redsl_refactor_plan.toon.yaml",
            "redsl_refactor_report.md",
        ],
        "summary_files": ["redsl_refactor_plan.md"],
    },
    "redup": {
        "package": "redup",
        "binary": "redup",
        "description": "Detect duplicated/redundant code blocks",
        "default_subcommand": "scan",
        "default_args": ["."],
        "key_outputs": ["redup_report.md", "redup_report.yaml"],
        "summary_files": ["redup_report.md"],
    },
    "regres": {
        "package": "regres",
        "binary": "regres",
        "description": "Regression test discovery and grouping",
        "default_subcommand": None,
        "default_args": ["."],
        "key_outputs": [],
        "summary_files": [],
    },
    "regix": {
        "package": "regix",
        "binary": "regix",
        "description": "Regex-based code grep + transform",
        "default_subcommand": None,
        "default_args": ["."],
        "key_outputs": [],
        "summary_files": [],
    },
    "vallm": {
        "package": "vallm",
        "binary": "vallm",
        "description": "Validate LLM outputs against schemas/rules",
        "default_subcommand": None,
        "default_args": ["."],
        "key_outputs": [],
        "summary_files": [],
    },
    "pyqual": {
        "package": "pyqual",
        "binary": "pyqual",
        "description": "Python quality assessor",
        "default_subcommand": "init",
        "default_args": ["--profile", "python"],
        "key_outputs": ["pyqual.yaml"],
        "summary_files": ["pyqual.yaml"],
    },
    "domd": {
        "package": "domd",
        "binary": "domd",
        "description": "Project Markdown documentation auditor",
        "default_subcommand": None,
        "default_args": ["."],
        "key_outputs": [],
        "summary_files": [],
    },
    "clickmd": {
        "package": "clickmd",
        "binary": "clickmd",
        "description": "Clickable interactive Markdown renderer",
        "default_subcommand": None,
        "default_args": ["."],
        "key_outputs": [],
        "summary_files": [],
    },
    "algitex": {
        "package": "algitex",
        "binary": "algitex",
        "description": "Algorithmic / textual analysis pipeline",
        "default_subcommand": None,
        "default_args": ["."],
        "key_outputs": [],
        "summary_files": [],
    },
}


# Cache of tools we've already attempted to install (avoid reinstall storm).
_TOOL_INSTALL_CACHE: dict[str, dict[str, Any]] = {}
# Maximum bytes per inlined output file returned to caller.
_MAX_INLINE_FILE_BYTES = 64 * 1024
# Maximum bytes of stdout/stderr returned.
_MAX_STREAM_BYTES = 32 * 1024


def _truncate_text(text: str, limit: int = _MAX_STREAM_BYTES) -> str:
    if not text:
        return ""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text
    truncated = encoded[:limit].decode("utf-8", errors="replace")
    return truncated + f"\n... [truncated, {len(encoded) - limit} more bytes]"


def _ensure_tool_installed(
    tool_name: str, package: str, binary: str, extra_pip_deps: list[str] | None = None
) -> dict[str, Any]:
    """Ensure a CLI tool binary is available, attempting `pip install <package>` if not."""
    cached = _TOOL_INSTALL_CACHE.get(tool_name)
    if cached and cached.get("available"):
        # Still install extra_pip_deps if requested and not yet done.
        if extra_pip_deps and not cached.get("extra_deps_installed"):
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-cache-dir"] + extra_pip_deps,
                capture_output=True, text=True, timeout=120,
            )
            cached["extra_deps_installed"] = True
        return cached

    binary_path = shutil.which(binary)
    if binary_path:
        if extra_pip_deps:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-cache-dir"] + extra_pip_deps,
                capture_output=True, text=True, timeout=120,
            )
        info = {"available": True, "binary_path": binary_path, "installed_now": False, "extra_deps_installed": True}
        _TOOL_INSTALL_CACHE[tool_name] = info
        return info

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-cache-dir", "--upgrade", package],
            capture_output=True,
            text=True,
            timeout=300,
        )
        installed_ok = proc.returncode == 0
        binary_path = shutil.which(binary)
        info: dict[str, Any] = {
            "available": bool(binary_path),
            "binary_path": binary_path,
            "installed_now": installed_ok,
            "pip_returncode": proc.returncode,
            "pip_stderr": _truncate_text(proc.stderr or "", 4 * 1024),
        }
    except subprocess.TimeoutExpired:
        info = {"available": False, "binary_path": None, "error": "pip install timeout"}
    except Exception as exc:
        info = {"available": False, "binary_path": None, "error": str(exc)}

    _TOOL_INSTALL_CACHE[tool_name] = info
    return info


def _inject_github_token(url: str) -> str:
    """Embed GITHUB_PAT / GH_TOKEN into a GitHub HTTPS URL for auth."""
    token = os.getenv("GITHUB_PAT") or os.getenv("GH_TOKEN") or ""
    if not token:
        return url
    if "github.com" not in url:
        return url
    # https://github.com/... → https://<token>@github.com/...
    return url.replace("https://", f"https://{token}@", 1)


def _git_clone_or_update(repo_url: str, target_dir: Path, ref: str = "HEAD") -> dict[str, Any]:
    """Clone repo_url into target_dir, or fetch+reset if it already exists."""
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"
    authed_url = _inject_github_token(repo_url)

    def _clone_ok(proc: subprocess.CompletedProcess) -> bool:
        """git may exit 0 but print fatal on stderr for private repos."""
        if proc.returncode != 0:
            return False
        stderr = (proc.stderr or "").lower()
        return "fatal:" not in stderr and "error:" not in stderr

    if not (target_dir / ".git").exists():
        if target_dir.exists() and any(target_dir.iterdir()):
            shutil.rmtree(target_dir, ignore_errors=True)
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", authed_url, str(target_dir)],
            capture_output=True, text=True, timeout=300, env=env,
        )
        ok = _clone_ok(proc)
        return {
            "action": "clone",
            "ok": ok,
            "returncode": proc.returncode,
            "stderr": _truncate_text(proc.stderr or "", 4 * 1024),
        }

    fetch = subprocess.run(
        ["git", "-C", str(target_dir), "fetch", "--depth", "1", "origin"],
        capture_output=True, text=True, timeout=180, env=env,
    )
    if fetch.returncode != 0:
        return {
            "action": "fetch",
            "ok": False,
            "returncode": fetch.returncode,
            "stderr": _truncate_text(fetch.stderr or "", 4 * 1024),
        }
    target_ref = ref if ref and ref != "HEAD" else "FETCH_HEAD"
    reset = subprocess.run(
        ["git", "-C", str(target_dir), "reset", "--hard", target_ref],
        capture_output=True, text=True, timeout=120, env=env,
    )
    return {
        "action": "fetch+reset",
        "ok": reset.returncode == 0,
        "returncode": reset.returncode,
        "stderr": _truncate_text(reset.stderr or "", 4 * 1024),
    }


def _derive_repo_id_from_url(repo_url: str) -> str:
    """Map https://github.com/owner/repo(.git) → 'owner/repo'."""
    cleaned = repo_url.strip()
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    cleaned = cleaned.rstrip("/")
    if "://" in cleaned:
        cleaned = cleaned.split("://", 1)[1]
    if "@" in cleaned and ":" in cleaned:
        # git@github.com:owner/repo style
        cleaned = cleaned.split(":", 1)[1]
    parts = [p for p in cleaned.split("/") if p]
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return cleaned or "anon/repo"


def _collect_output_files(repo_path: Path, paths: list[str]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rel in paths:
        candidate = (repo_path / rel).resolve()
        try:
            candidate.relative_to(repo_path.resolve())
        except ValueError:
            continue
        if str(candidate) in seen:
            continue
        seen.add(str(candidate))
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            data = candidate.read_bytes()
        except Exception as exc:
            collected.append({"path": rel, "error": str(exc)})
            continue
        if len(data) == 0:
            continue
        truncated = len(data) > _MAX_INLINE_FILE_BYTES
        text: str | None
        try:
            text = data[: _MAX_INLINE_FILE_BYTES].decode("utf-8")
        except UnicodeDecodeError:
            text = None
        collected.append({
            "path": rel,
            "size": len(data),
            "truncated": truncated,
            "content": text,
            "binary": text is None,
        })
    return collected


async def _run_tool_against_repo(request: ToolRunRequest) -> dict[str, Any]:
    tool_key = request.tool.strip().lower()
    spec = SUPPORTED_TOOLS.get(tool_key)
    if spec is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported tool '{request.tool}'. Known: {sorted(SUPPORTED_TOOLS)}",
        )

    repo_id = (request.repo_id or "").strip()
    if not repo_id and request.repo_url:
        repo_id = _derive_repo_id_from_url(request.repo_url)
    if not repo_id:
        raise HTTPException(status_code=400, detail="repo_id or repo_url is required")

    base = Path(request.base_path or str(skills_server.repo_base))
    repo_path = base / repo_id

    # 1. Materialize the repo locally.
    sync_info: dict[str, Any] = {"strategy": None, "ok": False}
    if request.repo_url:
        sync_info = _git_clone_or_update(request.repo_url, repo_path, request.ref)
        sync_info["strategy"] = "git_clone"
    elif request.use_git_proxy:
        try:
            proxy_sync = await skills_server._sync_from_git_proxy(repo_id, request.ref)
            sync_info = {"strategy": "git_proxy", "ok": True, **proxy_sync}
        except Exception as exc:
            sync_info = {"strategy": "git_proxy", "ok": False, "error": str(exc)}

    if not sync_info.get("ok") and not repo_path.exists():
        return {
            "tool": tool_key,
            "repo_id": repo_id,
            "repo_url": request.repo_url,
            "sync": sync_info,
            "install": None,
            "command": None,
            "returncode": None,
            "ok": False,
            "error": "Failed to materialize repository (no clone/sync succeeded).",
        }

    # 2. Ensure binary available.
    install_info = _ensure_tool_installed(
        tool_key, spec["package"], spec["binary"], spec.get("extra_pip_deps")
    )
    if request.auto_install is False and not install_info.get("available"):
        install_info = {**install_info, "skipped": True}
    if not install_info.get("available"):
        return {
            "tool": tool_key,
            "repo_id": repo_id,
            "repo_url": request.repo_url,
            "sync": sync_info,
            "install": install_info,
            "command": None,
            "returncode": None,
            "ok": False,
            "error": f"Tool '{tool_key}' is not installed and auto_install failed.",
        }

    # 3. Build command.
    binary_path = install_info["binary_path"] or spec["binary"]
    cmd: list[str] = [binary_path]
    if request.subcommand:
        cmd.append(request.subcommand)
    elif spec.get("default_subcommand"):
        cmd.append(spec["default_subcommand"])
    if request.args:
        cmd.extend(str(a) for a in request.args)
    else:
        cmd.extend(spec.get("default_args", []))

    env = os.environ.copy()
    for key in ("OPENROUTER_API_KEY", "LLM_MODEL", "OPENAI_API_KEY", "GITHUB_TOKEN"):
        val = os.getenv(key)
        if val:
            env[key] = val
    env.update({k: str(v) for k, v in (request.env or {}).items()})

    loop = asyncio.get_event_loop()

    def _run() -> dict[str, Any]:
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=request.timeout,
                env=env,
            )
            return {
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": _truncate_text(proc.stdout or ""),
                "stderr": _truncate_text(proc.stderr or ""),
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "ok": False,
                "returncode": None,
                "stdout": _truncate_text(exc.stdout or "") if isinstance(exc.stdout, str) else "",
                "stderr": f"timeout after {request.timeout}s",
            }
        except FileNotFoundError as exc:
            return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc)}

    run_result = await loop.run_in_executor(None, _run)

    # 3b. Fallback: if main command failed and spec defines fallback_subcommand,
    # run fallback (e.g. sumd map), touch a project marker, then retry main command.
    if not run_result.get("ok") and spec.get("fallback_subcommand"):
        fb_cmd = [binary_path, spec["fallback_subcommand"]] + [str(a) for a in spec.get("fallback_args", [])]

        def _run_fallback(c: list[str] = fb_cmd) -> dict[str, Any]:
            try:
                p = subprocess.run(c, cwd=str(repo_path), capture_output=True, text=True, timeout=request.timeout, env=env)
                return {"ok": p.returncode == 0, "stdout": p.stdout or "", "stderr": p.stderr or ""}
            except Exception as exc:
                return {"ok": False, "stdout": "", "stderr": str(exc)}

        fb_result = await loop.run_in_executor(None, _run_fallback)
        # Touch key_outputs[0] as project marker so scan can find it.
        key_outputs = spec.get("key_outputs", [])
        if key_outputs:
            marker = repo_path / key_outputs[0]
            if not marker.exists():
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.touch()
        # Retry main command now that the marker exists.
        retry_result = await loop.run_in_executor(None, _run)
        combined_fb_stdout = (fb_result.get("stdout") or "").rstrip("\n") + "\n\n" + (retry_result.get("stdout") or "")
        run_result = {**retry_result, "stdout": combined_fb_stdout}

    post_stdout_parts: list[str] = []
    if run_result.get("ok") and spec.get("post_commands"):
        for post_args in spec["post_commands"]:
            post_cmd = [binary_path] + [str(a) for a in post_args]

            def _run_post(c: list[str] = post_cmd) -> dict[str, Any]:
                try:
                    p = subprocess.run(
                        c,
                        cwd=str(repo_path),
                        capture_output=True,
                        text=True,
                        timeout=request.timeout,
                        env=env,
                    )
                    return {"ok": p.returncode == 0, "stdout": p.stdout or "", "stderr": p.stderr or ""}
                except Exception as exc:
                    return {"ok": False, "stdout": "", "stderr": str(exc)}

            post_result = await loop.run_in_executor(None, _run_post)
            if post_result.get("stdout"):
                post_stdout_parts.append(post_result["stdout"])

    combined_stdout = run_result.get("stdout", "")
    if post_stdout_parts:
        combined_stdout = combined_stdout.rstrip("\n") + "\n\n" + "\n".join(post_stdout_parts)

    # 4. Collect well-known output files.
    output_files = _collect_output_files(repo_path, list(spec.get("key_outputs", [])))
    summary_files = _collect_output_files(repo_path, list(spec.get("summary_files", [])))

    return {
        "tool": tool_key,
        "tool_description": spec.get("description"),
        "repo_id": repo_id,
        "repo_url": request.repo_url,
        "repo_path": str(repo_path),
        "sync": sync_info,
        "install": install_info,
        "command": cmd,
        "returncode": run_result.get("returncode"),
        "ok": bool(run_result.get("ok")),
        "stdout": combined_stdout,
        "stderr": run_result.get("stderr", ""),
        "output_files": output_files,
        "summary_files": summary_files,
    }


def _parse_tool_result(result: list[TextContent]) -> Any:
    if not result:
        return {}
    text = result[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def _run_redsl_refactor(project_path: Path, max_actions: int, dry_run: bool) -> dict[str, Any]:
    """Uruchamia redsl refactor jako subprocess i parsuje wynik."""
    cmd = [
        sys.executable, "-m", "redsl", "refactor",
        str(project_path),
        "-n", str(max_actions),
        "-f", "json",
    ]
    if dry_run:
        cmd.append("--dry-run")

    env = os.environ.copy()
    # Przekazuj klucze LLM jeśli dostępne
    for key in ("OPENROUTER_API_KEY", "LLM_MODEL", "OPENAI_API_KEY"):
        val = os.getenv(key)
        if val:
            env[key] = val

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        # Szukaj bloku JSON w stdout (redsl może poprzedzać go tekstem)
        payload: dict[str, Any] = {}
        for line in stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("{") or stripped.startswith("redsl_plan:"):
                # Spróbuj parsować JSON
                try:
                    payload = json.loads(stripped)
                    break
                except json.JSONDecodeError:
                    pass

        # Jeśli nie ma JSON, spróbuj całego stdout
        if not payload:
            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError:
                payload = {"raw_output": stdout}

        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "payload": payload,
            "stderr": stderr[:2000] if stderr else None,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "redsl timeout after 120s"}
    except FileNotFoundError:
        return {"success": False, "error": "redsl not found - not installed in container"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


skills_server = MCPSkillsServer()
app = FastAPI(title="mcp-skills", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "mcp-skills",
        "repo_base": str(skills_server.repo_base),
        "git_proxy_url": skills_server.git_proxy_url,
    }


@app.post("/sync")
async def sync_repo(request: SyncRepoRequest) -> dict[str, Any]:
    try:
        return await skills_server._sync_from_git_proxy(request.repo_id, request.ref)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/analyze/structure")
async def analyze_code_structure(request: AnalyzeStructureRequest) -> Any:
    try:
        result = await skills_server._analyze_code_structure(
            request.model_dump(exclude_none=True)
        )
        return _parse_tool_result(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/analyze/metrics")
async def compute_metrics(request: RepoMetricsRequest) -> Any:
    try:
        result = await skills_server._compute_metrics_for_repo(
            request.model_dump(exclude_none=True)
        )
        return _parse_tool_result(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/analyze/patterns")
async def detect_patterns(request: PatternDetectionRequest) -> Any:
    try:
        result = await skills_server._detect_code_patterns(
            request.model_dump(exclude_none=True)
        )
        return _parse_tool_result(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/refactor/recommend")
async def recommend_refactoring(request: RecommendRefactoringRequest) -> Any:
    try:
        result = await skills_server._recommend_refactoring(
            request.model_dump(exclude_none=True)
        )
        return _parse_tool_result(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/refactor/redsl")
async def redsl_refactor(request: RedslRefactorRequest) -> Any:
    """Uruchom redsl refactor na zsynchronizowanym repo z git-proxy.

    Kroki:
    1. Synchronizuj repo z git-proxy do katalogu skills cache
    2. Uruchom `redsl refactor --dry-run` (lub z --execute jeśli execute=True)
    3. Sparsuj i zwróć wynik z metrykami, decyzjami i rekomendacjami
    """
    base = Path(request.base_path or str(skills_server.repo_base))
    repo_path = base / request.repo_id

    # 1. Synchronizacja z git-proxy
    try:
        sync_result = await skills_server._sync_from_git_proxy(request.repo_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"git-proxy sync failed: {exc}") from exc

    # 2. Uruchom redsl w osobnym wątku (subprocess blokujący)
    dry_run = not request.execute
    loop = asyncio.get_event_loop()
    redsl_result = await loop.run_in_executor(
        None,
        lambda: _run_redsl_refactor(repo_path, request.max_actions, dry_run),
    )

    # 3. Sparsuj i znormalizuj wynik redsl
    payload = redsl_result.get("payload", {})
    # Obsługuj format z kluczem "analysis" (dry_run json) lub starszy format
    analysis = payload.get("analysis", payload.get("redsl_plan", {}).get("analysis", {}))
    decisions = payload.get("decisions", [])
    summary = payload.get("summary", payload.get("redsl_plan", {}).get("summary", {}))

    # Znormalizuj rekomendacje do formatu zgodnego z /refactor/recommend
    recommendations = []
    for decision in decisions[:20]:
        action = decision.get("action_type") or decision.get("action", "review")
        target = decision.get("file") or decision.get("target", "general")
        reason = decision.get("reason") or decision.get("description", "")
        priority_score = float(decision.get("priority", 0.5))
        priority = "high" if priority_score >= 0.8 else ("medium" if priority_score >= 0.5 else "low")
        recommendations.append({
            "type": action,
            "priority": priority,
            "target": target,
            "reason": reason,
            "suggested_action": action,
            "redsl_score": priority_score,
        })

    metrics = {
        "repo_id": request.repo_id,
        "file_count": analysis.get("total_files", 0),
        "total_lines": analysis.get("total_lines", 0),
        "avg_complexity": analysis.get("avg_complexity", 0.0),
        "critical_count": analysis.get("critical_count", 0),
        "alerts_count": analysis.get("alerts_count", 0),
        "total_functions": 0,
        "total_classes": 0,
        "largest_files": [],
    }

    return {
        "repo_id": request.repo_id,
        "engine": "redsl",
        "redsl_version": redsl_result.get("returncode"),
        "dry_run": dry_run,
        "sync": sync_result,
        "metrics": metrics,
        "recommendations": {
            "repo_id": request.repo_id,
            "goal": "maintainability",
            "summary": {
                "total_recommendations": len(recommendations),
                "high_priority": sum(1 for r in recommendations if r.get("priority") == "high"),
                "medium_priority": sum(1 for r in recommendations if r.get("priority") == "medium"),
            },
            "recommendations": recommendations,
            "metrics_summary": {
                "total_files": metrics["file_count"],
                "total_lines": metrics["total_lines"],
                "avg_lines_per_file": 0,
            },
        },
        "redsl_raw": {
            "decisions_count": len(decisions),
            "summary": summary,
            "stderr": redsl_result.get("stderr"),
            "success": redsl_result.get("success"),
        },
    }


@app.get("/tools/list")
async def list_tools_endpoint() -> dict[str, Any]:
    """List supported semcod CLI tools and their default invocation."""
    return {
        "count": len(SUPPORTED_TOOLS),
        "tools": [
            {
                "tool": name,
                "package": spec["package"],
                "binary": spec["binary"],
                "description": spec.get("description"),
                "default_subcommand": spec.get("default_subcommand"),
                "default_args": spec.get("default_args", []),
                "key_outputs": spec.get("key_outputs", []),
            }
            for name, spec in SUPPORTED_TOOLS.items()
        ],
    }


@app.post("/tools/run")
async def run_tool_endpoint(request: ToolRunRequest) -> dict[str, Any]:
    """Run a semcod CLI tool against a repo (clones if missing, installs if missing)."""
    return await _run_tool_against_repo(request)


def main() -> None:
    transport = os.getenv("MCP_SKILLS_TRANSPORT", "http").strip().lower()
    if transport == "stdio":
        asyncio.run(skills_server.run())
        return

    host = os.getenv("MCP_SKILLS_HTTP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_SKILLS_HTTP_PORT", "8080"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
