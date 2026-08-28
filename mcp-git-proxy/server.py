from __future__ import annotations

import base64
import os
import subprocess

import urllib.request
import urllib.error
import json as _json

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from git2mcp.proxy import GitProxyManager

_MUTATION_ENV = "GIT_PROXY_ALLOW_MUTATION"
_EXECUTE_ENV = "GIT_PROXY_ALLOW_EXECUTE"
_REMOTE_WRITE_ENV = "GIT_PROXY_ALLOW_REMOTE_WRITE"


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _require_capability(env_name: str, action: str) -> None:
    if not _env_enabled(env_name):
        raise PermissionError(
            f"Git proxy action '{action}' is disabled; start the service with {env_name}=1"
        )


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
    timeout_seconds: int = Field(default=600, ge=1, le=3600)


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


class CreateGithubRepoRequest(BaseModel):
    name: str
    description: str = ""
    private: bool = False
    auto_clone: bool = True
    branch: str = "main"
    github_token: str | None = None


app = FastAPI(title="mcp-git-proxy", version="0.1.0")
manager = GitProxyManager(
    base_dir=os.getenv("GIT_PROXY_REPO_ROOT", "/git-repos"),
    cache_dir=os.getenv("GIT_PROXY_CACHE_ROOT", "/git-cache"),
)


@app.exception_handler(PermissionError)
async def permission_error_handler(
    _request: Request,
    exc: PermissionError,
) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok", "service": "mcp-git-proxy"}


@app.get("/repos")
def list_repos():
    return manager.list_repos()


@app.post("/repos/sync")
def sync_repo(request: SyncRepoRequest):
    _require_capability(_MUTATION_ENV, "sync_repo")
    try:
        return manager.sync_repo(
            repo_id=request.repo_id,
            repo_url=request.repo_url,
            source_path=request.source_path,
            branch=request.branch,
        )
    except Exception as exc:
        detail = str(exc)
        if request.repo_url:
            safe_url = manager.redact_url_credentials(request.repo_url) or "<redacted-url>"
            detail = detail.replace(request.repo_url, safe_url)
        raise HTTPException(status_code=400, detail=detail) from exc


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
    _require_capability(_MUTATION_ENV, "import_package")
    try:
        archive = base64.b64decode(request.archive_b64, validate=True)
        return manager.import_package(request.repo_id, archive)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/commit")
def commit(repo_id: str, request: CommitRequest):
    _require_capability(_MUTATION_ENV, "commit")
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
    _require_capability(_REMOTE_WRITE_ENV, "push")
    try:
        return manager.push(repo_id, remote=request.remote, branch=request.branch)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/reset")
def reset(repo_id: str, request: ResetRequest):
    _require_capability(_MUTATION_ENV, "reset")
    try:
        return manager.reset(repo_id=repo_id, ref=request.ref, mode=request.mode)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/worktree/write")
def worktree_write(repo_id: str, request: WorktreeWriteRequest):
    _require_capability(_MUTATION_ENV, "worktree_write")
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
    if not request.check_only:
        _require_capability(_MUTATION_ENV, "patch_apply")
    try:
        return manager.patch_apply(repo_id, request.patch, check_only=request.check_only)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/stage")
def stage(repo_id: str, request: StageRequest):
    _require_capability(_MUTATION_ENV, "stage")
    try:
        return manager.stage(repo_id, paths=request.paths)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/stash/save")
def stash_save(repo_id: str, request: StashSaveRequest):
    _require_capability(_MUTATION_ENV, "stash_save")
    try:
        return manager.stash_save(repo_id, message=request.message)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/stash/pop")
def stash_pop(repo_id: str):
    _require_capability(_MUTATION_ENV, "stash_pop")
    try:
        return manager.stash_pop(repo_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/branch/draft")
def branch_draft(repo_id: str, request: BranchDraftRequest):
    _require_capability(_MUTATION_ENV, "branch_draft")
    try:
        return manager.branch_draft(repo_id, name=request.name, base=request.base)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/checkpoint")
def checkpoint_create(repo_id: str, request: CheckpointCreateRequest):
    _require_capability(_MUTATION_ENV, "checkpoint_create")
    try:
        return manager.checkpoint_create(repo_id, label=request.label)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/checkpoint/restore")
def checkpoint_restore(repo_id: str, request: CheckpointRestoreRequest):
    _require_capability(_MUTATION_ENV, "checkpoint_restore")
    try:
        return manager.checkpoint_restore(repo_id, checkpoint_id=request.checkpoint_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/repos/{repo_id:path}/run-tests")
def run_tests(repo_id: str, request: RunTestsRequest):
    _require_capability(_EXECUTE_ENV, "run_tests")
    try:
        repo_path = manager._repo_path(repo_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not repo_path.exists():
        raise HTTPException(status_code=404, detail=f"Repo not found: {repo_id}")

    try:
        process = subprocess.run(
            request.command,
            shell=True,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=request.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "repo_id": repo_id,
            "command": request.command,
            "returncode": None,
            "stdout": (exc.stdout or "")[-65_536:] if isinstance(exc.stdout, str) else "",
            "stderr": f"timeout after {request.timeout_seconds}s",
            "ok": False,
        }
    return {
        "repo_id": repo_id,
        "command": request.command,
        "returncode": process.returncode,
        "stdout": process.stdout[-65_536:],
        "stderr": process.stderr[-65_536:],
        "ok": process.returncode == 0,
    }


@app.post("/github/create-repo")
def github_create_repo(request: CreateGithubRepoRequest):
    """Create a new repository on GitHub via REST API, then optionally clone it locally."""
    _require_capability(_REMOTE_WRITE_ENV, "github_create_repo")
    token = request.github_token or os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(status_code=400, detail="No GitHub token available. Set GITHUB_PAT or pass github_token.")

    payload = _json.dumps({
        "name": request.name,
        "description": request.description,
        "private": request.private,
        "auto_init": True,
    }).encode()

    api_url = os.getenv("GITHUB_API_URL", "https://api.github.com")
    req = urllib.request.Request(
        f"{api_url}/user/repos",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            repo_data = _json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise HTTPException(status_code=exc.code, detail=f"GitHub API error: {body}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    result = {
        "github_repo": repo_data.get("full_name"),
        "html_url": repo_data.get("html_url"),
        "clone_url": repo_data.get("clone_url"),
        "private": repo_data.get("private"),
        "cloned_locally": False,
        "repo_id": None,
    }

    if request.auto_clone:
        clone_url = repo_data.get("clone_url", "")
        authenticated_clone_url = clone_url
        if clone_url.startswith("https://"):
            authenticated_clone_url = clone_url.replace("https://", f"https://{token}@")
        repo_id = request.name
        try:
            manager.sync_repo(
                repo_id=repo_id,
                repo_url=authenticated_clone_url,
                branch=request.branch,
            )
            repo = manager._repo_path(repo_id)
            subprocess.run(
                ["git", "-C", str(repo), "remote", "set-url", "origin", clone_url],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            result["cloned_locally"] = True
            result["repo_id"] = repo_id
        except Exception as exc:
            result["clone_error"] = str(exc).replace(token, "***")

    return result


@app.post("/repos/{repo_id:path}/sync-pull")
def sync_pull(repo_id: str, request: SyncPullRequest):
    """Pull updates from remote for an existing repository."""
    _require_capability(_MUTATION_ENV, "sync_pull")
    try:
        repo_path = manager._repo_path(repo_id)
        branch = manager._validate_git_arg(request.branch, label="branch")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
            ["git", "checkout", branch],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        if checkout_result.returncode != 0:
            raise HTTPException(
                status_code=400,
                detail=f"Checkout failed: {checkout_result.stderr}",
            )

        pull_result = subprocess.run(
            ["git", "pull", "origin", branch],
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
            "branch": branch,
            "commit": commit,
            "message": f"Pulled latest changes from origin/{branch}",
            "pull_output": pull_result.stdout,
            "pull_stderr": pull_result.stderr,
            "success": pull_result.returncode == 0
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Pull operation timed out")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
