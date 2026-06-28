"""semcod-mcp analyze — gateway analysis with live source_path or local code2llm."""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from semcod_mcp.paths import container_source_path, default_api_key, detect_stack_path, gateway_url, infer_repo_id
from semcod_mcp.templates import read_manifest


@dataclass
class AnalyzeReport:
    repo_id: str | None
    mode: str
    ok: bool
    summary: str
    raw: dict | None = None
    notes: list[str] = field(default_factory=list)


def _format_analyze_result(result: dict) -> str:
    analysis = result.get("analysis") or {}
    metrics = analysis.get("metrics") or {}
    recs = (analysis.get("recommendations") or {}).get("recommendations") or []
    lines = [
        f"# Analiza repo `{result.get('repo_id', '?')}`",
        "",
        f"- Pliki: `{metrics.get('file_count', '?')}`",
        f"- Linie: `{metrics.get('total_lines', '?')}`",
    ]
    largest = metrics.get("largest_files") or []
    if largest:
        lines.append("")
        lines.append("## Największe pliki")
        for item in largest[:7]:
            lines.append(f"- `{item.get('path', '?')}` — {item.get('lines', '?')} linii")
    if recs:
        lines.append("")
        lines.append("## Rekomendacje")
        for idx, rec in enumerate(recs[:7], start=1):
            lines.append(
                f"{idx}. **[{rec.get('priority', 'medium')}] `{rec.get('target', '?')}`** "
                f"— {rec.get('suggested_action', 'review')}"
            )
    note = result.get("note")
    if note:
        lines.append("")
        lines.append(f"_Info: {note}_")
    return "\n".join(lines)


def _poll_gateway_job(
    gw: str,
    job_id: str,
    api_key: str,
    *,
    timeout: float = 120.0,
    interval: float = 1.0,
) -> dict | None:
    base = gw.rstrip("/").removesuffix("/v1")
    url = f"{base}/jobs/{job_id}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=10.0)
            resp.raise_for_status()
            state = resp.json()
        except Exception:
            time.sleep(interval)
            continue
        status = state.get("status")
        if status == "done":
            return state.get("result")
        if status == "failed":
            return {"error": state.get("error") or "background job failed"}
        time.sleep(interval)
    return None


def _run_local_code2llm(project_dir: Path, *, task: str) -> AnalyzeReport:
    repo_id = infer_repo_id(project_dir)
    if not shutil.which("code2llm"):
        return AnalyzeReport(
            repo_id=repo_id,
            mode="local-code2llm",
            ok=False,
            summary="Brak `code2llm` w PATH — pip install code2llm",
            notes=["Lokalna analiza bez commita: code2llm czyta working tree bezpośrednio."],
        )
    out_dir = project_dir / ".semcod-mcp-code2llm"
    try:
        proc = subprocess.run(
            ["code2llm", str(project_dir), "-f", "toon", "-o", str(out_dir)],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=project_dir,
        )
    except subprocess.TimeoutExpired:
        return AnalyzeReport(
            repo_id=repo_id,
            mode="local-code2llm",
            ok=False,
            summary="code2llm timeout (>180s)",
        )
    if proc.returncode != 0:
        return AnalyzeReport(
            repo_id=repo_id,
            mode="local-code2llm",
            ok=False,
            summary=(proc.stderr or proc.stdout or "code2llm failed")[:2000],
        )
    map_file = out_dir / "map.toon.yaml"
    summary = f"# code2llm (lokalnie, working tree)\n\nZadanie: {task}\n\n"
    if map_file.is_file():
        summary += map_file.read_text(encoding="utf-8", errors="replace")[:3500]
    else:
        summary += (proc.stdout or "code2llm finished (brak map.toon.yaml)")[:3500]
    return AnalyzeReport(
        repo_id=repo_id,
        mode="local-code2llm",
        ok=True,
        summary=summary,
        notes=[
            "Bez commita — code2llm na katalogu roboczym.",
            "Stack offline lub --local: użyj koru/planfile do pętli SDLC.",
        ],
    )


def run_analyze(
    project_dir: Path,
    *,
    task: str = "Szybka analiza struktury i rekomendacje refaktoryzacji.",
    execute: bool = False,
    timeout: float = 120.0,
    use_local_source: bool = True,
    sync_mode: bool = True,
    local_tool: str | None = None,
) -> AnalyzeReport:
    project_dir = project_dir.resolve()
    manifest = read_manifest(project_dir)
    stack_path = detect_stack_path((manifest or {}).get("stack_path"))
    repo_id = (manifest or {}).get("repo_id") or infer_repo_id(project_dir)

    if local_tool == "code2llm":
        return _run_local_code2llm(project_dir, task=task)

    gw = (manifest or {}).get("gateway_url") or gateway_url(stack_path)
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
            "Fallback: semcod-mcp analyze --local code2llm (bez commita)",
        ]
        if shutil.which("code2llm"):
            return _run_local_code2llm(project_dir, task=task)
        return AnalyzeReport(
            repo_id=repo_id,
            mode="local",
            ok=False,
            summary="Gateway niedostępny; zainstaluj code2llm lub uruchom stack.",
            notes=notes,
        )

    if not repo_id:
        return AnalyzeReport(
            repo_id=None,
            mode="gateway",
            ok=False,
            summary="Brak repo_id (git remote origin lub .semcod-mcp.yaml).",
        )

    source_path = None
    if use_local_source:
        source_path = container_source_path(project_dir, stack_path)

    prompt_lines = [
        f"Repo: {repo_id}",
        "Branch: main",
        f"Execute: {'true' if execute else 'false'}",
    ]
    if source_path:
        prompt_lines.append(f"Source: {source_path}")
    prompt_lines.append(f"Zadanie: {task}")
    prompt = "\n".join(prompt_lines)

    payload: dict = {
        "model": "mcp-skills/analyze",
        "stream": False,
        "async_mode": not sync_mode,
        "messages": [{"role": "user", "content": prompt}],
    }
    if source_path:
        payload["source_path"] = source_path

    url = gw.rstrip("/") + "/chat/completions"
    notes: list[str] = []
    if source_path:
        notes.append(f"Live working tree: {source_path} (git-proxy sync, bez commita)")

    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        content = (
            body.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        job_id = body.get("job_id")
        if job_id and ("zakolejkowane" in content.lower() or "queued" in content.lower()):
            polled = _poll_gateway_job(gw, job_id, api_key, timeout=timeout)
            if polled and polled.get("skill") == "analyze":
                content = _format_analyze_result(polled)
            elif polled and polled.get("error"):
                content = f"❌ Błąd workflow: {polled['error']}"
            else:
                notes.append(f"Job {job_id} — pełny wynik: GET /jobs/{job_id}")

        return AnalyzeReport(
            repo_id=repo_id,
            mode="gateway",
            ok=True,
            summary=content[:8000] if content else "(empty response)",
            raw=body,
            notes=notes,
        )
    except Exception as exc:  # noqa: BLE001
        if shutil.which("code2llm"):
            notes.append(f"Gateway error: {exc}; fallback code2llm")
            fallback = _run_local_code2llm(project_dir, task=task)
            fallback.notes = notes + fallback.notes
            return fallback
        return AnalyzeReport(
            repo_id=repo_id,
            mode="gateway",
            ok=False,
            summary=str(exc),
            notes=notes,
        )
