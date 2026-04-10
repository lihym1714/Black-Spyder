from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from mcp.common import PROJECT_ROOT, build_request_id, utc_now_iso, write_json
from tools.agent_cli import run_named_workflow
from tools.ecosystem import ecosystem_doctor, ecosystem_snapshot

BRIDGE_STATE_PATH = PROJECT_ROOT / "state" / "opencode_bridge_state.json"
BRIDGE_MANIFEST_PATH = PROJECT_ROOT / "state" / "opencode-bridge-manifest.json"
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 8787
BRIDGE_ENVELOPE_VERSION = 1


class BridgeReuseError(RuntimeError):
    pass


class HostRegistrationRequest(BaseModel):
    host_name: str = Field(..., min_length=1)
    host_version: str | None = None
    capabilities: list[str] = Field(default_factory=list)


class ExecuteRequest(BaseModel):
    command_name: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class AnalyzeRequest(BaseModel):
    goal: str = Field(..., min_length=1)
    url: str | None = None
    method: str = "GET"
    artifact_path: str | None = None
    left_artifact_path: str | None = None
    right_artifact_path: str | None = None
    target_path: str | None = None
    rules_path: str | None = None


class ConverseRequest(BaseModel):
    goal: str = Field(..., min_length=1)


def default_bridge_state() -> dict[str, Any]:
    return {
        "created_at": utc_now_iso(),
        "hosts": [],
        "executions": [],
    }


def load_bridge_state() -> dict[str, Any]:
    if not BRIDGE_STATE_PATH.exists():
        return default_bridge_state()
    try:
        with BRIDGE_STATE_PATH.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except json.JSONDecodeError:
        return default_bridge_state()
    return state if isinstance(state, dict) else default_bridge_state()


def save_bridge_state(state: dict[str, Any]) -> None:
    write_json(BRIDGE_STATE_PATH, state)


def normalize_bridge_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def build_bridge_manifest() -> dict[str, Any]:
    ecosystem = ecosystem_snapshot()
    doctor = ecosystem_doctor()
    manifest = {
        "bridge_name": "black-spyder-opencode-bridge",
        "bridge_version": 1,
        "generated_at": utc_now_iso(),
        "entrypoint": "black-spyder-opencode-bridge",
        "recommended_entrypoint": "black-spyder opencode up",
        "default_preset": {
            "name": "opencode-conversation-first",
            "first_route": "/converse",
            "fallback_route": "/analyze",
            "low_level_route": "/execute",
        },
        "routes": {
            "health": "/health",
            "registry": "/registry",
            "connect": "/connect",
            "converse": "/converse",
            "analyze": "/analyze",
            "register_host": "/register-host",
            "execute": "/execute",
        },
        "ecosystem": ecosystem,
        "doctor": doctor,
    }
    write_json(BRIDGE_MANIFEST_PATH, manifest)
    return manifest


def bridge_base_url() -> str:
    return f"http://{BRIDGE_HOST}:{BRIDGE_PORT}"


def is_bridge_port_open(timeout: float = 0.2) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(timeout)
        return probe.connect_ex((BRIDGE_HOST, BRIDGE_PORT)) == 0


def probe_existing_bridge(timeout: float = 1.0) -> bool:
    base_url = bridge_base_url()
    try:
        client_timeout = httpx.Timeout(timeout, connect=timeout, read=timeout, write=timeout, pool=timeout)
        with httpx.Client(timeout=client_timeout, trust_env=False, follow_redirects=False) as client:
            health_response = client.get(f"{base_url}/health")
            registry_response = client.get(f"{base_url}/registry")
    except httpx.HTTPError:
        return False
    if health_response.status_code != 200 or registry_response.status_code != 200:
        return False
    try:
        health_payload = health_response.json()
        registry_payload = registry_response.json()
    except ValueError:
        return False
    health_status = health_payload.get("status")
    if health_payload.get("envelope_version") == BRIDGE_ENVELOPE_VERSION:
        if health_status != "ok":
            return False
    elif health_status != "ok" or "bridge_manifest_present" not in health_payload:
        return False

    registry_data = registry_payload.get("payload") if registry_payload.get("envelope_version") == BRIDGE_ENVELOPE_VERSION else registry_payload
    if not isinstance(registry_data, dict):
        return False
    return registry_data.get("bridge_name") == "black-spyder-opencode-bridge"


def ensure_bridge_available() -> dict[str, Any]:
    if probe_existing_bridge():
        return {
            "status": "reusing_existing_bridge",
            "bridge_url": bridge_base_url(),
            "reused_existing_bridge": True,
        }
    if is_bridge_port_open():
        raise BridgeReuseError(
            f"Port {BRIDGE_PORT} is already in use by a non-Black-Spyder service; cannot start the OpenCode bridge."
        )
    return {
        "status": "starting",
        "bridge_url": bridge_base_url(),
        "reused_existing_bridge": False,
    }


def envelope_response(*, status: str, payload: dict[str, Any], error: dict[str, Any] | None = None) -> dict[str, Any]:
    response: dict[str, Any] = {
        "envelope_version": BRIDGE_ENVELOPE_VERSION,
        "status": status,
        "payload": payload,
    }
    if error is not None:
        response["error"] = error
    return response


def record_host_registration(payload: HostRegistrationRequest) -> dict[str, Any]:
    state = load_bridge_state()
    for existing in state.setdefault("hosts", []):
        if (
            existing.get("host_name") == payload.host_name
            and existing.get("host_version") == payload.host_version
            and existing.get("capabilities") == payload.capabilities
        ):
            return existing
    host_record = {
        "host_id": f"host-{build_request_id()}",
        "host_name": payload.host_name,
        "host_version": payload.host_version,
        "capabilities": payload.capabilities,
        "registered_at": utc_now_iso(),
    }
    state.setdefault("hosts", []).append(host_record)
    save_bridge_state(state)
    return host_record


def connect_host(payload: HostRegistrationRequest) -> dict[str, Any]:
    host = record_host_registration(payload)
    manifest = build_bridge_manifest()
    doctor = ecosystem_doctor()
    return {
        "status": "connected",
        "host": host,
        "registry": manifest,
        "primary_route": "/converse",
        "structured_route": "/analyze",
        "execute_route": "/execute",
        "doctor": doctor,
    }


def record_execution(command_name: str, params: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    state = load_bridge_state()
    execution = {
        "execution_id": f"exec-{build_request_id()}",
        "command_name": command_name,
        "params": params,
        "recorded_at": utc_now_iso(),
        "result": result,
    }
    state.setdefault("executions", []).append(execution)
    save_bridge_state(state)
    return execution


app = FastAPI(title="Black-Spyder OpenCode Bridge")


@app.get("/health")
def health() -> dict[str, Any]:
    doctor = ecosystem_doctor()
    return envelope_response(
        status=doctor["status"],
        payload={
            "bridge_manifest_present": BRIDGE_MANIFEST_PATH.exists(),
            "registered_host_count": len(load_bridge_state().get("hosts", [])),
            "doctor": doctor,
        },
    )


@app.get("/registry")
def registry() -> dict[str, Any]:
    return envelope_response(status="ok", payload=build_bridge_manifest())


@app.post("/register-host")
def register_host(payload: HostRegistrationRequest) -> dict[str, Any]:
    return envelope_response(
        status="ok",
        payload={
            "status": "registered",
            "host": record_host_registration(payload),
            "registry_path": normalize_bridge_path(BRIDGE_MANIFEST_PATH),
        },
    )


@app.post("/connect")
def connect(payload: HostRegistrationRequest) -> dict[str, Any]:
    return envelope_response(status="ok", payload=connect_host(payload))


@app.post("/execute")
def execute(payload: ExecuteRequest) -> dict[str, Any]:
    try:
        result = run_named_workflow(payload.command_name, payload.params)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=envelope_response(
                status="error",
                payload={"command_name": payload.command_name},
                error={"message": str(exc)},
            ),
        ) from exc
    execution = record_execution(payload.command_name, payload.params, result)
    return envelope_response(status="ok", payload={"execution": execution})


@app.post("/analyze")
def analyze(payload: AnalyzeRequest) -> dict[str, Any]:
    try:
        params = payload.model_dump(exclude_none=True)
        result = run_named_workflow(
            "/analyze",
            params,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=envelope_response(
                status="error",
                payload={"command_name": "/analyze"},
                error={"message": str(exc)},
            ),
        ) from exc
    execution = record_execution("/analyze", params, result)
    return envelope_response(status="ok", payload={"execution": execution})


@app.post("/converse")
def converse(payload: ConverseRequest) -> dict[str, Any]:
    try:
        params = {"goal": payload.goal}
        result = run_named_workflow("/converse", params)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=envelope_response(
                status="error",
                payload={"command_name": "/converse"},
                error={"message": str(exc)},
            ),
        ) from exc
    execution = record_execution("/converse", params, result)
    return envelope_response(status="ok", payload={"execution": execution})


def main() -> None:
    build_bridge_manifest()
    uvicorn.run(app, host=BRIDGE_HOST, port=BRIDGE_PORT)


if __name__ == "__main__":
    main()
