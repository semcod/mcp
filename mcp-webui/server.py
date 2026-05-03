"""mcp-webui: lightweight test/QA UI for MCP Skills + git2mcp.

Pages:
- /          dashboard
- /repos     list + sync form
- /skills    invoke models via gateway
- /diff      worktree diff for repo
- /playground free-form prompt -> gateway
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates


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
