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
