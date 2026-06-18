from semcod_mcp.merge import (
    merge_continue_models,
    merge_mcp_servers,
    merge_vscode_settings,
    remove_continue_models,
    remove_mcp_server,
    remove_vscode_settings,
)


def test_merge_mcp_servers_adds_without_touching_existing():
    existing = {"mcpServers": {"other": {"command": "echo"}}}
    new_server = {"command": "docker", "args": ["compose"]}
    merged, msgs = merge_mcp_servers(existing, "semcod-mcp-skills", new_server)
    assert "other" in merged["mcpServers"]
    assert merged["mcpServers"]["semcod-mcp-skills"] == new_server
    assert any("added" in m for m in msgs)


def test_merge_mcp_servers_skips_when_different_without_force():
    existing = {"mcpServers": {"semcod-mcp-skills": {"command": "old"}}}
    merged, msgs = merge_mcp_servers(existing, "semcod-mcp-skills", {"command": "new"}, force=False)
    assert merged["mcpServers"]["semcod-mcp-skills"]["command"] == "old"
    assert any("skipped" in m for m in msgs)


def test_merge_continue_models_by_title():
    existing = {"models": [{"title": "other", "model": "x"}]}
    new_models = [{"title": "semcod-mcp-analyze", "model": "mcp-skills/analyze"}]
    merged, msgs = merge_continue_models(existing, new_models)
    assert len(merged["models"]) == 2
    assert any("added" in m for m in msgs)


def test_merge_vscode_settings_non_destructive():
    existing = {"editor.tabSize": 4}
    merged, _ = merge_vscode_settings(existing, {"semcod-mcp.gatewayUrl": "http://localhost:9000/v1"})
    assert merged["editor.tabSize"] == 4
    assert "semcod-mcp.gatewayUrl" in merged


def test_remove_mcp_server_preserves_other_servers():
    existing = {"mcpServers": {"other": {"command": "echo"}, "semcod-mcp-skills": {"command": "docker"}}}
    merged, msgs = remove_mcp_server(existing, "semcod-mcp-skills")
    assert merged is not None
    assert "other" in merged["mcpServers"]
    assert "semcod-mcp-skills" not in merged["mcpServers"]
    assert any("removed" in m for m in msgs)


def test_remove_mcp_server_deletes_empty_doc():
    existing = {"mcpServers": {"semcod-mcp-skills": {"command": "docker"}}}
    merged, msgs = remove_mcp_server(existing, "semcod-mcp-skills")
    assert merged is None
    assert any("removed" in m for m in msgs)


def test_remove_continue_models_by_title():
    existing = {
        "models": [
            {"title": "other", "model": "x"},
            {"title": "semcod-mcp-analyze", "model": "mcp-skills/analyze"},
        ]
    }
    merged, msgs = remove_continue_models(existing, {"semcod-mcp-analyze"})
    assert merged is not None
    assert len(merged["models"]) == 1
    assert merged["models"][0]["title"] == "other"
    assert any("removed" in m for m in msgs)


def test_remove_vscode_settings_keeps_unrelated_keys():
    existing = {"editor.tabSize": 4, "semcod-mcp.gatewayUrl": "http://localhost:9000/v1"}
    merged, msgs = remove_vscode_settings(existing, {"semcod-mcp.gatewayUrl"})
    assert merged == {"editor.tabSize": 4}
    assert any("removed" in m for m in msgs)
