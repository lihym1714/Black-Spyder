from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import typer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp.common import load_scope_policy
from mcp.scope_guard import evaluate_scope


app = typer.Typer(add_completion=False, help="Classify candidate paths for safe, policy-gated LLM orchestration.")


def classify_candidates(base_url: str, paths: list[str], method: str = "GET") -> dict[str, Any]:
    policy = load_scope_policy()
    allowed: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for candidate_path in paths:
        url = urljoin(base_url.rstrip("/") + "/", candidate_path.lstrip("/"))
        result = evaluate_scope(url, method, policy)
        item = {
            "url": url,
            "method": method.upper(),
            "allowed": result["allowed"],
            "approved_exception_used": result.get("approved_exception_used", False),
            "reasons": result["reasons"],
        }
        if result["allowed"]:
            allowed.append(item)
        else:
            blocked.append(item)

    next_actions = []
    for item in allowed:
        next_actions.append(
            {
                "type": "observe",
                "url": item["url"],
                "method": item["method"],
                "note": "Safe single observation allowed by current policy.",
            }
        )

    for item in blocked:
        next_actions.append(
            {
                "type": "blocked",
                "url": item["url"],
                "method": item["method"],
                "note": "Policy blocks this path; add an explicit approved_path_exceptions entry if operator approval exists.",
                "reasons": item["reasons"],
            }
        )

    return {
        "base_url": base_url,
        "allowed": allowed,
        "blocked": blocked,
        "next_actions": next_actions,
    }


@app.command()
def main(
    base_url: str = typer.Option(..., help="Authorized base URL, e.g. https://example.local"),
    paths: str = typer.Option(..., help="JSON array of candidate paths, e.g. [\"/\", \"/robots.txt\"]"),
    method: str = typer.Option("GET", help="Method to validate for all candidate paths."),
) -> None:
    parsed_paths = json.loads(paths)
    if not isinstance(parsed_paths, list) or not all(isinstance(item, str) for item in parsed_paths):
        raise typer.BadParameter("paths must be a JSON array of strings.")
    typer.echo(json.dumps(classify_candidates(base_url, parsed_paths, method), indent=2))


if __name__ == "__main__":
    app()
