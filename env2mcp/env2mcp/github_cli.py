"""GitHub CLI integration for authentication and token management."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple

from .config import EnvConfig


class GitHubCLI:
    """Interface to GitHub CLI (gh) tool."""

    def __init__(self):
        self._checked = False
        self._available = False

    def is_available(self) -> bool:
        """Check if gh CLI is installed and available."""
        if self._checked:
            return self._available
        try:
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                check=True,
                timeout=5
            )
            self._available = result.returncode == 0
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            self._available = False
        self._checked = True
        return self._available

    def get_auth_status(self) -> Dict:
        """Get current GitHub authentication status."""
        if not self.is_available():
            return {"authenticated": False, "error": "gh CLI not found"}

        try:
            result = subprocess.run(
                ["gh", "auth", "status", "--show-token"],
                capture_output=True,
                text=True,
                timeout=10
            )

            # Parse the output
            output = result.stdout + result.stderr
            status = {
                "authenticated": False,
                "token": None,
                "user": None,
                "protocol": None,
                "token_scopes": []
            }

            for line in output.split("\n"):
                if "Logged in to" in line:
                    status["authenticated"] = True
                elif "Token:" in line and "***" not in line:
                    # Token might be shown
                    parts = line.split("Token:")
                    if len(parts) > 1:
                        status["token"] = parts[1].strip()
                elif " account" in line.lower() or "as " in line.lower():
                    # Try to extract username
                    if "as " in line:
                        parts = line.split("as ")
                        if len(parts) > 1:
                            user_part = parts[1].strip()
                            if " " in user_part:
                                user_part = user_part.split()[0]
                            status["user"] = user_part.rstrip(".")

            return status
        except subprocess.TimeoutExpired:
            return {"authenticated": False, "error": "Command timed out"}
        except Exception as e:
            return {"authenticated": False, "error": str(e)}

    def get_token(self) -> Optional[str]:
        """Get GitHub token from gh CLI."""
        if not self.is_available():
            return None

        try:
            # Try to get token securely
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def get_user(self) -> Optional[str]:
        """Get authenticated GitHub username."""
        if not self.is_available():
            return None

        try:
            result = subprocess.run(
                ["gh", "api", "user", "--jq", ".login"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def login(self, method: str = "web", hostname: str = "github.com") -> Tuple[bool, str]:
        """Authenticate with GitHub.

        Args:
            method: 'web' for browser flow, 'token' for PAT
            hostname: GitHub instance (default: github.com)

        Returns:
            (success, message)
        """
        if not self.is_available():
            return False, "gh CLI is not installed. Install from https://cli.github.com/"

        try:
            if method == "web":
                result = subprocess.run(
                    ["gh", "auth", "login", "-h", hostname, "-w"],
                    capture_output=False,  # Show interactive prompt
                    timeout=120
                )
                if result.returncode == 0:
                    return True, "Successfully authenticated with GitHub"
                return False, "Authentication failed or was cancelled"
            elif method == "token":
                return False, "Token login requires manual entry. Run: gh auth login --with-token"
            else:
                return False, f"Unknown method: {method}"
        except subprocess.TimeoutExpired:
            return False, "Authentication timed out"
        except Exception as e:
            return False, f"Error during authentication: {e}"

    def logout(self, hostname: str = "github.com") -> Tuple[bool, str]:
        """Log out from GitHub."""
        if not self.is_available():
            return False, "gh CLI not found"

        try:
            result = subprocess.run(
                ["gh", "auth", "logout", "-h", hostname],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True, "Successfully logged out"
            return False, result.stderr or "Logout failed"
        except Exception as e:
            return False, str(e)

    def list_repos(self, owner: Optional[str] = None, limit: int = 30) -> list[Dict]:
        """List repositories for authenticated user or specific owner."""
        if not self.is_available():
            return []

        try:
            if owner:
                cmd = ["gh", "repo", "list", owner, "-L", str(limit), "--json", "name,url,description"]
            else:
                cmd = ["gh", "repo", "list", "-L", str(limit), "--json", "name,url,description"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired):
            pass
        return []

    def clone_url(self, repo: str) -> Optional[str]:
        """Get clone URL for a repository."""
        if not repo or "/" not in repo:
            return None

        # Return HTTPS URL with token support
        if repo.startswith("http"):
            return repo
        return f"https://github.com/{repo}.git"


def get_github_token(env_path: str | Path = ".env") -> Optional[str]:
    """Get GitHub token from environment or .env file.

    Priority:
    1. GITHUB_TOKEN from environment
    2. GITHUB_PAT from environment
    3. Token from gh CLI
    4. GITHUB_TOKEN from .env
    5. GITHUB_PAT from .env
    """
    # Check environment first
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PAT")
    if token:
        return token

    # Try gh CLI
    gh = GitHubCLI()
    token = gh.get_token()
    if token:
        return token

    # Check .env file
    config = EnvConfig(env_path)
    return config.get("GITHUB_TOKEN") or config.get("GITHUB_PAT")


def configure_github(env_path: str | Path = ".env", interactive: bool = True) -> Dict:
    """Configure GitHub integration interactively.

    Returns configuration result with status and saved values.
    """
    import os

    config = EnvConfig(env_path)
    gh = GitHubCLI()
    result = {
        "success": False,
        "message": "",
        "saved_to_env": False,
        "token_present": False,
        "username": None,
        "auth_method": None
    }

    if not gh.is_available():
        result["message"] = (
            "GitHub CLI (gh) is not installed.\n"
            "Install from: https://cli.github.com/\n\n"
            "Or manually set GITHUB_PAT in your .env file:"
        )
        if interactive:
            print(result["message"])
            token = input("GitHub Personal Access Token: ").strip()
            if token:
                config["GITHUB_PAT"] = token
                config.save()
                result["saved_to_env"] = True
                result["token_present"] = True
                result["success"] = True
                result["message"] = "Token saved to .env"
        return result

    # gh is available - check auth status
    auth_status = gh.get_auth_status()

    if auth_status.get("authenticated"):
        # Already logged in
        token = gh.get_token()
        username = gh.get_user() or auth_status.get("user")

        if token:
            config["GITHUB_PAT"] = token
            if username:
                config["GITHUB_USER"] = username
            config.save()

            result.update({
                "success": True,
                "saved_to_env": True,
                "token_present": True,
                "username": username,
                "auth_method": "gh_cli",
                "message": f"GitHub configured for user: {username}"
            })
        else:
            result["message"] = "Could not retrieve token from gh CLI"
    else:
        # Not logged in - prompt for auth
        if interactive:
            print("GitHub CLI is installed but you're not logged in.")
            print("Would you like to authenticate now? (y/n): ", end="")
            response = input().strip().lower()

            if response in ("y", "yes"):
                success, msg = gh.login(method="web")
                if success:
                    # Try again to get token
                    token = gh.get_token()
                    username = gh.get_user()
                    if token:
                        config["GITHUB_PAT"] = token
                        if username:
                            config["GITHUB_USER"] = username
                        config.save()
                        result.update({
                            "success": True,
                            "saved_to_env": True,
                            "token_present": True,
                            "username": username,
                            "auth_method": "gh_cli_web",
                            "message": f"GitHub configured for user: {username}"
                        })
                    else:
                        result["message"] = "Login succeeded but could not retrieve token"
                else:
                    result["message"] = msg
            else:
                # Manual token entry
                print("Enter GitHub Personal Access Token manually:")
                token = input("Token: ").strip()
                if token:
                    config["GITHUB_PAT"] = token
                    config.save()
                    result.update({
                        "success": True,
                        "saved_to_env": True,
                        "token_present": True,
                        "auth_method": "manual",
                        "message": "Token saved to .env"
                    })

    return result
