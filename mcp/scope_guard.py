from __future__ import annotations

import json
import sys
from urllib.parse import urlparse
from pathlib import Path
from typing import Any

import typer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp.common import get_approved_path_exception, is_host_allowed, is_method_allowed, is_path_forbidden, load_scope_policy


app = typer.Typer(add_completion=False, help="Validate whether a request is inside the local scope policy.")


def looks_production_like(hostname: str) -> bool:
    host = hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return False
    if host.endswith(".local"):
        return False
    return "." in host


def evaluate_scope(url: str, method: str, policy: dict[str, Any]) -> dict[str, Any]:
    parsed = urlparse(url)
    normalized_method = method.upper()
    reasons: list[str] = []
    approved_exception = get_approved_path_exception(url, policy)

    if parsed.scheme not in policy.get("allowed_schemes", []):
        reasons.append(f"Scheme '{parsed.scheme}' is not allowed.")
    if not is_host_allowed(url, policy):
        reasons.append(f"Host '{parsed.hostname or ''}' is not in allowed_hosts.")
    if is_path_forbidden(url, policy) and approved_exception is None:
        reasons.append(f"Path '{parsed.path or '/'}' matches a forbidden pattern.")

    approval_required = normalized_method in {value.upper() for value in policy.get("approval_required_methods", [])}
    if approval_required:
        reasons.append(f"Method '{normalized_method}' requires explicit approval and is not auto-executed.")
    elif not is_method_allowed(normalized_method, policy):
        reasons.append(f"Method '{normalized_method}' is not in allowed_methods.")

    if looks_production_like(parsed.hostname or "") and not policy.get("production_allowed", False):
        reasons.append("Target appears production-like while production_allowed is false.")

    return {
        "allowed": len(reasons) == 0,
        "reasons": reasons,
        "approved_exception_used": approved_exception is not None,
        "policy_summary": {
            "allowed_methods": policy.get("allowed_methods", []),
            "allowed_hosts": policy.get("allowed_hosts", []),
            "forbidden_path_patterns": policy.get("forbidden_path_patterns", []),
        },
    }


@app.command()
def main(url: str = typer.Option(..., help="Target URL to validate."), method: str = typer.Option("GET", help="HTTP method to validate.")) -> None:
    policy = load_scope_policy()
    typer.echo(json.dumps(evaluate_scope(url, method, policy), indent=2))


if __name__ == "__main__":
    app()
