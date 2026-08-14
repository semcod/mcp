#!/usr/bin/env bash
set -euo pipefail

account_id="${SUBACTOR_ACCOUNT_ID:-softreck}"
provider="${SUBACTOR_PROVIDER:-chatgpt}"
tool_id="${SUBACTOR_TOOL_ID:-codex}"
control_port="${SUBACTOR_CONTROL_PORT:-8088}"
connection_id="${SUBACTOR_OPENWEBUI_CONNECTION_ID:-subactor-${account_id}-${provider}-${tool_id}}"

discover_control_url() {
  command -v ss >/dev/null 2>&1 || return 1

  local listener host
  while IFS= read -r listener; do
    host="${listener%:${control_port}}"
    host="${host#[}"
    host="${host%]}"
    case "$host" in
      ""|"*"|"0.0.0.0"|"::"|"127."*|"::1") continue ;;
    esac
    printf 'http://%s:%s\n' "$host" "$control_port"
    return 0
  done < <(ss -H -ltn "sport = :${control_port}" | awk '{print $4}')

  return 1
}

control_url="${SUBACTOR_CONTROL_URL:-}"
control_discovered=false
if [[ -z "$control_url" ]]; then
  control_url="$(discover_control_url || true)"
  control_discovered=true
fi
if [[ -z "$control_url" ]]; then
  printf '%s\n' \
    "Unable to discover a non-loopback Subactor Control listener on port ${control_port}." \
    "Set SUBACTOR_CONTROL_URL to an address reachable from the OpenWebUI container." >&2
  exit 1
fi

docker compose exec -T \
  -e SUBACTOR_ACCOUNT_ID="$account_id" \
  -e SUBACTOR_PROVIDER="$provider" \
  -e SUBACTOR_TOOL_ID="$tool_id" \
  -e SUBACTOR_CONTROL_URL="$control_url" \
  -e SUBACTOR_CONTROL_DISCOVERED="$control_discovered" \
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
from urllib.request import Request, urlopen

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

    health_url = f"{control_url}/healthz"
    try:
        with urlopen(Request(health_url, method="GET"), timeout=5) as response:
            health = json.load(response)
            if response.status != 200 or health.get("status") != "ok":
                raise RuntimeError("unexpected health response")
    except Exception as exc:
        raise SystemExit(
            f"Subactor Control is not reachable from OpenWebUI at {health_url}: {exc}"
        ) from exc

    url = (
        f"{control_url}/mcp/accounts/{account_id}/providers/{provider}/tools/{tool_id}"
    )
    discovery_request = Request(
        url,
        data=json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(discovery_request, timeout=5) as response:
            discovery = json.load(response)
    except Exception as exc:
        raise SystemExit(
            f"Subactor MCP preflight failed at {url}: {exc}"
        ) from exc
    tool_names = sorted(
        tool.get("name")
        for tool in discovery.get("result", {}).get("tools", [])
        if isinstance(tool, dict) and isinstance(tool.get("name"), str)
    )
    expected_tools = ["cli.execute", "cli.plan", "cli.status"]
    if tool_names != expected_tools:
        raise SystemExit(
            f"Subactor MCP exposed an unexpected tool boundary: {tool_names}"
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
                "control_discovered": os.environ["SUBACTOR_CONTROL_DISCOVERED"]
                == "true",
                "url": url,
                "tools": tool_names,
                "token_logged": False,
            },
            sort_keys=True,
        )
    )


asyncio.run(configure())
PY
