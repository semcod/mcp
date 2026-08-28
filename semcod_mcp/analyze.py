"""semcod-mcp analyze — gateway analysis or local summary."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import httpx

from semcod_mcp.paths import default_api_key, gateway_url, infer_repo_id
from semcod_mcp.templates import read_manifest


@dataclass
class AnalyzeReport:
    repo_id: str | None
    mode: str
    ok: bool
    summary: str
    raw: dict | None = None
    notes: list[str] = field(default_factory=list)


def run_analyze(
    project_dir: Path,
    *,
    task: str = "Szybka analiza struktury i rekomendacje refaktoryzacji.",
    execute: bool = False,
    timeout: float = 120.0,
) -> AnalyzeReport:
    project_dir = project_dir.resolve()
    manifest = read_manifest(project_dir)
    repo_id = (manifest or {}).get("repo_id") or infer_repo_id(project_dir)

    gw = (manifest or {}).get("gateway_url") or gateway_url(None)
    api_key = default_api_key()
    health_url = gw.rstrip("/").removesuffix("/v1") + "/health"

    try:
        hr = httpx.get(health_url, timeout=5.0)
        gateway_up = hr.status_code < 400
    except Exception:  # noqa: BLE001
        gateway_up = False

    if not gateway_up:
        notes = [
            "Gateway offline — uruchom: cd <stack> && make start",
            f"Repo: {repo_id or 'unknown'}",
            "Lokalne pliki IDE sprawdź przez: semcod-mcp validate",
        ]
        return AnalyzeReport(
            repo_id=repo_id,
            mode="local",
            ok=False,
            summary="Gateway niedostępny; wykonano tylko ocenę lokalną.",
            notes=notes,
        )

    if not repo_id:
        return AnalyzeReport(
            repo_id=None,
            mode="gateway",
            ok=False,
            summary="Brak repo_id (git remote origin lub .semcod-mcp.yaml).",
        )

    prompt = (
        f"Repo: {repo_id}\n"
        f"Branch: main\n"
        f"Execute: {'true' if execute else 'false'}\n"
        f"Zadanie: {task}"
    )
    url = gw.rstrip("/") + "/chat/completions"
    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "mcp-skills/analyze",
                "stream": False,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        content = (
            payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return AnalyzeReport(
            repo_id=repo_id,
            mode="gateway",
            ok=True,
            summary=content[:4000] if content else "(empty response)",
            raw=payload,
        )
    except Exception as exc:  # noqa: BLE001
        return AnalyzeReport(
            repo_id=repo_id,
            mode="gateway",
            ok=False,
            summary=str(exc),
        )
