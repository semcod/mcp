"""Static package versions must equal their declared releases (GOV-VERSION-001)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r'^__version__\s*=\s*["\']([^"\']+)["\']', re.M)
PROJECT_RE = re.compile(r'^version\s*=\s*["\']([^"\']+)["\']', re.M)


def _version(path: Path, pattern: re.Pattern) -> str:
    match = pattern.search(path.read_text(encoding="utf-8"))
    assert match is not None, path
    return match.group(1)


def test_subpackage_versions_match_their_pyproject() -> None:
    for package in ("gh2mcp",):
        assert _version(ROOT / package / package / "__init__.py", VERSION_RE) == _version(
            ROOT / package / "pyproject.toml", PROJECT_RE
        )


def test_root_package_version_matches_version_file() -> None:
    expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert _version(ROOT / "semcod_mcp/__init__.py", VERSION_RE) == expected
