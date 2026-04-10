from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
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
DECOMPILED_ROOT = COMMON_PROJECT_ROOT / "evidence" / "decompiled"
app = typer.Typer(add_completion=False, help="Decompile a local APK into reproducible evidence artifacts.")


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(COMMON_PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    return lowered.strip("-") or "mobile-app"


def resolve_apk_path(apk_path: str) -> Path:
    candidate = Path(apk_path)
    candidate = candidate.resolve() if candidate.is_absolute() else (COMMON_PROJECT_ROOT / candidate).resolve()
    artifacts_root = (COMMON_PROJECT_ROOT / "artifacts").resolve()
    if not (artifacts_root == candidate or artifacts_root in candidate.parents):
        raise ValueError("APK path must stay inside the local artifacts/ directory.")
    if not candidate.exists():
        raise FileNotFoundError(f"APK path not found: {candidate}")
    if candidate.suffix.lower() != ".apk":
        raise ValueError("Only .apk files are supported by the APK decompile workflow.")
    return candidate


def summarize_archive(apk_file: Path) -> dict[str, Any]:
    with zipfile.ZipFile(apk_file) as archive:
        names = archive.namelist()
    extensions = Counter(Path(name).suffix.lower() or "<no_ext>" for name in names)
    dex_files = sorted(name for name in names if name.endswith(".dex"))
    return {
        "entry_count": len(names),
        "extension_counts": dict(sorted(extensions.items())),
        "contains_android_manifest": "AndroidManifest.xml" in names,
        "dex_files": dex_files,
    }


def run_subprocess(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def parse_badging(stdout: str) -> dict[str, Any]:
    package_name: str | None = None
    version_name: str | None = None
    version_code: str | None = None
    sdk_version: str | None = None
    target_sdk_version: str | None = None

    package_match = re.search(r"package: name='([^']+)'(?: versionCode='([^']+)')?(?: versionName='([^']+)')?", stdout)
    if package_match:
        package_name = package_match.group(1)
        version_code = package_match.group(2)
        version_name = package_match.group(3)

    sdk_match = re.search(r"sdkVersion:'([^']+)'", stdout)
    if sdk_match:
        sdk_version = sdk_match.group(1)

    target_sdk_match = re.search(r"targetSdkVersion:'([^']+)'", stdout)
    if target_sdk_match:
        target_sdk_version = target_sdk_match.group(1)

    return {
        "package_name": package_name,
        "version_name": version_name,
        "version_code": version_code,
        "sdk_version": sdk_version,
        "target_sdk_version": target_sdk_version,
    }


def run_apk_decompile(apk_path: str) -> dict[str, Any]:
    apk_file = resolve_apk_path(apk_path)
    request_id = build_request_id()
    slug = f"{slugify(apk_file.stem)}-{request_id[:8]}"
    output_root = DECOMPILED_ROOT / slug
    archive_summary = summarize_archive(apk_file)

    raw_tool_results: dict[str, Any] = {}
    normalized_tools: dict[str, Any] = {}
    decompiled_outputs: dict[str, str] = {}
    package_metadata: dict[str, Any] = {
        "package_name": None,
        "version_name": None,
        "version_code": None,
        "sdk_version": None,
        "target_sdk_version": None,
    }
    limitations: list[str] = []

    badging_command: list[str] | None = None
    if command_exists("aapt"):
        badging_command = [shutil.which("aapt") or "aapt", "dump", "badging", str(apk_file)]
    elif command_exists("aapt2"):
        badging_command = [shutil.which("aapt2") or "aapt2", "dump", "badging", str(apk_file)]

    if badging_command is not None:
        badging_result = run_subprocess(badging_command)
        raw_tool_results["badging"] = badging_result
        normalized_tools["badging"] = {
            "command": badging_result["command"],
            "exit_code": badging_result["exit_code"],
        }
        if badging_result["exit_code"] == 0:
            package_metadata = parse_badging(badging_result["stdout"])
        else:
            limitations.append("Badging extraction failed; package metadata may be incomplete.")
    else:
        limitations.append("aapt/aapt2 is unavailable, so package metadata extraction is limited.")

    if command_exists("jadx"):
        jadx_output = output_root / "jadx"
        jadx_result = run_subprocess([shutil.which("jadx") or "jadx", "--output-dir", str(jadx_output), str(apk_file)])
        raw_tool_results["jadx"] = jadx_result
        normalized_tools["jadx"] = {
            "command": jadx_result["command"],
            "exit_code": jadx_result["exit_code"],
            "output_dir": relative_path(jadx_output),
        }
        if jadx_result["exit_code"] == 0:
            decompiled_outputs["jadx"] = relative_path(jadx_output)
        else:
            limitations.append("jadx decompilation failed; Java source output is unavailable.")
    else:
        limitations.append("jadx is unavailable, so Java source decompilation was skipped.")

    if command_exists("apktool"):
        apktool_output = output_root / "apktool"
        apktool_result = run_subprocess([shutil.which("apktool") or "apktool", "d", "-f", "-o", str(apktool_output), str(apk_file)])
        raw_tool_results["apktool"] = apktool_result
        normalized_tools["apktool"] = {
            "command": apktool_result["command"],
            "exit_code": apktool_result["exit_code"],
            "output_dir": relative_path(apktool_output),
        }
        if apktool_result["exit_code"] == 0:
            decompiled_outputs["apktool"] = relative_path(apktool_output)
        else:
            limitations.append("apktool decompilation failed; resource and manifest decode output is unavailable.")
    else:
        limitations.append("apktool is unavailable, so resource-level decompilation was skipped.")

    raw_path = RAW_DIR / f"{request_id}-apk-decompile.json"
    normalized_path = NORMALIZED_DIR / f"{request_id}-apk-decompile.json"

    raw_payload = {
        "request_id": request_id,
        "observed_at": utc_now_iso(),
        "apk_path": relative_path(apk_file),
        "archive_summary": archive_summary,
        "tool_results": raw_tool_results,
        "decompiled_outputs": decompiled_outputs,
    }
    normalized_payload = {
        "request_id": request_id,
        "workflow": "mobile-decompile",
        "apk_path": relative_path(apk_file),
        "archive_summary": archive_summary,
        "package_metadata": package_metadata,
        "tool_summary": normalized_tools,
        "decompiled_outputs": decompiled_outputs,
        "notes": [
            "APK decompile evidence reflects local tooling output only.",
            "Use the generated decompile artifacts as supporting evidence for follow-up review.",
        ],
        "classification": "suspected",
        "confidence": "medium" if decompiled_outputs else "low",
        "limitations": limitations,
    }

    write_json(raw_path, raw_payload)
    write_json(normalized_path, normalized_payload)

    return {
        "request_id": request_id,
        "apk_path": relative_path(apk_file),
        "archive_summary": archive_summary,
        "package_metadata": package_metadata,
        "tool_summary": normalized_tools,
        "decompiled_outputs": decompiled_outputs,
        "artifact_paths": {
            "raw": relative_path(raw_path),
            "normalized": relative_path(normalized_path),
        },
        "limitations": limitations,
    }


@app.command()
def main(apk_path: str = typer.Option(..., help="Local APK file path under artifacts/.")) -> None:
    typer.echo(json.dumps(run_apk_decompile(apk_path=apk_path), indent=2))


if __name__ == "__main__":
    app()
