"""mcp-skills HTTP client helpers for mcp-gateway."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from gateway_config import LLM_MODEL, SKILLS_URL
import gateway_config
from gateway_prompt import message_content_to_text


async def expect_json(response: httpx.Response, action: str) -> dict[str, Any]:
    if response.status_code != 200:
        raise ValueError(f"{action} failed: {response.status_code} {response.text}")
    data = response.json()
    if isinstance(data, dict):
        return data
    raise ValueError(f"{action} returned non-object payload")


def is_tools_list_command(msg: str) -> bool:
    m = msg.lower()
    return bool(
        re.search(r"\blista\s+narz[eę]dzi\b", m)
        or re.search(r"\blist\s+tools?\b", m)
        or re.search(r"\bjakie\s+narz[eę]dzia\b", m)
        or re.search(r"\bshow\s+tools?\b", m)
        or re.search(r"\bdost[eę]pne\s+narz[eę]dzia\b", m)
        or re.search(r"\bnarz[eę]dzia\b.*\bdost[eę]pne\b", m)
    )


async def fetch_tools_list() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{SKILLS_URL}/tools/list")
        if response.status_code >= 400:
            return {"ok": False, "error": f"HTTP {response.status_code}"}
        return {**response.json(), "ok": True}


async def run_skills_tool(
    tool: str,
    repo_id: str | None,
    repo_url: str | None,
    subcommand: str | None = None,
    args: list[str] | None = None,
    timeout: float = 900.0,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "tool": tool,
        "auto_install": True,
        "use_git_proxy": True,
    }
    if repo_id:
        payload["repo_id"] = repo_id
    if repo_url:
        payload["repo_url"] = repo_url
    if subcommand:
        payload["subcommand"] = subcommand
    if args:
        payload["args"] = list(args)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{SKILLS_URL}/tools/run", json=payload)
        if response.status_code >= 400:
            text = response.text
            try:
                detail = response.json().get("detail", text)
            except Exception:
                detail = text
            return {
                "tool": tool,
                "repo_id": repo_id,
                "repo_url": repo_url,
                "ok": False,
                "error": f"mcp-skills /tools/run HTTP {response.status_code}: {detail}",
            }
        return response.json()


async def ask_openrouter_github_qa(user_request: str, github_context: dict[str, Any]) -> dict[str, Any]:
    api_key = gateway_config.OPENROUTER_API_KEY
    if not api_key:
        return {
            "ok": False,
            "error": "OPENROUTER_API_KEY is not configured",
        }

    system_prompt = (
        "Jesteś asystentem GitHub dla semcod/mcp. "
        "Odpowiadaj po polsku, rzeczowo i praktycznie. "
        "Bazuj na przekazanym kontekście runtime z gh2mcp. "
        "Jeśli w kontekście nie ma danych, napisz to wprost i podaj kolejne kroki."
    )
    user_prompt = (
        f"Pytanie użytkownika:\n{user_request}\n\n"
        "Kontekst runtime (JSON z gh2mcp):\n"
        f"{json.dumps(github_context, ensure_ascii=False)}"
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://mcp-gateway.local",
        "X-Title": "mcp-gateway-github-qa",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
        )

    if response.status_code >= 400:
        text = response.text
        try:
            detail = response.json().get("error", {}).get("message") or text
        except Exception:
            detail = text
        return {
            "ok": False,
            "error": f"OpenRouter HTTP {response.status_code}: {detail}",
        }

    try:
        data = response.json()
    except Exception as exc:
        return {
            "ok": False,
            "error": f"OpenRouter returned invalid JSON: {exc}",
        }

    choices = data.get("choices") if isinstance(data, dict) else None
    first = choices[0] if isinstance(choices, list) and choices else {}
    message = first.get("message") if isinstance(first, dict) else {}
    answer = message_content_to_text((message or {}).get("content", "")).strip()
    if not answer:
        return {
            "ok": False,
            "error": "OpenRouter returned empty answer",
        }
    return {
        "ok": True,
        "answer": answer,
    }


async def enrich_analysis_with_file_metrics(
    client: httpx.AsyncClient,
    repo_id: str,
    analysis: dict[str, Any],
) -> dict[str, Any]:
    metrics = analysis.get("metrics") or {}
    if not metrics.get("largest_files"):
        try:
            file_metrics = await expect_json(
                await client.post(f"{SKILLS_URL}/analyze/metrics", json={"repo_id": repo_id}),
                "skills metrics enrich",
            )
            for key in (
                "file_count",
                "total_lines",
                "total_imports",
                "total_functions",
                "total_classes",
                "avg_lines_per_file",
                "largest_files",
            ):
                if file_metrics.get(key) is not None:
                    metrics[key] = file_metrics[key]
            analysis["metrics"] = metrics
        except Exception:
            pass

    rec_block = analysis.get("recommendations") or {}
    recs = rec_block.get("recommendations") or []
    only_generic = not recs or all(str(r.get("target") or "general") == "general" for r in recs)
    if only_generic:
        try:
            rec_payload = await expect_json(
                await client.post(
                    f"{SKILLS_URL}/refactor/recommend",
                    json={"repo_id": repo_id, "goal": "maintainability"},
                ),
                "skills recommendations enrich",
            )
            analysis["recommendations"] = rec_payload
        except Exception:
            pass

    return analysis


async def run_skills_analysis(
    client: httpx.AsyncClient,
    repo_id: str,
    execute: bool = False,
    user_request: str = "",
    max_actions: int = 10,
) -> dict[str, Any]:
    try:
        redsl_res = await client.post(
            f"{SKILLS_URL}/refactor/redsl",
            json={
                "repo_id": repo_id,
                "max_actions": max_actions,
                "dry_run": not execute,
                "execute": execute,
                "user_request": user_request,
            },
            timeout=180.0,
        )
        if redsl_res.status_code == 200:
            data = redsl_res.json()
            if data.get("engine") == "redsl":
                analysis = {
                    "sync": data.get("sync", {}),
                    "metrics": data.get("metrics", {}),
                    "patterns": {"repo_id": repo_id, "patterns_detected": {}},
                    "recommendations": data.get("recommendations", {}),
                    "engine": "redsl",
                    "redsl_raw": data.get("redsl_raw", {}),
                }
                return await enrich_analysis_with_file_metrics(client, repo_id, analysis)
    except Exception:
        pass

    sync_res = await expect_json(
        await client.post(f"{SKILLS_URL}/sync", json={"repo_id": repo_id, "ref": "HEAD"}),
        "skills sync",
    )
    metrics = await expect_json(
        await client.post(f"{SKILLS_URL}/analyze/metrics", json={"repo_id": repo_id}),
        "skills metrics",
    )
    patterns = await expect_json(
        await client.post(f"{SKILLS_URL}/analyze/patterns", json={"repo_id": repo_id}),
        "skills patterns",
    )
    recommendations = await expect_json(
        await client.post(
            f"{SKILLS_URL}/refactor/recommend",
            json={"repo_id": repo_id, "goal": "maintainability"},
        ),
        "skills recommendations",
    )
    return {
        "sync": sync_res,
        "metrics": metrics,
        "patterns": patterns,
        "recommendations": recommendations,
        "engine": "mcp-skills",
    }
