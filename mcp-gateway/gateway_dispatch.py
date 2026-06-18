"""Skill workflow orchestration: sync → analyze → optional commit/push/PR."""

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
    inject_github_token,
    normalize_repo_url,
    redact_repo_url,
    save_github_token,
)
from gateway_jobs import update_job
from gateway_render import build_commit_changes, summary_text
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
            summary_md = summary_text(analysis, user_request)

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
                        push_result = await expect_json(
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
                        github_repo = github_repo_from_url(repo_url)
                        if not github_repo:
                            execution["pull_request"] = {
                                "skipped": True,
                                "reason": "Repo URL is not a GitHub URL",
                            }
                        else:
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

    raise ValueError(f"Unknown skill: {skill}")
