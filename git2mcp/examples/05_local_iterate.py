#!/usr/bin/env python3
"""git2mcp example: local iteration before commit.

Workflow:
  1. sync repo -> mcp-git-proxy
  2. checkpoint working tree
  3. apply patch (no commit)
  4. run tests in working tree
  5. on success: stage + commit on draft branch
  6. on failure: restore checkpoint, leave history clean
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

import httpx


SAMPLE_PATCH = """diff --git a/.mcp/local-iter.txt b/.mcp/local-iter.txt
new file mode 100644
--- /dev/null
+++ b/.mcp/local-iter.txt
@@ -0,0 +1 @@
+local iteration artifact
"""


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8081")
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--source-path", required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--task-id", default="local-iter")
    parser.add_argument("--patch-file", help="optional path to a unified diff; default applies a sample patch")
    parser.add_argument("--test-command", default="python3 -m compileall -q .")
    args = parser.parse_args()

    patch_text = SAMPLE_PATCH
    if args.patch_file:
        patch_text = open(args.patch_file, encoding="utf-8").read()

    base = args.base_url.rstrip("/")
    repo_id = args.repo_id

    async with httpx.AsyncClient(timeout=120.0) as client:
        sync = await client.post(
            f"{base}/repos/sync",
            json={"repo_id": repo_id, "source_path": args.source_path, "branch": args.branch},
        )
        sync.raise_for_status()

        ckpt = await client.post(f"{base}/repos/{repo_id}/checkpoint", json={"label": args.task_id})
        ckpt.raise_for_status()
        ckpt_id = ckpt.json()["checkpoint_id"]

        draft = await client.post(
            f"{base}/repos/{repo_id}/branch/draft",
            json={"name": args.task_id},
        )
        draft.raise_for_status()

        check = await client.post(
            f"{base}/repos/{repo_id}/patch/apply",
            json={"patch": patch_text, "check_only": True},
        )
        if check.status_code != 200:
            print(json.dumps({"status": "patch_check_failed", "detail": check.text}))
            return 2

        apply_resp = await client.post(
            f"{base}/repos/{repo_id}/patch/apply",
            json={"patch": patch_text},
        )
        apply_resp.raise_for_status()

        tests = await client.post(
            f"{base}/repos/{repo_id}/run-tests",
            json={"command": args.test_command},
        )
        tests.raise_for_status()
        tests_payload = tests.json()

        if not tests_payload.get("ok"):
            restore = await client.post(
                f"{base}/repos/{repo_id}/checkpoint/restore",
                json={"checkpoint_id": ckpt_id},
            )
            restore.raise_for_status()
            print(json.dumps({
                "status": "tests_failed_rolled_back",
                "tests": tests_payload,
                "restored_from": ckpt_id,
            }, indent=2))
            return 1

        await client.post(f"{base}/repos/{repo_id}/stage", json={"paths": None})
        commit = await client.post(
            f"{base}/repos/{repo_id}/commit",
            json={
                "message": f"chore(mcp): local-iterate task {args.task_id}",
                "changes": [],
                "author_name": "git2mcp-bot",
                "author_email": "git2mcp@local",
            },
        )

        diff = await client.post(f"{base}/repos/{repo_id}/worktree/diff", json={"staged": False})

        print(json.dumps({
            "status": "ok",
            "draft_branch": draft.json()["branch"],
            "checkpoint_id": ckpt_id,
            "tests": tests_payload,
            "commit": commit.json() if commit.status_code == 200 else commit.text,
            "post_diff": diff.json().get("diff", ""),
        }, indent=2))
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
