"""mcp-gateway: OpenAI-compatible HTTP shim for MCP skills + git2mcp.

Responsibilities:
- public entrypoint for OpenWebUI / external clients
- Bearer auth + tenant routing (tenants/*.yaml)
- /v1/models -> registered MCP skills
- /v1/chat/completions -> dispatches to skill workflow, streams SSE
- /jobs/* -> async job inspection
- /audit -> JSONL audit log writer
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import yaml
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse


TENANTS_DIR = Path(os.getenv("MCP_TENANTS_DIR", "/app/tenants"))
AUDIT_LOG = Path(os.getenv("MCP_AUDIT_LOG", "/audit/audit.jsonl"))
GIT_PROXY_URL = os.getenv("GIT_PROXY_URL", "http://mcp-git-proxy:8080")
SKILLS_URL = os.getenv("SKILLS_URL", "http://mcp-skills:8080")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "openrouter/x-ai/grok-code-fast-1")


def load_tenants() -> dict[str, dict]:
    tenants: dict[str, dict] = {}
    if not TENANTS_DIR.exists():
        return tenants
    for path in TENANTS_DIR.glob("*.yaml"):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        tenant_id = data.get("tenant_id") or path.stem
        tenants[tenant_id] = data
    return tenants


PROMPT_FIELD_REGEX = {
    "repo_id": re.compile(r"^\s*Repo\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "source_path": re.compile(r"^\s*Source\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "branch": re.compile(r"^\s*Branch\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "task": re.compile(r"^\s*Zadanie\s*:\s*(.+?)\s*$", re.IGNORECASE),
}


def message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
                elif item.get("type") == "text" and isinstance(item.get("content"), str):
                    parts.append(item["content"])
        return "\n".join(p for p in parts if p)
    if isinstance(content, dict):
        if isinstance(content.get("text"), str):
            return content["text"]
        if isinstance(content.get("content"), str):
            return content["content"]
    return str(content)


def parse_prompt_context(user_msg: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in user_msg.splitlines():
        for key, regex in PROMPT_FIELD_REGEX.items():
            match = regex.match(line)
            if match:
                parsed[key] = match.group(1).strip()
    return parsed


TENANTS = load_tenants()


def find_tenant_by_key(api_key: str) -> dict | None:
    for tenant in TENANTS.values():
        if api_key in tenant.get("api_keys", []):
            return tenant
    return None


def authenticate(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    api_key = authorization.split(" ", 1)[1].strip()
    tenant = find_tenant_by_key(api_key)
    if not tenant:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return tenant


def audit(event: dict) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    event = {**event, "ts": time.time()}
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# Models exposed via OpenAI-compatible API (MCP skills as "models")
SKILL_MODELS = {
    "mcp-skills/refactor": {
        "description": "Autonomous refactoring loop using git2mcp + mcp-skills",
        "skill": "refactor",
    },
    "mcp-skills/analyze": {
        "description": "Static analysis & metrics through mcp-skills",
        "skill": "analyze",
    },
}


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    repo_id: str | None = None
    source_path: str | None = None
    branch: str = "main"


# In-memory job store (MVP; Redis/Postgres in stage 5)
JOBS: dict[str, dict] = {}


app = FastAPI(title="mcp-gateway", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "mcp-gateway", "tenants": list(TENANTS.keys())}


@app.get("/v1/models")
def list_models(_: dict = Depends(authenticate)):
    return {
        "object": "list",
        "data": [
            {"id": model_id, "object": "model", "owned_by": "mcp-skills", **meta}
            for model_id, meta in SKILL_MODELS.items()
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest, tenant: dict = Depends(authenticate)):
    if req.model not in SKILL_MODELS:
        raise HTTPException(status_code=404, detail=f"Unknown model: {req.model}")

    skill = SKILL_MODELS[req.model]["skill"]
    if not tenant.get("features", {}).get(skill, False):
        raise HTTPException(status_code=403, detail=f"Feature '{skill}' not enabled for tenant")

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"status": "pending", "tenant": tenant["tenant_id"], "skill": skill}
    audit({"event": "chat_completions", "tenant": tenant["tenant_id"], "model": req.model, "job_id": job_id})

    user_msg = next(
        (message_content_to_text(m.content) for m in reversed(req.messages) if m.role == "user"),
        "",
    )
    prompt_ctx = parse_prompt_context(user_msg)

    tenant_id = tenant["tenant_id"]
    repo_id = req.repo_id or prompt_ctx.get("repo_id") or f"{tenant_id}/default"
    source_path = req.source_path or prompt_ctx.get("source_path")
    branch = req.branch
    if branch == "main" and prompt_ctx.get("branch"):
        branch = prompt_ctx["branch"]

    user_request = prompt_ctx.get("task") or user_msg

    async def runner() -> dict:
        try:
            return await dispatch_skill(skill, tenant, repo_id, source_path, branch, user_request)
        except Exception as exc:
            return {"error": str(exc)}

    completion_id = f"chatcmpl-{job_id}"
    created = int(time.time())

    if req.stream:
        async def event_stream():
            task = asyncio.create_task(runner())
            yield {
                "data": json.dumps(
                    {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": req.model,
                        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                    },
                    ensure_ascii=False,
                )
            }

            result = await task
            JOBS[job_id]["status"] = "done"
            JOBS[job_id]["result"] = result

            content = json.dumps(result, ensure_ascii=False)
            yield {
                "data": json.dumps(
                    {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": req.model,
                        "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
                    },
                    ensure_ascii=False,
                )
            }
            yield {
                "data": json.dumps(
                    {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": req.model,
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    },
                    ensure_ascii=False,
                )
            }
            yield {"data": "[DONE]"}
        return EventSourceResponse(event_stream())

    result = await runner()
    JOBS[job_id]["status"] = "done"
    JOBS[job_id]["result"] = result
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": json.dumps(result, ensure_ascii=False)},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "job_id": job_id,
    }


async def dispatch_skill(
    skill: str,
    tenant: dict,
    repo_id: str,
    source_path: str | None,
    branch: str,
    user_request: str,
) -> dict:
    tenant_id = tenant["tenant_id"]
    async with httpx.AsyncClient(timeout=300.0) as client:
        if source_path:
            sync = await client.post(
                f"{GIT_PROXY_URL}/repos/sync",
                json={
                    "repo_id": repo_id,
                    "source_path": source_path,
                    "branch": branch,
                },
            )
            if sync.status_code != 200:
                raise ValueError(f"Sync failed: {sync.status_code} {sync.text}")

        if skill == "analyze":
            return {
                "skill": "analyze",
                "tenant": tenant_id,
                "repo_id": repo_id,
                "message": user_request,
                "source_path": source_path,
                "branch": branch,
                "note": "Analyze workflow stub: wire to mcp-skills HTTP API",
            }

        if skill == "refactor":
            ckpt = await client.post(
                f"{GIT_PROXY_URL}/repos/{repo_id}/checkpoint",
                json={"label": f"task-{uuid.uuid4().hex[:8]}"},
            )
            diff = await client.post(
                f"{GIT_PROXY_URL}/repos/{repo_id}/worktree/diff",
                json={"staged": False},
            )
            return {
                "skill": "refactor",
                "tenant": tenant_id,
                "repo_id": repo_id,
                "source_path": source_path,
                "branch": branch,
                "user_request": user_request,
                "checkpoint": ckpt.json() if ckpt.status_code == 200 else None,
                "current_diff": diff.json().get("diff", "") if diff.status_code == 200 else "",
                "note": "MVP dispatcher: integrates checkpoint + diff; LLM patch loop wired in stage 5.",
            }

    raise ValueError(f"Unknown skill: {skill}")


@app.get("/jobs/{job_id}")
def get_job(job_id: str, _: dict = Depends(authenticate)):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return JOBS[job_id]


@app.get("/audit/tail")
def audit_tail(limit: int = 100, _: dict = Depends(authenticate)):
    if not AUDIT_LOG.exists():
        return {"events": []}
    lines = AUDIT_LOG.read_text(encoding="utf-8").splitlines()[-limit:]
    return {"events": [json.loads(line) for line in lines if line.strip()]}
