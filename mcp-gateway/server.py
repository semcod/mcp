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
from urllib.parse import urlparse

import httpx
import yaml
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

try:
    from env2mcp import EnvConfig, GitHubCLI

    ENV2MCP_AVAILABLE = True
except Exception:
    ENV2MCP_AVAILABLE = False


TENANTS_DIR = Path(os.getenv("MCP_TENANTS_DIR", "/app/tenants"))
AUDIT_LOG = Path(os.getenv("MCP_AUDIT_LOG", "/audit/audit.jsonl"))
GIT_PROXY_URL = os.getenv("GIT_PROXY_URL", "http://mcp-git-proxy:8080")
SKILLS_URL = os.getenv("SKILLS_URL", "http://mcp-skills:8080")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "openrouter/x-ai/grok-code-fast-1")
MCP_ENV_FILE = Path(os.getenv("MCP_ENV_FILE", "/app/.env"))
GITHUB_PAT = os.getenv("GITHUB_PAT", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API_URL = os.getenv("GITHUB_API_URL", "https://api.github.com")


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
    "repo_url": re.compile(r"^\s*Repo\s*URL\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "github_token": re.compile(r"^\s*(?:GitHub\s*Token|Github\s*Token|Token)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "source_path": re.compile(r"^\s*Source\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "branch": re.compile(r"^\s*Branch\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "task": re.compile(r"^\s*Zadanie\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "execute": re.compile(r"^\s*(?:Execute|Wykonaj)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "push": re.compile(r"^\s*(?:Push|Wypchnij)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "draft": re.compile(r"^\s*(?:Draft|Draft\s*branch)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "draft_name": re.compile(r"^\s*(?:Draft\s*name|Draft\s*branch\s*name)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "open_pr": re.compile(r"^\s*(?:PR|Pull\s*request|Open\s*PR)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "pr_title": re.compile(r"^\s*(?:PR\s*title|Pull\s*request\s*title)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "pr_body": re.compile(r"^\s*(?:PR\s*body|Pull\s*request\s*body)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "pr_base": re.compile(r"^\s*(?:PR\s*base|Pull\s*request\s*base)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "test_command": re.compile(r"^\s*(?:Test(?:\s*command)?|Testy)\s*:\s*(.+?)\s*$", re.IGNORECASE),
    "remote": re.compile(r"^\s*(?:Remote|Push\s*remote)\s*:\s*(.+?)\s*$", re.IGNORECASE),
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


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "tak", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "nie", "off"}:
        return False
    return default


def _load_env_file_values(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:]
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        values[key] = value
    return values


def _runtime_github_token() -> str:
    file_values = _load_env_file_values(MCP_ENV_FILE)
    return (
        file_values.get("GITHUB_TOKEN")
        or file_values.get("GITHUB_PAT")
        or os.getenv("GITHUB_TOKEN", "")
        or os.getenv("GITHUB_PAT", "")
    )


def _save_github_token(token: str) -> dict[str, Any]:
    cleaned = token.strip()
    if not cleaned:
        raise ValueError("GitHub token is empty")
    if not ENV2MCP_AVAILABLE:
        raise ValueError("env2mcp is not available in mcp-gateway")

    cfg = EnvConfig(MCP_ENV_FILE)
    cfg["GITHUB_PAT"] = cleaned
    cfg.remove("GITHUB_TOKEN")

    github_user: str | None = None
    try:
        gh = GitHubCLI()
        if gh.is_available():
            os.environ["GITHUB_TOKEN"] = cleaned
            github_user = gh.get_user()
            if github_user:
                cfg["GITHUB_USER"] = github_user
    except Exception:
        github_user = None

    cfg.save()
    return {
        "configured": True,
        "env_file": str(MCP_ENV_FILE),
        "github_user": github_user,
    }


def _normalize_repo_url(repo_url: str | None) -> str | None:
    if not repo_url:
        return None
    value = repo_url.strip()
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        return f"https://github.com/{value}.git"
    return value


def _inject_github_token(repo_url: str | None) -> str | None:
    if not repo_url:
        return repo_url
    parsed = urlparse(repo_url)
    if (parsed.scheme or "").lower() != "https":
        return repo_url
    if (parsed.hostname or "").lower() != "github.com":
        return repo_url
    if parsed.username:
        return repo_url

    token = _runtime_github_token()
    if not token:
        return repo_url

    if parsed.port:
        netloc = f"{token}@{parsed.hostname}:{parsed.port}"
    else:
        netloc = f"{token}@{parsed.hostname}"
    return parsed._replace(netloc=netloc).geturl()


def _redact_repo_url(repo_url: str | None) -> str | None:
    if not repo_url:
        return repo_url
    try:
        parsed = urlparse(repo_url)
        if parsed.scheme and parsed.netloc and "@" in parsed.netloc:
            netloc = parsed.netloc.split("@", 1)[1]
            return parsed._replace(netloc=netloc).geturl()
    except Exception:
        pass
    return repo_url


def _default_draft_name(repo_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]", "-", repo_id).strip("-")
    if not slug:
        slug = "repo"
    return f"{slug}-{uuid.uuid4().hex[:8]}"


def _github_repo_from_url(repo_url: str | None) -> tuple[str, str] | None:
    normalized_url = _normalize_repo_url(repo_url)
    if not normalized_url:
        return None

    value = normalized_url.strip()
    if value.startswith("git@github.com:"):
        path = value.split(":", 1)[1]
    else:
        parsed = urlparse(value)
        host = parsed.hostname or ""
        if host.lower() != "github.com":
            return None
        path = parsed.path.lstrip("/")

    if path.endswith(".git"):
        path = path[:-4]

    parts = [p for p in path.split("/") if p]
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def _default_pr_title(repo_id: str, user_request: str) -> str:
    first = user_request.strip().splitlines()[0] if user_request.strip() else ""
    if not first:
        return f"mcp: refactor {repo_id}"
    if len(first) > 72:
        first = first[:69].rstrip() + "..."
    return f"mcp: {first}"


def _default_pr_body(repo_id: str, user_request: str, base_branch: str) -> str:
    return "\n".join(
        [
            "## MCP automated refactor request",
            "",
            f"- Repo: `{repo_id}`",
            f"- Base branch: `{base_branch}`",
            "",
            "### User task",
            user_request,
            "",
            "Generated by mcp-gateway.",
        ]
    )


async def _create_github_pr(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str,
    draft: bool,
) -> dict[str, Any]:
    token = _runtime_github_token()
    if not token:
        raise ValueError("GitHub token not configured (set GITHUB_TOKEN or GITHUB_PAT)")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    payload = {
        "title": title,
        "head": head_branch,
        "base": base_branch,
        "body": body,
        "draft": draft,
    }
    response = await client.post(
        f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls",
        headers=headers,
        json=payload,
    )
    if response.status_code not in {200, 201}:
        raise ValueError(f"create PR failed: {response.status_code} {response.text}")

    data = response.json()
    return {
        "number": data.get("number"),
        "title": data.get("title"),
        "url": data.get("html_url"),
        "state": data.get("state"),
        "draft": data.get("draft"),
        "head": data.get("head", {}).get("ref"),
        "base": data.get("base", {}).get("ref"),
    }


def _summary_text(analysis: dict[str, Any], user_request: str) -> str:
    metrics = analysis.get("metrics", {})
    recs = analysis.get("recommendations", {}).get("recommendations", [])
    lines = [
        "# MCP Refactoring Summary",
        "",
        f"Request: {user_request}",
        f"Files: {metrics.get('file_count', 0)}",
        f"Total lines: {metrics.get('total_lines', 0)}",
        "",
        "## Suggested actions",
    ]
    if recs:
        for rec in recs[:5]:
            lines.append(f"- [{rec.get('priority', 'medium')}] {rec.get('target', 'general')}: {rec.get('suggested_action', 'review')}" )
    else:
        lines.append("- No automatic recommendations generated.")
    return "\n".join(lines) + "\n"


def _build_commit_changes(plan_payload: dict[str, Any], summary_md: str) -> list[dict[str, str]]:
    return [
        {
            "path": ".mcp/refactor-plan.json",
            "content": json.dumps(plan_payload, indent=2, ensure_ascii=False),
            "mode": "update",
        },
        {
            "path": ".mcp/refactor-summary.md",
            "content": summary_md,
            "mode": "update",
        },
    ]


async def _expect_json(response: httpx.Response, action: str) -> dict[str, Any]:
    if response.status_code != 200:
        raise ValueError(f"{action} failed: {response.status_code} {response.text}")
    data = response.json()
    if isinstance(data, dict):
        return data
    raise ValueError(f"{action} returned non-object payload")


async def _run_skills_analysis(client: httpx.AsyncClient, repo_id: str) -> dict[str, Any]:
    sync_res = await _expect_json(
        await client.post(f"{SKILLS_URL}/sync", json={"repo_id": repo_id, "ref": "HEAD"}),
        "skills sync",
    )
    metrics = await _expect_json(
        await client.post(f"{SKILLS_URL}/analyze/metrics", json={"repo_id": repo_id}),
        "skills metrics",
    )
    patterns = await _expect_json(
        await client.post(f"{SKILLS_URL}/analyze/patterns", json={"repo_id": repo_id}),
        "skills patterns",
    )
    recommendations = await _expect_json(
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
    }


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
    repo_url: str | None = None
    github_token: str | None = None
    source_path: str | None = None
    branch: str = "main"
    execute: bool | None = None
    push: bool | None = None
    draft: bool | None = None
    draft_name: str | None = None
    open_pr: bool | None = None
    pr_title: str | None = None
    pr_body: str | None = None
    pr_base: str | None = None
    test_command: str | None = None
    remote: str | None = None


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
    repo_url = req.repo_url or prompt_ctx.get("repo_url")
    github_token = req.github_token or prompt_ctx.get("github_token")
    source_path = req.source_path or prompt_ctx.get("source_path")
    branch = req.branch
    if branch == "main" and prompt_ctx.get("branch"):
        branch = prompt_ctx["branch"]

    user_request = prompt_ctx.get("task") or user_msg
    execute_commit = req.execute if req.execute is not None else parse_bool(prompt_ctx.get("execute"), default=False)
    push_after_tests = req.push if req.push is not None else parse_bool(prompt_ctx.get("push"), default=False)
    create_draft_branch = req.draft if req.draft is not None else parse_bool(prompt_ctx.get("draft"), default=push_after_tests)
    draft_name = req.draft_name or prompt_ctx.get("draft_name") or _default_draft_name(repo_id)
    open_pull_request = req.open_pr if req.open_pr is not None else parse_bool(prompt_ctx.get("open_pr"), default=push_after_tests)
    pr_title = req.pr_title or prompt_ctx.get("pr_title")
    pr_body = req.pr_body or prompt_ctx.get("pr_body")
    pr_base = req.pr_base or prompt_ctx.get("pr_base") or branch
    test_command = req.test_command or prompt_ctx.get("test_command") or "python3 -m compileall -q ."
    push_remote = req.remote or prompt_ctx.get("remote") or "origin"

    async def runner() -> dict:
        try:
            return await dispatch_skill(
                skill=skill,
                tenant=tenant,
                repo_id=repo_id,
                repo_url=repo_url,
                github_token=github_token,
                source_path=source_path,
                branch=branch,
                user_request=user_request,
                execute_commit=execute_commit,
                push_after_tests=push_after_tests,
                create_draft_branch=create_draft_branch,
                draft_name=draft_name,
                open_pull_request=open_pull_request,
                pr_title=pr_title,
                pr_body=pr_body,
                pr_base=pr_base,
                test_command=test_command,
                push_remote=push_remote,
            )
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
    repo_url: str | None,
    github_token: str | None,
    source_path: str | None,
    branch: str,
    user_request: str,
    execute_commit: bool,
    push_after_tests: bool,
    create_draft_branch: bool,
    draft_name: str,
    open_pull_request: bool,
    pr_title: str | None,
    pr_body: str | None,
    pr_base: str,
    test_command: str,
    push_remote: str,
) -> dict:
    tenant_id = tenant["tenant_id"]
    github_config_result: dict[str, Any] | None = None
    if github_token:
        github_config_result = _save_github_token(github_token)

    normalized_repo_url = _normalize_repo_url(repo_url)
    safe_repo_url = _redact_repo_url(normalized_repo_url)
    async with httpx.AsyncClient(timeout=300.0) as client:
        sync_payload: dict[str, Any] = {
            "repo_id": repo_id,
            "branch": branch,
        }
        if source_path:
            sync_payload["source_path"] = source_path
        if normalized_repo_url:
            sync_payload["repo_url"] = _inject_github_token(normalized_repo_url)

        sync = await _expect_json(
            await client.post(f"{GIT_PROXY_URL}/repos/sync", json=sync_payload),
            "git sync",
        )

        if skill == "analyze":
            analysis = await _run_skills_analysis(client, repo_id)
            return {
                "skill": "analyze",
                "tenant": tenant_id,
                "repo_id": repo_id,
                "repo_url": safe_repo_url,
                "user_request": user_request,
                "source_path": source_path,
                "branch": branch,
                "sync": sync,
                "github": github_config_result,
                "analysis": analysis,
                "note": "Analyze workflow executed through mcp-skills HTTP API.",
            }

        if skill == "refactor":
            ckpt = await _expect_json(
                await client.post(
                f"{GIT_PROXY_URL}/repos/{repo_id}/checkpoint",
                json={"label": f"task-{uuid.uuid4().hex[:8]}"},
                ),
                "checkpoint create",
            )

            analysis = await _run_skills_analysis(client, repo_id)
            base_branch = branch
            working_branch = branch
            plan_payload: dict[str, Any] = {
                "repo_id": repo_id,
                "tenant": tenant_id,
                "branch": working_branch,
                "base_branch": base_branch,
                "repo_url": safe_repo_url,
                "source_path": source_path,
                "user_request": user_request,
                "generated_at": int(time.time()),
                "analysis": analysis,
            }
            summary_md = _summary_text(analysis, user_request)

            execution: dict[str, Any] = {
                "execute_commit": execute_commit,
                "push_after_tests": push_after_tests,
                "create_draft_branch": create_draft_branch,
                "draft_name": draft_name,
                "open_pull_request": open_pull_request,
                "pr_base": pr_base,
                "test_command": test_command,
                "remote": push_remote,
                "committed": False,
                "pushed": False,
            }

            if execute_commit:
                if create_draft_branch:
                    draft_result = await _expect_json(
                        await client.post(
                            f"{GIT_PROXY_URL}/repos/{repo_id}/branch/draft",
                            json={"name": draft_name, "base": base_branch},
                        ),
                        "draft branch create",
                    )
                    working_branch = draft_result.get("branch", working_branch)
                    plan_payload["branch"] = working_branch
                    execution["draft_branch"] = draft_result

                commit_payload = {
                    "message": f"chore(mcp): refactor plan for {repo_id} ({working_branch})",
                    "changes": _build_commit_changes(plan_payload, summary_md),
                    "author_name": "mcp-gateway-bot",
                    "author_email": "mcp-gateway@local",
                }
                commit_result = await _expect_json(
                    await client.post(f"{GIT_PROXY_URL}/repos/{repo_id}/commit", json=commit_payload),
                    "git commit",
                )
                tests_result = await _expect_json(
                    await client.post(
                        f"{GIT_PROXY_URL}/repos/{repo_id}/run-tests",
                        json={"command": test_command},
                    ),
                    "run tests",
                )
                execution.update(
                    {
                        "committed": True,
                        "commit": commit_result,
                        "tests": tests_result,
                    }
                )

                if push_after_tests:
                    if not tenant.get("features", {}).get("push", False):
                        execution["push"] = {
                            "skipped": True,
                            "reason": "Tenant push feature disabled",
                        }
                    elif not tests_result.get("ok"):
                        execution["push"] = {
                            "skipped": True,
                            "reason": "Tests failed",
                        }
                    else:
                        push_result = await _expect_json(
                            await client.post(
                                f"{GIT_PROXY_URL}/repos/{repo_id}/push",
                                json={"remote": push_remote, "branch": working_branch},
                            ),
                            "git push",
                        )
                        execution["push"] = push_result
                        execution["pushed"] = True

                if open_pull_request:
                    if not execution.get("pushed"):
                        execution["pull_request"] = {
                            "skipped": True,
                            "reason": "Push was not executed",
                        }
                    else:
                        github_repo = _github_repo_from_url(repo_url)
                        if not github_repo:
                            execution["pull_request"] = {
                                "skipped": True,
                                "reason": "Repo URL is not a GitHub URL",
                            }
                        else:
                            owner, repo_name = github_repo
                            pr_result = await _create_github_pr(
                                client=client,
                                owner=owner,
                                repo=repo_name,
                                head_branch=working_branch,
                                base_branch=pr_base,
                                title=pr_title or _default_pr_title(repo_id, user_request),
                                body=pr_body or _default_pr_body(repo_id, user_request, pr_base),
                                draft=True,
                            )
                            execution["pull_request"] = pr_result

            diff = await _expect_json(
                await client.post(
                    f"{GIT_PROXY_URL}/repos/{repo_id}/worktree/diff",
                    json={"staged": False},
                ),
                "worktree diff",
            )

            return {
                "skill": "refactor",
                "tenant": tenant_id,
                "repo_id": repo_id,
                "repo_url": safe_repo_url,
                "source_path": source_path,
                "branch": working_branch,
                "base_branch": base_branch,
                "user_request": user_request,
                "sync": sync,
                "github": github_config_result,
                "checkpoint": ckpt,
                "analysis": analysis,
                "plan_preview": {
                    "summary": summary_md,
                    "artifacts": [".mcp/refactor-plan.json", ".mcp/refactor-summary.md"],
                },
                "execution": execution,
                "current_diff": diff.get("diff", ""),
                "note": "Gateway orchestrates sync+analysis and optional commit/push via git-proxy.",
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
