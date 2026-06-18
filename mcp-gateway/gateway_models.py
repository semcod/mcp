"""Pydantic request models for OpenAI-compatible gateway API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    async_mode: bool | None = None
    repo_id: str | None = None
    repo_url: str | None = None
    github_token: str | None = None
    source_path: str | None = None
    branch: str = "main"
    execute: bool | None = None
    push: bool | None = None
    draft: bool | None = None
    draft_name: str | None = None
    open_pr: bool | None = None
    pr_title: str | None = None
    pr_body: str | None = None
    pr_base: str | None = None
    test_command: str | None = None
    remote: str | None = None
