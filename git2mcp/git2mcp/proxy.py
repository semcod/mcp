from __future__ import annotations

import base64
import io
import shutil
import subprocess
import tarfile
from pathlib import Path
from urllib.parse import urlparse, unquote

from git import Repo, Actor
from git.remote import PushInfo


class GitProxyManager:
    def __init__(self, base_dir: str = "/git-repos", cache_dir: str = "/git-cache"):
        self.base_dir = Path(base_dir)
        self.cache_dir = Path(cache_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _repo_path(self, repo_id: str) -> Path:
        return self.base_dir / repo_id

    def _ensure_parent(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)

    def _allow_local_repo_url(self, repo_url: str | None) -> None:
        if not repo_url:
            return

        local_path = None
        if repo_url.startswith("file://"):
            parsed = urlparse(repo_url)
            local_path = unquote(parsed.path)
        elif repo_url.startswith("/"):
            local_path = repo_url

        if not local_path:
            return

        path = Path(local_path)
        if not path.exists():
            return

        safe_paths = {path}
        if path.is_dir() and (path / ".git").exists():
            safe_paths.add(path / ".git")

        for safe_path in safe_paths:
            subprocess.run(
                ["git", "config", "--global", "--add", "safe.directory", str(safe_path)],
                check=False,
                capture_output=True,
                text=True,
            )

    def list_repos(self) -> list[dict]:
        repos = []
        for dot_git in self.base_dir.glob("**/.git"):
            repo_root = dot_git.parent
            rel = repo_root.relative_to(self.base_dir)
            repo = Repo(repo_root)
            repos.append(
                {
                    "repo_id": str(rel),
                    "path": str(repo_root),
                    "active_branch": repo.active_branch.name if not repo.head.is_detached else "DETACHED",
                    "last_commit": repo.head.commit.hexsha,
                }
            )
        return repos

    def sync_repo(
        self,
        repo_id: str,
        repo_url: str | None = None,
        source_path: str | None = None,
        branch: str = "main",
    ) -> dict:
        repo_path = self._repo_path(repo_id)
        if source_path:
            source = Path(source_path)
            if not source.exists():
                raise FileNotFoundError(f"Source path does not exist: {source_path}")
            repo_path.parent.mkdir(parents=True, exist_ok=True)
            if repo_path.exists():
                shutil.rmtree(repo_path)
            if (source / ".git").exists():
                self._allow_local_repo_url(str(source.resolve()))
                Repo.clone_from(str(source.resolve()), str(repo_path))
                repo = Repo(repo_path)
            else:
                shutil.copytree(source, repo_path)
                repo = Repo.init(repo_path)
                repo.git.checkout("-b", branch)
                repo.git.add(all=True)
                if repo.is_dirty(untracked_files=True):
                    actor = Actor("git2mcp-bot", "git2mcp@local")
                    repo.index.commit("Initial import from source_path", author=actor, committer=actor)

            try:
                repo.git.checkout(branch)
            except Exception:
                pass
        elif repo_path.exists() and (repo_path / ".git").exists():
            repo = Repo(repo_path)
            repo.git.fetch("--all")
            try:
                repo.git.checkout(branch)
            except Exception:
                pass
            try:
                repo.git.pull("origin", branch)
            except Exception:
                pass
        elif repo_url:
            repo_path.parent.mkdir(parents=True, exist_ok=True)
            self._allow_local_repo_url(repo_url)
            Repo.clone_from(repo_url, str(repo_path), branch=branch)
            repo = Repo(repo_path)
        else:
            raise ValueError("Either repo_url or source_path must be provided")

        return {
            "repo_id": repo_id,
            "path": str(repo_path),
            "head": repo.head.commit.hexsha,
        }

    def export_package(self, repo_id: str, ref: str = "HEAD") -> dict:
        repo_path = self._repo_path(repo_id)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo not found: {repo_id}")

        repo = Repo(repo_path)
        commit = repo.commit(ref)
        tree = commit.tree

        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            for blob in tree.traverse():
                if blob.type != "blob":
                    continue
                if "/.git/" in blob.path or blob.path.startswith(".git/"):
                    continue
                data = blob.data_stream.read()
                tar_info = tarfile.TarInfo(name=blob.path)
                tar_info.size = len(data)
                tar.addfile(tarinfo=tar_info, fileobj=io.BytesIO(data))

        encoded = base64.b64encode(tar_buffer.getvalue()).decode("utf-8")
        return {
            "repo_id": repo_id,
            "ref": commit.hexsha,
            "archive_b64": encoded,
            "encoding": "base64+tar.gz",
        }

    def export_fragments(self, repo_id: str, ref: str = "HEAD", max_fragment_bytes: int = 200_000) -> dict:
        repo_path = self._repo_path(repo_id)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo not found: {repo_id}")

        repo = Repo(repo_path)
        commit = repo.commit(ref)
        tree = commit.tree

        fragments: list[dict] = []
        current_files: list[dict] = []
        current_size = 0
        total_files = 0

        for blob in tree.traverse():
            if blob.type != "blob":
                continue
            if "/.git/" in blob.path or blob.path.startswith(".git/"):
                continue

            data = blob.data_stream.read()
            encoded = base64.b64encode(data).decode("utf-8")
            item = {
                "path": blob.path,
                "content_b64": encoded,
            }
            item_size = len(blob.path) + len(encoded)

            if current_files and current_size + item_size > max_fragment_bytes:
                fragments.append(
                    {
                        "index": len(fragments),
                        "files": current_files,
                        "bytes": current_size,
                    }
                )
                current_files = []
                current_size = 0

            current_files.append(item)
            current_size += item_size
            total_files += 1

        if current_files:
            fragments.append(
                {
                    "index": len(fragments),
                    "files": current_files,
                    "bytes": current_size,
                }
            )

        return {
            "repo_id": repo_id,
            "ref": commit.hexsha,
            "mode": "fragments",
            "total_files": total_files,
            "fragment_count": len(fragments),
            "fragments": fragments,
        }

    def commit_changes(
        self,
        repo_id: str,
        message: str,
        changes: list[dict],
        author_name: str,
        author_email: str,
    ) -> dict:
        repo_path = self._repo_path(repo_id)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo not found: {repo_id}")

        repo = Repo(repo_path)
        for change in changes:
            path = change["path"]
            content = change.get("content", "")
            mode = change.get("mode", "update")
            absolute = repo_path / path
            self._ensure_parent(absolute)

            if mode == "delete":
                if absolute.exists():
                    absolute.unlink()
                repo.index.remove([path], working_tree=True, ignore_unmatch=True)
                continue

            absolute.write_text(content, encoding="utf-8")
            repo.index.add([path])

        actor = Actor(author_name, author_email)
        commit = repo.index.commit(message, author=actor, committer=actor)
        return {
            "repo_id": repo_id,
            "commit": commit.hexsha,
            "message": message,
        }

    def push(self, repo_id: str, remote: str = "origin", branch: str | None = None) -> dict:
        repo_path = self._repo_path(repo_id)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo not found: {repo_id}")

        repo = Repo(repo_path)
        if branch is None:
            branch = repo.active_branch.name

        remote_ref = repo.remote(remote)
        remote_urls = list(remote_ref.urls)
        if remote_urls:
            self._allow_local_repo_url(remote_urls[0])

        result = remote_ref.push(branch)

        error_flags = (
            PushInfo.ERROR
            | PushInfo.REJECTED
            | PushInfo.REMOTE_REJECTED
            | PushInfo.REMOTE_FAILURE
            | PushInfo.NO_MATCH
        )
        for push_info in result:
            if push_info.flags & error_flags:
                raise RuntimeError(f"Push failed: {push_info.summary}")

        return {
            "repo_id": repo_id,
            "remote": remote,
            "branch": branch,
            "result": [info.summary for info in result],
        }

    def worktree_write(self, repo_id: str, path: str, content: str, encoding: str = "utf-8") -> dict:
        repo_path = self._repo_path(repo_id)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo not found: {repo_id}")
        target = (repo_path / path).resolve()
        if not str(target).startswith(str(repo_path.resolve())):
            raise ValueError("Path traversal outside repo is not allowed")
        self._ensure_parent(target)
        target.write_text(content, encoding=encoding)
        return {"repo_id": repo_id, "path": path, "bytes": len(content.encode(encoding))}

    def worktree_read(self, repo_id: str, path: str, encoding: str = "utf-8") -> dict:
        repo_path = self._repo_path(repo_id)
        target = (repo_path / path).resolve()
        if not str(target).startswith(str(repo_path.resolve())):
            raise ValueError("Path traversal outside repo is not allowed")
        if not target.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return {"repo_id": repo_id, "path": path, "content": target.read_text(encoding=encoding)}

    def worktree_diff(self, repo_id: str, staged: bool = False) -> dict:
        repo_path = self._repo_path(repo_id)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo not found: {repo_id}")
        repo = Repo(repo_path)
        args = ["--cached"] if staged else []
        diff_text = repo.git.diff(*args)
        return {"repo_id": repo_id, "staged": staged, "diff": diff_text}

    def patch_apply(self, repo_id: str, patch: str, check_only: bool = False) -> dict:
        repo_path = self._repo_path(repo_id)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo not found: {repo_id}")
        cmd = ["git", "apply"]
        if check_only:
            cmd.append("--check")
        cmd.append("-")
        proc = subprocess.run(
            cmd,
            cwd=repo_path,
            input=patch,
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"git apply failed: {proc.stderr.strip() or proc.stdout.strip()}")
        return {"repo_id": repo_id, "applied": not check_only, "checked": check_only}

    def stage(self, repo_id: str, paths: list[str] | None = None) -> dict:
        repo_path = self._repo_path(repo_id)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo not found: {repo_id}")
        repo = Repo(repo_path)
        if paths:
            repo.index.add(paths)
        else:
            repo.git.add(A=True)
        return {"repo_id": repo_id, "staged": paths or "all"}

    def stash_save(self, repo_id: str, message: str = "git2mcp stash") -> dict:
        repo_path = self._repo_path(repo_id)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo not found: {repo_id}")
        repo = Repo(repo_path)
        try:
            output = repo.git.stash("push", "-u", "-m", message)
        except Exception as exc:
            raise RuntimeError(f"git stash failed: {exc}") from exc
        return {"repo_id": repo_id, "output": output}

    def stash_pop(self, repo_id: str) -> dict:
        repo_path = self._repo_path(repo_id)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo not found: {repo_id}")
        repo = Repo(repo_path)
        try:
            output = repo.git.stash("pop")
        except Exception as exc:
            raise RuntimeError(f"git stash pop failed: {exc}") from exc
        return {"repo_id": repo_id, "output": output}

    def branch_draft(self, repo_id: str, name: str, base: str | None = None) -> dict:
        repo_path = self._repo_path(repo_id)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo not found: {repo_id}")
        repo = Repo(repo_path)
        full_name = name if name.startswith("draft/") else f"draft/{name}"
        if base:
            repo.git.checkout("-B", full_name, base)
        else:
            repo.git.checkout("-B", full_name)
        return {"repo_id": repo_id, "branch": full_name, "head": repo.head.commit.hexsha}

    def checkpoint_create(self, repo_id: str, label: str | None = None) -> dict:
        repo_path = self._repo_path(repo_id)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo not found: {repo_id}")
        ckpt_dir = self.cache_dir / "checkpoints" / repo_id
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone
        ckpt_id = label or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        archive = ckpt_dir / f"{ckpt_id}.tar"
        with tarfile.open(archive, "w") as tar:
            for entry in repo_path.iterdir():
                if entry.name == ".git":
                    continue
                tar.add(entry, arcname=entry.name)
        return {"repo_id": repo_id, "checkpoint_id": ckpt_id, "archive": str(archive)}

    def checkpoint_restore(self, repo_id: str, checkpoint_id: str) -> dict:
        repo_path = self._repo_path(repo_id)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo not found: {repo_id}")
        archive = self.cache_dir / "checkpoints" / repo_id / f"{checkpoint_id}.tar"
        if not archive.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_id}")
        for entry in repo_path.iterdir():
            if entry.name == ".git":
                continue
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        with tarfile.open(archive, "r") as tar:
            tar.extractall(repo_path, filter="data")
        return {"repo_id": repo_id, "restored_from": checkpoint_id}

    def reset(self, repo_id: str, ref: str = "HEAD~1", mode: str = "hard") -> dict:
        repo_path = self._repo_path(repo_id)
        if not repo_path.exists():
            raise FileNotFoundError(f"Repo not found: {repo_id}")

        if mode not in {"hard", "soft", "mixed"}:
            raise ValueError(f"Unsupported reset mode: {mode}")

        repo = Repo(repo_path)
        previous = repo.head.commit.hexsha
        repo.git.reset(f"--{mode}", ref)
        current = repo.head.commit.hexsha
        return {
            "repo_id": repo_id,
            "mode": mode,
            "ref": ref,
            "previous_commit": previous,
            "current_commit": current,
        }
