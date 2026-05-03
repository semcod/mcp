from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from env2mcp import EnvConfig, GitHubCLI


class GitHubTokenSyncService:
    def __init__(self, env_path: str | Path = ".env"):
        self.env_path = Path(env_path)

    def get_status(self, include_token: bool = False) -> dict:
        cfg = EnvConfig(self.env_path)
        token = cfg.get("GITHUB_PAT") or cfg.get("GITHUB_TOKEN")
        user = cfg.get("GITHUB_USER")

        gh = GitHubCLI()
        gh_available = gh.is_available()
        gh_user = gh.get_user() if gh_available else None

        data = {
            "configured": bool(token),
            "token_hint": (token[:8] + "...") if token else None,
            "user": user or gh_user,
            "env_path": str(self.env_path),
            "gh_available": gh_available,
        }
        if include_token:
            data["token"] = token
        return data

    def set_org(self, org: str | None = None) -> dict:
        gh = GitHubCLI()
        resolved_org = (org or "").strip()
        if not resolved_org:
            if gh.is_available():
                resolved_org = (gh.get_user() or "").strip()

        if not resolved_org:
            return {
                "success": False,
                "error": "No organization provided and unable to resolve username from gh CLI",
                "org": None,
            }

        cfg = EnvConfig(self.env_path)
        cfg["GITHUB_ORG"] = resolved_org
        cfg.save()
        os.environ["GITHUB_ORG"] = resolved_org

        return {
            "success": True,
            "org": resolved_org,
            "env_path": str(self.env_path),
            "note": "GITHUB_ORG saved to .env",
        }

    def list_orgs_and_repos(self, repos_limit: int = 30) -> dict:
        gh = GitHubCLI()
        if not gh.is_available():
            return {
                "success": False,
                "error": "gh CLI not available",
                "user": None,
                "orgs": [],
            }

        user = gh.get_user()
        if not user:
            return {
                "success": False,
                "error": "gh CLI has no authenticated user (run: gh auth login)",
                "user": None,
                "orgs": [],
            }

        orgs: list[dict] = []

        personal_repos = gh.list_repos(owner=user, limit=repos_limit)
        orgs.append(
            {
                "name": user,
                "type": "user",
                "repo_count": len(personal_repos),
                "repos": personal_repos,
            }
        )

        try:
            proc = subprocess.run(
                ["gh", "api", "user/orgs"],
                capture_output=True,
                text=True,
                timeout=20,
            )
            gh_orgs = json.loads(proc.stdout) if proc.returncode == 0 and proc.stdout.strip() else []
        except Exception:
            gh_orgs = []

        for item in gh_orgs:
            org_name = item.get("login")
            if not org_name:
                continue
            repos = gh.list_repos(owner=org_name, limit=repos_limit)
            orgs.append(
                {
                    "name": org_name,
                    "type": "organization",
                    "repo_count": len(repos),
                    "repos": repos,
                }
            )

        return {
            "success": True,
            "user": user,
            "org_count": len(orgs),
            "orgs": orgs,
        }

    def get_last_pushed_repo(self, owner: str | None = None, limit: int = 100) -> dict:
        gh = GitHubCLI()
        if not gh.is_available():
            return {
                "success": False,
                "error": "gh CLI not available",
                "owner": None,
                "repo": None,
            }

        cfg = EnvConfig(self.env_path)
        resolved_owner = (owner or "").strip()
        if not resolved_owner:
            resolved_owner = (cfg.get("GITHUB_ORG") or "").strip()
        if not resolved_owner:
            resolved_owner = (cfg.get("GITHUB_USER") or "").strip()
        if not resolved_owner:
            resolved_owner = (gh.get_user() or "").strip()

        if not resolved_owner:
            return {
                "success": False,
                "error": "Unable to resolve GitHub owner (set GITHUB_ORG or pass owner)",
                "owner": None,
                "repo": None,
            }

        try:
            safe_limit = int(limit)
        except Exception:
            safe_limit = 100
        safe_limit = max(1, min(safe_limit, 500))

        try:
            proc = subprocess.run(
                [
                    "gh",
                    "repo",
                    "list",
                    resolved_owner,
                    "-L",
                    str(safe_limit),
                    "--json",
                    "nameWithOwner,pushedAt,url",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as exc:
            return {
                "success": False,
                "error": f"gh repo list failed: {exc}",
                "owner": resolved_owner,
                "repo": None,
            }

        if proc.returncode != 0:
            error_text = (proc.stderr or proc.stdout or "gh repo list failed").strip()
            return {
                "success": False,
                "error": error_text,
                "owner": resolved_owner,
                "repo": None,
            }

        try:
            repos = json.loads(proc.stdout) if proc.stdout.strip() else []
        except Exception:
            repos = []

        if not repos:
            return {
                "success": False,
                "error": "No repositories found for owner",
                "owner": resolved_owner,
                "repo": None,
            }

        valid_repos = [
            item
            for item in repos
            if isinstance(item, dict) and item.get("nameWithOwner")
        ]
        valid_repos.sort(key=lambda item: item.get("pushedAt") or "", reverse=True)

        if not valid_repos:
            return {
                "success": False,
                "error": "No repositories with usable metadata",
                "owner": resolved_owner,
                "repo": None,
            }

        top = valid_repos[0]
        return {
            "success": True,
            "owner": resolved_owner,
            "repo": top.get("nameWithOwner"),
            "repo_url": top.get("url"),
            "pushed_at": top.get("pushedAt"),
            "candidate_count": len(valid_repos),
            "source": "gh_cli",
        }

    def sync_token(self, force_gh_cli: bool = False, include_token: bool = False) -> dict:
        cfg = EnvConfig(self.env_path)

        token = None
        source = None

        gh = GitHubCLI()

        if force_gh_cli:
            if not gh.is_available():
                return {
                    "success": False,
                    "configured": False,
                    "error": "gh CLI not available",
                    "source": None,
                }

            token = gh.get_token()
            if token:
                source = "gh_cli"
            else:
                return {
                    "success": False,
                    "configured": False,
                    "error": "gh CLI has no token (run: gh auth login)",
                    "source": None,
                }

        if not token:
            token = os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN")
            if token:
                source = "env"

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
                if not cfg.get("GITHUB_ORG"):
                    cfg["GITHUB_ORG"] = user

        cfg.save()
        os.environ["GITHUB_PAT"] = token
        if user and not os.getenv("GITHUB_ORG"):
            os.environ["GITHUB_ORG"] = user

        data = {
            "success": True,
            "configured": True,
            "source": source,
            "user": user,
            "token_hint": token[:8] + "...",
            "env_path": str(self.env_path),
        }
        if include_token:
            data["token"] = token
        return data
