#!/usr/bin/env python3
"""
Autonomiczny Agent Refaktoryzacji - LLM Agent z MCP
Koordynuje MCP Git Server i MCP Skills Server do analizy i refaktoryzacji kodu.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Wynik analizy repozytorium"""
    repo_id: str
    metrics: Dict[str, Any]
    patterns: Dict[str, Any]
    recommendations: Dict[str, Any]


class RefactoringAgent:
    """
    Autonomiczny Agent Refaktoryzacji
    Łączy się z MCP Git Server i MCP Skills Server
    """

    def __init__(self):
        self.skills_session: Optional[ClientSession] = None
        self.git_session: Optional[ClientSession] = None
        self.llm_provider = os.getenv("LLM_PROVIDER", "mock")  # mock, openai, ollama
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    async def connect_skills(self, command: str = "python", args: List[str] = None):
        """Połączenie z MCP Skills Server"""
        if args is None:
            args = ["/app/mcp-skills/server.py"]

        server_params = StdioServerParameters(command=command, args=args, env=None)
        self._skills_client = stdio_client(server_params)
        self._skills_read, self._skills_write = await self._skills_client.__aenter__()
        self.skills_session = ClientSession(self._skills_read, self._skills_write)
        await self.skills_session.initialize()
        logger.info("Connected to MCP Skills Server")

    async def connect_git_mcp(self, command: str = "npx", args: List[str] = None):
        """Połączenie z MCP Git Server (GitHub MCP)"""
        if args is None:
            # Użyj lokalnego git mcp jeśli dostępny
            args = ["-y", "@modelcontextprotocol/server-git"]

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": os.getenv("GITHUB_PAT", "")}
        )
        self._git_client = stdio_client(server_params)
        self._git_read, self._git_write = await self._git_client.__aenter__()
        self.git_session = ClientSession(self._git_read, self._git_write)
        await self.git_session.initialize()
        logger.info("Connected to MCP Git Server")

    async def analyze_repository(self, repo_id: str, target_paths: Optional[List[str]] = None) -> AnalysisResult:
        """
        Pełna analiza repozytorium używając MCP Skills
        """
        logger.info(f"Starting analysis of repo: {repo_id}")

        # 1. Oblicz metryki
        logger.info("Computing repository metrics...")
        metrics_result = await self.skills_session.call_tool(
            "compute_metrics_for_repo",
            {"repo_id": repo_id, "extensions": [".py", ".js", ".ts", ".java"]}
        )
        metrics = json.loads(metrics_result.content[0].text)

        # 2. Wykryj wzorce
        logger.info("Detecting code patterns...")
        patterns_result = await self.skills_session.call_tool(
            "detect_code_patterns",
            {"repo_id": repo_id, "pattern_types": ["complexity", "imports", "duplication"]}
        )
        patterns = json.loads(patterns_result.content[0].text)

        # 3. Pobierz rekomendacje
        logger.info("Generating refactoring recommendations...")
        rec_result = await self.skills_session.call_tool(
            "recommend_refactoring",
            {
                "repo_id": repo_id,
                "target_paths": target_paths or [],
                "goal": "maintainability"
            }
        )
        recommendations = json.loads(rec_result.content[0].text)

        # 4. Jeśli podane target_paths, analizuj strukturę
        if target_paths:
            logger.info(f"Analyzing specific paths: {target_paths}")
            structure_result = await self.skills_session.call_tool(
                "analyze_code_structure",
                {"repo_id": repo_id, "paths": target_paths}
            )
            structure = json.loads(structure_result.content[0].text)
            metrics["structure_analysis"] = structure

        return AnalysisResult(
            repo_id=repo_id,
            metrics=metrics,
            patterns=patterns,
            recommendations=recommendations
        )

    async def generate_refactoring_plan(self, analysis: AnalysisResult) -> str:
        """
        Generuje plan refaktoryzacji używając LLM
        """
        prompt = self._build_refactoring_prompt(analysis)

        if self.llm_provider == "openai" and self.openai_api_key:
            return await self._call_openai(prompt)
        elif self.llm_provider == "ollama":
            return await self._call_ollama(prompt)
        else:
            # Mock LLM - zwraca strukturyzowaną odpowiedź
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
            prompt += f"\n  Cel: {rec.get('target', 'N/A')}"

        prompt += """

## Zadanie:
Zaproponuj szczegółowy plan refaktoryzacji z konkretnymi krokami:

1. PRIORYTETYZACJA: Które zmiany wykonać najpierw i dlaczego?
2. KONKRETNE KROKI: Jakie dokładne zmiany wprowadzić w kodzie?
3. ARCHITEKTURA: Jakie wzorce projektowe zastosować?
4. RYZYKA: Na co uważać podczas refaktoryzacji?
5. TESTOWANIE: Jak zapewnić, że zmiany nie zepsują funkcjonalności?

Odpowiedź w formacie JSON:
{
  "summary": "Krótkie podsumowanie sytuacji",
  "priority_actions": [
    {"priority": 1, "action": "...", "files_affected": [...], "estimated_effort": "..."}
  ],
  "architectural_changes": [...],
  "risks": [...],
  "testing_strategy": "..."
}
"""

        return prompt

    async def _call_openai(self, prompt: str) -> str:
        """Wywołanie OpenAI API"""
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=self.openai_api_key)
            response = await client.chat.completions.create(
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

    async def _call_ollama(self, prompt: str) -> str:
        """Wywołanie lokalnego Ollama"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.ollama_host}/api/generate",
                    json={
                        "model": "codellama",
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=120.0
                )
                data = response.json()
                return data.get("response", "")
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            return self._mock_llm_response_from_prompt(prompt)

    def _mock_llm_response(self, analysis: AnalysisResult) -> str:
        """Generuje mock odpowiedź LLM na podstawie analizy"""
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
        """
        Pełny workflow autonomicznej refaktoryzacji
        """
        logger.info("=" * 60)
        logger.info(f"STARTING AUTONOMOUS REFACTORING WORKFLOW")
        logger.info(f"Repository: {repo_id}")
        logger.info(f"Target paths: {target_paths}")
        logger.info(f"Dry run: {dry_run}")
        logger.info("=" * 60)

        # 1. Analiza
        analysis = await self.analyze_repository(repo_id, target_paths)

        # 2. Generowanie planu
        plan = await self.generate_refactoring_plan(analysis)

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
            # Tu byłaby implementacja faktycznych zmian
            # Na razie tylko symulacja
            result["execution"] = {
                "status": "simulated",
                "message": "Actual refactoring not yet implemented - requires Git MCP integration"
            }

        return result

    async def close(self):
        """Zamknięcie połączeń"""
        if hasattr(self, '_skills_client'):
            await self._skills_client.__aexit__(None, None, None)
        if hasattr(self, '_git_client'):
            await self._git_client.__aexit__(None, None, None)
        logger.info("Connections closed")


async def main():
    """Główna funkcja agenta"""
    import argparse

    parser = argparse.ArgumentParser(description="Autonomous Refactoring Agent")
    parser.add_argument("--repo", required=True, help="Repository ID (e.g., my_org/repo)")
    parser.add_argument("--paths", nargs="+", help="Target paths to analyze")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run mode")
    parser.add_argument("--llm", choices=["mock", "openai", "ollama"], default="mock", help="LLM provider")

    args = parser.parse_args()

    # Konfiguracja
    os.environ["LLM_PROVIDER"] = args.llm

    agent = RefactoringAgent()

    try:
        # Połączenie z MCP Skills (lokalnie)
        await agent.connect_skills()

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

    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        raise
    finally:
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
