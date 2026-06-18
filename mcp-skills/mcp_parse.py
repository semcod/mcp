"""Parse MCP TextContent tool results to JSON."""

from __future__ import annotations

import json
from typing import Any

from mcp.types import TextContent

def parse_tool_result(result: list[TextContent]) -> Any:
    if not result:
        return {}
    text = result[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}

