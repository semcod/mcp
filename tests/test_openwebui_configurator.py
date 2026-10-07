from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "configure-openwebui-subactor.sh"


def executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def mock_environment(tmp_path: Path, listener: str) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    capture = tmp_path / "docker-arguments.txt"
    executable(
        bin_dir / "ss",
        "#!/usr/bin/env bash\n" f"printf '%s\\n' '{listener}'\n",
    )
    executable(
        bin_dir / "docker",
        """#!/usr/bin/env bash
printf '%s\n' "$@" > "$SUBACTOR_TEST_DOCKER_CAPTURE"
cat >/dev/null
printf '%s\n' '{"configured":true}'
""",
    )
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "SUBACTOR_TEST_DOCKER_CAPTURE": str(capture),
        }
    )
    env.pop("SUBACTOR_CONTROL_URL", None)
    return env, capture


def test_discovers_non_loopback_control_listener(tmp_path: Path) -> None:
    env, capture = mock_environment(
        tmp_path,
        "LISTEN 0 2048 10.240.0.1:8088 0.0.0.0:*",
    )

    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    arguments = capture.read_text(encoding="utf-8").splitlines()
    assert "SUBACTOR_CONTROL_URL=http://10.240.0.1:8088" in arguments
    assert "SUBACTOR_CONTROL_DISCOVERED=true" in arguments


def test_refuses_to_persist_an_undiscovered_endpoint(tmp_path: Path) -> None:
    env, capture = mock_environment(tmp_path, "")

    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Unable to discover" in result.stderr
    assert not capture.exists()


def test_explicit_control_url_skips_discovery(tmp_path: Path) -> None:
    env, capture = mock_environment(tmp_path, "")
    env["SUBACTOR_CONTROL_URL"] = "https://control.subactor.internal"

    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    arguments = capture.read_text(encoding="utf-8").splitlines()
    assert "SUBACTOR_CONTROL_URL=https://control.subactor.internal" in arguments
    assert "SUBACTOR_CONTROL_DISCOVERED=false" in arguments


@pytest.mark.parametrize("override", ["untrusted:latest", "redis:7-alpine"])
def test_image_override_preserves_authenticated_boundary(override: str) -> None:
    assert shutil.which("docker") is not None, (
        "Docker Compose is required to render the security boundary"
    )
    env = os.environ.copy()
    env["OPENWEBUI_IMAGE"] = override
    result = subprocess.run(
        ["docker", "compose", "--profile", "openwebui", "config", "--format", "json"],
        cwd=ROOT, env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    webui = services["openwebui"]
    assert webui["image"] == (
        "ghcr.io/open-webui/open-webui:v0.11.0@sha256:"
        "72c0ba641ba75e7aa52655cb242570906ececd09b1140fb736483038a22b3228"
    )
    assert webui["environment"]["WEBUI_AUTH"] == "True"
    assert webui["environment"]["ENABLE_SIGNUP"] == "False"
    assert webui["ports"][0]["host_ip"] == "127.0.0.1"
    assert services["mcp-gateway"]["ports"][0]["host_ip"] == "127.0.0.1"
    assert any(
        volume["target"] == "/run/secrets/openwebui-mcp-bearer"
        and volume.get("read_only") is True
        for volume in webui["volumes"]
    )
    assert "@sha256:" in services["redis"]["image"]
