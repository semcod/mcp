"""Skill workflow orchestration: sync → analyze → optional commit/push/PR."""

from __future__ import annotations

from typing import Any

import httpx

from dispatch_refactor import dispatch_refactor_skill
from gateway_config import GIT_PROXY_URL
from gateway_github import inject_github_token, normalize_repo_url, redact_repo_url, save_github_token
from gateway_jobs import update_job
from gateway_skills import expect_json, run_skills_analysis


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
    job_id: str | None = None,
) -> dict:
    tenant_id = tenant["tenant_id"]
    github_config_result: dict[str, Any] | None = None
    if github_token:
        github_config_result = save_github_token(github_token)

    if job_id:
        update_job(job_id, status="analyzing", phase="analyzing")

    normalized_repo_url = normalize_repo_url(repo_url)
    safe_repo_url = redact_repo_url(normalized_repo_url)
    async with httpx.AsyncClient(timeout=300.0) as client:
        sync_payload: dict[str, Any] = {
            "repo_id": repo_id,
            "branch": branch,
        }
        if source_path:
            sync_payload["source_path"] = source_path
        if normalized_repo_url:
            sync_payload["repo_url"] = inject_github_token(normalized_repo_url)

        sync = await expect_json(
            await client.post(f"{GIT_PROXY_URL}/repos/sync", json=sync_payload),
            "git sync",
        )

        if skill == "analyze":
            analysis = await run_skills_analysis(client, repo_id, execute=False, user_request=user_request)
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
            return await dispatch_refactor_skill(
                client,
                tenant=tenant,
                tenant_id=tenant_id,
                repo_id=repo_id,
                repo_url=repo_url,
                safe_repo_url=safe_repo_url,
                source_path=source_path,
                branch=branch,
                user_request=user_request,
                sync=sync,
                github_config_result=github_config_result,
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

    raise ValueError(f"Unknown skill: {skill}")
