"""Safe JSON/YAML merge helpers — never destroy unrelated IDE config."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def save_json(path: Path, data: dict[str, Any], *, dry_run: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if dry_run:
        return
    path.write_text(payload, encoding="utf-8")


def merge_mcp_servers(
    existing: dict[str, Any],
    server_name: str,
    server_cfg: dict[str, Any],
    *,
    force: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    """Merge one MCP server entry; return (merged_doc, messages)."""
    out = copy.deepcopy(existing)
    servers = out.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError("mcpServers must be an object")

    messages: list[str] = []
    if server_name in servers:
        if servers[server_name] == server_cfg:
            messages.append(f"unchanged: mcpServers.{server_name}")
            return out, messages
        if force:
            servers[server_name] = server_cfg
            messages.append(f"replaced: mcpServers.{server_name}")
        else:
            messages.append(f"skipped: mcpServers.{server_name} already exists (use --force)")
        return out, messages

    servers[server_name] = server_cfg
    messages.append(f"added: mcpServers.{server_name}")
    return out, messages


def merge_continue_models(
    existing: dict[str, Any],
    models: list[dict[str, Any]],
    *,
    force: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    out = copy.deepcopy(existing)
    current = out.setdefault("models", [])
    if not isinstance(current, list):
        raise ValueError("continue config models must be a list")

    messages: list[str] = []
    by_title = {
        m.get("title"): i for i, m in enumerate(current) if isinstance(m, dict) and m.get("title")
    }
    for model in models:
        title = model.get("title")
        if not title:
            continue
        if title in by_title:
            idx = by_title[title]
            if current[idx] == model:
                messages.append(f"unchanged: continue model {title}")
            elif force:
                current[idx] = model
                messages.append(f"replaced: continue model {title}")
            else:
                messages.append(f"skipped: continue model {title} (use --force)")
        else:
            current.append(model)
            messages.append(f"added: continue model {title}")
    return out, messages


def merge_vscode_settings(
    existing: dict[str, Any],
    updates: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    out = copy.deepcopy(existing)
    messages: list[str] = []
    for key, value in updates.items():
        if key not in out:
            out[key] = value
            messages.append(f"added: settings {key}")
        elif out[key] == value:
            messages.append(f"unchanged: settings {key}")
        else:
            messages.append(f"skipped: settings {key} (existing value kept)")
    return out, messages
