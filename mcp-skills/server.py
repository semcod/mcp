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

from code_analysis import (
    build_maintainability_recommendations,
    compute_repo_file_metrics,
    detect_repo_patterns,
    merge_recommendations,
    recommendations_payload,
)
from http_models import (
    AnalyzeStructureRequest,
    PatternDetectionRequest,
    RecommendRefactoringRequest,
    RedslRefactorRequest,
    RepoMetricsRequest,
    SyncRepoRequest,
    ToolRunRequest,
)
from mcp_parse import parse_tool_result
from redsl_runner import run_redsl_refactor
from tool_run import (
    TOOL_INSTALL_CACHE,
    collect_output_files,
    derive_repo_id_from_url,
    run_tool_against_repo,
)
from tools_registry import SUPPORTED_TOOLS

from mcp.server import Server
from mcp.server import NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.types import (
    ListToolsResult,
    TextContent,
    Tool,
    INTERNAL_ERROR,
)

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

        metrics = compute_repo_file_metrics(repo_path, extensions)
        metrics["repo_id"] = repo_id
        return [TextContent(type="text", text=json.dumps(metrics, indent=2))]

    async def _detect_code_patterns(self, arguments: dict) -> list:
        """Wykrywanie wzorców kodu i antywzorców"""
        repo_id = arguments.get("repo_id")
        base_path = arguments.get("base_path", str(self.repo_base))

        repo_path = Path(base_path) / repo_id

        if not repo_path.exists():
            return [TextContent(type="text", text=json.dumps({
                "error": f"Repo '{repo_id}' not found"
            }))]

        result = {
            "repo_id": repo_id,
            "patterns_detected": detect_repo_patterns(repo_path),
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

        recommendations = build_maintainability_recommendations(
            metrics,
            repo_id=repo_id,
            goal=goal,
        )

        result = recommendations_payload(
            repo_id,
            metrics,
            recommendations,
            goal=goal,
        )
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
        return parse_tool_result(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/analyze/metrics")
async def compute_metrics(request: RepoMetricsRequest) -> Any:
    try:
        result = await skills_server._compute_metrics_for_repo(
            request.model_dump(exclude_none=True)
        )
        return parse_tool_result(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/analyze/patterns")
async def detect_patterns(request: PatternDetectionRequest) -> Any:
    try:
        result = await skills_server._detect_code_patterns(
            request.model_dump(exclude_none=True)
        )
        return parse_tool_result(result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/refactor/recommend")
async def recommend_refactoring(request: RecommendRefactoringRequest) -> Any:
    try:
        result = await skills_server._recommend_refactoring(
            request.model_dump(exclude_none=True)
        )
        return parse_tool_result(result)
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
        lambda: run_redsl_refactor(repo_path, request.max_actions, dry_run),
    )

    # 3. Sparsuj i znormalizuj wynik redsl
    payload = redsl_result.get("payload", {})
    # Obsługuj format z kluczem "analysis" (dry_run json) lub starszy format
    analysis = payload.get("analysis", payload.get("redsl_plan", {}).get("analysis", {}))
    decisions = payload.get("decisions", [])
    summary = payload.get("summary", payload.get("redsl_plan", {}).get("summary", {}))

    # Znormalizuj rekomendacje redsl (mogą mieć target=general)
    redsl_recommendations = []
    for decision in decisions[:20]:
        action = decision.get("action_type") or decision.get("action", "review")
        target = decision.get("file") or decision.get("target", "general")
        reason = decision.get("reason") or decision.get("description", "")
        priority_score = float(decision.get("priority", 0.5))
        priority = "high" if priority_score >= 0.8 else ("medium" if priority_score >= 0.5 else "low")
        redsl_recommendations.append({
            "type": action,
            "priority": priority,
            "target": target,
            "reason": reason,
            "suggested_action": action,
            "redsl_score": priority_score,
        })

    file_metrics = compute_repo_file_metrics(repo_path)
    metrics = {
        "repo_id": request.repo_id,
        "file_count": file_metrics.get("file_count", analysis.get("total_files", 0)),
        "total_lines": file_metrics.get("total_lines", analysis.get("total_lines", 0)),
        "avg_complexity": analysis.get("avg_complexity", 0.0),
        "critical_count": analysis.get("critical_count", 0),
        "alerts_count": analysis.get("alerts_count", 0),
        "total_functions": file_metrics.get("total_functions", 0),
        "total_classes": file_metrics.get("total_classes", 0),
        "avg_lines_per_file": file_metrics.get("avg_lines_per_file", 0),
        "largest_files": file_metrics.get("largest_files", []),
    }

    supplemental = build_maintainability_recommendations(
        metrics,
        repo_id=request.repo_id,
        goal="maintainability",
    )
    recommendations = merge_recommendations(redsl_recommendations, supplemental)
    rec_payload = recommendations_payload(
        request.repo_id,
        metrics,
        recommendations,
        goal="maintainability",
    )

    return {
        "repo_id": request.repo_id,
        "engine": "redsl",
        "redsl_version": redsl_result.get("returncode"),
        "dry_run": dry_run,
        "sync": sync_result,
        "metrics": metrics,
        "recommendations": rec_payload,
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
    return await run_tool_against_repo(request, skills_server)


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


# Backward compatibility for tests and dynamic imports
_parse_tool_result = parse_tool_result
_run_redsl_refactor = run_redsl_refactor
_TOOL_INSTALL_CACHE = TOOL_INSTALL_CACHE
_derive_repo_id_from_url = derive_repo_id_from_url
_collect_output_files = collect_output_files


async def _run_tool_against_repo(request: ToolRunRequest) -> dict[str, Any]:
    return await run_tool_against_repo(request, skills_server)
