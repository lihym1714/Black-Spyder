from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from mcp.common import PROJECT_ROOT
import yaml

AGENTS_DIR = PROJECT_ROOT / "agents"
COMMANDS_DIR = PROJECT_ROOT / "commands"
POLICY_PATH = PROJECT_ROOT / "policies" / "scope.yaml"
STATE_TEMPLATE_PATH = PROJECT_ROOT / "state" / "state.json"
RUNTIME_STATE_PATH = PROJECT_ROOT / "state" / "runtime_state.json"
SUPPORTED_COMMAND_WORKFLOWS = {
    "registry",
    "commands",
    "ecosystem",
    "observe",
    "recon",
    "compare-auth",
    "mobile-review",
    "write-finding",
    "next-step",
    "sessions",
    "session-show",
    "doctor",
}


@dataclass(frozen=True)
class AgentMetadata:
    name: str
    description: str
    workflows: list[str]
    allowed_tools: list[str]
    docs: list[str]
    runtime_entrypoints: list[str]


@dataclass(frozen=True)
class CommandMetadata:
    name: str
    summary: str
    workflow: str
    agent: str
    usage: str
    examples: list[str]
    passthrough_args: list[str]


def parse_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        raise ValueError(f"Expected frontmatter in {path}")
    closing = normalized.find("\n---\n", 4)
    if closing == -1:
        raise ValueError(f"Missing closing frontmatter delimiter in {path}")
    frontmatter = normalized[4:closing]
    data = yaml.safe_load(frontmatter) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Frontmatter must be a mapping in {path}")
    return data


def require_string(metadata: dict[str, Any], key: str, path: Path) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}: '{key}' must be a non-empty string")
    return value.strip()


def require_string_list(metadata: dict[str, Any], key: str, path: Path) -> list[str]:
    value = metadata.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{path}: '{key}' must be a list of non-empty strings")
    return [item.strip() for item in value]


def load_agent_registry() -> dict[str, AgentMetadata]:
    registry: dict[str, AgentMetadata] = {}
    for path in sorted(AGENTS_DIR.glob("*.md")):
        if path.name.endswith(".ko.md"):
            continue
        metadata = parse_frontmatter(path)
        name = require_string(metadata, "name", path)
        docs = [str(path.relative_to(PROJECT_ROOT))]
        ko_path = path.with_name(path.stem + ".ko.md")
        if ko_path.exists():
            docs.append(str(ko_path.relative_to(PROJECT_ROOT)))
        registry[name] = AgentMetadata(
            name=name,
            description=require_string(metadata, "description", path),
            workflows=require_string_list(metadata, "workflows", path),
            allowed_tools=require_string_list(metadata, "allowed_tools", path),
            docs=docs,
            runtime_entrypoints=require_string_list(metadata, "runtime_entrypoints", path),
        )
    return registry


def load_command_catalog() -> dict[str, CommandMetadata]:
    catalog: dict[str, CommandMetadata] = {}
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        metadata = parse_frontmatter(path)
        name = require_string(metadata, "name", path)
        workflow = require_string(metadata, "workflow", path)
        catalog[name] = CommandMetadata(
            name=name,
            summary=require_string(metadata, "summary", path),
            workflow=workflow,
            agent=require_string(metadata, "agent", path),
            usage=require_string(metadata, "usage", path),
            examples=require_string_list(metadata, "examples", path),
            passthrough_args=require_string_list(metadata, "passthrough_args", path),
        )
    return catalog


def get_command(name: str) -> CommandMetadata:
    catalog = load_command_catalog()
    if name not in catalog:
        raise KeyError(f"Unknown command: {name}")
    return catalog[name]


def ecosystem_snapshot() -> dict[str, Any]:
    agents = load_agent_registry()
    commands = load_command_catalog()
    return {
        "agents": [asdict(agent) for agent in agents.values()],
        "commands": [asdict(command) for command in commands.values()],
        "paths": {
            "agents_dir": str(AGENTS_DIR.relative_to(PROJECT_ROOT)),
            "commands_dir": str(COMMANDS_DIR.relative_to(PROJECT_ROOT)),
            "policy": str(POLICY_PATH.relative_to(PROJECT_ROOT)),
            "state_template": str(STATE_TEMPLATE_PATH.relative_to(PROJECT_ROOT)),
            "runtime_state": str(RUNTIME_STATE_PATH.relative_to(PROJECT_ROOT)),
        },
    }


def load_runtime_sessions() -> list[dict[str, Any]]:
    if not RUNTIME_STATE_PATH.exists():
        return []
    with RUNTIME_STATE_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return []
    sessions = data.get("sessions", [])
    return sessions if isinstance(sessions, list) else []


def list_runtime_sessions() -> dict[str, Any]:
    sessions = load_runtime_sessions()
    return {
        "count": len(sessions),
        "sessions": [
            {
                "session_id": session.get("session_id"),
                "workflow": session.get("workflow"),
                "agent": session.get("agent"),
                "status": session.get("status"),
                "updated_at": session.get("updated_at"),
            }
            for session in sessions
        ],
    }


def get_runtime_session(session_id: str) -> dict[str, Any]:
    for session in load_runtime_sessions():
        if session.get("session_id") == session_id:
            return session
    raise KeyError(f"Unknown session_id: {session_id}")


def ecosystem_doctor() -> dict[str, Any]:
    snapshot = ecosystem_snapshot()
    agent_names = {agent["name"] for agent in snapshot["agents"]}
    command_checks = []
    for command in snapshot["commands"]:
        command_checks.append(
            {
                "command": command["name"],
                "agent_exists": command["agent"] in agent_names,
                "workflow": command["workflow"],
                "workflow_supported": command["workflow"] in SUPPORTED_COMMAND_WORKFLOWS,
            }
        )

    return {
        "status": "ok" if all(item["agent_exists"] and item["workflow_supported"] for item in command_checks) else "error",
        "agent_count": len(snapshot["agents"]),
        "command_count": len(snapshot["commands"]),
        "runtime_state_present": RUNTIME_STATE_PATH.exists(),
        "checks": command_checks,
    }
