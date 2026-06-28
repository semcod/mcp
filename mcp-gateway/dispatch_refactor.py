"""Refactor skill execution helpers (commit, push, PR) for gateway dispatch."""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx

from gateway_config import GIT_PROXY_URL
from gateway_github import (
    create_github_pr,
    default_pr_body,
    default_pr_title,
    github_repo_from_url,
)
from gateway_jobs import update_job
from gateway_render import build_commit_changes, summary_text
from gateway_skills import expect_json, run_skills_analysis


def build_execution_state(
    *,
    execute_commit: bool,
    push_after_tests: bool,
    create_draft_branch: bool,
    draft_name: str,
    open_pull_request: bool,
    pr_base: str,
    test_command: str,
    push_remote: str,
) -> dict[str, Any]:
    return {
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


async def maybe_push_after_tests(
    client: httpx.AsyncClient,
    *,
    tenant: dict,
    repo_id: str,
    working_branch: str,
    push_remote: str,
    tests_result: dict[str, Any],
    execution: dict[str, Any],
) -> None:
    if not execution.get("push_after_tests"):
        return

    if not tenant.get("features", {}).get("push", False):
        execution["push"] = {"skipped": True, "reason": "Tenant push feature disabled"}
        return
    if not tests_result.get("ok"):
        execution["push"] = {"skipped": True, "reason": "Tests failed"}
        return

    push_result = await expect_json(
        await client.post(
            f"{GIT_PROXY_URL}/repos/{repo_id}/push",
            json={"remote": push_remote, "branch": working_branch},
        ),
        "git push",
    )
    execution["push"] = push_result
    execution["pushed"] = True


async def maybe_open_pull_request(
    client: httpx.AsyncClient,
    *,
    repo_id: str,
    repo_url: str | None,
    working_branch: str,
    pr_base: str,
    pr_title: str | None,
    pr_body: str | None,
    user_request: str,
    execution: dict[str, Any],
) -> None:
    if not execution.get("open_pull_request"):
        return
    if not execution.get("pushed"):
        execution["pull_request"] = {"skipped": True, "reason": "Push was not executed"}
        return

    github_repo = github_repo_from_url(repo_url)
    if not github_repo:
        execution["pull_request"] = {"skipped": True, "reason": "Repo URL is not a GitHub URL"}
        return

    owner, repo_name = github_repo
    pr_result = await create_github_pr(
        client=client,
        owner=owner,
        repo=repo_name,
        head_branch=working_branch,
        base_branch=pr_base,
        title=pr_title or default_pr_title(repo_id, user_request),
        body=pr_body or default_pr_body(repo_id, user_request, pr_base),
        draft=True,
    )
    execution["pull_request"] = pr_result


async def execute_refactor_commit(
    client: httpx.AsyncClient,
    *,
    tenant: dict,
    repo_id: str,
    repo_url: str | None,
    branch: str,
    user_request: str,
    execute_commit: bool,
    create_draft_branch: bool,
    draft_name: str,
    open_pull_request: bool,
    pr_title: str | None,
    pr_body: str | None,
    pr_base: str,
    test_command: str,
    push_remote: str,
    plan_payload: dict[str, Any],
    summary_md: str,
    execution: dict[str, Any],
    job_id: str | None,
) -> tuple[str, str]:
    working_branch = branch
    base_branch = branch

    if not execute_commit:
        return working_branch, base_branch

    if create_draft_branch:
        draft_result = await expect_json(
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
        "changes": build_commit_changes(plan_payload, summary_md),
        "author_name": "mcp-gateway-bot",
        "author_email": "mcp-gateway@local",
    }
    commit_result = await expect_json(
        await client.post(f"{GIT_PROXY_URL}/repos/{repo_id}/commit", json=commit_payload),
        "git commit",
    )
    if job_id:
        update_job(job_id, status="testing", phase="testing")

    tests_result = await expect_json(
        await client.post(
            f"{GIT_PROXY_URL}/repos/{repo_id}/run-tests",
            json={"command": test_command},
        ),
        "run tests",
    )
    execution.update({"committed": True, "commit": commit_result, "tests": tests_result})

    await maybe_push_after_tests(
        client,
        tenant=tenant,
        repo_id=repo_id,
        working_branch=working_branch,
        push_remote=push_remote,
        tests_result=tests_result,
        execution=execution,
    )
    await maybe_open_pull_request(
        client,
        repo_id=repo_id,
        repo_url=repo_url,
        working_branch=working_branch,
        pr_base=pr_base,
        pr_title=pr_title,
        pr_body=pr_body,
        user_request=user_request,
        execution=execution,
    )
    return working_branch, base_branch


async def dispatch_refactor_skill(
    client: httpx.AsyncClient,
    *,
    tenant: dict,
    tenant_id: str,
    repo_id: str,
    repo_url: str | None,
    safe_repo_url: str | None,
    source_path: str | None,
    branch: str,
    user_request: str,
    sync: dict[str, Any],
    github_config_result: dict[str, Any] | None,
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
    job_id: str | None,
) -> dict[str, Any]:
    if job_id:
        update_job(job_id, status="refactoring", phase="refactoring")

    ckpt = await expect_json(
        await client.post(
            f"{GIT_PROXY_URL}/repos/{repo_id}/checkpoint",
            json={"label": f"task-{uuid.uuid4().hex[:8]}"},
        ),
        "checkpoint create",
    )

    analysis = await run_skills_analysis(client, repo_id, execute=execute_commit, user_request=user_request)
    base_branch = branch
    plan_payload: dict[str, Any] = {
        "repo_id": repo_id,
        "tenant": tenant_id,
        "branch": branch,
        "base_branch": base_branch,
        "repo_url": safe_repo_url,
        "source_path": source_path,
        "user_request": user_request,
        "generated_at": int(time.time()),
        "analysis": analysis,
    }
    summary_md = summary_text(analysis, user_request)
    execution = build_execution_state(
        execute_commit=execute_commit,
        push_after_tests=push_after_tests,
        create_draft_branch=create_draft_branch,
        draft_name=draft_name,
        open_pull_request=open_pull_request,
        pr_base=pr_base,
        test_command=test_command,
        push_remote=push_remote,
    )

    working_branch, base_branch = await execute_refactor_commit(
        client,
        tenant=tenant,
        repo_id=repo_id,
        repo_url=repo_url,
        branch=branch,
        user_request=user_request,
        execute_commit=execute_commit,
        create_draft_branch=create_draft_branch,
        draft_name=draft_name,
        open_pull_request=open_pull_request,
        pr_title=pr_title,
        pr_body=pr_body,
        pr_base=pr_base,
        test_command=test_command,
        push_remote=push_remote,
        plan_payload=plan_payload,
        summary_md=summary_md,
        execution=execution,
        job_id=job_id,
    )

    diff = await expect_json(
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
