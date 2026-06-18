"""semcod-mcp doctor — health checks for stack and local config."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from semcod_mcp.merge import load_json
from semcod_mcp.paths import MANIFEST_NAME, default_api_key, detect_stack_path, gateway_url
from semcod_mcp.templates import SERVER_NAME, read_manifest


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


@dataclass
class DoctorReport:
    checks: list[Check] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return all(c.ok for c in self.checks if c.name.startswith("required:"))

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append(Check(name=name, ok=ok, detail=detail))


def _http_ok(url: str, headers: dict | None = None, timeout: float = 5.0) -> tuple[bool, str]:
    try:
        r = httpx.get(url, headers=headers or {}, timeout=timeout)
        if r.status_code < 400:
            return True, f"HTTP {r.status_code}"
        return False, f"HTTP {r.status_code}: {r.text[:120]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def run_doctor(project_dir: Path | None = None) -> DoctorReport:
    report = DoctorReport()
    project_dir = (project_dir or Path.cwd()).resolve()

    # Tooling
    report.add(
        "required:docker",
        shutil.which("docker") is not None,
        "docker CLI found" if shutil.which("docker") else "install Docker",
    )

    stack = detect_stack_path()
    report.add(
        "required:stack-path",
        stack is not None,
        str(stack) if stack else "set --stack-path or SEMCOD_MCP_STACK",
    )

    manifest = read_manifest(project_dir)
    report.add(
        "optional:manifest",
        manifest is not None,
        MANIFEST_NAME + " present" if manifest else f"run semcod-mcp init in {project_dir}",
    )

    if stack:
        compose_file = stack / "docker-compose.yml"
        try:
            subprocess.run(
                ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            report.add("optional:compose-ps", True, "docker compose ps OK")
        except Exception as exc:  # noqa: BLE001
            report.add("optional:compose-ps", False, str(exc))

    gw = gateway_url(stack)
    api_key = default_api_key()
    ok, detail = _http_ok(gw.replace("/v1", "") + "/health" if gw.endswith("/v1") else gw + "/health")
    # gateway health is at /health without /v1
    health_url = gw.rstrip("/").removesuffix("/v1") + "/health"
    ok, detail = _http_ok(health_url)
    report.add("required:gateway-health", ok, f"{health_url} — {detail}")

    models_url = gw.rstrip("/") + "/models"
    ok, detail = _http_ok(models_url, headers={"Authorization": f"Bearer {api_key}"})
    report.add("required:gateway-models", ok, f"{models_url} — {detail}")

    # Local IDE configs
    cursor_mcp = project_dir / ".cursor" / "mcp.json"
    if cursor_mcp.is_file():
        try:
            data = load_json(cursor_mcp)
            has_server = SERVER_NAME in data.get("mcpServers", {})
            report.add("optional:cursor-mcp", has_server, str(cursor_mcp))
        except json.JSONDecodeError as exc:
            report.add("optional:cursor-mcp", False, f"invalid JSON: {exc}")
    else:
        report.add("optional:cursor-mcp", False, "missing — run init")

    report.add(
        "optional:pyqual",
        shutil.which("pyqual") is not None,
        "pyqual in PATH" if shutil.which("pyqual") else "pip install pyqual (optional)",
    )

    return report
