#!/usr/bin/env python3
"""
Autonomiczny Agent Refaktoryzacji - Wersja Standalone
Działa bez zewnętrznych MCP serwerów - implementuje analizę lokalnie.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Wynik analizy repozytorium"""
    repo_id: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    patterns: Dict[str, Any] = field(default_factory=dict)
    recommendations: Dict[str, Any] = field(default_factory=dict)


class LocalCodeAnalyzer:
    """Lokalny analizator kodu - implementacja MCP Skills lokalnie"""

    def __init__(self, repo_base: str = "/repos"):
        self.repo_base = Path(repo_base)

    def analyze_code_structure(self, repo_id: str, paths: List[str]) -> Dict[str, Any]:
        """Analiza struktury kodu dla podanych ścieżek"""
        repo_path = self.repo_base / repo_id
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
                    "imports": imports[:10],
                    "preview": lines[:10],
                })
            except Exception as e:
                results.append({
                    "path": rel_path,
                    "exists": True,
                    "error": str(e)
                })

        return {
            "repo_id": repo_id,
            "path_analysis": results
        }

    def compute_metrics_for_repo(self, repo_id: str, extensions: List[str] = None) -> Dict[str, Any]:
        """Obliczanie metryk dla całego repozytorium"""
        if extensions is None:
            extensions = [".py"]

        repo_path = self.repo_base / repo_id

        if not repo_path.exists():
            return {"error": f"Repo '{repo_id}' does not exist at {repo_path}"}

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

        file_metrics.sort(key=lambda x: x["lines"], reverse=True)

        return {
            "repo_id": repo_id,
            "file_count": total_files,
            "total_lines": total_lines,
            "total_imports": total_imports,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "avg_lines_per_file": total_lines // total_files if total_files > 0 else 0,
            "largest_files": file_metrics[:10]
        }

    def detect_code_patterns(self, repo_id: str, pattern_types: List[str] = None) -> Dict[str, Any]:
        """Wykrywanie wzorców kodu i antywzorców"""
        if pattern_types is None:
            pattern_types = ["complexity", "imports"]

        repo_path = self.repo_base / repo_id

        if not repo_path.exists():
            return {"error": f"Repo '{repo_id}' not found"}

        patterns = {
            "large_files": [],
            "high_complexity": [],
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

                # Wykrywanie złożoności
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

        return {
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

    def recommend_refactoring(self, repo_id: str, goal: str = "maintainability") -> Dict[str, Any]:
        """Generowanie rekomendacji refaktoryzacji"""
        metrics = self.compute_metrics_for_repo(repo_id)
        patterns = self.detect_code_patterns(repo_id)

        recommendations = []

        if goal in ["maintainability", "modularity"]:
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

            if metrics.get("total_classes", 0) > 50 and metrics.get("file_count", 0) < 20:
                recommendations.append({
                    "type": "organize_classes",
                    "priority": "medium",
                    "target": "project_structure",
                    "reason": "High class density - consider organizing into packages",
                    "suggested_action": "Group related classes into subpackages"
                })

        if goal in ["performance", "maintainability"]:
            if metrics.get("total_imports", 0) > metrics.get("total_lines", 0) * 0.1:
                recommendations.append({
                    "type": "optimize_imports",
                    "priority": "low",
                    "target": "imports",
                    "reason": "High import ratio - consider lazy imports or restructuring",
                    "suggested_action": "Use lazy imports in non-critical paths"
                })

        avg_lines = metrics.get("avg_lines_per_file", 0)
        if avg_lines > 300:
            recommendations.append({
                "type": "reduce_file_size",
                "priority": "medium",
                "target": "general",
                "reason": f"Average file size ({avg_lines} lines) is above recommended 300 lines",
                "suggested_action": "Follow single responsibility principle per file"
            })

        return {
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


class RefactoringAgent:
    """Autonomiczny Agent Refaktoryzacji - Standalone"""

    def __init__(self, repo_base: str = "/repos"):
        self.analyzer = LocalCodeAnalyzer(repo_base)
        self.llm_provider = os.getenv("LLM_PROVIDER", "mock")

    async def analyze_repository(self, repo_id: str, target_paths: Optional[List[str]] = None) -> AnalysisResult:
        """Pełna analiza repozytorium"""
        logger.info(f"Starting analysis of repo: {repo_id}")

        logger.info("Computing repository metrics...")
        metrics = self.analyzer.compute_metrics_for_repo(repo_id, [".py", ".js", ".ts"])

        logger.info("Detecting code patterns...")
        patterns = self.analyzer.detect_code_patterns(repo_id, ["complexity", "imports"])

        logger.info("Generating refactoring recommendations...")
        recommendations = self.analyzer.recommend_refactoring(repo_id, "maintainability")

        structure = None
        if target_paths:
            logger.info(f"Analyzing specific paths: {target_paths}")
            structure = self.analyzer.analyze_code_structure(repo_id, target_paths)
            metrics["structure_analysis"] = structure

        return AnalysisResult(
            repo_id=repo_id,
            metrics=metrics,
            patterns=patterns,
            recommendations=recommendations
        )

    def generate_refactoring_plan(self, analysis: AnalysisResult) -> str:
        """Generuje plan refaktoryzacji używając LLM lub mock"""
        prompt = self._build_refactoring_prompt(analysis)

        if self.llm_provider == "openai" and os.getenv("OPENAI_API_KEY"):
            return self._call_openai_sync(prompt)
        else:
            return self._mock_llm_response(analysis)

    def _build_refactoring_prompt(self, analysis: AnalysisResult) -> str:
        """Buduje prompt dla LLM"""
        metrics = analysis.metrics
        patterns = analysis.patterns
        recs = analysis.recommendations

        prompt = f"""Jesteś ekspertem w refaktoryzacji kodu. Na podstawie poniższej analizy repozytorium, zaproponuj szczegółowy plan refaktoryzacji.

## Analiza Repozytorium: {analysis.repo_id}

### Metryki:
- Liczba plików: {metrics.get('file_count', 'N/A')}
- Całkowita liczba linii: {metrics.get('total_lines', 'N/A')}
- Średnia liczba linii na plik: {metrics.get('avg_lines_per_file', 'N/A')}
- Całkowita liczba importów: {metrics.get('total_imports', 'N/A')}
- Całkowita liczba funkcji: {metrics.get('total_functions', 'N/A')}
- Całkowita liczba klas: {metrics.get('total_classes', 'N/A')}

### Wykryte Problemy:
- Duże pliki (>500 linii): {patterns.get('patterns_detected', {}).get('large_files_count', 0)}
- Wysoka złożoność: {patterns.get('patterns_detected', {}).get('high_complexity_count', 0)}

### Rekomendacje Systemowe:
"""

        for rec in recs.get('recommendations', []):
            prompt += f"\n- [{rec.get('priority', 'unknown').upper()}] {rec.get('type')}: {rec.get('reason')}"
            prompt += f"\n  Sugestia: {rec.get('suggested_action')}"

        prompt += """

## Zadanie:
Zaproponuj szczegółowy plan refaktoryzacji z konkretnymi krokami:

1. PRIORYTETYZACJA: Które zmiany wykonać najpierw i dlaczego?
2. KONKRETNE KROKI: Jakie dokładne zmiany wprowadzić w kodzie?
3. ARCHITEKTURA: Jakie wzorce projektowe zastosować?
4. RYZYKA: Na co uważać podczas refaktoryzacji?

Odpowiedź w formacie JSON."""

        return prompt

    def _call_openai_sync(self, prompt: str) -> str:
        """Wywołanie OpenAI API (synchronicznie)"""
        try:
            import openai
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "Jesteś ekspertem w refaktoryzacji kodu."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return self._mock_llm_response_from_prompt(prompt)

    def _mock_llm_response(self, analysis: AnalysisResult) -> str:
        """Generuje mock odpowiedź LLM"""
        recs = analysis.recommendations.get('recommendations', [])

        priority_actions = []
        for i, rec in enumerate(recs[:3], 1):
            priority_actions.append({
                "priority": i,
                "action": rec.get('suggested_action'),
                "files_affected": [rec.get('target')] if rec.get('target') != 'general' else ['multiple files'],
                "estimated_effort": "2-4 hours"
            })

        result = {
            "summary": f"Repozytorium {analysis.repo_id} wymaga refaktoryzacji w celu poprawy utrzymywalności.",
            "priority_actions": priority_actions,
            "architectural_changes": [
                "Wprowadź podział na warstwy (controllers, services, repositories)",
                "Zastosuj wzorzec Dependency Injection",
                "Wydziel wspólne komponenty do osobnych modułów"
            ],
            "risks": [
                "Potencjalne zmiany w API publicznym",
                "Testy integracyjne mogą wymagać aktualizacji",
                "Ryzyko wprowadzenia regresji"
            ],
            "testing_strategy": "Wykonaj pełny zestaw testów przed i po refaktoryzacji. Użyj testów mutacyjnych."
        }

        return json.dumps(result, indent=2, ensure_ascii=False)

    def _mock_llm_response_from_prompt(self, prompt: str) -> str:
        """Mock odpowiedź gdy LLM nie jest dostępny"""
        return json.dumps({
            "summary": "Analiza wykazała potrzebę refaktoryzacji (LLM niedostępny - mock response)",
            "priority_actions": [
                {"priority": 1, "action": "Review and split large files", "files_affected": ["TBD"], "estimated_effort": "4 hours"}
            ],
            "architectural_changes": ["Modularize codebase"],
            "risks": ["Regression risk"],
            "testing_strategy": "Full test suite execution"
        }, indent=2)

    async def execute_refactoring_workflow(
        self,
        repo_id: str,
        target_paths: Optional[List[str]] = None,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Pełny workflow autonomicznej refaktoryzacji"""
        logger.info("=" * 60)
        logger.info("STARTING AUTONOMOUS REFACTORING WORKFLOW")
        logger.info(f"Repository: {repo_id}")
        logger.info(f"Target paths: {target_paths}")
        logger.info(f"Dry run: {dry_run}")
        logger.info("=" * 60)

        # 1. Analiza
        analysis = await self.analyze_repository(repo_id, target_paths)

        # 2. Generowanie planu
        plan = self.generate_refactoring_plan(analysis)

        # 3. Parsowanie planu
        try:
            plan_data = json.loads(plan)
        except json.JSONDecodeError:
            plan_data = {"raw_plan": plan}

        result = {
            "repository": repo_id,
            "analysis": {
                "metrics": analysis.metrics,
                "patterns_detected": analysis.patterns,
            },
            "refactoring_plan": plan_data,
            "dry_run": dry_run,
            "status": "analysis_complete"
        }

        if not dry_run:
            result["execution"] = {
                "status": "not_implemented",
                "message": "Actual code modification not yet implemented - requires Git integration"
            }

        return result


async def main():
    """Główna funkcja agenta"""
    import argparse

    parser = argparse.ArgumentParser(description="Autonomous Refactoring Agent (Standalone)")
    parser.add_argument("--repo", required=True, help="Repository ID (e.g., test/sample-project)")
    parser.add_argument("--paths", nargs="+", help="Target paths to analyze")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run mode")
    parser.add_argument("--llm", choices=["mock", "openai"], default="mock", help="LLM provider")
    parser.add_argument("--repo-base", default="/repos", help="Base path for repositories")

    args = parser.parse_args()

    # Konfiguracja
    os.environ["LLM_PROVIDER"] = args.llm

    agent = RefactoringAgent(repo_base=args.repo_base)

    try:
        # Uruchom workflow
        result = await agent.execute_refactoring_workflow(
            repo_id=args.repo,
            target_paths=args.paths,
            dry_run=args.dry_run
        )

        # Wyświetl wynik
        print("\n" + "=" * 60)
        print("REFACTORING WORKFLOW RESULT")
        print("=" * 60)
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # Zapisz do pliku
        output_dir = Path("/output")
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / f"{args.repo.replace('/', '_')}_analysis.json"
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\nResult saved to: {output_file}")

    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
