"""Command-line interface for env2mcp."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import EnvConfig
from .github_cli import GitHubCLI, configure_github, get_github_token


def cmd_github_login(args) -> int:
    """Handle github login command."""
    env_path = Path(args.env_file) if args.env_file else Path(".env")

    result = configure_github(env_path, interactive=True)

    if result["success"]:
        print(f"\n✓ {result['message']}")
        if result.get("username"):
            print(f"  User: {result['username']}")
        print(f"  Saved to: {env_path.absolute()}")
        return 0
    else:
        print(f"\n✗ {result['message']}")
        return 1


def cmd_github_status(args) -> int:
    """Check GitHub authentication status."""
    gh = GitHubCLI()

    if not gh.is_available():
        print("✗ GitHub CLI (gh) is not installed")
        print("  Install from: https://cli.github.com/")
        return 1

    status = gh.get_auth_status()

    if status.get("authenticated"):
        print("✓ GitHub CLI is authenticated")
        user = gh.get_user()
        if user:
            print(f"  User: {user}")
        if status.get("protocol"):
            print(f"  Protocol: {status['protocol']}")
    else:
        print("✗ Not authenticated with GitHub")
        if status.get("error"):
            print(f"  Error: {status['error']}")

    # Check .env file
    env_path = Path(args.env_file) if args.env_file else Path(".env")
    config = EnvConfig(env_path)
    token = config.get("GITHUB_PAT") or config.get("GITHUB_TOKEN")

    if token:
        print(f"✓ Token found in {env_path}")
    else:
        print(f"✗ No token in {env_path}")

    return 0 if (status.get("authenticated") or token) else 1


def cmd_github_logout(args) -> int:
    """Handle github logout command."""
    gh = GitHubCLI()

    if not gh.is_available():
        print("✗ GitHub CLI (gh) is not installed")
        return 1

    success, msg = gh.logout()

    # Also remove from .env
    env_path = Path(args.env_file) if args.env_file else Path(".env")
    config = EnvConfig(env_path)
    had_token = "GITHUB_PAT" in config or "GITHUB_TOKEN" in config
    config.remove("GITHUB_PAT")
    config.remove("GITHUB_TOKEN")
    config.remove("GITHUB_USER")
    config.save()

    if success:
        print(f"✓ {msg}")
    else:
        print(f"✗ {msg}")

    if had_token:
        print(f"✓ Removed tokens from {env_path}")

    return 0 if success else 1


def cmd_github_repos(args) -> int:
    """List GitHub repositories."""
    gh = GitHubCLI()

    if not gh.is_available():
        print("✗ GitHub CLI (gh) is not installed")
        return 1

    repos = gh.list_repos(owner=args.owner, limit=args.limit)

    if not repos:
        print("No repositories found or not authenticated")
        return 1

    print(f"\n{'Repository':<40} {'URL':<50}")
    print("-" * 90)

    for repo in repos:
        name = repo.get("name", "unknown")
        url = repo.get("url", "")
        desc = repo.get("description", "")[:40]
        print(f"{name:<40} {url:<50}")
        if desc:
            print(f"  {desc}")

    return 0


def cmd_env_show(args) -> int:
    """Show current environment configuration."""
    env_path = Path(args.env_file) if args.env_file else Path(".env")
    config = EnvConfig(env_path)

    print(f"Configuration from: {env_path.absolute()}")
    print("-" * 50)

    for key, value in sorted(config.items()):
        # Mask sensitive values
        if any(s in key.lower() for s in ["token", "key", "password", "secret", "pat"]):
            display_value = value[:4] + "***" if len(value) > 4 else "***"
        else:
            display_value = value
        print(f"{key}={display_value}")

    return 0


def cmd_env_set(args) -> int:
    """Set environment variable."""
    env_path = Path(args.env_file) if args.env_file else Path(".env")
    config = EnvConfig(env_path)

    config[args.key] = args.value
    config.save()

    print(f"✓ Set {args.key} in {env_path}")
    return 0


def cmd_env_get(args) -> int:
    """Get environment variable."""
    env_path = Path(args.env_file) if args.env_file else Path(".env")
    config = EnvConfig(env_path)

    value = config.get(args.key)
    if value is None:
        print(f"✗ {args.key} not found")
        return 1

    if args.show:
        print(value)
    else:
        # Mask sensitive values
        if any(s in args.key.lower() for s in ["token", "key", "password", "secret", "pat"]):
            display_value = value[:4] + "***" if len(value) > 4 else "***"
        else:
            display_value = value
        print(f"{args.key}={display_value}")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="env2mcp",
        description="Environment configuration manager for MCP projects"
    )
    parser.add_argument(
        "--env-file",
        help="Path to .env file (default: .env)"
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # GitHub commands
    github_parser = subparsers.add_parser("github", help="GitHub integration")
    github_subparsers = github_parser.add_subparsers(dest="github_command")

    # github login
    login_parser = github_subparsers.add_parser("login", help="Authenticate with GitHub")
    login_parser.set_defaults(func=cmd_github_login)

    # github status
    status_parser = github_subparsers.add_parser("status", help="Check GitHub auth status")
    status_parser.set_defaults(func=cmd_github_status)

    # github logout
    logout_parser = github_subparsers.add_parser("logout", help="Logout from GitHub")
    logout_parser.set_defaults(func=cmd_github_logout)

    # github repos
    repos_parser = github_subparsers.add_parser("repos", help="List repositories")
    repos_parser.add_argument("--owner", help="Repository owner (default: authenticated user)")
    repos_parser.add_argument("--limit", type=int, default=30, help="Number of repos to show")
    repos_parser.set_defaults(func=cmd_github_repos)

    # Env commands
    env_parser = subparsers.add_parser("env", help="Environment management")
    env_subparsers = env_parser.add_subparsers(dest="env_command")

    # env show
    show_parser = env_subparsers.add_parser("show", help="Show all environment variables")
    show_parser.set_defaults(func=cmd_env_show)

    # env set
    set_parser = env_subparsers.add_parser("set", help="Set environment variable")
    set_parser.add_argument("key", help="Variable name")
    set_parser.add_argument("value", help="Variable value")
    set_parser.set_defaults(func=cmd_env_set)

    # env get
    get_parser = env_subparsers.add_parser("get", help="Get environment variable")
    get_parser.add_argument("key", help="Variable name")
    get_parser.add_argument("--show", action="store_true", help="Show full value (not masked)")
    get_parser.set_defaults(func=cmd_env_get)

    # Quick github setup (default)
    quick_parser = subparsers.add_parser("setup-github", help="Quick GitHub setup wizard")
    quick_parser.set_defaults(func=cmd_github_login)

    args = parser.parse_args(argv)

    if hasattr(args, "func"):
        return args.func(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
