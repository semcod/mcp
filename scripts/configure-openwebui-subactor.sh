#!/usr/bin/env bash
set -euo pipefail

account_id="${SUBACTOR_ACCOUNT_ID:-softreck}"
provider="${SUBACTOR_PROVIDER:-chatgpt}"
tool_id="${SUBACTOR_TOOL_ID:-codex}"
control_url="${SUBACTOR_CONTROL_URL:-http://172.17.0.1:8088}"
connection_id="${SUBACTOR_OPENWEBUI_CONNECTION_ID:-subactor-${account_id}-${provider}-${tool_id}}"

docker compose exec -T \
  -e SUBACTOR_ACCOUNT_ID="$account_id" \
  -e SUBACTOR_PROVIDER="$provider" \
  -e SUBACTOR_TOOL_ID="$tool_id" \
  -e SUBACTOR_CONTROL_URL="$control_url" \
  -e SUBACTOR_OPENWEBUI_CONNECTION_ID="$connection_id" \
  openwebui sh -lc '
    export WEBUI_SECRET_KEY="$(tr -d "\r\n" < /run/secrets/openwebui-session)"
    python -
  ' <<'PY'
import asyncio
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from open_webui.models.config import Config


def identifier(name: str) -> str:
    value = os.environ[name].strip().lower()
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", value) is None:
        raise SystemExit(f"invalid {name}")
    return value


async def configure() -> None:
    account_id = identifier("SUBACTOR_ACCOUNT_ID")
    provider = identifier("SUBACTOR_PROVIDER")
    tool_id = identifier("SUBACTOR_TOOL_ID")
    connection_id = os.environ["SUBACTOR_OPENWEBUI_CONNECTION_ID"].strip()
    if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}", connection_id) is None:
        raise SystemExit("invalid SUBACTOR_OPENWEBUI_CONNECTION_ID")

    control_url = os.environ["SUBACTOR_CONTROL_URL"].strip().rstrip("/")
    parsed = urlsplit(control_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SystemExit("invalid SUBACTOR_CONTROL_URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SystemExit("SUBACTOR_CONTROL_URL must not contain credentials or a query")

    secret_path = Path("/run/secrets/openwebui-mcp-bearer")
    token = secret_path.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise SystemExit("OpenWebUI MCP bearer secret is missing or too short")

    url = (
        f"{control_url}/mcp/accounts/{account_id}/providers/{provider}/tools/{tool_id}"
    )
    connection = {
        "auth_type": "bearer",
        "config": {
            "access_grants": [
                {
                    "permission": "read",
                    "principal_id": "*",
                    "principal_type": "user",
                }
            ],
            "enable": True,
            "function_name_filter_list": "cli.status,cli.plan,cli.execute",
        },
        "headers": None,
        "info": {
            "description": (
                "Scoped Subactor MCP: closed DSL, grant and intent required for execution."
            ),
            "id": connection_id,
            "name": f"Subactor — {account_id} / {provider} / {tool_id}",
        },
        "key": token,
        "path": "",
        "type": "mcp",
        "url": url,
    }
    connections = await Config.get("tool_server.connections", [])
    if not isinstance(connections, list):
        raise SystemExit("OpenWebUI tool_server.connections is not a list")
    updated = [
        item
        for item in connections
        if (item.get("info") or {}).get("id") != connection_id
    ]
    updated.append(connection)
    await Config.upsert({"tool_server.connections": updated})
    print(
        json.dumps(
            {
                "configured": True,
                "connection_id": connection_id,
                "url": url,
                "tools": ["cli.status", "cli.plan", "cli.execute"],
                "token_logged": False,
            },
            sort_keys=True,
        )
    )


asyncio.run(configure())
PY
