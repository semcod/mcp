from __future__ import annotations

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
