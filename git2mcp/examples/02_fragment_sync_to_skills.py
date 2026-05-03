#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess

import httpx


async def main() -> None:
    parser = argparse.ArgumentParser(description="git2mcp example: fragment sync to mcp-skills")
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--source-path", required=True)
    parser.add_argument("--git-proxy-url", default="http://localhost:8081")
    parser.add_argument("--skills-container", default="mcp-skills")
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=120.0) as client:
        sync = await client.post(
            f"{args.git_proxy_url}/repos/sync",
            json={
                "repo_id": args.repo_id,
                "source_path": args.source_path,
                "branch": "main",
            },
        )
        sync.raise_for_status()

    script = f"""
import asyncio, json
from server import MCPSkillsServer

async def run():
    s = MCPSkillsServer()
    r = await s._sync_from_git_proxy({args.repo_id!r})
    print(json.dumps(r))

asyncio.run(run())
"""

    proc = subprocess.run(
        [
            "docker-compose",
            "exec",
            "-T",
            args.skills_container,
            "python",
            "-c",
            script,
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    skills_result = json.loads(proc.stdout.strip())
    result = {
        "sync": sync.json(),
        "skills_sync": skills_result,
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
