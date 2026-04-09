from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from tools.ecosystem import ecosystem_snapshot, ecosystem_doctor

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = PROJECT_ROOT / ".venv"
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
POLICY_FILE = PROJECT_ROOT / "policies" / "scope.yaml"
REQUIRED_DIRS = [
    PROJECT_ROOT / "evidence" / "raw",
    PROJECT_ROOT / "evidence" / "normalized",
    PROJECT_ROOT / "findings",
    PROJECT_ROOT / "state",
    PROJECT_ROOT / "templates",
    PROJECT_ROOT / "mcp",
    PROJECT_ROOT / "tools",
    PROJECT_ROOT / "agents",
    PROJECT_ROOT / "commands",
]


def detect_os() -> str:
    name = platform.system().lower()
    if "darwin" in name:
        return "macOS"
    if "windows" in name:
        return "Windows"
    if "linux" in name:
        return "Linux"
    return platform.system()


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def run_command(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=check, text=True, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required command is unavailable: {' '.join(command)}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else ""
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{stderr}") from exc


def install_guidance(os_name: str) -> dict[str, str]:
    if os_name == "macOS":
        return {
            "python3": "brew install python",
            "pip": "python3 -m ensurepip --upgrade",
            "git": "brew install git",
            "curl": "brew install curl",
            "yara": "brew install yara",
        }
    if os_name == "Linux":
        if command_exists("apt-get"):
            return {
                "python3": "sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip",
                "pip": "sudo apt-get update && sudo apt-get install -y python3-pip",
                "git": "sudo apt-get update && sudo apt-get install -y git",
                "curl": "sudo apt-get update && sudo apt-get install -y curl",
                "yara": "sudo apt-get update && sudo apt-get install -y yara",
            }
        if command_exists("dnf"):
            return {
                "python3": "sudo dnf install -y python3 python3-pip",
                "pip": "sudo dnf install -y python3-pip",
                "git": "sudo dnf install -y git",
                "curl": "sudo dnf install -y curl",
                "yara": "sudo dnf install -y yara",
            }
        if command_exists("pacman"):
            return {
                "python3": "sudo pacman -Sy --noconfirm python python-pip",
                "pip": "sudo pacman -Sy --noconfirm python-pip",
                "git": "sudo pacman -Sy --noconfirm git",
                "curl": "sudo pacman -Sy --noconfirm curl",
                "yara": "sudo pacman -Sy --noconfirm yara",
            }
    if os_name == "Windows":
        return {
            "python3": "winget install -e --id Python.Python.3.12",
            "pip": "py -m ensurepip --upgrade",
            "git": "winget install -e --id Git.Git",
            "curl": "curl ships with current Windows builds; if missing, install via winget or Git for Windows.",
            "yara": "Install YARA manually or via your preferred Windows package manager.",
        }
    return {name: f"Install {name} using your system package manager." for name in ["python3", "pip", "git", "curl", "yara"]}


def attempt_install(command_name: str, os_name: str) -> str | None:
    if os_name == "macOS" and command_exists("brew"):
        package = "python" if command_name in {"python3", "pip"} else command_name
        run_command(["brew", "install", package])
        return f"brew install {package}"
    if os_name == "Linux" and command_exists("apt-get"):
        packages = {
            "python3": ["python3", "python3-venv", "python3-pip"],
            "pip": ["python3-pip"],
            "git": ["git"],
            "curl": ["curl"],
            "yara": ["yara"],
        }[command_name]
        run_command(["sudo", "apt-get", "update"])
        run_command(["sudo", "apt-get", "install", "-y", *packages])
        return f"sudo apt-get update && sudo apt-get install -y {' '.join(packages)}"
    if os_name == "Linux" and command_exists("dnf"):
        packages = {
            "python3": ["python3", "python3-pip"],
            "pip": ["python3-pip"],
            "git": ["git"],
            "curl": ["curl"],
            "yara": ["yara"],
        }[command_name]
        run_command(["sudo", "dnf", "install", "-y", *packages])
        return f"sudo dnf install -y {' '.join(packages)}"
    if os_name == "Linux" and command_exists("pacman"):
        packages = {
            "python3": ["python", "python-pip"],
            "pip": ["python-pip"],
            "git": ["git"],
            "curl": ["curl"],
            "yara": ["yara"],
        }[command_name]
        run_command(["sudo", "pacman", "-Sy", "--noconfirm", *packages])
        return f"sudo pacman -Sy --noconfirm {' '.join(packages)}"
    if os_name == "Windows" and command_exists("winget"):
        packages = {
            "python3": ["winget", "install", "-e", "--id", "Python.Python.3.12"],
            "git": ["winget", "install", "-e", "--id", "Git.Git"],
        }
        if command_name in packages:
            run_command(packages[command_name])
            return " ".join(packages[command_name])
    return None


def ensure_prerequisites(attempt_auto_install: bool) -> tuple[str, list[str], list[str]]:
    os_name = detect_os()
    guidance = install_guidance(os_name)
    checked: list[str] = []
    missing: list[str] = []

    for command_name in ["python3", "git", "curl"]:
        checked.append(command_name)
        if not command_exists(command_name):
            missing.append(command_name)
            if attempt_auto_install:
                attempted = attempt_install(command_name, os_name)
                if attempted:
                    print(f"Attempted installation for {command_name}: {attempted}")

    if command_exists("python3"):
        checked.append("pip")
        pip_ok = run_command(["python3", "-m", "pip", "--version"], check=False)
        if pip_ok.returncode != 0:
            ensurepip = run_command(["python3", "-m", "ensurepip", "--upgrade"], check=False)
            if ensurepip.returncode != 0:
                missing.append("pip")
    else:
        missing.append("pip")

    if missing:
        print("Missing prerequisites detected:")
        for name in sorted(set(missing)):
            print(f"- {name}: {guidance.get(name, f'Install {name} manually.')}")
        raise SystemExit(1)

    return os_name, checked, sorted(set(missing))


def report_optional_tools(os_name: str, attempt_auto_install: bool) -> None:
    guidance = install_guidance(os_name)
    optional_tools = ["yara"]
    for command_name in optional_tools:
        if command_exists(command_name):
            print(f"- Optional tool available: {command_name}")
            continue
        if attempt_auto_install:
            attempted = attempt_install(command_name, os_name)
            if attempted and command_exists(command_name):
                print(f"- Optional tool installed: {command_name} ({attempted})")
                continue
        print(f"- Optional tool missing: {command_name} ({guidance.get(command_name)})")


def ensure_venv() -> Path:
    if not VENV_DIR.exists():
        run_command(["python3", "-m", "venv", str(VENV_DIR)])
    return VENV_DIR / ("Scripts" if detect_os() == "Windows" else "bin") / ("python.exe" if detect_os() == "Windows" else "python")


def install_dependencies(venv_python: Path) -> None:
    if not REQUIREMENTS_FILE.exists():
        raise RuntimeError(f"Missing requirements file: {REQUIREMENTS_FILE}")
    run_command([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    run_command([str(venv_python), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])
    run_command([str(venv_python), "-m", "pip", "install", "-e", str(PROJECT_ROOT)])


def ensure_directories(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def bootstrap(attempt_install_missing: bool = False) -> None:
    os_name, checked, _ = ensure_prerequisites(attempt_install_missing)
    venv_python = ensure_venv()
    ensure_directories(REQUIRED_DIRS)

    if not POLICY_FILE.exists():
        print(f"Policy file is missing: {POLICY_FILE}")
        raise SystemExit(1)

    install_dependencies(venv_python)
    ecosystem_snapshot()
    doctor_report = ecosystem_doctor()
    if doctor_report["status"] != "ok":
        raise RuntimeError(
            "Ecosystem doctor reported blocking issues after bootstrap:\n"
            + json.dumps(doctor_report, indent=2)
        )

    print("Setup summary:")
    print(f"- OS: {os_name}")
    print(f"- Checked commands: {', '.join(checked)}")
    report_optional_tools(os_name, attempt_install_missing)
    print(f"- Virtual environment: {VENV_DIR}")
    print(f"- Requirements installed from: {REQUIREMENTS_FILE}")
    print("- Console entry points installed: black-spyder-bootstrap, black-spyder-agent")
    print(f"- Policy file validated: {POLICY_FILE}")
    print("- Workspace directories ensured: evidence/raw, evidence/normalized, findings, state, commands")
    print(f"- Ecosystem index generated: {PROJECT_ROOT / 'state' / 'ecosystem-index-v1.json'}")
    print(f"- Doctor status: {doctor_report['status']} ({doctor_report['blocking_check_count']} blocking, {doctor_report['warning_check_count']} warning)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the local Black-Spyder workspace.")
    parser.add_argument(
        "--attempt-install",
        action="store_true",
        help="Attempt package-manager installation when possible.",
    )
    args = parser.parse_args()
    bootstrap(attempt_install_missing=args.attempt_install)


if __name__ == "__main__":
    main()
