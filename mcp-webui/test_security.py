"""Security defaults for the local MCP WebUI."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient


def _load_webui():
    server_path = Path(__file__).with_name("server.py")
    module_name = f"mcp_webui_server_{uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, server_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_mutating_webui_actions_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MCP_WEBUI_ALLOW_SECRET_WRITE", raising=False)
    monkeypatch.delenv("MCP_WEBUI_ALLOW_MUTATION", raising=False)
    monkeypatch.delenv("MCP_WEBUI_ALLOW_EXECUTE", raising=False)
    module = _load_webui()
    client = TestClient(module.app)

    secret = client.post("/github/configure", data={"token": "secret"})
    assert secret.status_code == 403
    assert "MCP_WEBUI_ALLOW_SECRET_WRITE" in secret.json()["detail"]

    sync = client.post(
        "/repos/sync",
        data={"repo_id": "team/repo", "source_path": "/tmp/repo", "branch": "main"},
    )
    assert sync.status_code == 403
    assert "MCP_WEBUI_ALLOW_MUTATION" in sync.json()["detail"]

    execute = client.post(
        "/skills/run",
        data={"model": "mcp-skills/refactor", "prompt": "run"},
    )
    assert execute.status_code == 403
    assert "MCP_WEBUI_ALLOW_EXECUTE" in execute.json()["detail"]
