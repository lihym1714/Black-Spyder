from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import typer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp.common import PROJECT_ROOT as COMMON_PROJECT_ROOT


app = typer.Typer(add_completion=False, help="Extract candidate schema hints from a normalized observation.")


def load_artifact(path: str) -> dict[str, Any]:
    artifact_path = Path(path)
    if not artifact_path.is_absolute():
        artifact_path = COMMON_PROJECT_ROOT / artifact_path
    with artifact_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def collect_candidate_fields(value: Any, prefix: str = "") -> set[str]:
    fields: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            path = f"{prefix}.{key}" if prefix else key
            fields.add(path)
            fields.update(collect_candidate_fields(nested, path))
    elif isinstance(value, list) and value:
        fields.update(collect_candidate_fields(value[0], f"{prefix}[]" if prefix else "[]"))
    return fields


def normalize_endpoint_pattern(url: str) -> str:
    parsed = urlparse(url)
    parts = []
    for segment in parsed.path.split("/"):
        if not segment:
            continue
        if re.fullmatch(r"\d+", segment):
            parts.append("{id}")
        elif re.fullmatch(r"[0-9a-fA-F-]{8,}", segment):
            parts.append("{token}")
        else:
            parts.append(segment)
    return "/" + "/".join(parts)


def extract_schema(artifact_path: str) -> dict[str, Any]:
    artifact = load_artifact(artifact_path)
    headers = artifact.get("headers", {})
    preview = artifact.get("body_preview", "")
    notes = ["Preview-based inference only; conclusions require corroborating evidence."]
    candidate_fields: list[str] = []

    parsed_preview: Any | None = None
    if isinstance(preview, str) and preview.strip().startswith(("{", "[")):
        try:
            parsed_preview = json.loads(preview)
            candidate_fields = sorted(collect_candidate_fields(parsed_preview))
        except json.JSONDecodeError:
            notes.append("Body preview looks structured but could not be parsed completely.")
    else:
        notes.append("Body preview does not look like complete JSON.")

    auth_indicators = []
    status = artifact.get("status")
    if status in {401, 403}:
        auth_indicators.append(f"HTTP {status} suggests an authentication or authorization boundary.")
    if "www-authenticate" in headers:
        auth_indicators.append("WWW-Authenticate header present.")
    if any(token in preview.lower() for token in ["bearer", "token", "session", "login"]):
        auth_indicators.append("Body preview contains auth-related keywords.")

    return {
        "candidate_fields": candidate_fields,
        "candidate_endpoint_patterns": [normalize_endpoint_pattern(artifact.get("url", "/"))],
        "auth_indicators": auth_indicators,
        "notes": notes,
    }


@app.command()
def main(artifact_path: str = typer.Option(..., help="Path to a normalized observation artifact.")) -> None:
    typer.echo(json.dumps(extract_schema(artifact_path), indent=2))


if __name__ == "__main__":
    app()
