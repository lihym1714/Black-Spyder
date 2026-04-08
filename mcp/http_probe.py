from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import typer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp.common import (
    build_request_id,
    ensure_within_max_bytes,
    load_scope_policy,
    mask_sensitive_headers,
    normalize_headers,
    safe_body_preview,
    sha256_hex,
    utc_now_iso,
    write_json,
)
from mcp.scope_guard import evaluate_scope


RAW_DIR = PROJECT_ROOT / "evidence" / "raw"
NORMALIZED_DIR = PROJECT_ROOT / "evidence" / "normalized"
app = typer.Typer(add_completion=False, help="Perform one safe observational HTTP request.")


def perform_probe(url: str, method: str = "GET", headers: dict[str, str] | None = None) -> dict[str, Any]:
    policy = load_scope_policy()
    normalized_method = method.upper()

    scope_result = evaluate_scope(url, normalized_method, policy)
    if not scope_result["allowed"]:
        return {
            "request_id": None,
            "url": url,
            "method": normalized_method,
            "error": "Request rejected by scope policy.",
            "scope_guard": scope_result,
        }

    request_id = build_request_id()
    request_headers = {"User-Agent": policy.get("user_agent", "Black-Spyder/0.1")}
    if headers:
        request_headers.update(headers)

    timeout = httpx.Timeout(float(policy.get("request_timeout_seconds", 10)))
    start = time.perf_counter()

    with httpx.Client(follow_redirects=bool(policy.get("allow_redirects", False)), timeout=timeout) as client:
        with client.stream(normalized_method, url, headers=request_headers) as response:
            collected = bytearray()
            max_bytes = int(policy.get("max_response_bytes", 65536))
            for chunk in response.iter_bytes():
                if not chunk:
                    continue
                remaining = max_bytes - len(collected)
                if remaining <= 0:
                    break
                collected.extend(chunk[:remaining])
                if len(collected) >= max_bytes:
                    break
            body = ensure_within_max_bytes(bytes(collected), max_bytes)
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

            masked_request_headers = mask_sensitive_headers(dict(request_headers))
            masked_response_headers = mask_sensitive_headers(dict(response.headers))
            body_preview = safe_body_preview(body)
            body_hash = sha256_hex(body)
            raw_path = RAW_DIR / f"{request_id}.json"
            normalized_path = NORMALIZED_DIR / f"{request_id}.json"

            raw_observation = {
                "request_id": request_id,
                "observed_at": utc_now_iso(),
                "url": str(response.request.url),
                "method": normalized_method,
                "request_headers": masked_request_headers,
                "status": response.status_code,
                "response_headers": masked_response_headers,
                "content_type": response.headers.get("content-type", ""),
                "content_length": len(body),
                "body_hash": body_hash,
                "body_preview": body_preview,
                "redirected": str(response.url) != url,
                "final_url": str(response.url),
                "elapsed_ms": elapsed_ms,
            }

            normalized_observation = {
                "request_id": request_id,
                "host": response.request.url.host,
                "url": str(response.request.url),
                "method": normalized_method,
                "status": response.status_code,
                "headers": normalize_headers(masked_response_headers),
                "body_hash": body_hash,
                "body_preview": body_preview,
                "notes": [
                    "Single safe observation only.",
                    "No request body was sent.",
                ],
                "classification": "suspected",
                "confidence": "low",
            }

            write_json(raw_path, raw_observation)
            write_json(normalized_path, normalized_observation)

            return {
                "request_id": request_id,
                "url": str(response.request.url),
                "method": normalized_method,
                "status": response.status_code,
                "response_headers": masked_response_headers,
                "content_type": response.headers.get("content-type", ""),
                "content_length": len(body),
                "body_hash": body_hash,
                "body_preview": body_preview,
                "redirected": str(response.url) != url,
                "final_url": str(response.url),
                "elapsed_ms": elapsed_ms,
                "artifact_paths": {
                    "raw": str(raw_path.relative_to(PROJECT_ROOT)),
                    "normalized": str(normalized_path.relative_to(PROJECT_ROOT)),
                },
            }


@app.command()
def main(
    url: str = typer.Option(..., help="Authorized URL to observe."),
    method: str = typer.Option("GET", help="Allowed method: GET, HEAD, or OPTIONS."),
    headers: str | None = typer.Option(None, help="Optional JSON object of request headers."),
) -> None:
    parsed_headers = json.loads(headers) if headers else None
    typer.echo(json.dumps(perform_probe(url=url, method=method, headers=parsed_headers), indent=2))


if __name__ == "__main__":
    app()
