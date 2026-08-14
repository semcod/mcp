from __future__ import annotations

import os
import subprocess
from pathlib import Path


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
