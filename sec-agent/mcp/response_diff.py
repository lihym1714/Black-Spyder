from __future__ import annotations

import json
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import typer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp.common import PROJECT_ROOT as COMMON_PROJECT_ROOT


app = typer.Typer(add_completion=False, help="Compare two normalized observation artifacts.")


def load_artifact(path: str) -> dict[str, Any]:
    artifact_path = Path(path)
    if not artifact_path.is_absolute():
        artifact_path = COMMON_PROJECT_ROOT / artifact_path
    with artifact_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def diff_observations(left_artifact_path: str, right_artifact_path: str) -> dict[str, Any]:
    left = load_artifact(left_artifact_path)
    right = load_artifact(right_artifact_path)

    left_headers = left.get("headers", {})
    right_headers = right.get("headers", {})
    header_differences = []
    for key in sorted(set(left_headers) | set(right_headers)):
        if left_headers.get(key) != right_headers.get(key):
            header_differences.append(
                {
                    "header": key,
                    "left": left_headers.get(key),
                    "right": right_headers.get(key),
                }
            )

    ratio = SequenceMatcher(None, left.get("body_preview", ""), right.get("body_preview", "")).ratio()
    preview_similarity_hint = f"{ratio:.2f}"
    status_changed = left.get("status") != right.get("status")
    body_hash_changed = left.get("body_hash") != right.get("body_hash")

    notable_differences = []
    if status_changed:
        notable_differences.append("HTTP status changed.")
    if body_hash_changed:
        notable_differences.append("Response body hash changed.")
    if header_differences:
        notable_differences.append(f"{len(header_differences)} response header differences detected.")
    if not notable_differences:
        notable_differences.append("No notable differences detected.")

    return {
        "status_changed": status_changed,
        "header_differences": header_differences,
        "body_hash_changed": body_hash_changed,
        "preview_similarity_hint": preview_similarity_hint,
        "notable_differences": notable_differences,
        "summary": " ".join(notable_differences),
    }


@app.command()
def main(
    left_artifact_path: str = typer.Option(..., help="Path to the left normalized observation."),
    right_artifact_path: str = typer.Option(..., help="Path to the right normalized observation."),
) -> None:
    typer.echo(json.dumps(diff_observations(left_artifact_path, right_artifact_path), indent=2))


if __name__ == "__main__":
    app()
