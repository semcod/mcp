# env2mcp

Environment configuration manager for MCP projects. Provides utilities to manage `.env` files and integrate with GitHub CLI (`gh`) for authentication.

## Installation

```bash
# From project root
pip install -e ./env2mcp

# Or with pipx
pipx install ./env2mcp
```

## Quick Start

### GitHub Setup Wizard

```bash
# Interactive setup - checks gh CLI, prompts for auth, saves to .env
env2mcp setup-github

# Or use the github command group
env2mcp github login
```

### Environment Management

```bash
# Show all environment variables
env2mcp env show

# Set a variable
env2mcp env set OPENROUTER_API_KEY "sk-or-v1-..."

# Get a variable (masked by default)
env2mcp env get OPENROUTER_API_KEY
env2mcp env get OPENROUTER_API_KEY --show  # Show full value
```

### GitHub Commands

```bash
# Check auth status
env2mcp github status

# Login (interactive)
env2mcp github login

# List your repos
env2mcp github repos --limit 10

# List repos for specific user/org
env2mcp github repos --owner microsoft --limit 5

# Logout
env2mcp github logout
```

## Python API

```python
from env2mcp import EnvConfig, GitHubCLI, get_github_token

# Load .env file
config = EnvConfig(".env")

# Get/set values
api_key = config.get("OPENROUTER_API_KEY")
config["GITHUB_PAT"] = "ghp_xxx"
config.save()

# GitHub CLI integration
gh = GitHubCLI()
if gh.is_available():
    token = gh.get_token()
    user = gh.get_user()
    repos = gh.list_repos(limit=10)
```

## How It Works

1. **GitHub Authentication**: Checks for `gh` CLI and uses it to get tokens securely
2. **Token Storage**: Saves `GITHUB_PAT` to `.env` file with backup creation
3. **Environment Loading**: Loads variables from both `.env` file and actual environment (env takes precedence)

## Integration with MCP

The package is used across the MCP project:

- `mcp-git-proxy` uses `GITHUB_PAT` for authenticated git operations
- `llm-agent` loads configuration via env2mcp
- `mcp-webui` provides UI for GitHub repo configuration


## License

Licensed under Apache-2.0.
