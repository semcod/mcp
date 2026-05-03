from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI
from pydantic import BaseModel

from .sync import GitHubTokenSyncService

ENV_FILE = os.getenv("GH2MCP_ENV_FILE", "/app/.env")
SYNC_ON_START = os.getenv("GH2MCP_SYNC_ON_START", "true").lower() in {"1", "true", "yes"}
SYNC_INTERVAL = int(os.getenv("GH2MCP_SYNC_INTERVAL", "0"))

app = FastAPI(title="gh2mcp", version="0.1.0")
service = GitHubTokenSyncService(ENV_FILE)


class SyncTokenRequest(BaseModel):
    force_gh_cli: bool = False


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
def status() -> dict:
    return service.get_status()


@app.post("/sync/token")
def sync_token(payload: SyncTokenRequest) -> dict:
    return service.sync_token(force_gh_cli=payload.force_gh_cli)
