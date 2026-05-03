from __future__ import annotations

import asyncio
import pytest

import server as gateway


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("Pobierz token GitHub z gh CLI", True),
        ("Pokaż github token i zsynchronizuj", True),
        ("Zaktualizuj token GitHub z gh CLI", True),
        ("pobierz token gihutb", True),
        ("GitHub Token:", True),
        ("Repo: x/y\nZadanie: refactor", False),
    ],
)
def test_is_github_token_sync_command(msg: str, expected: bool):
    ctx = gateway.parse_prompt_context(msg)
    assert gateway._is_github_token_sync_command(msg, ctx) is expected


def test_is_github_token_sync_command_false_if_explicit_token_value():
    msg = "GitHub Token: ghp_abc123"
    ctx = gateway.parse_prompt_context(msg)
    assert gateway._is_github_token_sync_command(msg, ctx) is False


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("zapisz token github do .env: ghp_abc123", True),
        ("save github token to .env ghp_abc123", True),
        ("ustaw token github w env", True),
        ("pobierz token github", False),
    ],
)
def test_is_github_token_save_command(msg: str, expected: bool):
    ctx = gateway.parse_prompt_context(msg)
    assert gateway._is_github_token_save_command(msg, ctx) is expected


def test_extract_github_token_from_text():
    msg = "zapisz token github do .env: ghp_abc123XYZ"
    assert gateway._extract_github_token_from_text(msg) == "ghp_abc123XYZ"


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("ustaw organizacje github: semcod", True),
        ("zmien org na my-team", True),
        ("set organization to semcod", True),
        ("pokaz liste wszystkich organizacji", False),
    ],
)
def test_is_org_set_command(msg: str, expected: bool):
    assert gateway._is_org_set_command(msg) is expected


@pytest.mark.parametrize(
    "msg,expected",
    [
        ("pokaz liste wszystkich organizacji", True),
        ("wylistuj organizacje i repo", True),
        ("list all organizations and repositories", True),
        ("ustaw organizacje github semcod", False),
    ],
)
def test_is_org_list_command(msg: str, expected: bool):
    assert gateway._is_org_list_command(msg) is expected


def test_extract_org_from_text():
    msg = "ustaw organizacje github: semcod"
    assert gateway._extract_org_from_text(msg, {}) == "github"

    msg2 = "set org=my-team"
    assert gateway._extract_org_from_text(msg2, {}) == "my-team"


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json):
        return _FakeResponse(_FakeAsyncClient.sync_payload)

    async def get(self, url):
        return _FakeResponse(_FakeAsyncClient.status_payload)


def test_sync_github_token_via_gh2mcp_success_note(monkeypatch):
    _FakeAsyncClient.sync_payload = {"success": True, "source": "gh_cli", "error": None}
    _FakeAsyncClient.status_payload = {"configured": True, "token_hint": "ghp_......", "user": "tom"}
    monkeypatch.setattr(gateway.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(gateway._sync_github_token_via_gh2mcp())
    assert result["success"] is True
    assert result["source"] == "gh_cli"
    assert "saved to /app/.env" in result["note"]


def test_sync_github_token_via_gh2mcp_failure_note(monkeypatch):
    _FakeAsyncClient.sync_payload = {
        "success": False,
        "source": None,
        "error": "gh CLI has no token (run: gh auth login)",
    }
    _FakeAsyncClient.status_payload = {"configured": True, "token_hint": "ghp_......", "user": None}
    monkeypatch.setattr(gateway.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(gateway._sync_github_token_via_gh2mcp())
    assert result["success"] is False
    assert result["source"] is None
    assert "failed" in result["note"].lower()
    assert "gh auth login" in result["note"]
