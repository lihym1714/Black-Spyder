from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import typer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_RULES = PROJECT_ROOT / "rules" / "mobile_controls.yar"
app = typer.Typer(add_completion=False, help="Run read-only YARA scanning against local artifacts.")


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def parse_yara_output(stdout: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(maxsplit=1)
        if len(parts) != 2:
            continue
        rule_name, target = parts
        matches.append({"rule": rule_name, "target": target})
    return matches


def run_yara_scan(target_path: str, rules_path: str | None = None) -> dict[str, Any]:
    yara_path = shutil.which("yara")
    chosen_rules = Path(rules_path) if rules_path else DEFAULT_RULES
    target = Path(target_path)

    if yara_path is None:
        return {
            "available": False,
            "error": "yara CLI is not installed.",
            "install_hint": "Install yara locally, then rerun this scan.",
        }

    if not chosen_rules.exists():
        return {
            "available": True,
            "error": f"Rules file not found: {chosen_rules}",
        }

    if not target.exists():
        return {
            "available": True,
            "error": f"Target path not found: {target}",
        }

    command = [yara_path]
    if target.is_dir():
        command.append("-r")
    command.extend([str(chosen_rules), str(target)])

    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    matches = parse_yara_output(stdout)

    return {
        "available": True,
        "rules_path": str(chosen_rules),
        "target_path": str(target),
        "match_count": len(matches),
        "matches": matches,
        "stderr": stderr,
        "exit_code": completed.returncode,
    }


@app.command()
def main(
    target_path: str = typer.Option(..., help="Local file or directory to scan."),
    rules_path: str | None = typer.Option(None, help="Optional YARA rules file path."),
) -> None:
    typer.echo(json.dumps(run_yara_scan(target_path=target_path, rules_path=rules_path), indent=2))


if __name__ == "__main__":
    app()
