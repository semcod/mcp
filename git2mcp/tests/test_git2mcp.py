from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

from git import Repo
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
PROXY_SERVER_PATH = ROOT / "mcp-git-proxy" / "server.py"


def _load_proxy_app(repo_root: Path, cache_root: Path):
    os.environ["GIT_PROXY_REPO_ROOT"] = str(repo_root)
    os.environ["GIT_PROXY_CACHE_ROOT"] = str(cache_root)

    module_name = f"mcp_git_proxy_server_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, PROXY_SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.app


def _create_sample_repo_source(source: Path) -> None:
    source.mkdir(parents=True, exist_ok=True)
    (source / "main.py").write_text(
        "def greet(name: str) -> str:\n"
        "    return f'Hello {name}'\n",
        encoding="utf-8",
    )
    pkg = source / "pkg"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "util.py").write_text("VALUE = 42\n", encoding="utf-8")


def test_git_proxy_e2e_sync_export_commit_and_tests(tmp_path):
    repo_root = tmp_path / "git-repos"
    cache_root = tmp_path / "git-cache"
    app = _load_proxy_app(repo_root, cache_root)
    client = TestClient(app)

    source_repo = tmp_path / "source" / "sample-project"
    _create_sample_repo_source(source_repo)

    repo_id = "team/repo-a"

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    sync = client.post(
        "/repos/sync",
        json={
            "repo_id": repo_id,
            "source_path": str(source_repo),
            "branch": "main",
        },
    )
    assert sync.status_code == 200
    sync_payload = sync.json()
    assert sync_payload["repo_id"] == repo_id
    assert Path(sync_payload["path"]).exists()

    repos = client.get("/repos")
    assert repos.status_code == 200
    repo_ids = [item["repo_id"] for item in repos.json()]
    assert repo_id in repo_ids

    exported = client.post("/packages/export", json={"repo_id": repo_id, "ref": "HEAD"})
    assert exported.status_code == 200
    export_payload = exported.json()
    assert export_payload["repo_id"] == repo_id
    assert len(export_payload["archive_b64"]) > 20

    commit = client.post(
        f"/repos/{repo_id}/commit",
        json={
            "message": "test: add refactor metadata",
            "changes": [
                {
                    "path": ".mcp/refactor-plan.json",
                    "content": '{"ok": true}',
                    "mode": "update",
                }
            ],
            "author_name": "tester",
            "author_email": "tester@example.com",
        },
    )
    assert commit.status_code == 200
    commit_payload = commit.json()
    assert commit_payload["repo_id"] == repo_id
    assert len(commit_payload["commit"]) == 40

    tests = client.post(
        f"/repos/{repo_id}/run-tests",
        json={"command": "python3 -m compileall -q ."},
    )
    assert tests.status_code == 200
    tests_payload = tests.json()
    assert tests_payload["repo_id"] == repo_id
    assert tests_payload["ok"] is True


def test_git_proxy_e2e_push_to_bare_remote(tmp_path):
    repo_root = tmp_path / "git-repos"
    cache_root = tmp_path / "git-cache"
    app = _load_proxy_app(repo_root, cache_root)
    client = TestClient(app)

    bare_remote = tmp_path / "remote.git"
    Repo.init(bare_remote, bare=True)

    seed_worktree = tmp_path / "seed-worktree"
    seed_worktree.mkdir(parents=True, exist_ok=True)
    seed_repo = Repo.init(seed_worktree)
    (seed_worktree / "app.py").write_text(
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n",
        encoding="utf-8",
    )
    seed_repo.git.add(all=True)
    seed_repo.index.commit("seed: initial commit")
    try:
        seed_repo.git.checkout("-b", "main")
    except Exception:
        seed_repo.git.checkout("main")
    seed_repo.create_remote("origin", str(bare_remote))
    seed_repo.remote("origin").push("main")

    repo_id = "team/repo-push"
    sync = client.post(
        "/repos/sync",
        json={
            "repo_id": repo_id,
            "repo_url": str(bare_remote),
            "branch": "main",
        },
    )
    assert sync.status_code == 200

    commit = client.post(
        f"/repos/{repo_id}/commit",
        json={
            "message": "test: push through proxy",
            "changes": [
                {
                    "path": ".mcp/push-check.json",
                    "content": '{"pushed": true}',
                    "mode": "update",
                }
            ],
            "author_name": "tester",
            "author_email": "tester@example.com",
        },
    )
    assert commit.status_code == 200
    commit_payload = commit.json()
    assert len(commit_payload["commit"]) == 40

    tests = client.post(
        f"/repos/{repo_id}/run-tests",
        json={"command": "python3 -m compileall -q ."},
    )
    assert tests.status_code == 200
    assert tests.json()["ok"] is True

    pushed = client.post(
        f"/repos/{repo_id}/push",
        json={"remote": "origin", "branch": "main"},
    )
    assert pushed.status_code == 200

    verify_clone = tmp_path / "verify-clone"
    Repo.clone_from(str(bare_remote), verify_clone, branch="main")
    pushed_file = verify_clone / ".mcp" / "push-check.json"
    assert pushed_file.exists()
    assert pushed_file.read_text(encoding="utf-8") == '{"pushed": true}'
