"""Lightweight tests for the /tools/run flow in mcp-skills.

These tests do not require real tool packages; they monkeypatch
_ensure_tool_installed and subprocess execution so the suite is fast
and offline-safe.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def server_module(tmp_path_factory):
    """Import the mcp-skills server with a writable repo_base."""
    base = tmp_path_factory.mktemp("mcp-skills-test-repo-base")
    os.environ["SKILLS_REPO_BASE"] = str(base)
    import importlib
    import sys
    # Ensure fresh import so the env var takes effect.
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.skills_server.repo_base = Path(base)
    return server


def test_derive_repo_id_from_url(server_module):
    derive = server_module._derive_repo_id_from_url
    assert derive("https://github.com/owner/repo") == "owner/repo"
    assert derive("https://github.com/owner/repo.git") == "owner/repo"
    assert derive("https://github.com/owner/repo/") == "owner/repo"
    assert derive("git@github.com:owner/repo.git") == "owner/repo"


def test_supported_tools_registry_has_expected_entries(server_module):
    expected = {
        "sumd", "code2llm", "code2docs", "code2logic", "code2schema",
        "redsl", "redup", "regres", "regix", "vallm", "pyqual", "domd",
    }
    assert expected.issubset(set(server_module.SUPPORTED_TOOLS))


def test_collect_output_files_reads_small_text(server_module, tmp_path):
    (tmp_path / "SUMD.md").write_text("# Hello\n")
    result = server_module._collect_output_files(tmp_path, ["SUMD.md", "missing.md"])
    assert len(result) == 1
    assert result[0]["path"] == "SUMD.md"
    assert result[0]["content"] == "# Hello\n"
    assert result[0]["truncated"] is False
    assert result[0]["binary"] is False


@pytest.mark.asyncio
async def test_run_tool_against_repo_unsupported(server_module):
    from fastapi import HTTPException

    req = server_module.ToolRunRequest(tool="unknown-tool", repo_id="x/y")
    with pytest.raises(HTTPException) as exc:
        await server_module._run_tool_against_repo(req)
    assert exc.value.status_code == 400
    assert "Unsupported tool" in exc.value.detail


@pytest.mark.asyncio
async def test_run_tool_against_repo_happy_path(server_module, tmp_path, monkeypatch):
    """Simulate: repo already materialized + tool already installed + stubbed run."""
    base = tmp_path / "base"
    base.mkdir()
    repo_path = base / "owner/repo"
    repo_path.mkdir(parents=True)
    (repo_path / "SUMD.md").write_text("# Stubbed SUMD\n")

    # Tool is already "installed" per the cache.
    server_module._TOOL_INSTALL_CACHE["sumd"] = {
        "available": True,
        "binary_path": "/fake/bin/sumd",
        "installed_now": False,
    }

    # Avoid actually spawning a subprocess.
    class FakeCompleted:
        def __init__(self):
            self.returncode = 0
            self.stdout = "Generated SUMD.md\n"
            self.stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeCompleted())

    req = server_module.ToolRunRequest(
        tool="sumd",
        repo_id="owner/repo",
        repo_url=None,
        base_path=str(base),
        use_git_proxy=False,  # skip real sync
    )
    result = await server_module._run_tool_against_repo(req)

    assert result["ok"] is True
    assert result["tool"] == "sumd"
    assert result["repo_id"] == "owner/repo"
    assert result["returncode"] == 0
    assert "Generated SUMD.md" in result["stdout"]
    # SUMD.md was present in the repo, should be picked up as summary file.
    summary_paths = [f["path"] for f in result["summary_files"]]
    assert "SUMD.md" in summary_paths
    assert any("# Stubbed SUMD" in (f.get("content") or "") for f in result["summary_files"])


@pytest.mark.asyncio
async def test_run_tool_against_repo_install_fails(server_module, tmp_path, monkeypatch):
    base = tmp_path / "base"
    base.mkdir()
    repo_path = base / "owner/repo"
    repo_path.mkdir(parents=True)

    # Force the install-cache miss and make pip install fail quickly.
    server_module._TOOL_INSTALL_CACHE.pop("vallm", None)

    original_which = server_module.shutil.which
    monkeypatch.setattr(server_module.shutil, "which", lambda name: None)

    class FakeFail:
        returncode = 1
        stdout = ""
        stderr = "ERROR: Could not find a version"

    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: FakeFail())

    req = server_module.ToolRunRequest(
        tool="vallm",
        repo_id="owner/repo",
        base_path=str(base),
        use_git_proxy=False,
    )
    try:
        result = await server_module._run_tool_against_repo(req)
    finally:
        monkeypatch.setattr(server_module.shutil, "which", original_which)

    assert result["ok"] is False
    assert "is not installed" in result["error"]
    assert result["install"]["available"] is False
