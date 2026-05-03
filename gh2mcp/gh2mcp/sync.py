from __future__ import annotations

import os
from pathlib import Path

from env2mcp import EnvConfig, GitHubCLI


class GitHubTokenSyncService:
    def __init__(self, env_path: str | Path = ".env"):
        self.env_path = Path(env_path)

    def get_status(self) -> dict:
        cfg = EnvConfig(self.env_path)
        token = cfg.get("GITHUB_PAT") or cfg.get("GITHUB_TOKEN")
        user = cfg.get("GITHUB_USER")

        gh = GitHubCLI()
        gh_available = gh.is_available()
        gh_user = gh.get_user() if gh_available else None

        return {
            "configured": bool(token),
            "token_hint": (token[:8] + "...") if token else None,
            "user": user or gh_user,
            "env_path": str(self.env_path),
            "gh_available": gh_available,
        }

    def sync_token(self, force_gh_cli: bool = False) -> dict:
        cfg = EnvConfig(self.env_path)

        token = None
        source = None

        if not force_gh_cli:
            token = os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN")
            if token:
                source = "env"

        gh = GitHubCLI()
        if not token and gh.is_available():
            token = gh.get_token()
            if token:
                source = "gh_cli"

        if not token:
            token = cfg.get("GITHUB_PAT") or cfg.get("GITHUB_TOKEN")
            if token:
                source = "env_file"

        if not token:
            return {
                "success": False,
                "configured": False,
                "error": "Brak tokenu GitHub (env, gh CLI, .env)",
                "source": None,
            }

        cfg["GITHUB_PAT"] = token
        user = None
        if gh.is_available():
            user = gh.get_user()
            if user:
                cfg["GITHUB_USER"] = user

        cfg.save()
        os.environ["GITHUB_PAT"] = token

        return {
            "success": True,
            "configured": True,
            "source": source,
            "user": user,
            "token_hint": token[:8] + "...",
            "env_path": str(self.env_path),
        }
