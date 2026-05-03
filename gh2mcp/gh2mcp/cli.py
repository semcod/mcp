from __future__ import annotations

import argparse
import sys
import time

from .sync import GitHubTokenSyncService


def _cmd_status(args: argparse.Namespace) -> int:
    service = GitHubTokenSyncService(args.env_file)
    data = service.get_status()
    print(data)
    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    service = GitHubTokenSyncService(args.env_file)
    data = service.sync_token(force_gh_cli=args.force_gh_cli)
    print(data)
    return 0 if data.get("success") else 1


def _cmd_agent(args: argparse.Namespace) -> int:
    service = GitHubTokenSyncService(args.env_file)
    if args.sync_on_start:
        print(service.sync_token(force_gh_cli=args.force_gh_cli))

    while True:
        time.sleep(args.interval)
        print(service.sync_token(force_gh_cli=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gh2mcp", description="GitHub token sync helper for MCP")
    parser.add_argument("--env-file", default=".env", help="Path to .env file")

    subparsers = parser.add_subparsers(dest="command")

    status = subparsers.add_parser("status", help="Show token status")
    status.set_defaults(func=_cmd_status)

    sync = subparsers.add_parser("sync", help="Sync token to .env")
    sync.add_argument("--force-gh-cli", action="store_true", help="Force token source = gh CLI")
    sync.set_defaults(func=_cmd_sync)

    agent = subparsers.add_parser("agent", help="Run periodic sync agent")
    agent.add_argument("--interval", type=int, default=300, help="Sync interval seconds")
    agent.add_argument("--sync-on-start", action="store_true", help="Sync immediately on startup")
    agent.add_argument("--force-gh-cli", action="store_true", help="Force first sync from gh CLI")
    agent.set_defaults(func=_cmd_agent)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
