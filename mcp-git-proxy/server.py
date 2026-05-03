from __future__ import annotations

import base64
import os
import subprocess
import tarfile
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from git2mcp.proxy import GitProxyManager


class SyncRepoRequest(BaseModel):
    repo_id: str
    repo_url: str | None = None
    source_path: str | None = None
    branch: str = "main"


class ExportPackageRequest(BaseModel):
    repo_id: str
    ref: str = "HEAD"


class ExportFragmentsRequest(BaseModel):
    repo_id: str
    ref: str = "HEAD"
    max_fragment_bytes: int = 200_000


class CommitRequest(BaseModel):
    message: str
    changes: list[dict] = Field(default_factory=list)
    author_name: str = "git2mcp-bot"
    author_email: str = "git2mcp@local"


class PushRequest(BaseModel):
    remote: str = "origin"
    branch: str | None = None


class RunTestsRequest(BaseModel):
    command: str = "python3 -m compileall -q ."


class ImportPackageRequest(BaseModel):
    repo_id: str
    archive_b64: str
    branch: str = "main"


app = FastAPI(title="mcp-git-proxy", version="0.1.0")
manager = GitProxyManager(
    base_dir=os.getenv("GIT_PROXY_REPO_ROOT", "/git-repos"),
    cache_dir=os.getenv("GIT_PROXY_CACHE_ROOT", "/git-cache"),
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "mcp-git-proxy"}


@app.get("/repos")
def list_repos():
    return manager.list_repos()


@app.post("/repos/sync")
def sync_repo(request: SyncRepoRequest):
    try:
        return manager.sync_repo(
            repo_id=request.repo_id,
            repo_url=request.repo_url,
            source_path=request.source_path,
            branch=request.branch,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/packages/export-fragments")
def export_fragments(request: ExportFragmentsRequest):
    try:
        return manager.export_fragments(
            repo_id=request.repo_id,
            ref=request.ref,
            max_fragment_bytes=request.max_fragment_bytes,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/packages/export")
def export_package(request: ExportPackageRequest):
    try:
        return manager.export_package(request.repo_id, request.ref)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/packages/import")
def import_package(request: ImportPackageRequest):
    repo_path = Path(os.getenv("GIT_PROXY_REPO_ROOT", "/git-repos")) / request.repo_id
    repo_path.mkdir(parents=True, exist_ok=True)

    archive = base64.b64decode(request.archive_b64)
    with tarfile.open(fileobj=BytesIO(archive), mode="r:gz") as tar:
        tar.extractall(repo_path)

    return {"repo_id": request.repo_id, "imported_to": str(repo_path)}


@app.post("/repos/{repo_id:path}/commit")
def commit(repo_id: str, request: CommitRequest):
    try:
        return manager.commit_changes(
            repo_id=repo_id,
            message=request.message,
            changes=request.changes,
            author_name=request.author_name,
            author_email=request.author_email,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/push")
def push(repo_id: str, request: PushRequest):
    try:
        return manager.push(repo_id, remote=request.remote, branch=request.branch)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/run-tests")
def run_tests(repo_id: str, request: RunTestsRequest):
    repo_path = Path(os.getenv("GIT_PROXY_REPO_ROOT", "/git-repos")) / repo_id
    if not repo_path.exists():
        raise HTTPException(status_code=404, detail=f"Repo not found: {repo_id}")

    process = subprocess.run(
        request.command,
        shell=True,
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    return {
        "repo_id": repo_id,
        "command": request.command,
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "ok": process.returncode == 0,
    }
