"""Pydantic models for mcp-skills HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, Field

class SyncRepoRequest(BaseModel):
    repo_id: str
    ref: str = "HEAD"


class AnalyzeStructureRequest(BaseModel):
    repo_id: str
    paths: list[str]
    base_path: str | None = None


class RepoMetricsRequest(BaseModel):
    repo_id: str
    base_path: str | None = None
    extensions: list[str] = Field(default_factory=lambda: [".py"])


class PatternDetectionRequest(BaseModel):
    repo_id: str
    base_path: str | None = None
    pattern_types: list[str] = Field(default_factory=lambda: ["complexity", "imports"])


class RecommendRefactoringRequest(BaseModel):
    repo_id: str
    target_paths: list[str] = Field(default_factory=list)
    goal: str = "maintainability"
    base_path: str | None = None


class RedslRefactorRequest(BaseModel):
    repo_id: str
    max_actions: int = 10
    dry_run: bool = True
    execute: bool = False
    user_request: str = ""
    base_path: str | None = None


class ToolRunRequest(BaseModel):
    """Generic request to run a semcod CLI tool against a repo."""

    tool: str
    repo_id: str | None = None
    repo_url: str | None = None
    ref: str = "HEAD"
    subcommand: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    auto_install: bool = True
    timeout: int = 600
    base_path: str | None = None
    use_git_proxy: bool = True

