#!/usr/bin/env python3
"""
Simple HTTP server for MCP Refactoring Dashboard
Serves the HTML dashboard and provides API endpoints for data
"""

import http.server
import socketserver
import json
import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = int(os.getenv("DASHBOARD_PORT", "8080"))
HTML_DIR = Path(__file__).parent
OUTPUT_DIR = Path("/output")
REPOS_DIR = Path("/repos")


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler for dashboard"""

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # API endpoints
        if path == '/api/status':
            self.send_json(self.get_status())
            return

        if path == '/api/analyses':
            self.send_json(self.get_analyses())
            return

        if path.startswith('/api/analysis/'):
            filename = path.replace('/api/analysis/', '')
            self.send_json(self.get_analysis(filename))
            return

        if path == '/api/repos':
            self.send_json(self.get_repos())
            return

        # Serve static files
        if path == '/':
            path = '/index.html'

        file_path = HTML_DIR / path.lstrip('/')

        if file_path.exists() and file_path.is_file():
            self.serve_file(file_path)
        else:
            self.send_error(404, "File not found")

    def serve_file(self, file_path: Path):
        """Serve a static file"""
        content_type = self.get_content_type(file_path.suffix)

        try:
            with open(file_path, 'rb') as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Content-length', len(content))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, str(e))

    def send_json(self, data: dict):
        """Send JSON response"""
        content = json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-length', len(content))
        self.end_headers()
        self.wfile.write(content)

    def get_content_type(self, ext: str) -> str:
        """Get MIME type for file extension"""
        types = {
            '.html': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.svg': 'image/svg+xml',
        }
        return types.get(ext, 'application/octet-stream')

    def get_status(self) -> dict:
        """Get system status"""
        analyses = list(OUTPUT_DIR.glob("*_analysis.json")) if OUTPUT_DIR.exists() else []
        repos = [d.name for d in REPOS_DIR.iterdir() if d.is_dir()] if REPOS_DIR.exists() else []

        return {
            "status": "running",
            "version": "0.1.0",
            "analyses_count": len(analyses),
            "repositories_count": len(repos),
            "output_dir": str(OUTPUT_DIR),
            "repos_dir": str(REPOS_DIR),
        }

    def get_analyses(self) -> list:
        """List all available analyses"""
        if not OUTPUT_DIR.exists():
            return []

        analyses = []
        for f in OUTPUT_DIR.glob("*_analysis.json"):
            try:
                with open(f) as fp:
                    data = json.load(fp)
                analyses.append({
                    "filename": f.name,
                    "repository": data.get("repository", "unknown"),
                    "status": data.get("status", "unknown"),
                    "dry_run": data.get("dry_run", True),
                })
            except:
                analyses.append({
                    "filename": f.name,
                    "repository": "unknown",
                    "status": "error",
                })

        return analyses

    def get_analysis(self, filename: str) -> dict:
        """Get specific analysis data"""
        file_path = OUTPUT_DIR / filename

        if not file_path.exists():
            return {"error": "Analysis not found"}

        try:
            with open(file_path) as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e)}

    def get_repos(self) -> list:
        """List all repositories"""
        if not REPOS_DIR.exists():
            return []

        repos = []
        for d in REPOS_DIR.iterdir():
            if d.is_dir():
                file_count = sum(1 for f in d.rglob("*.py"))
                repos.append({
                    "name": d.name,
                    "path": str(d.relative_to(REPOS_DIR)),
                    "file_count": file_count,
                })

        return repos


class TCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def main():
    print(f"Starting MCP Dashboard Server on port {PORT}")
    print(f"Serving HTML from: {HTML_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Repos directory: {REPOS_DIR}")
    print(f"\nDashboard available at: http://localhost:{PORT}")
    print("Press Ctrl+C to stop")
    print("-" * 50)

    with TCPServer(("", PORT), DashboardHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")


if __name__ == "__main__":
    main()
