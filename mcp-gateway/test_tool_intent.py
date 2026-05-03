"""Tests for NLP tool intent parsing and tool result rendering."""
from __future__ import annotations

import pytest

import server as gateway


@pytest.mark.parametrize(
    "msg,expected_tool,expected_repo_url,expected_repo_id",
    [
        (
            "wygeneruj sumd dla https://github.com/tom-sapletta-com/mcp-demo-integration-lab",
            "sumd",
            "https://github.com/tom-sapletta-com/mcp-demo-integration-lab",
            "tom-sapletta-com/mcp-demo-integration-lab",
        ),
        (
            "uruchom code2llm na https://github.com/owner/repo.git",
            "code2llm",
            "https://github.com/owner/repo.git",
            "owner/repo",
        ),
        (
            "run redsl on https://github.com/foo/bar",
            "redsl",
            "https://github.com/foo/bar",
            "foo/bar",
        ),
        (
            "Przeanalizuj redup dla owner/repo",
            "redup",
            None,
            "owner/repo",
        ),
        (
            "sumd https://github.com/tom-sapletta-com/mcp-demo-integration-lab",
            "sumd",
            "https://github.com/tom-sapletta-com/mcp-demo-integration-lab",
            "tom-sapletta-com/mcp-demo-integration-lab",
        ),
    ],
)
def test_parse_tool_intent_recognizes_tool_and_repo(
    msg: str,
    expected_tool: str,
    expected_repo_url: str | None,
    expected_repo_id: str | None,
):
    intent = gateway.parse_tool_intent(msg)
    assert intent is not None, f"Expected intent for: {msg!r}"
    assert intent["tool"] == expected_tool
    assert intent["repo_url"] == expected_repo_url
    assert intent["repo_id"] == expected_repo_id


@pytest.mark.parametrize(
    "msg",
    [
        "",
        "Repo: owner/repo\nZadanie: refactor",
        "Pokaż token github",
        "lista repo na github",
        "Hello world",
    ],
)
def test_parse_tool_intent_returns_none_for_non_tool_prompts(msg: str):
    assert gateway.parse_tool_intent(msg) is None


def test_parse_tool_intent_uses_prompt_ctx_repo_id():
    msg = "wygeneruj sumd"
    ctx = {"repo_id": "owner/repo"}
    intent = gateway.parse_tool_intent(msg, ctx)
    assert intent is not None
    assert intent["tool"] == "sumd"
    assert intent["repo_id"] == "owner/repo"


def test_render_tool_text_includes_artifacts_and_status():
    payload = {
        "tool": "sumd",
        "tool_description": "SUMD generator",
        "repo_id": "owner/repo",
        "repo_url": "https://github.com/owner/repo",
        "ok": True,
        "returncode": 0,
        "command": ["sumd", "scan", "."],
        "sync": {"strategy": "git_clone", "ok": True, "action": "clone"},
        "install": {"available": True, "binary_path": "/usr/local/bin/sumd"},
        "stdout": "Generated SUMD.md",
        "stderr": "",
        "summary_files": [
            {
                "path": "SUMD.md",
                "size": 42,
                "truncated": False,
                "content": "# Project\n\nHello world",
                "binary": False,
            }
        ],
        "output_files": [
            {
                "path": "SUMD.md",
                "size": 42,
                "truncated": False,
                "content": "# Project\n\nHello world",
                "binary": False,
            },
            {
                "path": "SUMR.md",
                "size": 10,
                "truncated": False,
                "content": "Summary",
                "binary": False,
            },
        ],
    }
    text = gateway._render_tool_text(payload)
    assert "✅" in text
    assert "`sumd`" in text
    assert "`owner/repo`" in text
    assert "https://github.com/owner/repo" in text
    assert "## stdout" in text
    assert "Generated SUMD.md" in text
    assert "## Wygenerowane artefakty" in text
    assert "SUMD.md" in text
    # The non-summary file is listed under "Pozostałe pliki wyjściowe".
    assert "SUMR.md" in text


def test_render_tool_text_handles_failure():
    payload = {
        "tool": "code2llm",
        "repo_id": "owner/repo",
        "ok": False,
        "returncode": 2,
        "command": ["code2llm", "."],
        "sync": {"strategy": "git_clone", "ok": False, "action": "clone", "stderr": "boom"},
        "install": {"available": False, "error": "pip install failed"},
        "stdout": "",
        "stderr": "Traceback: ...",
        "error": "Tool 'code2llm' is not installed and auto_install failed.",
    }
    text = gateway._render_tool_text(payload)
    assert "❌" in text
    assert "auto_install failed" in text
    assert "## stderr" in text


def test_render_chat_content_dispatches_tool_skill():
    result = {
        "skill": "tool",
        "tenant": "default",
        "repo_id": "owner/repo",
        "tool_result": {
            "tool": "sumd",
            "repo_id": "owner/repo",
            "ok": True,
            "returncode": 0,
            "command": ["sumd", "scan", "."],
            "stdout": "ok",
            "stderr": "",
            "sync": {"strategy": "git_clone", "ok": True},
            "install": {"available": True, "binary_path": "/usr/local/bin/sumd"},
            "summary_files": [],
            "output_files": [],
        },
    }
    rendered = gateway._render_chat_content(result)
    assert "`sumd`" in rendered
    assert "✅" in rendered


def test_force_tool_skill_with_no_intent_returns_helpful_error():
    """When user picks mcp-skills/tool but writes nothing recognizable."""
    intent_stub = {"tool": None, "repo_url": None, "repo_id": None, "args": []}
    # _render_tool_text directly handles this shape.
    rendered = gateway._render_tool_text({
        "tool": None,
        "ok": False,
        "error": (
            "Nie rozpoznałem nazwy narzędzia. Dostępne: "
            + ", ".join(gateway.SUPPORTED_TOOL_NAMES)
        ),
    })
    assert "Nie rozpoznałem" in rendered
    assert "sumd" in rendered
