"""mcp-gateway: OpenAI-compatible HTTP shim for MCP skills + git2mcp.

Thin route layer — logic lives in gateway_* modules.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from fastapi import Depends, FastAPI
from sse_starlette.sse import EventSourceResponse

from gateway_chat import handle_chat_completions
from gateway_config import AUDIT_LOG, JOB_POLL_INTERVAL_SECONDS, OPENROUTER_API_KEY, RQ_QUEUE_NAME, SKILL_MODELS
from gateway_gh2mcp import (
    get_default_github_repo,
    gh2mcp_status_via_gh2mcp,
    github_auth_recovery_message,
    is_github_auth_error,
    last_pushed_repo_via_gh2mcp,
    list_orgs_via_gh2mcp,
    list_recent_repos_via_gh2mcp,
    resolve_repo_id_template,
    run_github_qa,
    save_github_token_via_env2mcp,
    sync_github_token_via_gh2mcp,
)
from gateway_prompt import (
    SUPPORTED_TOOL_NAMES,
    extract_owner_from_repo_template,
    extract_repo_template_expression,
    is_last_pushed_repo_template,
    message_content_to_text,
    normalize_command_text,
    parse_bool,
    parse_prompt_context,
    parse_tool_intent,
)
from gateway_jobs import (
    execute_dispatch_job,
    get_rq_redis_client,
    load_job,
    queue_workflow_job,
    save_job,
    update_job,
)
from gateway_models import ChatCompletionRequest, ChatMessage
from gateway_github import (
    default_draft_name,
    extract_github_token_from_text,
    extract_org_from_text,
    extract_repo_list_limit,
    github_repo_from_url,
    is_github_token_save_command,
    is_github_token_sync_command,
    is_org_list_command,
    is_org_set_command,
    is_repo_list_command,
    normalize_repo_url,
    runtime_github_token,
    save_github_token,
)
from gateway_render import (
    build_commit_changes,
    render_analyze_text,
    render_chat_content,
    render_github_qa_text,
    render_queued_text,
    render_refactor_text,
    render_system_text,
    render_tool_text,
    render_tools_list_text,
    summary_text,
)
from gateway_skills import (
    ask_openrouter_github_qa,
    expect_json,
    fetch_tools_list,
    is_tools_list_command,
    run_skills_tool,
)
from gateway_tenants import TENANTS, audit, authenticate, get_preferred_repo, load_tenants, track_repo_usage
from gateway_dispatch import dispatch_skill

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
    return await handle_chat_completions(req, tenant)


@app.get("/jobs/{job_id}")
def get_job(job_id: str, _: dict = Depends(authenticate)):
    payload = _load_job(job_id)
    if payload is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Job not found")
    return payload


@app.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str, _: dict = Depends(authenticate)):
    from fastapi import HTTPException

    if _load_job(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_stream():
        last_marker = ""
        while True:
            state = _load_job(job_id) or {}
            status = state.get("status") or "pending"
            phase = state.get("phase") or status
            marker = f"{status}:{phase}:{state.get('updated_at')}"

            if marker != last_marker:
                payload: dict[str, Any] = {
                    "job_id": job_id,
                    "status": status,
                    "phase": phase,
                    "updated_at": state.get("updated_at"),
                    "error": state.get("error"),
                }
                if status in {"done", "failed"}:
                    payload["result"] = state.get("result")
                yield {"data": json.dumps(payload, ensure_ascii=False)}
                last_marker = marker

            if status in {"done", "failed"}:
                break

            await asyncio.sleep(JOB_POLL_INTERVAL_SECONDS)

        yield {"data": "[DONE]"}

    return EventSourceResponse(event_stream())


@app.get("/audit/tail")
def audit_tail(limit: int = 100, _: dict = Depends(authenticate)):
    if not AUDIT_LOG.exists():
        return {"events": []}
    lines = AUDIT_LOG.read_text(encoding="utf-8").splitlines()[-limit:]
    return {"events": [json.loads(line) for line in lines if line.strip()]}


async def _ask_openrouter_github_qa(user_request: str, github_context: dict[str, Any]) -> dict[str, Any]:
    import gateway_config

    gateway_config.OPENROUTER_API_KEY = OPENROUTER_API_KEY
    return await ask_openrouter_github_qa(user_request, github_context)


# Backward compatibility for tests (`import server as gateway`)
_get_redis_client = __import__("gateway_tenants", fromlist=["get_redis_client"]).get_redis_client
_get_rq_redis_client = get_rq_redis_client
_get_preferred_repo = get_preferred_repo
_track_repo_usage = track_repo_usage
_get_default_github_repo = get_default_github_repo
_sync_github_token_via_gh2mcp = sync_github_token_via_gh2mcp
_set_default_org_via_gh2mcp = __import__(
    "gateway_gh2mcp", fromlist=["set_default_org_via_gh2mcp"]
).set_default_org_via_gh2mcp
_list_recent_repos_via_gh2mcp = list_recent_repos_via_gh2mcp
_list_orgs_via_gh2mcp = list_orgs_via_gh2mcp
_gh2mcp_status_via_gh2mcp = gh2mcp_status_via_gh2mcp
_last_pushed_repo_via_gh2mcp = last_pushed_repo_via_gh2mcp
_is_github_auth_error = is_github_auth_error
_github_auth_recovery_message = github_auth_recovery_message
_resolve_repo_id_template = resolve_repo_id_template
_save_github_token_via_env2mcp = save_github_token_via_env2mcp
_run_github_qa = run_github_qa
_save_job = save_job
_load_job = load_job
_update_job = update_job
_queue_workflow_job = queue_workflow_job
_expect_json = expect_json
_is_tools_list_command = is_tools_list_command
_fetch_tools_list = fetch_tools_list
_run_skills_tool = run_skills_tool
_normalize_command_text = normalize_command_text
_extract_github_token_from_text = extract_github_token_from_text
_extract_repo_template_expression = extract_repo_template_expression
_is_last_pushed_repo_template = is_last_pushed_repo_template
_extract_owner_from_repo_template = extract_owner_from_repo_template
_is_github_token_save_command = is_github_token_save_command
_is_github_token_sync_command = is_github_token_sync_command
_extract_org_from_text = extract_org_from_text
_is_org_set_command = is_org_set_command
_is_org_list_command = is_org_list_command
_is_repo_list_command = is_repo_list_command
_extract_repo_list_limit = extract_repo_list_limit
_normalize_repo_url = normalize_repo_url
_github_repo_from_url = github_repo_from_url
_runtime_github_token = runtime_github_token
_save_github_token = save_github_token
_default_draft_name = default_draft_name
_summary_text = summary_text
_render_chat_content = render_chat_content
_render_analyze_text = render_analyze_text
_render_refactor_text = render_refactor_text
_render_tools_list_text = render_tools_list_text
_build_commit_changes = build_commit_changes
_render_system_text = render_system_text
_render_queued_text = render_queued_text
_render_tool_text = render_tool_text
_render_github_qa_text = render_github_qa_text
