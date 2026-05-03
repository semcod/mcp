# git2mcp - Git Proxy Client for MCP

Python package for Git operations via MCP (Model Context Protocol) HTTP API. Provides both sync and async clients for `mcp-git-proxy`.

## Features

- **Repository Sync** - Clone or sync from local path/URL
- **Commit Operations** - Create commits with multiple file changes
- **Test Runner** - Execute tests in repository context
- **Push/Pull** - Remote operations
- **Local Operations (NEW)** - Work without commits:
  - Worktree read/write/diff
  - Patch apply/check
  - Staging (git add)
  - Stash save/pop
  - Draft branches
  - Checkpoints (tarball snapshots)
  - Git reset (hard/soft/mixed)
- **Fragment Transfer** - Export repository as fragments for MCP skills

## Installation

```bash
pip install -e .
```

## Quick Start

### Sync Repository

```python
from git2mcp import Git2MCPClient

async with Git2MCPClient("http://localhost:8081") as client:
    # Sync from local path
    result = await client.sync_repo(
        repo_id="team/project",
        source_path="/path/to/source",
        branch="main"
    )
    print(f"Synced to: {result['path']}")
```

### Create Commit

```python
await client.commit(
    repo_id="team/project",
    message="feat: add new feature",
    changes=[
        {"path": "main.py", "content": "print('hello')", "mode": "update"}
    ]
)
```

### Local Operations (No Commit)

```python
# Write file directly to worktree
await client.worktree_write(
    repo_id="team/project",
    path="notes/todo.txt",
    content="- Fix bug"
)

# Apply patch
patch = """diff --git a/main.py b/main.py
--- a/main.py
+++ b/main.py
@@ -1 +1 @@
-print("old")
+print("new")
"""
await client.patch_apply(repo_id="team/project", patch=patch)

# Create checkpoint before changes
ckpt = await client.checkpoint_create(repo_id="team/project", label="before-refactor")

# If something goes wrong, restore checkpoint
await client.checkpoint_restore(repo_id="team/project", checkpoint_id=ckpt["checkpoint_id"])
```

## Client Methods

### Repository Management
- `list_repos()` - List all managed repositories
- `sync_repo(repo_id, source_path=None, repo_url=None, branch="main")` - Sync repository
- `export_package(repo_id, ref="HEAD")` - Export as tar.gz
- `export_fragments(repo_id, ref="HEAD", max_fragment_bytes=200000)` - Export as fragments

### Commit Operations
- `commit(repo_id, message, changes=[], author_name="bot", author_email="bot@local")` - Create commit
- `push(repo_id, remote="origin", branch=None)` - Push to remote
- `reset(repo_id, ref="HEAD~1", mode="hard")` - Reset repository

### Local Operations (NEW in 0.1.8)
- `worktree_read(repo_id, path)` - Read file from worktree
- `worktree_write(repo_id, path, content)` - Write file to worktree
- `worktree_diff(repo_id, staged=False)` - Get diff
- `patch_apply(repo_id, patch, check_only=False)` - Apply unified diff
- `stage(repo_id, paths=None)` - Stage files (git add)
- `stash_save(repo_id, message="stash")` - Save stash
- `stash_pop(repo_id)` - Pop stash
- `branch_draft(repo_id, name, base=None)` - Create draft branch
- `checkpoint_create(repo_id, label=None)` - Create checkpoint
- `checkpoint_restore(repo_id, checkpoint_id)` - Restore checkpoint

### Testing
- `run_tests(repo_id, command="python3 -m compileall -q .")` - Run tests

## Examples

See `examples/` directory:

1. **01_sync_and_commit.py** - Basic sync and commit
2. **02_fragment_sync_to_skills.py** - Fragment transfer to MCP skills
3. **03_agent_git2mcp.py** - Full LLM agent workflow
4. **04_dry_run_vs_execute.py** - Dry-run vs execute with auto-revert
5. **05_local_iterate.py** - Local iteration without commits

## Architecture

```
git2mcp (client) → HTTP → mcp-git-proxy (Docker)
                        ↓
                   git-repo-storage (volume)
```

## Testing

```bash
pytest tests/test_git2mcp.py -v
```

## License

Licensed under Apache-2.0.
