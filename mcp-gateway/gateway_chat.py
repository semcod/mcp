"""Chat completions orchestration — prompt routing and SSE streaming."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from fastapi import HTTPException
from sse_starlette.sse import EventSourceResponse

from gateway_config import JOB_POLL_INTERVAL_SECONDS, MCP_ASYNC_ENABLED, SKILL_MODELS
from chat_workflow_handlers import (
    handle_github_admin_commands,
    handle_tool_intent,
    handle_tools_list,
)
from gateway_dispatch import dispatch_skill
from gateway_gh2mcp import get_default_github_repo, resolve_repo_id_template
from gateway_github import (
    default_draft_name,
    is_github_token_save_command,
    is_github_token_sync_command,
    is_org_list_command,
    is_org_set_command,
    is_repo_list_command,
)
from gateway_jobs import load_job, queue_workflow_job, save_job, update_job
from gateway_models import ChatCompletionRequest
from gateway_prompt import (
    message_content_to_text,
    parse_bool,
    parse_prompt_context,
    parse_tool_intent,
)
from gateway_render import render_chat_content
from gateway_tenants import get_preferred_repo, track_repo_usage


def _audit(event: dict) -> None:
    import server as gateway

    gateway.audit(event)


async def run_chat_workflow(
    tenant: dict,
    *,
    skill: str,
    job_id: str,
    user_msg: str,
    prompt_ctx: dict[str, str],
    token_save_command: bool,
    token_sync_command: bool,
    org_set_command: bool,
    org_list_command: bool,
    repo_list_command: bool,
    tool_intent: dict[str, Any] | None,
    force_tool_skill: bool,
    tenant_id: str,
    repo_id_input: str | None,
    repo_url: str | None,
    github_token: str | None,
    source_path: str | None,
    branch: str,
    user_request: str,
    execute_commit: bool,
    push_after_tests: bool,
    create_draft_branch: bool,
    draft_name_input: str | None,
    open_pull_request: bool,
    pr_title: str | None,
    pr_body: str | None,
    pr_base: str,
    test_command: str,
    push_remote: str,
    async_mode: bool,
) -> dict[str, Any]:
    if skill in {"analyze", "refactor"} and not repo_id_input:
        github_default = await get_default_github_repo()
        if github_default:
            repo_id_input = github_default["repo_id"]
            if not repo_url:
                repo_url = github_default.get("repo_url")
        else:
            repo_id_input = f"{tenant_id}/default"

    admin_result = await handle_github_admin_commands(
        tenant=tenant,
        user_msg=user_msg,
        prompt_ctx=prompt_ctx,
        user_request=user_request,
        org_set_command=org_set_command,
        org_list_command=org_list_command,
        repo_list_command=repo_list_command,
        token_save_command=token_save_command,
        token_sync_command=token_sync_command,
    )
    if admin_result is not None:
        return admin_result

    if skill == "github_qa":
        gw = __import__("server")
        return await gw._run_github_qa(
            user_request=user_request,
            repo_id=repo_id_input,
            repo_url=repo_url,
        )

    tools_list_result = await handle_tools_list(
        tenant_id=tenant_id,
        user_msg=user_msg,
        user_request=user_request,
        force_tool_skill=force_tool_skill,
    )
    if tools_list_result is not None:
        return tools_list_result

    tool_result = await handle_tool_intent(
        tenant=tenant,
        tenant_id=tenant_id,
        tool_intent=tool_intent,
        repo_id_input=repo_id_input,
        repo_url=repo_url,
        user_request=user_request,
    )
    if tool_result is not None:
        return tool_result

    try:
        resolved_repo_id, repo_selection = await resolve_repo_id_template(repo_id_input)
        resolved_repo_url = (repo_selection or {}).get("repo_url") if not repo_url else None
        effective_repo_url = repo_url or resolved_repo_url
        draft_name = draft_name_input or default_draft_name(resolved_repo_id)
        dispatch_payload = {
            "skill": skill,
            "tenant": tenant,
            "repo_id": resolved_repo_id,
            "repo_url": effective_repo_url,
            "github_token": github_token,
            "source_path": source_path,
            "branch": branch,
            "user_request": user_request,
            "execute_commit": execute_commit,
            "push_after_tests": push_after_tests,
            "create_draft_branch": create_draft_branch,
            "draft_name": draft_name,
            "open_pull_request": open_pull_request,
            "pr_title": pr_title,
            "pr_body": pr_body,
            "pr_base": pr_base,
            "test_command": test_command,
            "push_remote": push_remote,
            "repo_selection": repo_selection,
        }

        queue_error: str | None = None
        if async_mode and skill in {"analyze", "refactor"}:
            try:
                queue_workflow_job(job_id, dispatch_payload)
                update_job(
                    job_id,
                    status="queued",
                    phase="queued",
                    tenant=tenant["tenant_id"],
                    skill=skill,
                    repo_id=resolved_repo_id,
                    branch=branch,
                )
                return {
                    "skill": "queued",
                    "status": "queued",
                    "tenant": tenant["tenant_id"],
                    "repo_id": resolved_repo_id,
                    "branch": branch,
                    "job_id": job_id,
                    "note": "Workflow uruchomiony w tle (Redis/RQ worker).",
                }
            except Exception as exc:
                queue_error = str(exc)
                update_job(job_id, queue_error=queue_error)

        result = await dispatch_skill(
            skill=skill,
            tenant=tenant,
            repo_id=resolved_repo_id,
            repo_url=effective_repo_url,
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
            job_id=job_id,
        )
        if repo_selection:
            result["repo_selection"] = repo_selection
        if queue_error:
            fallback_note = (
                "Queue unavailable; executed synchronously instead. "
                f"Reason: {queue_error}"
            )
            existing_note = result.get("note")
            result["note"] = f"{existing_note} {fallback_note}" if existing_note else fallback_note
        if resolved_repo_id and not result.get("error"):
            track_repo_usage(tenant_id, resolved_repo_id, platform="github")
        return result
    except Exception as exc:
        return {"error": str(exc)}


async def handle_chat_completions(req: ChatCompletionRequest, tenant: dict) -> Any:
    if req.model not in SKILL_MODELS:
        raise HTTPException(status_code=404, detail=f"Unknown model: {req.model}")

    skill = SKILL_MODELS[req.model]["skill"]
    if not tenant.get("features", {}).get(skill, False):
        raise HTTPException(status_code=403, detail=f"Feature '{skill}' not enabled for tenant")

    job_id = uuid.uuid4().hex
    save_job(
        job_id,
        {
            "status": "pending",
            "tenant": tenant["tenant_id"],
            "skill": skill,
            "created_at": time.time(),
        },
    )
    _audit({"event": "chat_completions", "tenant": tenant["tenant_id"], "model": req.model, "job_id": job_id})

    user_msg = next(
        (message_content_to_text(m.content) for m in reversed(req.messages) if m.role == "user"),
        "",
    )
    prompt_ctx = parse_prompt_context(user_msg)
    token_save_command = is_github_token_save_command(user_msg, prompt_ctx)
    token_sync_command = is_github_token_sync_command(user_msg, prompt_ctx)
    org_set_command = is_org_set_command(user_msg)
    org_list_command = is_org_list_command(user_msg)
    repo_list_command = is_repo_list_command(user_msg)
    tool_intent = parse_tool_intent(user_msg, prompt_ctx)
    force_tool_skill = skill == "tool"
    if force_tool_skill and tool_intent is None:
        tool_intent = {"tool": None, "repo_url": None, "repo_id": None, "args": []}

    tenant_id = tenant["tenant_id"]
    preferred_repo = get_preferred_repo(tenant_id)
    repo_id_input = req.repo_id or prompt_ctx.get("repo_id") or preferred_repo
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
    draft_name_input = req.draft_name or prompt_ctx.get("draft_name")
    open_pull_request = req.open_pr if req.open_pr is not None else parse_bool(prompt_ctx.get("open_pr"), default=push_after_tests)
    pr_title = req.pr_title or prompt_ctx.get("pr_title")
    pr_body = req.pr_body or prompt_ctx.get("pr_body")
    pr_base = req.pr_base or prompt_ctx.get("pr_base") or branch
    test_command = req.test_command or prompt_ctx.get("test_command") or "python3 -m compileall -q ."
    push_remote = req.remote or prompt_ctx.get("remote") or "origin"
    async_mode = MCP_ASYNC_ENABLED if req.async_mode is None else req.async_mode

    workflow_kwargs = {
        "tenant": tenant,
        "skill": skill,
        "job_id": job_id,
        "user_msg": user_msg,
        "prompt_ctx": prompt_ctx,
        "token_save_command": token_save_command,
        "token_sync_command": token_sync_command,
        "org_set_command": org_set_command,
        "org_list_command": org_list_command,
        "repo_list_command": repo_list_command,
        "tool_intent": tool_intent,
        "force_tool_skill": force_tool_skill,
        "tenant_id": tenant_id,
        "repo_id_input": repo_id_input,
        "repo_url": repo_url,
        "github_token": github_token,
        "source_path": source_path,
        "branch": branch,
        "user_request": user_request,
        "execute_commit": execute_commit,
        "push_after_tests": push_after_tests,
        "create_draft_branch": create_draft_branch,
        "draft_name_input": draft_name_input,
        "open_pull_request": open_pull_request,
        "pr_title": pr_title,
        "pr_body": pr_body,
        "pr_base": pr_base,
        "test_command": test_command,
        "push_remote": push_remote,
        "async_mode": async_mode,
    }

    completion_id = f"chatcmpl-{job_id}"
    created = int(time.time())

    if req.stream:

        async def event_stream():
            task = asyncio.create_task(run_chat_workflow(**workflow_kwargs))
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
            if result.get("skill") != "queued":
                update_job(job_id, status="done", phase="done", result=result, completed_at=time.time())

            content = render_chat_content(result)
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

            if result.get("skill") == "queued":
                last_marker = "queued"
                while True:
                    await asyncio.sleep(JOB_POLL_INTERVAL_SECONDS)
                    state = load_job(job_id) or {}
                    status = state.get("status") or "queued"
                    phase = state.get("phase") or status
                    marker = f"{status}:{phase}"
                    if marker != last_marker:
                        yield {
                            "data": json.dumps(
                                {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": req.model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {"content": f"\n\n_Status: `{phase}`_"},
                                            "finish_reason": None,
                                        }
                                    ],
                                },
                                ensure_ascii=False,
                            )
                        }
                        last_marker = marker
                    if status == "done":
                        final_result = state.get("result") or {
                            "error": "Job finished but no result payload",
                        }
                        yield {
                            "data": json.dumps(
                                {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": req.model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {"content": f"\n\n{render_chat_content(final_result)}"},
                                            "finish_reason": None,
                                        }
                                    ],
                                },
                                ensure_ascii=False,
                            )
                        }
                        break
                    if status == "failed":
                        error_result = {"error": state.get("error") or "Unknown background job error"}
                        yield {
                            "data": json.dumps(
                                {
                                    "id": completion_id,
                                    "object": "chat.completion.chunk",
                                    "created": created,
                                    "model": req.model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {"content": f"\n\n{render_chat_content(error_result)}"},
                                            "finish_reason": None,
                                        }
                                    ],
                                },
                                ensure_ascii=False,
                            )
                        }
                        break

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

    result = await run_chat_workflow(**workflow_kwargs)
    if result.get("skill") != "queued":
        update_job(job_id, status="done", phase="done", result=result, completed_at=time.time())
    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": render_chat_content(result)},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "job_id": job_id,
    }
