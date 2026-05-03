from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import server as gateway


def _extract_sse_data(raw_text: str) -> list[str]:
    payloads: list[str] = []
    for line in raw_text.splitlines():
        if line.startswith("data: "):
            payloads.append(line[len("data: "):])
    return payloads


def _authorized_client() -> TestClient:
    gateway.app.dependency_overrides[gateway.authenticate] = lambda: {
        "tenant_id": "default",
        "features": {"analyze": True, "refactor": True, "push": True},
    }
    return TestClient(gateway.app)


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
    assert gateway._extract_org_from_text(msg, {}) == "semcod"

    msg2 = "set org=my-team"
    assert gateway._extract_org_from_text(msg2, {}) == "my-team"

    assert gateway._extract_org_from_text("ignored", {"repo_url": "owner/repo"}) == "owner"
    assert gateway._extract_org_from_text("ignored", {"repo_url": "https://github.com/acme/project.git"}) == "acme"


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
        if url.endswith("/repo/last-pushed"):
            return _FakeResponse(_FakeAsyncClient.last_repo_payload)
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


def test_extract_repo_template_expression():
    expr = gateway._extract_repo_template_expression("{{show last pushed repo from github}}")
    assert expr == "show last pushed repo from github"
    assert gateway._extract_repo_template_expression("team/repo") is None


@pytest.mark.parametrize(
    "expression,expected",
    [
        ("show last pushed repo from github", True),
        ("pokaz ostatnio wypchniete repo z github", True),
        ("show organizations", False),
    ],
)
def test_is_last_pushed_repo_template(expression: str, expected: bool):
    assert gateway._is_last_pushed_repo_template(expression) is expected


def test_resolve_repo_id_template_last_pushed(monkeypatch):
    _FakeAsyncClient.last_repo_payload = {
        "success": True,
        "owner": "semcod",
        "repo": "semcod/mcp",
        "repo_url": "https://github.com/semcod/mcp",
        "pushed_at": "2026-05-03T12:00:00Z",
        "source": "gh_cli",
    }
    monkeypatch.setattr(gateway.httpx, "AsyncClient", _FakeAsyncClient)

    repo_id, meta = asyncio.run(gateway._resolve_repo_id_template("{{show last pushed repo from github}}"))
    assert repo_id == "semcod/mcp"
    assert meta is not None
    assert meta["strategy"] == "last_pushed_repo_from_github"
    assert meta["owner"] == "semcod"


def test_resolve_repo_id_template_last_pushed_repo_url_in_meta(monkeypatch):
    _FakeAsyncClient.last_repo_payload = {
        "success": True,
        "owner": "semcod",
        "repo": "semcod/mcp",
        "repo_url": "https://github.com/semcod/mcp",
        "pushed_at": "2026-05-03T12:00:00Z",
        "source": "gh_cli",
    }
    monkeypatch.setattr(gateway.httpx, "AsyncClient", _FakeAsyncClient)

    repo_id, meta = asyncio.run(gateway._resolve_repo_id_template("{{show last pushed repo from github}}"))
    assert repo_id == "semcod/mcp"
    assert meta is not None
    assert meta["repo_url"] == "https://github.com/semcod/mcp"

    # Simulate the effective_repo_url logic from chat_completions
    repo_url_input = None
    resolved_repo_url = (meta or {}).get("repo_url") if not repo_url_input else None
    effective_repo_url = repo_url_input or resolved_repo_url
    assert effective_repo_url == "https://github.com/semcod/mcp"


def test_resolve_repo_id_template_unsupported():
    with pytest.raises(ValueError):
        asyncio.run(gateway._resolve_repo_id_template("{{show org list}}"))


# ---------------------------------------------------------------------------
# GitHub auth error detection + auto-recovery
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "error,expected",
    [
        ("HTTP 401: Requires authentication (https://api.github.com/graphql)", True),
        ("Bad credentials", True),
        ("gh CLI has no token (run: gh auth login)", True),
        ("Could not resolve to a User with the login of 'foo'", True),
        ("No repositories found for owner", False),
        ("connection refused", False),
        (None, False),
        ("", False),
    ],
)
def test_is_github_auth_error(error, expected):
    assert gateway._is_github_auth_error(error) is expected


def test_github_auth_recovery_message_has_three_options():
    msg = gateway._github_auth_recovery_message("HTTP 401: Requires authentication")
    assert "HTTP 401" in msg
    assert "Zapisz token github do .env" in msg
    assert "gh auth login" in msg
    assert "env2mcp env set GITHUB_PAT" in msg
    assert "spróbuj ponownie" in msg.lower()


def test_resolve_repo_id_template_auto_recovers_on_auth_error(monkeypatch):
    """First call: 401 auth error. Sync succeeds. Retry: success."""

    call_log: list[str] = []

    async def fake_last_pushed(owner=None, limit=100):
        call_log.append("last_pushed")
        if call_log.count("last_pushed") == 1:
            return {"success": False, "error": "HTTP 401: Requires authentication", "repo": None}
        return {
            "success": True,
            "owner": "semcod",
            "repo": "semcod/mcp",
            "repo_url": "https://github.com/semcod/mcp",
            "pushed_at": "2026-05-03T13:23:16Z",
            "source": "gh_cli",
        }

    async def fake_sync():
        call_log.append("sync")
        return {"success": True, "source": "gh_cli"}

    monkeypatch.setattr(gateway, "_last_pushed_repo_via_gh2mcp", fake_last_pushed)
    monkeypatch.setattr(gateway, "_sync_github_token_via_gh2mcp", fake_sync)

    repo_id, meta = asyncio.run(
        gateway._resolve_repo_id_template("{{show last pushed repo from github owner=semcod}}")
    )
    assert repo_id == "semcod/mcp"
    assert meta["repo_url"] == "https://github.com/semcod/mcp"
    assert call_log == ["last_pushed", "sync", "last_pushed"]


def test_resolve_repo_id_template_auth_error_with_failed_recovery_raises_helpful_message(monkeypatch):
    """Auth error + sync fails → ValueError with three-option recovery message."""

    async def fake_last_pushed(owner=None, limit=100):
        return {"success": False, "error": "HTTP 401: Requires authentication", "repo": None}

    async def fake_sync():
        return {"success": False, "error": "gh CLI has no token"}

    monkeypatch.setattr(gateway, "_last_pushed_repo_via_gh2mcp", fake_last_pushed)
    monkeypatch.setattr(gateway, "_sync_github_token_via_gh2mcp", fake_sync)

    with pytest.raises(ValueError) as exc_info:
        asyncio.run(
            gateway._resolve_repo_id_template("{{show last pushed repo from github owner=semcod}}")
        )

    msg = str(exc_info.value)
    assert "HTTP 401" in msg
    assert "Zapisz token github do .env" in msg
    assert "env2mcp env set GITHUB_PAT" in msg


def test_resolve_repo_id_template_non_auth_error_does_not_trigger_recovery(monkeypatch):
    """Non-auth error → no sync attempt, original error message."""

    sync_calls = []

    async def fake_last_pushed(owner=None, limit=100):
        return {"success": False, "error": "No repositories found for owner", "repo": None}

    async def fake_sync():
        sync_calls.append(1)
        return {"success": True}

    monkeypatch.setattr(gateway, "_last_pushed_repo_via_gh2mcp", fake_last_pushed)
    monkeypatch.setattr(gateway, "_sync_github_token_via_gh2mcp", fake_sync)

    with pytest.raises(ValueError) as exc_info:
        asyncio.run(gateway._resolve_repo_id_template("{{show last pushed repo from github}}"))

    assert "No repositories found for owner" in str(exc_info.value)
    assert sync_calls == []  # recovery not triggered for non-auth errors


# ---------------------------------------------------------------------------
# effective_repo_url logic (mirrors chat_completions handler)
# ---------------------------------------------------------------------------

def _compute_effective_repo_url(repo_url: str | None, meta: dict | None) -> str | None:
    """Mirrors: resolved_repo_url = (repo_selection or {}).get('repo_url') if not repo_url else None
                effective_repo_url = repo_url or resolved_repo_url"""
    resolved_repo_url = (meta or {}).get("repo_url") if not repo_url else None
    return repo_url or resolved_repo_url


def test_effective_repo_url_explicit_repo_url_wins(monkeypatch):
    _FakeAsyncClient.last_repo_payload = {
        "success": True,
        "owner": "semcod",
        "repo": "semcod/mcp",
        "repo_url": "https://github.com/semcod/mcp",
        "pushed_at": "2026-05-03T12:00:00Z",
        "source": "gh_cli",
    }
    monkeypatch.setattr(gateway.httpx, "AsyncClient", _FakeAsyncClient)

    _repo_id, meta = asyncio.run(
        gateway._resolve_repo_id_template("{{show last pushed repo from github}}")
    )
    explicit = "https://github.com/other/explicit.git"
    assert _compute_effective_repo_url(explicit, meta) == explicit


def test_effective_repo_url_falls_back_to_resolved(monkeypatch):
    _FakeAsyncClient.last_repo_payload = {
        "success": True,
        "owner": "semcod",
        "repo": "semcod/mcp",
        "repo_url": "https://github.com/semcod/mcp",
        "pushed_at": "2026-05-03T12:00:00Z",
        "source": "gh_cli",
    }
    monkeypatch.setattr(gateway.httpx, "AsyncClient", _FakeAsyncClient)

    _repo_id, meta = asyncio.run(
        gateway._resolve_repo_id_template("{{show last pushed repo from github}}")
    )
    assert _compute_effective_repo_url(None, meta) == "https://github.com/semcod/mcp"


def test_effective_repo_url_both_none():
    assert _compute_effective_repo_url(None, None) is None
    assert _compute_effective_repo_url(None, {}) is None


def test_effective_repo_url_no_template_resolution():
    assert _compute_effective_repo_url("https://github.com/team/proj.git", None) == "https://github.com/team/proj.git"


def test_render_chat_content_analyze_human_readable():
    result = {
        "skill": "analyze",
        "repo_id": "demo/refactor-lab",
        "branch": "main",
        "analysis": {
            "metrics": {"file_count": 12, "total_lines": 420},
            "recommendations": {
                "recommendations": [
                    {"priority": "high", "target": "users", "suggested_action": "Split responsibilities"}
                ]
            },
        },
    }
    content = gateway._render_chat_content(result)
    assert content.startswith("# Analiza repo `demo/refactor-lab`")
    assert "## Proponowane etapy" in content
    assert "Split responsibilities" in content


def test_render_chat_content_refactor_human_readable():
    result = {
        "skill": "refactor",
        "repo_id": "demo/integration-lab",
        "branch": "feature/x",
        "base_branch": "main",
        "plan_preview": {"summary": "# MCP Refactoring Summary\n\nPlan..."},
        "execution": {
            "execute_commit": True,
            "committed": True,
            "pushed": False,
            "tests": {"ok": True},
            "pull_request": {"skipped": True, "reason": "Push was not executed"},
        },
    }
    content = gateway._render_chat_content(result)
    assert content.startswith("# Plan refaktoryzacji `demo/integration-lab`")
    assert "## Status wykonania" in content
    assert "Committed: `true`" in content
    assert "PR: pominięto (Push was not executed)" in content


def test_render_chat_content_system_human_readable():
    result = {
        "skill": "system",
        "github": {
            "action": "set-default-github-org",
            "success": True,
            "org": "semcod",
            "note": "Default org updated",
        },
    }
    content = gateway._render_chat_content(result)
    assert "Operacja systemowa" in content
    assert "Organizacja domyślna: `semcod`" in content


def test_render_chat_content_queued_human_readable():
    result = {
        "skill": "queued",
        "status": "queued",
        "repo_id": "semcod/mcp",
        "branch": "main",
        "job_id": "abc123",
        "note": "Workflow uruchomiony w tle (Redis/RQ worker).",
    }
    content = gateway._render_chat_content(result)
    assert "Zadanie zakolejkowane" in content
    assert "`abc123`" in content
    assert "GET /jobs/abc123" in content


def test_stream_job_not_found_returns_404(monkeypatch):
    monkeypatch.setattr(gateway, "_load_job", lambda _job_id: None)

    client = _authorized_client()
    try:
        response = client.get(
            "/jobs/missing/stream",
            headers={"Authorization": "Bearer sk-mcp-default-dev-key"},
        )
        assert response.status_code == 404
    finally:
        gateway.app.dependency_overrides.clear()


def test_stream_job_emits_status_updates_and_done(monkeypatch):
    states = [
        {"status": "queued", "phase": "queued", "updated_at": 1.0},
        {"status": "analyzing", "phase": "analyzing", "updated_at": 2.0},
        {
            "status": "done",
            "phase": "done",
            "updated_at": 3.0,
            "result": {"skill": "analyze", "repo_id": "semcod/mcp"},
        },
    ]
    calls = {"count": 0}

    def fake_load_job(_job_id: str):
        idx = calls["count"]
        calls["count"] += 1
        if idx < len(states):
            return states[idx]
        return states[-1]

    monkeypatch.setattr(gateway, "_load_job", fake_load_job)
    monkeypatch.setattr(gateway, "JOB_POLL_INTERVAL_SECONDS", 0.0)

    client = _authorized_client()
    try:
        response = client.get(
            "/jobs/job-123/stream",
            headers={"Authorization": "Bearer sk-mcp-default-dev-key"},
        )

        assert response.status_code == 200
        payloads = _extract_sse_data(response.text)
        assert payloads[-1] == "[DONE]"

        events = [json.loads(item) for item in payloads[:-1]]
        assert [event["status"] for event in events] == ["analyzing", "done"]
        assert events[-1]["result"]["repo_id"] == "semcod/mcp"
    finally:
        gateway.app.dependency_overrides.clear()


def test_stream_job_emits_failure_with_error(monkeypatch):
    states = [
        {"status": "queued", "phase": "queued", "updated_at": 10.0},
        {
            "status": "failed",
            "phase": "failed",
            "updated_at": 11.0,
            "error": "run tests failed",
        },
    ]
    calls = {"count": 0}

    def fake_load_job(_job_id: str):
        idx = calls["count"]
        calls["count"] += 1
        if idx < len(states):
            return states[idx]
        return states[-1]

    monkeypatch.setattr(gateway, "_load_job", fake_load_job)
    monkeypatch.setattr(gateway, "JOB_POLL_INTERVAL_SECONDS", 0.0)

    client = _authorized_client()
    try:
        response = client.get(
            "/jobs/job-err/stream",
            headers={"Authorization": "Bearer sk-mcp-default-dev-key"},
        )

        assert response.status_code == 200
        payloads = _extract_sse_data(response.text)
        assert payloads[-1] == "[DONE]"

        events = [json.loads(item) for item in payloads[:-1]]
        assert events[-1]["status"] == "failed"
        assert events[-1]["error"] == "run tests failed"
    finally:
        gateway.app.dependency_overrides.clear()
