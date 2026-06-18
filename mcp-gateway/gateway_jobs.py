"""Redis/RQ job store and background workflow execution for mcp-gateway."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from gateway_config import JOB_TTL_SECONDS, MCP_ASYNC_ENABLED, REDIS_URL, RQ_QUEUE_NAME

try:
    from redis import Redis
    from rq import Queue

    RQ_AVAILABLE = True
except Exception:
    Redis = None
    Queue = None
    RQ_AVAILABLE = False

JOBS: dict[str, dict] = {}
_REDIS_STATE_CLIENT: Any | None = None
_REDIS_RQ_CLIENT: Any | None = None
_RQ_QUEUE: Any | None = None


def job_storage_key(job_id: str) -> str:
    return f"mcp:job:{job_id}"


def get_state_redis_client() -> Any | None:
    global _REDIS_STATE_CLIENT
    if not RQ_AVAILABLE:
        return None
    if _REDIS_STATE_CLIENT is not None:
        return _REDIS_STATE_CLIENT
    try:
        _REDIS_STATE_CLIENT = Redis.from_url(REDIS_URL, decode_responses=True)
        _REDIS_STATE_CLIENT.ping()
        return _REDIS_STATE_CLIENT
    except Exception:
        _REDIS_STATE_CLIENT = None
        return None


def get_rq_redis_client() -> Any | None:
    global _REDIS_RQ_CLIENT
    if not RQ_AVAILABLE:
        return None
    if _REDIS_RQ_CLIENT is not None:
        return _REDIS_RQ_CLIENT
    try:
        _REDIS_RQ_CLIENT = Redis.from_url(REDIS_URL, decode_responses=False)
        _REDIS_RQ_CLIENT.ping()
        return _REDIS_RQ_CLIENT
    except Exception:
        _REDIS_RQ_CLIENT = None
        return None


def get_queue() -> Any | None:
    global _RQ_QUEUE
    if not MCP_ASYNC_ENABLED:
        return None
    if not RQ_AVAILABLE:
        return None
    if _RQ_QUEUE is not None:
        return _RQ_QUEUE
    redis_client = get_rq_redis_client()
    if redis_client is None:
        return None
    _RQ_QUEUE = Queue(name=RQ_QUEUE_NAME, connection=redis_client, default_timeout=900)
    return _RQ_QUEUE


def save_job(job_id: str, payload: dict[str, Any]) -> None:
    JOBS[job_id] = payload
    redis_client = get_state_redis_client()
    if redis_client is None:
        return
    try:
        redis_client.setex(
            job_storage_key(job_id),
            JOB_TTL_SECONDS,
            json.dumps(payload, ensure_ascii=False),
        )
    except Exception:
        return


def load_job(job_id: str) -> dict[str, Any] | None:
    redis_client = get_state_redis_client()
    if redis_client is not None:
        try:
            raw = redis_client.get(job_storage_key(job_id))
            if raw:
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    JOBS[job_id] = payload
                    return payload
        except Exception:
            pass
    return JOBS.get(job_id)


def update_job(job_id: str, **updates: Any) -> dict[str, Any]:
    current = load_job(job_id) or {}
    current.update(updates)
    current["updated_at"] = time.time()
    save_job(job_id, current)
    return current


def queue_workflow_job(job_id: str, payload: dict[str, Any]) -> None:
    queue = get_queue()
    if queue is None:
        raise RuntimeError("Async queue is unavailable (enable MCP_ASYNC_ENABLED and Redis/RQ)")
    queue.enqueue(
        "server.execute_dispatch_job",
        kwargs={"job_id": job_id, "payload": payload},
        job_id=job_id,
        result_ttl=JOB_TTL_SECONDS,
        failure_ttl=JOB_TTL_SECONDS,
    )


def execute_dispatch_job(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    from gateway_dispatch import dispatch_skill

    update_job(job_id, status="analyzing", phase="analyzing", started_at=time.time())
    try:
        result = asyncio.run(
            dispatch_skill(
                skill=payload["skill"],
                tenant=payload["tenant"],
                repo_id=payload["repo_id"],
                repo_url=payload.get("repo_url"),
                github_token=payload.get("github_token"),
                source_path=payload.get("source_path"),
                branch=payload["branch"],
                user_request=payload["user_request"],
                execute_commit=payload["execute_commit"],
                push_after_tests=payload["push_after_tests"],
                create_draft_branch=payload["create_draft_branch"],
                draft_name=payload["draft_name"],
                open_pull_request=payload["open_pull_request"],
                pr_title=payload.get("pr_title"),
                pr_body=payload.get("pr_body"),
                pr_base=payload["pr_base"],
                test_command=payload["test_command"],
                push_remote=payload["push_remote"],
                job_id=job_id,
            )
        )
        repo_selection = payload.get("repo_selection")
        if repo_selection:
            result["repo_selection"] = repo_selection
        update_job(
            job_id,
            status="done",
            phase="done",
            completed_at=time.time(),
            result=result,
        )
        return result
    except Exception as exc:
        update_job(
            job_id,
            status="failed",
            phase="failed",
            completed_at=time.time(),
            error=str(exc),
        )
        raise
