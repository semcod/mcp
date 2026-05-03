#!/usr/bin/env python3
"""
Autonomous Refactoring Agent using git2mcp proxy workflow.
- Sync repo via MCP Git Proxy
- Cache full repo for skills-side analysis
- Generate refactoring plan with lite LLM
- Commit changes through git2mcp (no shell file edits)
- Run tests before optional push
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import os
import tarfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

from git2mcp.client import Git2MCPClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    repo_id: str
    metrics: dict[str, Any] = field(default_factory=dict)
    patterns: dict[str, Any] = field(default_factory=dict)
    recommendations: dict[str, Any] = field(default_factory=dict)


class CachedCodeAnalyzer:
    def __init__(self, cache_base: str = "/skills-cache"):
        self.cache_base = Path(cache_base)
        self.cache_base.mkdir(parents=True, exist_ok=True)

    def _repo_path(self, repo_id: str) -> Path:
        return self.cache_base / repo_id

    def import_package(self, repo_id: str, archive_b64: str) -> Path:
        target = self._repo_path(repo_id)
        if target.exists():
            for path in sorted(target.glob("**/*"), key=lambda p: len(p.parts), reverse=True):
                if path.is_file():
                    path.unlink(missing_ok=True)
                elif path.is_dir() and path != target:
                    path.rmdir()
        target.mkdir(parents=True, exist_ok=True)

        archive = base64.b64decode(archive_b64)
        with tarfile.open(fileobj=BytesIO(archive), mode="r:gz") as tar:
            tar.extractall(target)
        return target

    def compute_metrics(self, repo_id: str, extensions: list[str] | None = None) -> dict[str, Any]:
        if extensions is None:
            extensions = [".py", ".js", ".ts"]

        repo = self._repo_path(repo_id)
        if not repo.exists():
            return {"error": f"Repo cache missing at {repo}"}

        files = []
        total_lines = 0
        total_imports = 0
        total_functions = 0
        total_classes = 0

        for ext in extensions:
            for file_path in repo.rglob(f"*{ext}"):
                if "/.git/" in str(file_path):
                    continue
                try:
                    text = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                lines = text.splitlines()
                imports = sum(1 for line in lines if line.strip().startswith("import ") or line.strip().startswith("from "))
                functions = sum(1 for line in lines if line.strip().startswith("def "))
                classes = sum(1 for line in lines if line.strip().startswith("class "))

                files.append(
                    {
                        "path": str(file_path.relative_to(repo)),
                        "lines": len(lines),
                        "imports": imports,
                        "functions": functions,
                        "classes": classes,
                    }
                )
                total_lines += len(lines)
                total_imports += imports
                total_functions += functions
                total_classes += classes

        files.sort(key=lambda item: item["lines"], reverse=True)
        count = len(files)
        return {
            "repo_id": repo_id,
            "file_count": count,
            "total_lines": total_lines,
            "total_imports": total_imports,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "avg_lines_per_file": total_lines // count if count else 0,
            "largest_files": files[:10],
        }

    def detect_patterns(self, repo_id: str) -> dict[str, Any]:
        repo = self._repo_path(repo_id)
        if not repo.exists():
            return {"error": f"Repo cache missing at {repo}"}

        large_files = []
        high_complexity = []
        import_map: dict[str, int] = {}

        for file_path in repo.rglob("*.py"):
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = text.splitlines()
            rel = str(file_path.relative_to(repo))

            if len(lines) > 500:
                large_files.append({"path": rel, "lines": len(lines)})
            if len(lines) > 300:
                high_complexity.append({"path": rel, "indicator": f"{len(lines)} lines"})

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    import_map[stripped] = import_map.get(stripped, 0) + 1

        common_imports = sorted(import_map.items(), key=lambda item: item[1], reverse=True)[:10]
        return {
            "repo_id": repo_id,
            "patterns_detected": {
                "large_files_count": len(large_files),
                "high_complexity_count": len(high_complexity),
                "large_files": large_files[:5],
                "high_complexity": high_complexity[:5],
                "common_imports": common_imports,
            },
        }

    def recommend_refactoring(self, repo_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
        recommendations = []
        for file_info in metrics.get("largest_files", [])[:3]:
            if file_info["lines"] > 500:
                recommendations.append(
                    {
                        "type": "split_file",
                        "priority": "high",
                        "target": file_info["path"],
                        "reason": f"File has {file_info['lines']} lines",
                        "suggested_action": "Split into smaller cohesive modules",
                    }
                )

        if metrics.get("total_imports", 0) > metrics.get("total_lines", 0) * 0.1:
            recommendations.append(
                {
                    "type": "optimize_imports",
                    "priority": "medium",
                    "target": "imports",
                    "reason": "High import-to-line ratio",
                    "suggested_action": "Use lazy imports in non-critical paths",
                }
            )

        return {
            "repo_id": repo_id,
            "summary": {
                "total_recommendations": len(recommendations),
                "high_priority": sum(1 for r in recommendations if r["priority"] == "high"),
                "medium_priority": sum(1 for r in recommendations if r["priority"] == "medium"),
            },
            "recommendations": recommendations,
        }


class Git2MCPRefactoringAgent:
    def __init__(self, cache_base: str = "/skills-cache"):
        self.git_proxy_url = os.getenv("GIT_PROXY_URL", "http://mcp-git-proxy:8080")
        self.llm_provider = os.getenv("LLM_PROVIDER", "openrouter-lite")
        self.llm_model = os.getenv("LLM_MODEL", "openrouter/x-ai/grok-code-fast-1")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")

        self.git_client = Git2MCPClient(self.git_proxy_url)
        self.analyzer = CachedCodeAnalyzer(cache_base=cache_base)

    async def sync_and_cache_repo(self, repo_id: str, repo_url: str | None, source_path: str | None, branch: str) -> dict[str, Any]:
        sync_result = await self.git_client.sync_repo(
            repo_id=repo_id,
            repo_url=repo_url,
            source_path=source_path,
            branch=branch,
        )
        package = await self.git_client.export_package(repo_id=repo_id)
        cache_path = self.analyzer.import_package(repo_id, package["archive_b64"])
        return {
            "sync": sync_result,
            "package_ref": package.get("ref"),
            "cache_path": str(cache_path),
        }

    async def analyze(self, repo_id: str) -> AnalysisResult:
        metrics = self.analyzer.compute_metrics(repo_id)
        patterns = self.analyzer.detect_patterns(repo_id)
        recommendations = self.analyzer.recommend_refactoring(repo_id, metrics)
        return AnalysisResult(repo_id=repo_id, metrics=metrics, patterns=patterns, recommendations=recommendations)

    async def generate_plan(self, analysis: AnalysisResult) -> dict[str, Any]:
        if self.llm_provider in {"openrouter", "openrouter-lite"} and self.openrouter_api_key:
            try:
                from openai import OpenAI

                client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.openrouter_api_key)
                prompt = (
                    "Przygotuj JSON planu refaktoryzacji. "
                    f"Repo: {analysis.repo_id}. "
                    f"Metryki: {json.dumps(analysis.metrics, ensure_ascii=False)}. "
                    f"Wzorce: {json.dumps(analysis.patterns, ensure_ascii=False)}."
                )
                completion = client.chat.completions.create(
                    model=self.llm_model,
                    messages=[
                        {"role": "system", "content": "Zwracaj wyłącznie poprawny JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                )
                content = completion.choices[0].message.content
                return json.loads(content)
            except Exception as exc:
                logger.warning("OpenRouter call failed, fallback to mock plan: %s", exc)

        recs = analysis.recommendations.get("recommendations", [])
        return {
            "summary": f"Plan refaktoryzacji dla {analysis.repo_id}",
            "priority_actions": [
                {
                    "priority": i + 1,
                    "action": rec.get("suggested_action", "Review module"),
                    "files_affected": [rec.get("target", "unknown")],
                    "estimated_effort": "2-4h",
                }
                for i, rec in enumerate(recs[:3])
            ],
            "architectural_changes": [
                "Utrzymuj mniejsze moduły",
                "Wydziel odpowiedzialności do warstw",
            ],
            "risks": ["Regresje funkcjonalne", "Niespójny styl kodu"],
            "testing_strategy": "Uruchom py_compile lub testy projektu po commitach.",
        }

    def build_commit_changes(self, plan: dict[str, Any]) -> list[dict[str, str]]:
        plan_json = json.dumps(plan, indent=2, ensure_ascii=False)
        summary_md = "# MCP Refactoring Plan\n\n" + plan.get("summary", "No summary") + "\n"
        return [
            {"path": ".mcp/refactor-plan.json", "content": plan_json, "mode": "update"},
            {"path": ".mcp/refactor-summary.md", "content": summary_md, "mode": "update"},
        ]

    async def execute(
        self,
        repo_id: str,
        repo_url: str | None,
        source_path: str | None,
        branch: str,
        execute_commit: bool,
        push_after_tests: bool,
        test_command: str,
    ) -> dict[str, Any]:
        logger.info("Syncing repo via mcp-git-proxy")
        sync_info = await self.sync_and_cache_repo(repo_id, repo_url, source_path, branch)

        logger.info("Analyzing cached repository")
        analysis = await self.analyze(repo_id)

        logger.info("Generating refactoring plan")
        plan = await self.generate_plan(analysis)

        result: dict[str, Any] = {
            "repository": repo_id,
            "sync": sync_info,
            "analysis": {
                "metrics": analysis.metrics,
                "patterns_detected": analysis.patterns,
                "recommendations": analysis.recommendations,
            },
            "refactoring_plan": plan,
            "status": "analysis_complete",
            "dry_run": not execute_commit,
        }

        if execute_commit:
            logger.info("Creating commit through git2mcp")
            changes = self.build_commit_changes(plan)
            commit_result = await self.git_client.commit_changes(
                repo_id=repo_id,
                message="chore(mcp): add autonomous refactoring plan artifacts",
                changes=changes,
            )
            tests_result = await self.git_client.run_tests(repo_id, test_command)
            result["execution"] = {
                "commit": commit_result,
                "tests": tests_result,
                "pushed": False,
            }
            if push_after_tests and tests_result.get("ok"):
                push_result = await self.git_client.push(repo_id=repo_id, branch=branch)
                result["execution"]["push"] = push_result
                result["execution"]["pushed"] = True

        return result


async def main() -> None:
    parser = argparse.ArgumentParser(description="git2mcp autonomous refactoring agent")
    parser.add_argument("--repo", required=True, help="Logical repo id, e.g. team/repo-a")
    parser.add_argument("--repo-url", default=None, help="Remote git URL for initial sync")
    parser.add_argument("--source-path", default=None, help="Path mounted in git-proxy container, e.g. /host-repos/test/sample-project")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--execute", action="store_true", help="Create commit via git2mcp")
    parser.add_argument("--push", action="store_true", help="Push commit after passing tests")
    parser.add_argument("--test-command", default="python -m compileall -q .")
    parser.add_argument("--cache-base", default="/skills-cache")

    args = parser.parse_args()
    agent = Git2MCPRefactoringAgent(cache_base=args.cache_base)

    result = await agent.execute(
        repo_id=args.repo,
        repo_url=args.repo_url,
        source_path=args.source_path,
        branch=args.branch,
        execute_commit=args.execute,
        push_after_tests=args.push,
        test_command=args.test_command,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{args.repo.replace('/', '_')}_analysis.json"
    output_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved result to %s", output_file)


if __name__ == "__main__":
    asyncio.run(main())
