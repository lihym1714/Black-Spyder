from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp.common import PROJECT_ROOT as COMMON_PROJECT_ROOT


app = typer.Typer(add_completion=False, help="Safely write evidence or finding artifacts inside the project.")
ALLOWED_ROOTS = [COMMON_PROJECT_ROOT / "findings", COMMON_PROJECT_ROOT / "evidence"]


def resolve_safe_path(relative_path: str) -> Path:
    target = (COMMON_PROJECT_ROOT / relative_path).resolve()
    if not any(root.resolve() == target or root.resolve() in target.parents for root in ALLOWED_ROOTS):
        raise ValueError("Writes are only allowed inside findings/ or evidence/.")
    return target


def write_artifact(relative_path: str, content: Any, mode: str) -> dict[str, Any]:
    if mode not in {"text", "json"}:
        raise ValueError("Mode must be 'text' or 'json'.")
    target = resolve_safe_path(relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if mode == "json":
        with target.open("w", encoding="utf-8") as handle:
            json.dump(content, handle, indent=2)
            handle.write("\n")
    else:
        with target.open("w", encoding="utf-8") as handle:
            handle.write(str(content))

    return {"written": True, "absolute_path": str(target)}


@app.command()
def main(
    relative_path: str = typer.Option(..., help="Relative path under findings/ or evidence/."),
    content: str = typer.Option(..., help="Content to write. For JSON mode, pass a JSON string."),
    mode: str = typer.Option("text", help="Write mode: text or json."),
) -> None:
    parsed_content: Any = json.loads(content) if mode == "json" else content
    typer.echo(json.dumps(write_artifact(relative_path, parsed_content, mode), indent=2))


if __name__ == "__main__":
    app()
