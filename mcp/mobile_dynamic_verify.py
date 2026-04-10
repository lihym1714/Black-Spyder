from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import typer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp.common import PROJECT_ROOT as COMMON_PROJECT_ROOT
from mcp.common import build_request_id, utc_now_iso, write_json


RAW_DIR = COMMON_PROJECT_ROOT / "evidence" / "raw"
NORMALIZED_DIR = COMMON_PROJECT_ROOT / "evidence" / "normalized"
app = typer.Typer(add_completion=False, help="Capture reproducible adb-based mobile verification evidence.")


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(COMMON_PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def run_subprocess(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def adb_command(*args: str, device_id: str | None = None) -> list[str]:
    base = [shutil.which("adb") or "adb"]
    if device_id:
        base.extend(["-s", device_id])
    base.extend(args)
    return base


def parse_adb_devices(stdout: str) -> list[dict[str, str]]:
    devices: list[dict[str, str]] = []
    for line in stdout.splitlines()[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        serial, _, status = stripped.partition("\t")
        if serial and status:
            devices.append({"serial": serial, "status": status})
    return devices


def parse_package_dump(stdout: str) -> dict[str, Any]:
    debuggable = "DEBUGGABLE" in stdout or "debuggable" in stdout.lower()
    requested_permissions = sorted(set(re.findall(r"android\.permission\.[A-Z0-9_]+", stdout)))
    package_paths = sorted(set(re.findall(r"codePath=([^\s]+)", stdout)))
    user_ids = sorted(set(re.findall(r"userId=(\d+)", stdout)))
    return {
        "debuggable_clue": debuggable,
        "requested_permissions": requested_permissions,
        "package_paths": package_paths,
        "user_ids": user_ids,
    }


def run_mobile_dynamic_verify(package_name: str, device_id: str | None = None) -> dict[str, Any]:
    request_id = build_request_id()
    raw_path = RAW_DIR / f"{request_id}-mobile-verify.json"
    normalized_path = NORMALIZED_DIR / f"{request_id}-mobile-verify.json"
    limitations: list[str] = []

    adb_path = shutil.which("adb")
    if adb_path is None:
        result: dict[str, Any] = {
            "request_id": request_id,
            "package_name": package_name,
            "available": False,
            "error": "adb is not installed.",
            "limitations": ["Dynamic mobile verification requires adb and a connected device or emulator."],
        }
        write_json(raw_path, {**result, "observed_at": utc_now_iso()})
        write_json(normalized_path, {**result, "classification": "suspected", "confidence": "low"})
        result["artifact_paths"] = {"raw": relative_path(raw_path), "normalized": relative_path(normalized_path)}
        return result

    devices_result = run_subprocess(adb_command("devices"))
    devices = parse_adb_devices(devices_result["stdout"])
    usable_devices = [device for device in devices if device["status"] == "device"]
    selected_device = device_id or (usable_devices[0]["serial"] if usable_devices else None)

    raw_payload: dict[str, Any] = {
        "request_id": request_id,
        "observed_at": utc_now_iso(),
        "package_name": package_name,
        "devices": devices,
        "selected_device": selected_device,
        "commands": {"devices": devices_result},
    }

    if selected_device is None:
        limitations.append("No connected adb device or emulator is available for dynamic verification.")
        normalized_payload = {
            "request_id": request_id,
            "workflow": "mobile-verify",
            "package_name": package_name,
            "selected_device": None,
            "installed": False,
            "notes": [],
            "classification": "suspected",
            "confidence": "low",
            "limitations": limitations,
        }
        write_json(raw_path, raw_payload)
        write_json(normalized_path, normalized_payload)
        return {
            "request_id": request_id,
            "package_name": package_name,
            "selected_device": None,
            "devices": devices,
            "installed": False,
            "artifact_paths": {"raw": relative_path(raw_path), "normalized": relative_path(normalized_path)},
            "limitations": limitations,
        }

    package_path_result = run_subprocess(adb_command("shell", "pm", "path", package_name, device_id=selected_device))
    dumpsys_result = run_subprocess(adb_command("shell", "dumpsys", "package", package_name, device_id=selected_device))
    pidof_result = run_subprocess(adb_command("shell", "pidof", package_name, device_id=selected_device))
    props_result = run_subprocess(adb_command("shell", "getprop", device_id=selected_device))

    raw_payload["commands"].update(
        {
            "pm_path": package_path_result,
            "dumpsys_package": dumpsys_result,
            "pidof": pidof_result,
            "getprop": props_result,
        }
    )

    installed = package_path_result["exit_code"] == 0 and "package:" in package_path_result["stdout"]
    package_details = parse_package_dump(dumpsys_result["stdout"]) if dumpsys_result["exit_code"] == 0 else {
        "debuggable_clue": False,
        "requested_permissions": [],
        "package_paths": [],
        "user_ids": [],
    }
    pid = pidof_result["stdout"].strip() or None
    device_model_match = re.search(r"\[ro.product.model\]: \[(.+)\]", props_result["stdout"])
    device_release_match = re.search(r"\[ro.build.version.release\]: \[(.+)\]", props_result["stdout"])

    if not installed:
        limitations.append("The package is not installed on the selected adb target.")
    if dumpsys_result["exit_code"] != 0:
        limitations.append("dumpsys package output was unavailable or incomplete.")

    normalized_payload: dict[str, Any] = {
        "request_id": request_id,
        "workflow": "mobile-verify",
        "package_name": package_name,
        "selected_device": selected_device,
        "installed": installed,
        "runtime_state": {
            "pid": pid,
            "debuggable_clue": package_details["debuggable_clue"],
            "requested_permissions": package_details["requested_permissions"],
            "package_paths": package_details["package_paths"],
            "user_ids": package_details["user_ids"],
        },
        "device_profile": {
            "model": device_model_match.group(1) if device_model_match else None,
            "android_release": device_release_match.group(1) if device_release_match else None,
        },
        "notes": [
            "Dynamic verification captures adb-observed state only.",
            "No runtime hooking, bypass, or exploitation is performed by this workflow.",
        ],
        "classification": "suspected",
        "confidence": "medium" if installed else "low",
        "limitations": limitations,
    }

    write_json(raw_path, raw_payload)
    write_json(normalized_path, normalized_payload)

    return {
        "request_id": request_id,
        "package_name": package_name,
        "selected_device": selected_device,
        "installed": installed,
        "devices": devices,
        "runtime_state": normalized_payload["runtime_state"],
        "device_profile": normalized_payload["device_profile"],
        "artifact_paths": {"raw": relative_path(raw_path), "normalized": relative_path(normalized_path)},
        "limitations": limitations,
    }


@app.command()
def main(
    package_name: str = typer.Option(..., help="Android package name to verify on the connected device/emulator."),
    device_id: str | None = typer.Option(None, help="Optional adb device serial to target."),
) -> None:
    typer.echo(json.dumps(run_mobile_dynamic_verify(package_name=package_name, device_id=device_id), indent=2))


if __name__ == "__main__":
    app()
