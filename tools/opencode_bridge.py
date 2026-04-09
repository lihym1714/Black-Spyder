from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from mcp.common import PROJECT_ROOT, build_request_id, utc_now_iso, write_json
from tools.agent_cli import run_named_workflow
from tools.ecosystem import ecosystem_doctor, ecosystem_snapshot

BRIDGE_STATE_PATH = PROJECT_ROOT / "state" / "opencode_bridge_state.json"
BRIDGE_MANIFEST_PATH = PROJECT_ROOT / "state" / "opencode-bridge-manifest.json"


class HostRegistrationRequest(BaseModel):
    host_name: str = Field(..., min_length=1)
    host_version: str | None = None
    capabilities: list[str] = Field(default_factory=list)


class ExecuteRequest(BaseModel):
    command_name: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


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
        "routes": {
            "health": "/health",
            "registry": "/registry",
            "register_host": "/register-host",
            "execute": "/execute",
        },
        "ecosystem": ecosystem,
        "doctor": doctor,
    }
    write_json(BRIDGE_MANIFEST_PATH, manifest)
    return manifest


def record_host_registration(payload: HostRegistrationRequest) -> dict[str, Any]:
    state = load_bridge_state()
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
    return {
        "status": doctor["status"],
        "bridge_manifest_present": BRIDGE_MANIFEST_PATH.exists(),
        "registered_host_count": len(load_bridge_state().get("hosts", [])),
        "doctor": doctor,
    }


@app.get("/registry")
def registry() -> dict[str, Any]:
    return build_bridge_manifest()


@app.post("/register-host")
def register_host(payload: HostRegistrationRequest) -> dict[str, Any]:
    return {
        "status": "registered",
        "host": record_host_registration(payload),
        "registry_path": normalize_bridge_path(BRIDGE_MANIFEST_PATH),
    }


@app.post("/execute")
def execute(payload: ExecuteRequest) -> dict[str, Any]:
    try:
        result = run_named_workflow(payload.command_name, payload.params)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    execution = record_execution(payload.command_name, payload.params, result)
    return {
        "status": "ok",
        "execution": execution,
    }


def main() -> None:
    build_bridge_manifest()
    uvicorn.run(app, host="127.0.0.1", port=8787)


if __name__ == "__main__":
    main()
