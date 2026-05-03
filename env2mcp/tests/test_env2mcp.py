"""Tests for env2mcp config module."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from env2mcp.config import EnvConfig


def test_import():
    """Verify the main package can be imported."""
    import env2mcp  # noqa: F401


def test_format_value_token_no_quotes():
    """GitHub tokens and simple values must NOT be quoted."""
    cfg = EnvConfig.__new__(EnvConfig)
    cfg._data = {}
    assert cfg._format_value("GITHUB_PAT", "gho_TYdD9yBhpJy") == "gho_TYdD9yBhpJy"
    assert cfg._format_value("GITHUB_PAT", "ghp_abc123XYZ") == "ghp_abc123XYZ"


def test_format_value_no_double_quote_wrap():
    """Values already wrapped in quotes must not get double-quoted."""
    cfg = EnvConfig.__new__(EnvConfig)
    cfg._data = {}
    result = cfg._format_value("KEY", '"gho_abc123"')
    assert result == "gho_abc123", f"Expected bare token, got: {result!r}"
    assert not result.startswith('"'), f"Should not be quoted: {result!r}"


def test_format_value_spaces_quoted():
    """Values with spaces must be quoted."""
    cfg = EnvConfig.__new__(EnvConfig)
    cfg._data = {}
    result = cfg._format_value("KEY", "hello world")
    assert result == '"hello world"'


def test_format_value_empty():
    cfg = EnvConfig.__new__(EnvConfig)
    cfg._data = {}
    assert cfg._format_value("KEY", "") == '""'


def test_format_value_numeric():
    cfg = EnvConfig.__new__(EnvConfig)
    cfg._data = {}
    assert cfg._format_value("PORT", "9000") == "9000"


def test_save_load_roundtrip(tmp_path):
    """Save then load must preserve values without adding quotes."""
    env_file = tmp_path / ".env"
    cfg = EnvConfig(env_file)
    cfg.set("GITHUB_PAT", "gho_TestToken123")
    cfg.set("PORT_GATEWAY", "9000")
    cfg.set("DESC", "hello world")
    cfg.save(create_backup=False)

    content = env_file.read_text()
    assert "GITHUB_PAT=gho_TestToken123" in content, f"Token should be unquoted: {content}"
    assert 'PORT_GATEWAY=9000' in content
    assert 'DESC="hello world"' in content

    cfg2 = EnvConfig(env_file)
    assert cfg2.get("GITHUB_PAT") == "gho_TestToken123"
    assert cfg2.get("PORT_GATEWAY") == "9000"
    assert cfg2.get("DESC") == "hello world"
