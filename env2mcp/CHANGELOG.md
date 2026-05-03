# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.5] - 2026-05-03

### Fixed
- `_format_value` no longer wraps plain tokens (GitHub PAT, URLs, port numbers) in
  double-quotes. Values are only quoted when they contain whitespace or shell-special
  characters. This prevents `docker-compose` and `bash` from reading `GITHUB_PAT` as
  `"gho_..."` (with literal quote characters), which caused git clone auth failures.
- `save` + `_load` roundtrip is now idempotent — repeated saves no longer accumulate
  extra quote layers.

## [0.1.4] - 2026-05-03

### Docs
- Update README.md
- Update docs/ENV2MCP.md
- Update docs/PRODUCT.md
- Update docs/USAGE.md

### Other
- Update ansible/e2e-docker-stack.yml
- Update env2mcp/env2mcp/github_cli.py
- Update env2mcp/uv.lock
- Update mcp-gateway/server.py

## [0.1.3] - 2026-05-03

### Docs
- Update README.md
- Update TODO.md
- Update docs/USAGE.md

### Other
- Update env2mcp/uv.lock

## [0.1.2] - 2026-05-03

### Docs
- Update README.md
- Update docs/USAGE.md

### Other
- Update env2mcp/uv.lock

## [0.1.1] - 2026-05-03

### Docs
- Update README.md
- Update docs/PRODUCT.md
- Update docs/USAGE.md
- Update env2mcp/README.md

### Other
- Update ansible/e2e-docker-stack.yml
- Update env2mcp/.gitignore
- Update env2mcp/env2mcp/__init__.py
- Update env2mcp/env2mcp/cli.py
- Update env2mcp/env2mcp/config.py
- Update env2mcp/env2mcp/github_cli.py
- Update env2mcp/pyproject.toml
- Update env2mcp/tests/test_env2mcp.py
- Update env2mcp/uv.lock
- Update mcp-gateway/server.py
- ... and 5 more files

