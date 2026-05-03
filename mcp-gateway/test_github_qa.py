from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

import server as gateway


def _authorized_client() -> TestClient:
    gateway.app.dependency_overrides[gateway.authenticate] = lambda: {
        "tenant_id": "default",
        "features": {
            "analyze": True,
            "refactor": True,
            "push": True,
            "tool": True,
            "github_qa": True,
        },
    }
    return TestClient(gateway.app)


def test_render_chat_content_github_qa():
    result = {
        "skill": "github_qa",
        "answer": "To są Twoje ostatnie repozytoria.",
        "llm": {"model": "openrouter/x-ai/grok-code-fast-1", "used": True},
    }
    rendered = gateway._render_chat_content(result)
    assert "To są Twoje ostatnie repozytoria." in rendered
    assert "GitHub Q&A" in rendered


def test_run_github_qa_missing_openrouter_key(monkeypatch):
    async def fake_status():
        return {"success": True, "configured": True, "user": "tom"}

    async def fake_recent(limit=10, owner=None, include_orgs=True):
        return {"success": True, "count": 1, "repos": [{"nameWithOwner": "tom/repo"}]}

    monkeypatch.setattr(gateway, "_gh2mcp_status_via_gh2mcp", fake_status)
    monkeypatch.setattr(gateway, "_list_recent_repos_via_gh2mcp", fake_recent)
    monkeypatch.setattr(gateway, "OPENROUTER_API_KEY", "")

    result = asyncio.run(gateway._run_github_qa("jakie mam ostatnie repo?"))
    assert result["skill"] == "github_qa"
    assert result["ok"] is False
    assert "OPENROUTER_API_KEY" in result["error"]


def test_chat_completions_github_qa_model(monkeypatch):
    async def fake_run_github_qa(user_request: str, repo_id=None, repo_url=None):
        return {
            "skill": "github_qa",
            "ok": True,
            "question": user_request,
            "answer": "To jest odpowiedź z GitHub Q&A.",
            "llm": {"provider": "openrouter", "model": "test-model", "used": True},
        }

    monkeypatch.setattr(gateway, "_run_github_qa", fake_run_github_qa)
    monkeypatch.setattr(gateway, "audit", lambda _event: None)

    client = _authorized_client()
    try:
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer sk-mcp-default-dev-key"},
            json={
                "model": "mcp-skills/github-qa",
                "messages": [{"role": "user", "content": "kto jest właścicielem ostatniego repo?"}],
            },
        )
        assert response.status_code == 200
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        assert "To jest odpowiedź z GitHub Q&A." in content
        assert "GitHub Q&A" in content
    finally:
        gateway.app.dependency_overrides.clear()


def test_models_include_github_qa():
    client = _authorized_client()
    try:
        response = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer sk-mcp-default-dev-key"},
        )
        assert response.status_code == 200
        model_ids = {item["id"] for item in response.json().get("data", [])}
        assert "mcp-skills/github-qa" in model_ids
    finally:
        gateway.app.dependency_overrides.clear()
