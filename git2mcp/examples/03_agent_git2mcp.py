#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(description="git2mcp example: run full LLM agent workflow")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--source-path", required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--test-command", default="python3 -m compileall -q .")
    args = parser.parse_args()

    command = [
        "docker-compose",
        "run",
        "--rm",
        "llm-agent",
        "python",
        "agent_git2mcp.py",
        "--repo",
        args.repo,
        "--source-path",
        args.source_path,
        "--branch",
        args.branch,
        "--test-command",
        args.test_command,
    ]

    if args.execute:
        command.append("--execute")
    if args.push:
        command.append("--push")

    proc = subprocess.run(command, capture_output=True, text=True, check=True)
    print(proc.stdout)

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return

    status = payload.get("status")
    tests_ok = payload.get("execution", {}).get("tests", {}).get("ok")
    print(f"agent_status={status} tests_ok={tests_ok} dry_run={payload.get('dry_run')}")


if __name__ == "__main__":
    main()
