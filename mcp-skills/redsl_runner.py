"""redsl subprocess runner for /refactor/redsl."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

def run_redsl_refactor(project_path: Path, max_actions: int, dry_run: bool) -> dict[str, Any]:
    """Uruchamia redsl refactor jako subprocess i parsuje wynik."""
    cmd = [
        sys.executable, "-m", "redsl", "refactor",
        str(project_path),
        "-n", str(max_actions),
        "-f", "json",
    ]
    if dry_run:
        cmd.append("--dry-run")

    env = os.environ.copy()
    # Przekazuj klucze LLM jeśli dostępne
    for key in ("OPENROUTER_API_KEY", "LLM_MODEL", "OPENAI_API_KEY"):
        val = os.getenv(key)
        if val:
            env[key] = val

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()

        # Szukaj bloku JSON w stdout (redsl może poprzedzać go tekstem)
        payload: dict[str, Any] = {}
        for line in stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("{") or stripped.startswith("redsl_plan:"):
                # Spróbuj parsować JSON
                try:
                    payload = json.loads(stripped)
                    break
                except json.JSONDecodeError:
                    pass

        # Jeśli nie ma JSON, spróbuj całego stdout
        if not payload:
            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError:
                payload = {"raw_output": stdout}

        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "payload": payload,
            "stderr": stderr[:2000] if stderr else None,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "redsl timeout after 120s"}
    except FileNotFoundError:
        return {"success": False, "error": "redsl not found - not installed in container"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
