from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.modules.pop("env2mcp", None)
sys.path.insert(0, str(ROOT / "env2mcp"))

import gh2mcp.sync as sync_module
from gh2mcp.sync import GitHubTokenSyncService


class _GhUnavailable:
    def is_available(self) -> bool:
        return False

    def get_token(self):
        return None

    def get_user(self):
        return None


class _GhUserRepos:
    def is_available(self) -> bool:
        return True

    def get_token(self):
        return "ghp_token"

    def get_user(self):
        return "alice"

    def list_repos(self, owner: str, limit: int = 30):
        return [f"{owner}/repo-1", f"{owner}/repo-2"]


class _ProcResult:
    def __init__(self, returncode: int, stdout: str, stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _GhAvailableUser:
    def is_available(self) -> bool:
        return True

    def get_token(self):
        return None

    def get_user(self):
        return "semcod"


class _GhNoToken:
    def is_available(self) -> bool:
        return True

    def get_token(self):
        return None

    def get_user(self):
        return None


def test_sync_token_saves_from_env_and_reads_back(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("GITHUB_PAT", "ghp_env_token_123456")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(sync_module, "GitHubCLI", _GhUnavailable)

    env_path = tmp_path / ".env"
    service = GitHubTokenSyncService(env_path)

    result = service.sync_token(force_gh_cli=False, include_token=True)
    assert result["success"] is True
    assert result["source"] == "env"
    assert result["token"] == "ghp_env_token_123456"

    status = service.get_status(include_token=True)
    assert status["configured"] is True
    assert status["token"] == "ghp_env_token_123456"
    assert status["token_hint"].startswith("ghp_env_")
    assert env_path.exists()
    assert 'GITHUB_PAT="ghp_env_token_123456"' in env_path.read_text(encoding="utf-8")


def test_sync_token_reads_from_env_file_when_env_missing(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GITHUB_PAT", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(sync_module, "GitHubCLI", _GhUnavailable)

    env_path = tmp_path / ".env"
    env_path.write_text('GITHUB_PAT="ghp_file_token_abcdef"\n', encoding="utf-8")
    service = GitHubTokenSyncService(env_path)

    result = service.sync_token(force_gh_cli=False, include_token=True)
    assert result["success"] is True
    assert result["source"] == "env_file"
    assert result["token"] == "ghp_file_token_abcdef"

    status = service.get_status(include_token=True)
    assert status["configured"] is True
    assert status["token"] == "ghp_file_token_abcdef"


def test_sync_token_force_gh_cli_does_not_fallback_to_env_or_file(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("GITHUB_PAT", "ghp_env_token_should_not_be_used")
    monkeypatch.setattr(sync_module, "GitHubCLI", _GhNoToken)

    env_path = tmp_path / ".env"
    env_path.write_text('GITHUB_PAT="ghp_file_token_should_not_be_used"\n', encoding="utf-8")
    service = GitHubTokenSyncService(env_path)

    result = service.sync_token(force_gh_cli=True, include_token=True)
    assert result["success"] is False
    assert result["source"] is None
    assert "gh CLI has no token" in result["error"]


def test_set_org_defaults_to_gh_username(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sync_module, "GitHubCLI", _GhUserRepos)
    env_path = tmp_path / ".env"
    service = GitHubTokenSyncService(env_path)

    result = service.set_org(org=None)
    assert result["success"] is True
    assert result["org"] == "alice"
    assert 'GITHUB_ORG="alice"' in env_path.read_text(encoding="utf-8")


def test_list_orgs_and_repos(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sync_module, "GitHubCLI", _GhUserRepos)

    def _fake_run(*args, **kwargs):
        return _ProcResult(returncode=0, stdout='[{"login":"acme"},{"login":"tools"}]')

    monkeypatch.setattr(sync_module.subprocess, "run", _fake_run)
    service = GitHubTokenSyncService(tmp_path / ".env")

    result = service.list_orgs_and_repos(repos_limit=5)
    assert result["success"] is True
    assert result["org_count"] == 3
    names = [item["name"] for item in result["orgs"]]
    assert names == ["alice", "acme", "tools"]


def test_get_last_pushed_repo_selects_latest(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sync_module, "GitHubCLI", _GhUserRepos)

    def _fake_run(*args, **kwargs):
        return _ProcResult(
            returncode=0,
            stdout='['
            '{"nameWithOwner":"alice/old","pushedAt":"2026-01-01T00:00:00Z","url":"https://github.com/alice/old"},'
            '{"nameWithOwner":"alice/new","pushedAt":"2026-03-01T00:00:00Z","url":"https://github.com/alice/new"}'
            ']'
        )

    monkeypatch.setattr(sync_module.subprocess, "run", _fake_run)
    service = GitHubTokenSyncService(tmp_path / ".env")

    result = service.get_last_pushed_repo(owner="alice", limit=50)
    assert result["success"] is True
    assert result["repo"] == "alice/new"
    assert result["source"] == "gh_cli"


def test_get_last_pushed_repo_success(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sync_module, "GitHubCLI", _GhAvailableUser)
    monkeypatch.delenv("GITHUB_ORG", raising=False)
    monkeypatch.delenv("GITHUB_USER", raising=False)

    class _Proc:
        returncode = 0
        stdout = (
            '[{"nameWithOwner":"semcod/old-repo","pushedAt":"2026-01-01T00:00:00Z","url":"https://github.com/semcod/old-repo"},'
            '{"nameWithOwner":"semcod/mcp","pushedAt":"2026-05-03T12:00:00Z","url":"https://github.com/semcod/mcp"}]'
        )
        stderr = ""

    monkeypatch.setattr(sync_module.subprocess, "run", lambda *args, **kwargs: _Proc())

    service = GitHubTokenSyncService(tmp_path / ".env")
    result = service.get_last_pushed_repo(owner=None, limit=100)
    assert result["success"] is True
    assert result["owner"] == "semcod"
    assert result["repo"] == "semcod/mcp"
    assert result["source"] == "gh_cli"


def test_get_last_pushed_repo_no_repos(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(sync_module, "GitHubCLI", _GhAvailableUser)
    monkeypatch.delenv("GITHUB_ORG", raising=False)
    monkeypatch.delenv("GITHUB_USER", raising=False)

    class _Proc:
        returncode = 0
        stdout = "[]"
        stderr = ""

    monkeypatch.setattr(sync_module.subprocess, "run", lambda *args, **kwargs: _Proc())

    service = GitHubTokenSyncService(tmp_path / ".env")
    result = service.get_last_pushed_repo(owner="semcod", limit=10)
    assert result["success"] is False
    assert "No repositories found" in result["error"]
