"""Offline structural/syntax checks for the DiapStash source tree.

This is deliberately stdlib-only. It cannot validate Home Assistant runtime behavior.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "diapstash"
ERRORS: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        ERRORS.append(message)


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        check(isinstance(value, dict), f"Expected JSON object: {path.relative_to(ROOT)}")
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError) as err:
        ERRORS.append(f"Could not read JSON {path.relative_to(ROOT)}: {err}")
        return {}


def main() -> int:
    manifest = read_json(INTEGRATION / "manifest.json")
    hacs = read_json(ROOT / "hacs.json")
    read_json(INTEGRATION / "strings.json")
    for language in ("en", "de", "fr", "es"):
        read_json(INTEGRATION / "translations" / f"{language}.json")

    check(manifest.get("domain") == "diapstash", "Unexpected integration domain")
    check(manifest.get("config_flow") is True, "config_flow must be enabled")
    version = manifest.get("version")
    check(isinstance(version, str) and bool(re.fullmatch(r"\d+\.\d+\.\d+", version)), "Invalid manifest version")
    check(bool(hacs.get("homeassistant")), "HACS minimum Home Assistant version missing")

    const_text = (INTEGRATION / "const.py").read_text(encoding="utf-8")
    declared_version = re.search(r'^INTEGRATION_VERSION\s*=\s*["\']([^"\']+)["\']', const_text, re.M)
    check(declared_version is not None, "INTEGRATION_VERSION not found")
    if declared_version:
        check(declared_version.group(1) == version, "manifest version and const.py version differ")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if version:
        check(f"**{version}**" in readme, "README stable version does not match manifest")
        check(f"## v{version}" in changelog, "CHANGELOG missing current version heading")

    for f in INTEGRATION.rglob("*.py"):
        try:
            compile(f.read_text(encoding="utf-8"), str(f), "exec")
        except (SyntaxError, UnicodeDecodeError) as err:
            ERRORS.append(f"Python syntax failed in {f.relative_to(ROOT)}: {err}")
    check(any(INTEGRATION.glob("*.py")), "No integration Python files found")

    for directory in (ROOT / "brand", INTEGRATION / "brand"):
        for name in ("icon.png", "logo.png"):
            f = directory / name
            try:
                check(f.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), f"Not a PNG: {f.relative_to(ROOT)}")
            except OSError:
                ERRORS.append(f"Missing brand image: {f.relative_to(ROOT)}")

    for necessary in (
        ROOT / "AGENTS.md", ROOT / ".vscode" / "tasks.json",
        ROOT / "docs" / "CODEX_HANDOFF.md", ROOT / "README.md",
    ):
        check(necessary.is_file(), f"Missing required file: {necessary.relative_to(ROOT)}")
    read_json(ROOT / ".vscode" / "tasks.json")
    read_json(ROOT / ".vscode" / "settings.json")
    read_json(ROOT / ".vscode" / "extensions.json")
    read_json(ROOT / "diapstash.code-workspace")

    if ERRORS:
        print("FAIL — DiapStash project checks:")
        for err in ERRORS:
            print("  -", err)
        return 1
    print(f"PASS — DiapStash v{version}: syntax, manifest, HACS, translations, brand assets, workspace files")
    print("INFO — No live Home Assistant, HACS CI or DiapStash API checks were performed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
