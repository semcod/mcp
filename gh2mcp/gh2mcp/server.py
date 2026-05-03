from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI
from fastapi import Query
from pydantic import BaseModel

from .sync import GitHubTokenSyncService

ENV_FILE = os.getenv("GH2MCP_ENV_FILE", "/app/.env")
SYNC_ON_START = os.getenv("GH2MCP_SYNC_ON_START", "true").lower() in {"1", "true", "yes"}
SYNC_INTERVAL = int(os.getenv("GH2MCP_SYNC_INTERVAL", "0"))

app = FastAPI(title="gh2mcp", version="0.1.0")
service = GitHubTokenSyncService(ENV_FILE)


class SyncTokenRequest(BaseModel):
    force_gh_cli: bool = False
    include_token: bool = False


class SetOrgRequest(BaseModel):
    org: str | None = None


class ListOrgsRequest(BaseModel):
    repos_limit: int = 30


class LastPushedRepoRequest(BaseModel):
    owner: str | None = None
    limit: int = 100


_sync_task: asyncio.Task | None = None


async def _periodic_sync() -> None:
    while True:
        service.sync_token(force_gh_cli=False)
        await asyncio.sleep(SYNC_INTERVAL)


@app.on_event("startup")
async def on_startup() -> None:
    global _sync_task
    if SYNC_ON_START:
        service.sync_token(force_gh_cli=False)

    if SYNC_INTERVAL > 0:
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
def status(include_token: bool = Query(False)) -> dict:
    return service.get_status(include_token=include_token)


@app.post("/sync/token")
def sync_token(payload: SyncTokenRequest) -> dict:
    return service.sync_token(
        force_gh_cli=payload.force_gh_cli,
        include_token=payload.include_token,
    )


@app.post("/org/set")
def set_org(payload: SetOrgRequest) -> dict:
    return service.set_org(org=payload.org)


@app.post("/org/list")
def list_orgs(payload: ListOrgsRequest) -> dict:
    return service.list_orgs_and_repos(repos_limit=payload.repos_limit)


@app.post("/repo/last-pushed")
def last_pushed_repo(payload: LastPushedRepoRequest) -> dict:
    return service.get_last_pushed_repo(owner=payload.owner, limit=payload.limit)
