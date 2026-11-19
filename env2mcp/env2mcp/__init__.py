"""env2mcp - Environment configuration manager for MCP projects.

Provides utilities to:
- Load/save .env files
- Integrate with GitHub CLI (gh) for authentication
- Manage project configuration
"""

from .config import EnvConfig, load_env, save_env
from .github_cli import GitHubCLI, get_github_token

__version__ = "0.1.4"
__all__ = ["EnvConfig", "load_env", "save_env", "GitHubCLI", "get_github_token"]
