from __future__ import annotations

import html
import os
from pathlib import Path

import markdown
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

DOCS_ROOT = Path(os.getenv("MCP_DOCS_ROOT", "/docs"))
_port_openwebui = os.getenv("PORT_OPENWEBUI", "3000")
OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", f"http://localhost:{_port_openwebui}/")

app = FastAPI(title="mcp-docs", version="0.1.0")


def _markdown_to_html(md_text: str) -> str:
    return markdown.markdown(
        md_text,
        extensions=["fenced_code", "tables", "toc", "sane_lists"],
        output_format="html5",
    )


def _page(title: str, body: str) -> str:
    openwebui_url = OPENWEBUI_URL
    return f"""<!doctype html>
<html lang=\"pl\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #0b1020;
      --card: #111833;
      --text: #e7ecff;
      --muted: #99a6d3;
      --link: #7dd3fc;
      --code-bg: #0b122a;
      --border: #2a3766;
      --success: #4ade80;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "JetBrains Mono", "Fira Code", monospace;
      background: radial-gradient(circle at 20% -20%, #1f2a57, var(--bg));
      color: var(--text);
      line-height: 1.6;
    }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
    .card {{
      background: color-mix(in srgb, var(--card) 85%, #000 15%);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
      box-shadow: 0 10px 30px rgba(0,0,0,.25);
    }}
    a {{ color: var(--link); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    h1, h2, h3 {{ line-height: 1.2; }}
    code {{ background: var(--code-bg); padding: 2px 6px; border-radius: 6px; }}
    pre {{
      background: var(--code-bg);
      padding: 12px;
      border-radius: 10px;
      overflow-x: auto;
      border: 1px solid var(--border);
      position: relative;
      margin: 16px 0;
    }}
    .pre-actions {{
      position: absolute;
      top: 8px;
      right: 8px;
      display: flex;
      gap: 8px;
    }}
    .pre-btn {{
      background: rgba(125, 211, 252, 0.15);
      border: 1px solid var(--link);
      color: var(--link);
      padding: 4px 10px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      font-family: inherit;
      transition: all 0.2s;
    }}
    .pre-btn:hover {{
      background: var(--link);
      color: var(--bg);
    }}
    .pre-btn.copied {{
      background: var(--success);
      border-color: var(--success);
      color: var(--bg);
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border: 1px solid var(--border); padding: 8px; text-align: left; }}
    .topbar {{ display: flex; gap: 12px; align-items: center; margin-bottom: 16px; color: var(--muted); }}
    .topbar a {{ color: var(--muted); }}
    .muted {{ color: var(--muted); }}
    .toast {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: var(--success);
      color: var(--bg);
      padding: 12px 20px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      opacity: 0;
      transform: translateY(20px);
      transition: all 0.3s;
      pointer-events: none;
      z-index: 1000;
      font-weight: bold;
    }}
    .toast.show {{
      opacity: 1;
      transform: translateY(0);
    }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    {body}
  </div>
  <div id=\"toast\" class=\"toast\">Skopiowano do schowka!</div>
  <script>
    (function() {{
      const OPENWEBUI_URL = "{openwebui_url}";
      const toast = document.getElementById("toast");

      function showToast(msg) {{
        toast.textContent = msg;
        toast.classList.add("show");
        setTimeout(() => toast.classList.remove("show"), 2000);
      }}

      function addPreButtons() {{
        document.querySelectorAll("pre").forEach(function(pre) {{
          const code = pre.textContent || "";
          const isPrompt = code.includes("Repo:") || code.includes("Zadanie:") || code.includes("Execute:");

          const actions = document.createElement("div");
          actions.className = "pre-actions";

          // Kopiuj
          const copyBtn = document.createElement("button");
          copyBtn.className = "pre-btn";
          copyBtn.textContent = "📋 Kopiuj";
          copyBtn.onclick = function() {{
            navigator.clipboard.writeText(code).then(function() {{
              copyBtn.classList.add("copied");
              copyBtn.textContent = "✅ Skopiowano";
              showToast("Skopiowano do schowka!");
              setTimeout(function() {{
                copyBtn.classList.remove("copied");
                copyBtn.textContent = "📋 Kopiuj";
              }}, 2000);
            }});
          }};
          actions.appendChild(copyBtn);

          // Wyślij do OpenWebUI (tylko dla promptów)
          if (isPrompt) {{
            const sendBtn = document.createElement("button");
            sendBtn.className = "pre-btn";
            sendBtn.textContent = "🚀 OpenWebUI";
            sendBtn.onclick = function() {{
              navigator.clipboard.writeText(code).then(function() {{
                showToast("Skopiowano! Otwieram OpenWebUI...");
                setTimeout(function() {{
                  window.open(OPENWEBUI_URL, "_blank");
                }}, 500);
              }});
            }};
            actions.appendChild(sendBtn);
          }}

          pre.appendChild(actions);
        }});
      }}

      if (document.readyState === "loading") {{
        document.addEventListener("DOMContentLoaded", addPreButtons);
      }} else {{
        addPreButtons();
      }}
    }})();
  </script>
</body>
</html>
"""


def _safe_doc_path(rel_path: str) -> Path:
    candidate = (DOCS_ROOT / rel_path).resolve()
    docs_root = DOCS_ROOT.resolve()
    if not str(candidate).startswith(str(docs_root)):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail=f"Document not found: {rel_path}")
    return candidate


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "mcp-docs"}


@app.get("/api/docs")
def list_docs() -> JSONResponse:
    docs = []
    if DOCS_ROOT.exists():
        for path in sorted(DOCS_ROOT.rglob("*.md")):
            docs.append(str(path.relative_to(DOCS_ROOT)))
    return JSONResponse({"count": len(docs), "docs": docs})


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    docs = []
    if DOCS_ROOT.exists():
        for path in sorted(DOCS_ROOT.rglob("*.md")):
            rel = str(path.relative_to(DOCS_ROOT))
            docs.append(rel)

    items = "\n".join(
        f"<li><a href='/docs/{html.escape(rel)}'>{html.escape(rel)}</a></li>" for rel in docs
    )

    body = f"""
    <div class=\"card\">
      <div class=\"topbar\">
        <strong>MCP Docs Service</strong>
        <span>•</span>
        <a href=\"/docs/README.md\">README</a>
        <span>•</span>
        <a href=\"/docs/CHAT_PLAYBOOKS.md\">CHAT_PLAYBOOKS</a>
        <span>•</span>
        <a href=\"/api/docs\">API list</a>
        <span>•</span>
        <a href=\"{openwebui_url}\" target=\"_blank\">🚀 OpenWebUI</a>
      </div>
      <h1>Dokumentacja projektu i playbooki</h1>
      <p class=\"muted\">Osobna usługa Docker udostępniająca dokumentację projektu oraz gotowe dialogi chat do refaktoryzacji, migracji, integracji i modularyzacji.</p>
      <h2>Dostępne dokumenty</h2>
      <ul>{items}</ul>
    </div>
    """
    return _page("MCP Docs", body)


@app.get("/docs/{doc_path:path}", response_class=HTMLResponse)
def render_doc(doc_path: str) -> str:
    file_path = _safe_doc_path(doc_path)
    text = file_path.read_text(encoding="utf-8")
    rendered = _markdown_to_html(text)

    body = f"""
    <div class=\"topbar\">
      <a href=\"/\">← dokumenty</a>
      <span>•</span>
      <span class=\"muted\">{html.escape(doc_path)}</span>
    </div>
    <div class=\"card\">{rendered}</div>
    """
    return _page(f"MCP Docs - {doc_path}", body)
