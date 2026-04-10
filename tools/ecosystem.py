from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from mcp.common import PROJECT_ROOT, sha256_hex, utc_now_iso, write_json
import yaml

AGENTS_DIR = PROJECT_ROOT / "agents"
COMMANDS_DIR = PROJECT_ROOT / "commands"
POLICY_PATH = PROJECT_ROOT / "policies" / "scope.yaml"
STATE_TEMPLATE_PATH = PROJECT_ROOT / "state" / "state.json"
RUNTIME_STATE_PATH = PROJECT_ROOT / "state" / "runtime_state.json"
ECOSYSTEM_INDEX_PATH = PROJECT_ROOT / "state" / "ecosystem-index-v1.json"
ECOSYSTEM_INDEX_SCHEMA_VERSION = 1
SUPPORTED_COMMAND_WORKFLOWS = {
    "analyze",
    "registry",
    "commands",
    "ecosystem",
    "observe",
    "recon",
    "compare-auth",
    "mobile-review",
    "mobile-decompile",
    "mobile-verify",
    "write-finding",
    "next-step",
    "sessions",
    "session-search",
    "session-show",
    "session-resume",
    "doctor",
}
RUN_MANIFEST_SCHEMA_VERSION = 1


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


@dataclass(frozen=True)
class SourceFileFingerprint:
    path: str
    sha256: str


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


def canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def iter_agent_source_paths() -> list[Path]:
    return sorted(path for path in AGENTS_DIR.glob("*.md") if not path.name.endswith(".ko.md"))


def iter_command_source_paths() -> list[Path]:
    return sorted(COMMANDS_DIR.glob("*.md"))


def fingerprint_source_file(path: Path) -> SourceFileFingerprint:
    normalized_path = normalize_catalog_path(path)
    return SourceFileFingerprint(
        path=normalized_path,
        sha256=sha256_hex(path.read_bytes()),
    )


def normalize_catalog_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def build_source_manifest() -> list[SourceFileFingerprint]:
    paths = [*iter_agent_source_paths(), *iter_command_source_paths()]
    return [fingerprint_source_file(path) for path in paths]


def compute_source_digest(source_manifest: list[SourceFileFingerprint]) -> str:
    payload = [asdict(entry) for entry in source_manifest]
    return sha256_hex(canonical_json_bytes(payload))


def parse_agent_registry_from_sources() -> dict[str, AgentMetadata]:
    registry: dict[str, AgentMetadata] = {}
    for path in iter_agent_source_paths():
        metadata = parse_frontmatter(path)
        name = require_string(metadata, "name", path)
        docs = [normalize_catalog_path(path)]
        ko_path = path.with_name(path.stem + ".ko.md")
        if ko_path.exists():
            docs.append(normalize_catalog_path(ko_path))
        registry[name] = AgentMetadata(
            name=name,
            description=require_string(metadata, "description", path),
            workflows=require_string_list(metadata, "workflows", path),
            allowed_tools=require_string_list(metadata, "allowed_tools", path),
            docs=docs,
            runtime_entrypoints=require_string_list(metadata, "runtime_entrypoints", path),
        )
    return registry


def parse_command_catalog_from_sources() -> dict[str, CommandMetadata]:
    catalog: dict[str, CommandMetadata] = {}
    for path in iter_command_source_paths():
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


def build_ecosystem_index() -> dict[str, Any]:
    source_manifest = build_source_manifest()
    agent_registry = parse_agent_registry_from_sources()
    command_catalog = parse_command_catalog_from_sources()
    return {
        "schema_version": ECOSYSTEM_INDEX_SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "source_digest": compute_source_digest(source_manifest),
        "source_files": [asdict(entry) for entry in source_manifest],
        "agents": [asdict(agent_registry[name]) for name in sorted(agent_registry)],
        "commands": [asdict(command_catalog[name]) for name in sorted(command_catalog)],
    }


def write_ecosystem_index(index: dict[str, Any]) -> None:
    write_json(ECOSYSTEM_INDEX_PATH, index)


def load_cached_ecosystem_index() -> dict[str, Any] | None:
    if not ECOSYSTEM_INDEX_PATH.exists():
        return None
    with ECOSYSTEM_INDEX_PATH.open("r", encoding="utf-8") as handle:
        cached = json.load(handle)
    if not isinstance(cached, dict):
        return None
    if cached.get("schema_version") != ECOSYSTEM_INDEX_SCHEMA_VERSION:
        return None
    source_files = cached.get("source_files")
    if not isinstance(source_files, list):
        return None
    current_manifest = build_source_manifest()
    current_digest = compute_source_digest(current_manifest)
    if cached.get("source_digest") != current_digest:
        return None
    return cached


def load_ecosystem_index() -> dict[str, Any]:
    cached = load_cached_ecosystem_index()
    if cached is not None:
        return cached
    rebuilt = build_ecosystem_index()
    write_ecosystem_index(rebuilt)
    return rebuilt


def hydrate_agent_registry(index: dict[str, Any]) -> dict[str, AgentMetadata]:
    registry: dict[str, AgentMetadata] = {}
    for entry in index.get("agents", []):
        if not isinstance(entry, dict):
            raise ValueError("Invalid agent entry in ecosystem index")
        agent = AgentMetadata(
            name=require_string(entry, "name", ECOSYSTEM_INDEX_PATH),
            description=require_string(entry, "description", ECOSYSTEM_INDEX_PATH),
            workflows=require_string_list(entry, "workflows", ECOSYSTEM_INDEX_PATH),
            allowed_tools=require_string_list(entry, "allowed_tools", ECOSYSTEM_INDEX_PATH),
            docs=require_string_list(entry, "docs", ECOSYSTEM_INDEX_PATH),
            runtime_entrypoints=require_string_list(entry, "runtime_entrypoints", ECOSYSTEM_INDEX_PATH),
        )
        registry[agent.name] = agent
    return registry


def hydrate_command_catalog(index: dict[str, Any]) -> dict[str, CommandMetadata]:
    catalog: dict[str, CommandMetadata] = {}
    for entry in index.get("commands", []):
        if not isinstance(entry, dict):
            raise ValueError("Invalid command entry in ecosystem index")
        command = CommandMetadata(
            name=require_string(entry, "name", ECOSYSTEM_INDEX_PATH),
            summary=require_string(entry, "summary", ECOSYSTEM_INDEX_PATH),
            workflow=require_string(entry, "workflow", ECOSYSTEM_INDEX_PATH),
            agent=require_string(entry, "agent", ECOSYSTEM_INDEX_PATH),
            usage=require_string(entry, "usage", ECOSYSTEM_INDEX_PATH),
            examples=require_string_list(entry, "examples", ECOSYSTEM_INDEX_PATH),
            passthrough_args=require_string_list(entry, "passthrough_args", ECOSYSTEM_INDEX_PATH),
        )
        catalog[command.name] = command
    return catalog


def load_agent_registry() -> dict[str, AgentMetadata]:
    return hydrate_agent_registry(load_ecosystem_index())


def load_command_catalog() -> dict[str, CommandMetadata]:
    return hydrate_command_catalog(load_ecosystem_index())


def get_command(name: str) -> CommandMetadata:
    catalog = load_command_catalog()
    if name not in catalog:
        raise KeyError(f"Unknown command: {name}")
    return catalog[name]


def ecosystem_snapshot() -> dict[str, Any]:
    index = load_ecosystem_index()
    return {
        "schema_version": index["schema_version"],
        "source_digest": index["source_digest"],
        "generated_at": index["generated_at"],
        "agents": index["agents"],
        "commands": index["commands"],
        "paths": {
            "agents_dir": str(AGENTS_DIR.relative_to(PROJECT_ROOT)),
            "commands_dir": str(COMMANDS_DIR.relative_to(PROJECT_ROOT)),
            "policy": str(POLICY_PATH.relative_to(PROJECT_ROOT)),
            "state_template": str(STATE_TEMPLATE_PATH.relative_to(PROJECT_ROOT)),
            "runtime_state": normalize_catalog_path(RUNTIME_STATE_PATH),
            "ecosystem_index": str(ECOSYSTEM_INDEX_PATH.relative_to(PROJECT_ROOT)),
        },
    }


def load_runtime_sessions() -> list[dict[str, Any]]:
    if not RUNTIME_STATE_PATH.exists():
        return []
    try:
        with RUNTIME_STATE_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    sessions = data.get("sessions", [])
    return sessions if isinstance(sessions, list) else []


def canonicalize_manifest_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: canonicalize_manifest_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonicalize_manifest_value(item) for item in value]
    return value


def build_runtime_run_manifest(workflow: str, agent: str, params: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "workflow": workflow,
        "agent": agent,
        "params": canonicalize_manifest_value(params),
    }


def get_session_run_manifest(session: dict[str, Any]) -> dict[str, Any]:
    manifest = session.get("run_manifest")
    if isinstance(manifest, dict):
        return manifest
    workflow = session.get("workflow")
    agent = session.get("agent")
    inputs = session.get("inputs", {})
    if not isinstance(workflow, str) or not isinstance(agent, str) or not isinstance(inputs, dict):
        raise KeyError("Session is missing a resumable run manifest")
    return build_runtime_run_manifest(workflow, agent, inputs)


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


def search_runtime_sessions(
    *,
    query: str | None = None,
    workflow: str | None = None,
    status: str | None = None,
    agent: str | None = None,
) -> dict[str, Any]:
    lowered_query = query.lower() if query else None
    matches = []
    for session in load_runtime_sessions():
        if workflow and session.get("workflow") != workflow:
            continue
        if status and session.get("status") != status:
            continue
        if agent and session.get("agent") != agent:
            continue
        if lowered_query:
            haystack = json.dumps(session, sort_keys=True).lower()
            if lowered_query not in haystack:
                continue
        matches.append(
            {
                "session_id": session.get("session_id"),
                "workflow": session.get("workflow"),
                "agent": session.get("agent"),
                "status": session.get("status"),
                "updated_at": session.get("updated_at"),
                "run_manifest": get_session_run_manifest(session),
            }
        )
    return {"count": len(matches), "sessions": matches}


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
        agent_exists = command["agent"] in agent_names
        workflow_supported = command["workflow"] in SUPPORTED_COMMAND_WORKFLOWS
        command_checks.append(
            {
                "code": f"COMMAND_{command['name'].strip('/').replace('-', '_').upper() or 'ROOT'}",
                "command": command["name"],
                "severity": "error" if not agent_exists or not workflow_supported else "info",
                "status": "ok" if agent_exists and workflow_supported else "error",
                "message": "Command metadata is internally consistent."
                if agent_exists and workflow_supported
                else "Command metadata has an invalid agent or unsupported workflow.",
                "remediation": "Update the command spec so the agent exists and the workflow is supported.",
                "agent_exists": agent_exists,
                "workflow": command["workflow"],
                "workflow_supported": workflow_supported,
            }
        )

    core_checks = [
        {
            "code": "AGENT_REGISTRY_PRESENT",
            "severity": "error" if not snapshot["agents"] else "info",
            "status": "ok" if snapshot["agents"] else "error",
            "message": "Agent registry is loaded." if snapshot["agents"] else "No agent metadata was loaded.",
            "remediation": "Ensure English agent specs contain valid frontmatter and can be indexed.",
        },
        {
            "code": "COMMAND_CATALOG_PRESENT",
            "severity": "error" if not snapshot["commands"] else "info",
            "status": "ok" if snapshot["commands"] else "error",
            "message": "Command catalog is loaded." if snapshot["commands"] else "No command metadata was loaded.",
            "remediation": "Ensure commands/*.md exists with valid frontmatter.",
        },
        {
            "code": "ECOSYSTEM_INDEX_PRESENT",
            "severity": "warning" if not ECOSYSTEM_INDEX_PATH.exists() else "info",
            "status": "ok" if ECOSYSTEM_INDEX_PATH.exists() else "warning",
            "message": "Generated ecosystem index is present." if ECOSYSTEM_INDEX_PATH.exists() else "Generated ecosystem index is missing and will be created on demand.",
            "remediation": "Run an ecosystem-facing command such as 'black-spyder-agent ecosystem' to generate the index.",
        },
        {
            "code": "RUNTIME_STATE_PRESENT",
            "severity": "info",
            "status": "ok" if RUNTIME_STATE_PATH.exists() else "ok",
            "message": "Runtime state file is present." if RUNTIME_STATE_PATH.exists() else "Runtime state file has not been created yet.",
            "remediation": "Run any runtime command to create local runtime state if needed.",
        },
    ]

    all_checks = [*core_checks, *command_checks]
    blocking_checks = [check for check in all_checks if check["status"] == "error" and check["severity"] == "error"]
    warning_checks = [check for check in all_checks if check["status"] == "warning"]

    return {
        "status": "ok" if not blocking_checks else "error",
        "agent_count": len(snapshot["agents"]),
        "command_count": len(snapshot["commands"]),
        "runtime_state_present": RUNTIME_STATE_PATH.exists(),
        "ecosystem_index_present": ECOSYSTEM_INDEX_PATH.exists(),
        "blocking_check_count": len(blocking_checks),
        "warning_check_count": len(warning_checks),
        "checks": all_checks,
    }
