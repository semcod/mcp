from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .sync import GitHubTokenSyncService

ENV_FILE = os.getenv("GH2MCP_ENV_FILE", "/app/.env")
SYNC_ON_START = os.getenv("GH2MCP_SYNC_ON_START", "false").lower() in {"1", "true", "yes"}
SYNC_INTERVAL = int(os.getenv("GH2MCP_SYNC_INTERVAL", "0"))
_MUTATION_ENV = "GH2MCP_ALLOW_MUTATION"

app = FastAPI(title="gh2mcp", version="0.1.0")
service = GitHubTokenSyncService(ENV_FILE)


class SyncTokenRequest(BaseModel):
    force_gh_cli: bool = False


class SetOrgRequest(BaseModel):
    org: str | None = None


class ListOrgsRequest(BaseModel):
    repos_limit: int = 30


class LastPushedRepoRequest(BaseModel):
    owner: str | None = None
    limit: int = 100


class RecentReposRequest(BaseModel):
    limit: int = 10
    owner: str | None = None
    include_orgs: bool = True


_sync_task: asyncio.Task | None = None


def _mutation_enabled() -> bool:
    return os.getenv(_MUTATION_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _require_mutation(action: str) -> None:
    if not _mutation_enabled():
        raise PermissionError(
            f"gh2mcp mutation '{action}' is disabled; start the service with {_MUTATION_ENV}=1"
        )


@app.exception_handler(PermissionError)
async def permission_error_handler(
    _request: Request,
    exc: PermissionError,
) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


async def _periodic_sync() -> None:
    while True:
        _require_mutation("periodic_sync")
        service.sync_token(force_gh_cli=False)
        await asyncio.sleep(SYNC_INTERVAL)


@app.on_event("startup")
async def on_startup() -> None:
    global _sync_task
    if SYNC_ON_START and _mutation_enabled():
        service.sync_token(force_gh_cli=False)

    if SYNC_INTERVAL > 0 and _mutation_enabled():
        _sync_task = asyncio.create_task(_periodic_sync())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global _sync_task
    if _sync_task:
        _sync_task.cancel()
        _sync_task = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "gh2mcp"}


@app.get("/status")
def status() -> dict:
    return service.get_status(include_token=False)


@app.post("/sync/token")
def sync_token(payload: SyncTokenRequest) -> dict:
    _require_mutation("sync_token")
    return service.sync_token(
        force_gh_cli=payload.force_gh_cli,
        include_token=False,
    )


@app.post("/org/set")
def set_org(payload: SetOrgRequest) -> dict:
    _require_mutation("set_org")
    return service.set_org(org=payload.org)


@app.post("/org/list")
def list_orgs(payload: ListOrgsRequest) -> dict:
    return service.list_orgs_and_repos(repos_limit=payload.repos_limit)


@app.post("/repo/last-pushed")
def last_pushed_repo(payload: LastPushedRepoRequest) -> dict:
    return service.get_last_pushed_repo(owner=payload.owner, limit=payload.limit)


@app.post("/repo/recent")
def recent_repos(payload: RecentReposRequest) -> dict:
    return service.get_recent_repos(
        limit=payload.limit,
        owner=payload.owner,
        include_orgs=payload.include_orgs,
    )
