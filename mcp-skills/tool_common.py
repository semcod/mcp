"""Shared constants and text helpers for mcp-skills tool execution."""

from __future__ import annotations

_MAX_INLINE_FILE_BYTES = 64 * 1024
_MAX_STREAM_BYTES = 32 * 1024


def truncate_text(text: str, limit: int = _MAX_STREAM_BYTES) -> str:
    if not text:
        return ""
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return text
    truncated = encoded[:limit].decode("utf-8", errors="replace")
    return truncated + f"\n... [truncated, {len(encoded) - limit} more bytes]"
