import asyncio

import httpx


class Git2MCPClient:
    def __init__(self, base_url: str, timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _request(self, method: str, path: str, payload=None):
        url = f"{self.base_url}{path}"
        last_error = None
        for _ in range(5):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(method, url, json=payload)
                response.raise_for_status()
                return response.json()
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                last_error = exc
                await asyncio.sleep(1)

        if last_error:
            raise last_error
        raise RuntimeError("git2mcp request failed without detailed error")

    async def health(self):
        return await self._request("GET", "/health")

    async def list_repos(self):
        return await self._request("GET", "/repos")

    async def sync_repo(self, repo_id: str, repo_url: str | None = None, source_path: str | None = None, branch: str = "main"):
        payload = {
            "repo_id": repo_id,
            "repo_url": repo_url,
            "source_path": source_path,
            "branch": branch,
        }
        return await self._request("POST", "/repos/sync", payload)

    async def export_package(self, repo_id: str, ref: str = "HEAD"):
        return await self._request("POST", "/packages/export", {"repo_id": repo_id, "ref": ref})

    async def commit_changes(self, repo_id: str, message: str, changes: list[dict], author_name: str = "git2mcp-bot", author_email: str = "git2mcp@local"):
        payload = {
            "repo_id": repo_id,
            "message": message,
            "changes": changes,
            "author_name": author_name,
            "author_email": author_email,
        }
        return await self._request("POST", f"/repos/{repo_id}/commit", payload)

    async def run_tests(self, repo_id: str, command: str):
        return await self._request("POST", f"/repos/{repo_id}/run-tests", {"command": command})

    async def push(self, repo_id: str, remote: str = "origin", branch: str | None = None):
        payload = {"remote": remote, "branch": branch}
        return await self._request("POST", f"/repos/{repo_id}/push", payload)

    async def reset(self, repo_id: str, ref: str = "HEAD~1", mode: str = "hard"):
        payload = {"ref": ref, "mode": mode}
        return await self._request("POST", f"/repos/{repo_id}/reset", payload)

    async def worktree_write(self, repo_id: str, path: str, content: str, encoding: str = "utf-8"):
        payload = {"path": path, "content": content, "encoding": encoding}
        return await self._request("POST", f"/repos/{repo_id}/worktree/write", payload)

    async def worktree_read(self, repo_id: str, path: str, encoding: str = "utf-8"):
        payload = {"path": path, "encoding": encoding}
        return await self._request("POST", f"/repos/{repo_id}/worktree/read", payload)

    async def worktree_diff(self, repo_id: str, staged: bool = False):
        payload = {"staged": staged}
        return await self._request("POST", f"/repos/{repo_id}/worktree/diff", payload)

    async def patch_apply(self, repo_id: str, patch: str, check_only: bool = False):
        payload = {"patch": patch, "check_only": check_only}
        return await self._request("POST", f"/repos/{repo_id}/patch/apply", payload)

    async def stage(self, repo_id: str, paths: list[str] | None = None):
        payload = {"paths": paths}
        return await self._request("POST", f"/repos/{repo_id}/stage", payload)

    async def stash_save(self, repo_id: str, message: str = "git2mcp stash"):
        payload = {"message": message}
        return await self._request("POST", f"/repos/{repo_id}/stash/save", payload)

    async def stash_pop(self, repo_id: str):
        return await self._request("POST", f"/repos/{repo_id}/stash/pop", {})

    async def branch_draft(self, repo_id: str, name: str, base: str | None = None):
        payload = {"name": name, "base": base}
        return await self._request("POST", f"/repos/{repo_id}/branch/draft", payload)

    async def checkpoint_create(self, repo_id: str, label: str | None = None):
        payload = {"label": label}
        return await self._request("POST", f"/repos/{repo_id}/checkpoint", payload)

    async def checkpoint_restore(self, repo_id: str, checkpoint_id: str):
        payload = {"checkpoint_id": checkpoint_id}
        return await self._request("POST", f"/repos/{repo_id}/checkpoint/restore", payload)
