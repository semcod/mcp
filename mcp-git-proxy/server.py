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


class ResetRequest(BaseModel):
    ref: str = "HEAD~1"
    mode: str = "hard"


class ImportPackageRequest(BaseModel):
    repo_id: str
    archive_b64: str
    branch: str = "main"


class WorktreeWriteRequest(BaseModel):
    path: str
    content: str
    encoding: str = "utf-8"


class WorktreeReadRequest(BaseModel):
    path: str
    encoding: str = "utf-8"


class WorktreeDiffRequest(BaseModel):
    staged: bool = False


class PatchApplyRequest(BaseModel):
    patch: str
    check_only: bool = False


class StageRequest(BaseModel):
    paths: list[str] | None = None


class StashSaveRequest(BaseModel):
    message: str = "git2mcp stash"


class BranchDraftRequest(BaseModel):
    name: str
    base: str | None = None


class CheckpointCreateRequest(BaseModel):
    label: str | None = None


class CheckpointRestoreRequest(BaseModel):
    checkpoint_id: str


class SyncPullRequest(BaseModel):
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


@app.post("/repos/{repo_id:path}/reset")
def reset(repo_id: str, request: ResetRequest):
    try:
        return manager.reset(repo_id=repo_id, ref=request.ref, mode=request.mode)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/worktree/write")
def worktree_write(repo_id: str, request: WorktreeWriteRequest):
    try:
        return manager.worktree_write(repo_id, request.path, request.content, request.encoding)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/worktree/read")
def worktree_read(repo_id: str, request: WorktreeReadRequest):
    try:
        return manager.worktree_read(repo_id, request.path, request.encoding)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/worktree/diff")
def worktree_diff(repo_id: str, request: WorktreeDiffRequest):
    try:
        return manager.worktree_diff(repo_id, staged=request.staged)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/patch/apply")
def patch_apply(repo_id: str, request: PatchApplyRequest):
    try:
        return manager.patch_apply(repo_id, request.patch, check_only=request.check_only)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/stage")
def stage(repo_id: str, request: StageRequest):
    try:
        return manager.stage(repo_id, paths=request.paths)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/stash/save")
def stash_save(repo_id: str, request: StashSaveRequest):
    try:
        return manager.stash_save(repo_id, message=request.message)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/stash/pop")
def stash_pop(repo_id: str):
    try:
        return manager.stash_pop(repo_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/branch/draft")
def branch_draft(repo_id: str, request: BranchDraftRequest):
    try:
        return manager.branch_draft(repo_id, name=request.name, base=request.base)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/checkpoint")
def checkpoint_create(repo_id: str, request: CheckpointCreateRequest):
    try:
        return manager.checkpoint_create(repo_id, label=request.label)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/checkpoint/restore")
def checkpoint_restore(repo_id: str, request: CheckpointRestoreRequest):
    try:
        return manager.checkpoint_restore(repo_id, checkpoint_id=request.checkpoint_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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


@app.post("/repos/{repo_id:path}/sync-pull")
def sync_pull(repo_id: str, request: SyncPullRequest):
    """Pull updates from remote for an existing repository."""
    repo_path = Path(os.getenv("GIT_PROXY_REPO_ROOT", "/git-repos")) / repo_id

    if not repo_path.exists():
        raise HTTPException(status_code=404, detail=f"Repo not found: {repo_id}")

    if not (repo_path / ".git").exists():
        raise HTTPException(status_code=400, detail=f"Not a git repository: {repo_id}")

    try:
        # Fetch from origin
        fetch_result = subprocess.run(
            ["git", "fetch", "origin"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60
        )

        if fetch_result.returncode != 0:
            raise HTTPException(
                status_code=400,
                detail=f"Fetch failed: {fetch_result.stderr}"
            )

        # Checkout and pull the requested branch
        checkout_result = subprocess.run(
            ["git", "checkout", request.branch],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        pull_result = subprocess.run(
            ["git", "pull", "origin", request.branch],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=60
        )

        # Get current commit
        commit_result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        commit = commit_result.stdout.strip() if commit_result.returncode == 0 else "unknown"

        return {
            "repo_id": repo_id,
            "branch": request.branch,
            "commit": commit,
            "message": f"Pulled latest changes from origin/{request.branch}",
            "pull_output": pull_result.stdout,
            "pull_stderr": pull_result.stderr,
            "success": pull_result.returncode == 0
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Pull operation timed out")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
