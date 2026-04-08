from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_PATH = PROJECT_ROOT / "policies" / "scope.yaml"
SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "proxy-authorization",
    "x-api-key",
}


def load_scope_policy(path: Path | None = None) -> dict[str, Any]:
    policy_path = path or DEFAULT_POLICY_PATH
    if not policy_path.exists():
        raise FileNotFoundError(f"Scope policy not found: {policy_path}")
    with policy_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("Scope policy must be a mapping.")
    return data


def mask_sensitive_headers(headers: dict[str, Any] | None) -> dict[str, Any]:
    if not headers:
        return {}
    masked: dict[str, Any] = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADER_NAMES:
            masked[key] = "***MASKED***"
        else:
            masked[key] = value
    return masked


def normalize_headers(headers: dict[str, Any] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    if not headers:
        return normalized
    for key in sorted(headers.keys(), key=str.lower):
        value = headers[key]
        normalized[key.lower()] = ", ".join(value) if isinstance(value, list) else str(value)
    return normalized


def safe_body_preview(content: bytes, max_chars: int = 500) -> str:
    return content.decode("utf-8", errors="replace")[:max_chars]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ensure_within_max_bytes(data: bytes, limit: int) -> bytes:
    if limit < 0:
        raise ValueError("Byte limit must be non-negative.")
    return data[:limit]


def is_host_allowed(url: str, policy: dict[str, Any]) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    allowed_hosts = {str(host).lower() for host in policy.get("allowed_hosts", [])}
    return hostname in allowed_hosts


def is_method_allowed(method: str, policy: dict[str, Any]) -> bool:
    return method.upper() in {value.upper() for value in policy.get("allowed_methods", [])}


def is_path_forbidden(url: str, policy: dict[str, Any]) -> bool:
    path = urlparse(url).path or "/"
    patterns = policy.get("forbidden_path_patterns", [])
    return any(fnmatch(path, pattern) for pattern in patterns)


def build_request_id() -> str:
    return uuid.uuid4().hex


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=False)
        handle.write("\n")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
