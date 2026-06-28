from __future__ import annotations

import os
from pathlib import Path

from env2mcp import EnvConfig, GitHubCLI

from gh2mcp.gh_repo_queries import (
    clamp_limit,
    collect_repos_for_owners,
    dedupe_repos_by_slug,
    fetch_user_org_logins,
    gh_repo_list,
    newest_repo_with_slug,
    resolve_github_token,
    resolve_owner,
)


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

        for org_name in fetch_user_org_logins():
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

        resolved_owner, error = resolve_owner(self.env_path, gh, owner)
        if error:
            return error

        safe_limit = clamp_limit(limit, default=100, minimum=1, maximum=500)
        repos, list_error = gh_repo_list(
            resolved_owner,
            safe_limit,
            fields="nameWithOwner,pushedAt,url",
        )
        if list_error:
            return {
                "success": False,
                "error": list_error,
                "owner": resolved_owner,
                "repo": None,
            }

        if not repos:
            return {
                "success": False,
                "error": "No repositories found for owner",
                "owner": resolved_owner,
                "repo": None,
            }

        top = newest_repo_with_slug(repos)
        if not top:
            return {
                "success": False,
                "error": "No repositories with usable metadata",
                "owner": resolved_owner,
                "repo": None,
            }

        valid_count = len([item for item in repos if isinstance(item, dict) and item.get("nameWithOwner")])
        return {
            "success": True,
            "owner": resolved_owner,
            "repo": top.get("nameWithOwner"),
            "repo_url": top.get("url"),
            "pushed_at": top.get("pushedAt"),
            "candidate_count": valid_count,
            "source": "gh_cli",
        }

    def get_recent_repos(self, limit: int = 10, owner: str | None = None, include_orgs: bool = True) -> dict:
        gh = GitHubCLI()
        if not gh.is_available():
            return {
                "success": False,
                "error": "gh CLI not available",
                "repos": [],
            }

        user = gh.get_user()
        if not user:
            return {
                "success": False,
                "error": "gh CLI has no authenticated user (run: gh auth login)",
                "repos": [],
            }

        safe_limit = clamp_limit(limit, default=10, minimum=1, maximum=100)
        owners: list[str] = []
        if owner and owner.strip():
            owners.append(owner.strip())
        else:
            owners.append(user)
            if include_orgs:
                for org_name in fetch_user_org_logins():
                    if org_name not in owners:
                        owners.append(org_name)

        candidates, errors = collect_repos_for_owners(
            owners,
            safe_limit,
            fields="nameWithOwner,pushedAt,url,isPrivate",
        )
        for item in candidates:
            item["isPrivate"] = bool(item.get("isPrivate"))

        if not candidates:
            return {
                "success": False,
                "error": errors[0] if errors else "No repositories found",
                "user": user,
                "repos": [],
                "source": "gh_cli",
            }

        deduped = dedupe_repos_by_slug(candidates, safe_limit)
        return {
            "success": True,
            "user": user,
            "owner": owner,
            "repos": deduped,
            "count": len(deduped),
            "owners_checked": owners,
            "errors": errors,
            "source": "gh_cli",
        }

    def sync_token(self, force_gh_cli: bool = False, include_token: bool = False) -> dict:
        cfg = EnvConfig(self.env_path)
        gh = GitHubCLI()

        token, source, error = resolve_github_token(
            self.env_path, gh, force_gh_cli=force_gh_cli
        )
        if error:
            return error

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
