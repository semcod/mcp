"""mcp-webui: lightweight test/QA UI for MCP Skills + git2mcp.

Pages:
- /          dashboard
- /repos     list + sync form
- /github    GitHub configuration and repo management
- /skills    invoke models via gateway
- /diff      worktree diff for repo
- /playground free-form prompt -> gateway
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# Import env2mcp if available (for GitHub config)
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "env2mcp"))
    from env2mcp import EnvConfig, GitHubCLI, get_github_token
    ENV2MCP_AVAILABLE = True
except ImportError:
    ENV2MCP_AVAILABLE = False


GATEWAY_URL = os.getenv("GATEWAY_URL", "http://mcp-gateway:9000")
GIT_PROXY_URL = os.getenv("GIT_PROXY_URL", "http://mcp-git-proxy:8080")
WEBUI_API_KEY = os.getenv("WEBUI_API_KEY", "sk-mcp-default-dev-key")

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI(title="mcp-webui", version="0.1.0")


def gateway_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {WEBUI_API_KEY}", "Content-Type": "application/json"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            health = (await client.get(f"{GATEWAY_URL}/health")).json()
        except Exception as exc:
            health = {"error": str(exc)}
        try:
            models = (
                await client.get(f"{GATEWAY_URL}/v1/models", headers=gateway_headers())
            ).json()
        except Exception as exc:
            models = {"error": str(exc)}
    return templates.TemplateResponse("index.html", {"request": request, "health": health, "models": models})


@app.get("/repos", response_class=HTMLResponse)
async def repos_page(request: Request):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            repos = (await client.get(f"{GIT_PROXY_URL}/repos")).json()
        except Exception as exc:
            repos = []
    return templates.TemplateResponse("repos.html", {"request": request, "repos": repos})


@app.post("/repos/sync")
async def repos_sync(repo_id: str = Form(...), source_path: str = Form(...), branch: str = Form("main")):
    async with httpx.AsyncClient(timeout=120.0) as client:
        await client.post(
            f"{GIT_PROXY_URL}/repos/sync",
            json={"repo_id": repo_id, "source_path": source_path, "branch": branch},
        )
    return RedirectResponse(url="/repos", status_code=303)


@app.get("/diff", response_class=HTMLResponse)
async def diff_page(request: Request, repo_id: str | None = None):
    diff_text = ""
    if repo_id:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                r = await client.post(
                    f"{GIT_PROXY_URL}/repos/{repo_id}/worktree/diff",
                    json={"staged": False},
                )
                diff_text = r.json().get("diff", "") if r.status_code == 200 else r.text
            except Exception as exc:
                diff_text = str(exc)
    return templates.TemplateResponse(
        "diff.html",
        {"request": request, "repo_id": repo_id or "", "diff": diff_text},
    )


@app.get("/skills", response_class=HTMLResponse)
async def skills_page(request: Request):
    return templates.TemplateResponse("skills.html", {"request": request})


@app.post("/skills/run", response_class=JSONResponse)
async def skills_run(
    model: str = Form(...),
    prompt: str = Form(...),
    repo_id: str = Form(""),
    source_path: str = Form(""),
):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    if repo_id:
        payload["repo_id"] = repo_id
    if source_path:
        payload["source_path"] = source_path

    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(
            f"{GATEWAY_URL}/v1/chat/completions",
            json=payload,
            headers=gateway_headers(),
        )
    try:
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception:
        return JSONResponse({"raw": r.text}, status_code=r.status_code)


@app.get("/playground", response_class=HTMLResponse)
async def playground(request: Request):
    return templates.TemplateResponse("playground.html", {"request": request})


# GitHub Configuration Endpoints

def _get_github_config():
    """Get GitHub configuration status."""
    config = {
        "configured": False,
        "user": None,
        "token_hint": None,
        "my_repos": []
    }

    # Check environment variables
    token = os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN")
    if token:
        config["configured"] = True
        config["token_hint"] = token[:8] + "..." if len(token) > 8 else "***"

    # Try env2mcp for more details
    if ENV2MCP_AVAILABLE:
        try:
            env_path = Path(__file__).parent.parent / ".env"
            cfg = EnvConfig(env_path)
            if not token:
                token = cfg.get("GITHUB_PAT") or cfg.get("GITHUB_TOKEN")
                if token:
                    config["configured"] = True
                    config["token_hint"] = token[:8] + "..."

            user = cfg.get("GITHUB_USER")
            if user:
                config["user"] = user

            # Try to list repos if we have token
            if token:
                gh = GitHubCLI()
                if gh.is_available():
                    repos = gh.list_repos(limit=10)
                    config["my_repos"] = repos
                    if not user:
                        config["user"] = gh.get_user()
        except Exception:
            pass

    return config


@app.get("/github", response_class=HTMLResponse)
async def github_page(request: Request):
    """GitHub configuration page."""
    github_config = _get_github_config()

    # Get list of repos from git-proxy
    repos = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            repos = (await client.get(f"{GIT_PROXY_URL}/repos")).json()
        except Exception:
            repos = []

    return templates.TemplateResponse(
        "github.html",
        {
            "request": request,
            "github_configured": github_config["configured"],
            "github_user": github_config["user"],
            "github_token_hint": github_config["token_hint"],
            "my_repos": github_config["my_repos"],
            "repos": repos,
            "clone_result": None,
            "sync_result": None
        }
    )


@app.post("/github/configure")
async def github_configure(request: Request, token: str = Form(""), action: str = Form("")):
    """Configure or clear GitHub token."""
    env_path = Path(__file__).parent.parent / ".env"

    if action == "clear":
        if ENV2MCP_AVAILABLE:
            try:
                cfg = EnvConfig(env_path)
                cfg.remove("GITHUB_PAT")
                cfg.remove("GITHUB_TOKEN")
                cfg.remove("GITHUB_USER")
                cfg.save()
            except Exception as exc:
                return RedirectResponse(url=f"/github?error={str(exc)}", status_code=303)
        return RedirectResponse(url="/github?cleared=1", status_code=303)

    if token:
        # Save to .env file using env2mcp
        if ENV2MCP_AVAILABLE:
            try:
                cfg = EnvConfig(env_path)
                cfg["GITHUB_PAT"] = token

                # Try to get username with the token
                gh = GitHubCLI()
                if gh.is_available():
                    # Set temporarily for gh to use
                    os.environ["GITHUB_TOKEN"] = token
                    user = gh.get_user()
                    if user:
                        cfg["GITHUB_USER"] = user

                cfg.save()
            except Exception as e:
                return RedirectResponse(url=f"/github?error={str(e)}", status_code=303)
        else:
            return RedirectResponse(url="/github?error=env2mcp_not_available", status_code=303)

    return RedirectResponse(url="/github?configured=1", status_code=303)


def _normalize_github_url(repo_url: str) -> str:
    """Convert owner/repo or URL to clone URL."""
    repo_url = repo_url.strip()

    # If it's already a full URL
    if repo_url.startswith("http"):
        return repo_url

    # If it's owner/repo format
    if "/" in repo_url and not repo_url.startswith("/"):
        # Check if it's just owner/repo (no protocol)
        parts = repo_url.split("/")
        if len(parts) == 2 and "." not in parts[0]:
            return f"https://github.com/{repo_url}.git"

    return repo_url


@app.post("/github/clone")
async def github_clone(
    request: Request,
    repo_url: str = Form(...),
    repo_id: str = Form(...),
    branch: str = Form("main")
):
    """Clone a repository from GitHub."""
    clone_url = _normalize_github_url(repo_url)

    # Add token to URL if available
    token = os.getenv("GITHUB_PAT") or os.getenv("GITHUB_TOKEN")
    if token and clone_url.startswith("https://github.com/"):
        # Insert token into URL: https://token@github.com/...
        clone_url = clone_url.replace("https://", f"https://{token}@")

    result = {"success": False, "repo_id": repo_id, "error": None}

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{GIT_PROXY_URL}/repos/sync",
                json={
                    "repo_id": repo_id,
                    "repo_url": clone_url,
                    "branch": branch
                }
            )

            if response.status_code == 200:
                result["success"] = True
                result["message"] = response.json()
            else:
                result["error"] = f"HTTP {response.status_code}: {response.text}"
    except Exception as exc:
        result["error"] = str(exc)

    # Re-render page with result
    github_config = _get_github_config()
    repos = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            repos = (await client.get(f"{GIT_PROXY_URL}/repos")).json()
        except Exception:
            pass

    return templates.TemplateResponse(
        "github.html",
        {
            "request": request,
            "github_configured": github_config["configured"],
            "github_user": github_config["user"],
            "github_token_hint": github_config["token_hint"],
            "my_repos": github_config["my_repos"],
            "repos": repos,
            "clone_result": result,
            "sync_result": None
        }
    )


@app.post("/github/sync")
async def github_sync(
    request: Request,
    repo_id: str = Form(...),
    branch: str = Form("main")
):
    """Sync/pull updates for an existing repository."""
    result = {"success": False, "error": None, "message": ""}

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{GIT_PROXY_URL}/repos/{repo_id}/sync-pull",
                json={"branch": branch}
            )

            if response.status_code == 200:
                result["success"] = True
                result["message"] = response.json().get("message", "Synced successfully")
            else:
                result["error"] = f"HTTP {response.status_code}: {response.text}"
    except Exception as exc:
        result["error"] = str(exc)

    # Re-render page with result
    github_config = _get_github_config()
    repos = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            repos = (await client.get(f"{GIT_PROXY_URL}/repos")).json()
        except Exception:
            pass

    return templates.TemplateResponse(
        "github.html",
        {
            "request": request,
            "github_configured": github_config["configured"],
            "github_user": github_config["user"],
            "github_token_hint": github_config["token_hint"],
            "my_repos": github_config["my_repos"],
            "repos": repos,
            "clone_result": None,
            "sync_result": result
        }
    )
