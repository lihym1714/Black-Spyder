from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import typer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.ecosystem import (
    RUN_MANIFEST_SCHEMA_VERSION,
    ecosystem_doctor,
    ecosystem_snapshot,
    get_command,
    get_runtime_session,
    get_session_run_manifest,
    list_runtime_sessions,
    search_runtime_sessions,
)
from tools.agent_runtime import (
    list_agents,
    next_step,
    route_workflow,
    run_autonomous_analysis,
    run_compare_auth,
    run_mobile_review,
    run_observe,
    run_recon,
    run_write_finding,
)

app = typer.Typer(add_completion=False, help="Run the Black-Spyder executable agent workflows.")
@dataclass(frozen=True)
class WorkflowDispatchRule:
    required_params: tuple[str, ...]
    handler: Callable[[dict[str, Any]], dict[str, Any]]


def emit(data: dict[str, Any]) -> None:
    typer.echo(json.dumps(data, indent=2))


def parse_json_or_value(raw: str) -> Any:
    stripped = raw.strip()
    lowered = stripped.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return stripped


def require_bool_param(params: dict[str, Any], key: str, default: bool) -> bool:
    value = params.get(key, default)
    if isinstance(value, bool):
        return value
    raise typer.BadParameter(f"{key} must be a boolean (true/false)")


def require_string_list_param(params: dict[str, Any], key: str, required: bool = False) -> list[str]:
    if key not in params:
        if required:
            raise typer.BadParameter(f"{key} is required")
        return []
    value = params[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise typer.BadParameter(f"{key} must be a JSON array of strings")
    return value


def require_dict_param(params: dict[str, Any], key: str) -> dict[str, Any] | None:
    if key not in params:
        return None
    value = params[key]
    if not isinstance(value, dict):
        raise typer.BadParameter(f"{key} must be a JSON object")
    return value


def reject_unknown_params(command_name: str, params: dict[str, Any]) -> None:
    command = get_command(command_name)
    allowed = set(command.passthrough_args)
    unknown = sorted(set(params) - allowed)
    if unknown:
        raise typer.BadParameter(f"{command_name} does not accept: {', '.join(unknown)}")


def parse_key_value_args(pairs: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise typer.BadParameter(f"Expected key=value argument, got: {pair}")
        key, value = pair.split("=", 1)
        parsed[key] = parse_json_or_value(value)
    return parsed


def canonicalize_for_manifest(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: canonicalize_for_manifest(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonicalize_for_manifest(item) for item in value]
    return value


def build_run_manifest(command_name: str, params: dict[str, Any]) -> dict[str, Any]:
    command = get_command(command_name)
    return {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "command": command.name,
        "workflow": command.workflow,
        "agent": command.agent,
        "params": canonicalize_for_manifest(params),
    }


def handle_registry(_: dict[str, Any]) -> dict[str, Any]:
    return list_agents()


def handle_commands(_: dict[str, Any]) -> dict[str, Any]:
    return {"commands": ecosystem_snapshot()["commands"]}


def handle_ecosystem(_: dict[str, Any]) -> dict[str, Any]:
    return ecosystem_snapshot()


def handle_observe(params: dict[str, Any]) -> dict[str, Any]:
    return run_observe(
        url=str(params["url"]),
        method=str(params.get("method", "GET")),
        headers=require_dict_param(params, "headers"),
        execute=require_bool_param(params, "execute", True),
    )


def handle_recon(params: dict[str, Any]) -> dict[str, Any]:
    return run_recon(artifact_path=str(params["artifact_path"]))


def handle_compare_auth(params: dict[str, Any]) -> dict[str, Any]:
    return run_compare_auth(
        left_artifact_path=str(params["left_artifact_path"]),
        right_artifact_path=str(params["right_artifact_path"]),
    )


def handle_mobile_review(params: dict[str, Any]) -> dict[str, Any]:
    rules_path = params.get("rules_path")
    return run_mobile_review(
        target_path=str(params["target_path"]),
        rules_path=str(rules_path) if rules_path is not None else None,
    )


def handle_write_finding(params: dict[str, Any]) -> dict[str, Any]:
    return run_write_finding(
        title=str(params["title"]),
        host=str(params["host"]),
        endpoint=str(params["endpoint"]),
        method=str(params.get("method", "GET")),
        auth_context=str(params.get("auth_context", "unknown")),
        classification=str(params.get("classification", "suspected")),
        artifacts=require_string_list_param(params, "artifacts", required=True),
        observations=require_string_list_param(params, "observations", required=True),
        limitations=require_string_list_param(params, "limitations"),
        remediation_notes=require_string_list_param(params, "remediation_notes"),
        relative_output_path=str(params["relative_output_path"]) if "relative_output_path" in params else None,
    )


def handle_analyze(params: dict[str, Any]) -> dict[str, Any]:
    return run_autonomous_analysis(
        goal=str(params["goal"]),
        url=str(params["url"]) if "url" in params else None,
        method=str(params.get("method", "GET")),
        artifact_path=str(params["artifact_path"]) if "artifact_path" in params else None,
        left_artifact_path=str(params["left_artifact_path"]) if "left_artifact_path" in params else None,
        right_artifact_path=str(params["right_artifact_path"]) if "right_artifact_path" in params else None,
        target_path=str(params["target_path"]) if "target_path" in params else None,
        rules_path=str(params["rules_path"]) if "rules_path" in params else None,
    )


def handle_next_step(_: dict[str, Any]) -> dict[str, Any]:
    return next_step()


def handle_sessions(_: dict[str, Any]) -> dict[str, Any]:
    return list_runtime_sessions()


def handle_session_search(params: dict[str, Any]) -> dict[str, Any]:
    return search_runtime_sessions(
        query=str(params["query"]) if "query" in params else None,
        workflow=str(params["workflow"]) if "workflow" in params else None,
        status=str(params["status"]) if "status" in params else None,
        agent=str(params["agent"]) if "agent" in params else None,
    )


def handle_session_show(params: dict[str, Any]) -> dict[str, Any]:
    return get_runtime_session(str(params["session_id"]))


def execute_run_manifest(run_manifest: dict[str, Any]) -> dict[str, Any]:
    workflow = run_manifest.get("workflow")
    params = run_manifest.get("params", {})
    if not isinstance(workflow, str) or workflow not in WORKFLOW_DISPATCH_TABLE:
        raise typer.BadParameter("Unsupported workflow mapping in run manifest")
    if not isinstance(params, dict):
        raise typer.BadParameter("Run manifest params must be an object")

    rule = WORKFLOW_DISPATCH_TABLE[workflow]
    missing = sorted(param for param in rule.required_params if param not in params)
    if missing:
        raise typer.BadParameter(f"Run manifest missing required params: {', '.join(missing)}")
    return rule.handler(params)


def handle_session_resume(params: dict[str, Any]) -> dict[str, Any]:
    session = get_runtime_session(str(params["session_id"]))
    run_manifest = get_session_run_manifest(session)
    return {
        "resumed_from_session_id": session["session_id"],
        "run_manifest": run_manifest,
        "result": execute_run_manifest(run_manifest),
    }


def handle_doctor(_: dict[str, Any]) -> dict[str, Any]:
    return ecosystem_doctor()


WORKFLOW_DISPATCH_TABLE: dict[str, WorkflowDispatchRule] = {
    "registry": WorkflowDispatchRule(required_params=(), handler=handle_registry),
    "commands": WorkflowDispatchRule(required_params=(), handler=handle_commands),
    "ecosystem": WorkflowDispatchRule(required_params=(), handler=handle_ecosystem),
    "observe": WorkflowDispatchRule(required_params=("url",), handler=handle_observe),
    "recon": WorkflowDispatchRule(required_params=("artifact_path",), handler=handle_recon),
    "compare-auth": WorkflowDispatchRule(
        required_params=("left_artifact_path", "right_artifact_path"),
        handler=handle_compare_auth,
    ),
    "mobile-review": WorkflowDispatchRule(required_params=("target_path",), handler=handle_mobile_review),
    "analyze": WorkflowDispatchRule(required_params=("goal",), handler=handle_analyze),
    "write-finding": WorkflowDispatchRule(
        required_params=("title", "host", "endpoint", "artifacts", "observations"),
        handler=handle_write_finding,
    ),
    "next-step": WorkflowDispatchRule(required_params=(), handler=handle_next_step),
    "sessions": WorkflowDispatchRule(required_params=(), handler=handle_sessions),
    "session-search": WorkflowDispatchRule(required_params=(), handler=handle_session_search),
    "session-show": WorkflowDispatchRule(required_params=("session_id",), handler=handle_session_show),
    "session-resume": WorkflowDispatchRule(required_params=("session_id",), handler=handle_session_resume),
    "doctor": WorkflowDispatchRule(required_params=(), handler=handle_doctor),
}


def run_named_workflow(command_name: str, params: dict[str, Any]) -> dict[str, Any]:
    command = get_command(command_name)
    reject_unknown_params(command_name, params)
    workflow = command.workflow
    if workflow not in WORKFLOW_DISPATCH_TABLE:
        raise typer.BadParameter(f"Unsupported workflow mapping: {workflow}")

    rule = WORKFLOW_DISPATCH_TABLE[workflow]
    missing = sorted(param for param in rule.required_params if param not in params)
    if missing:
        raise typer.BadParameter(f"{command_name} missing required args: {', '.join(missing)}")

    return {
        "run_manifest": build_run_manifest(command_name, params),
        "result": rule.handler(params),
    }


@app.command("registry")
def registry() -> None:
    emit(list_agents())


@app.command("commands")
def commands() -> None:
    emit({"commands": ecosystem_snapshot()["commands"]})


@app.command("ecosystem")
def ecosystem() -> None:
    emit(ecosystem_snapshot())


@app.command("doctor")
def doctor() -> None:
    emit(ecosystem_doctor())


@app.command("sessions")
def sessions() -> None:
    emit(list_runtime_sessions())


@app.command("session-search")
def session_search(
    query: str | None = typer.Option(None, help="Full-text query against stored session JSON."),
    workflow: str | None = typer.Option(None, help="Workflow filter."),
    status: str | None = typer.Option(None, help="Status filter."),
    agent: str | None = typer.Option(None, help="Agent filter."),
) -> None:
    emit(search_runtime_sessions(query=query, workflow=workflow, status=status, agent=agent))


@app.command("session-show")
def session_show(session_id: str = typer.Option(..., help="Runtime session ID to inspect.")) -> None:
    emit(get_runtime_session(session_id))


@app.command("session-resume")
def session_resume(session_id: str = typer.Option(..., help="Runtime session ID to resume.")) -> None:
    emit(handle_session_resume({"session_id": session_id}))


@app.command("slash")
def slash(
    command_name: str = typer.Argument(..., help="Slash-style command name, for example /observe-safe."),
    args: list[str] = typer.Argument(None, help="Command arguments as key=value pairs."),
) -> None:
    emit(run_named_workflow(command_name, parse_key_value_args(args or [])))


@app.command("route")
def route(
    goal: str = typer.Option("", help="Operator goal or task summary."),
    url: str | None = typer.Option(None, help="Candidate target URL for observation workflows."),
    method: str = typer.Option("GET", help="Candidate method for scope planning."),
    artifact_path: str | None = typer.Option(None, help="Normalized artifact path for recon workflows."),
    left_artifact_path: str | None = typer.Option(None, help="Left normalized artifact path for comparison workflows."),
    right_artifact_path: str | None = typer.Option(None, help="Right normalized artifact path for comparison workflows."),
    finding_title: str | None = typer.Option(None, help="Finding title when you want evidence-writer routing."),
    target_path: str | None = typer.Option(None, help="Local mobile artifact directory for mobile review routing."),
) -> None:
    emit(
        route_workflow(
            goal=goal or None,
            url=url,
            method=method,
            artifact_path=artifact_path,
            left_artifact_path=left_artifact_path,
            right_artifact_path=right_artifact_path,
            finding_title=finding_title,
            target_path=target_path,
        )
    )


@app.command("analyze")
def analyze(
    goal: str = typer.Option(..., help="Natural-language analysis goal."),
    url: str | None = typer.Option(None, help="Optional target URL."),
    method: str = typer.Option("GET", help="Method to use when URL analysis is needed."),
    artifact_path: str | None = typer.Option(None, help="Optional normalized artifact path."),
    left_artifact_path: str | None = typer.Option(None, help="Optional left artifact path for comparison."),
    right_artifact_path: str | None = typer.Option(None, help="Optional right artifact path for comparison."),
    target_path: str | None = typer.Option(None, help="Optional local mobile artifact path."),
    rules_path: str | None = typer.Option(None, help="Optional YARA rules path for mobile review."),
) -> None:
    emit(
        run_autonomous_analysis(
            goal=goal,
            url=url,
            method=method,
            artifact_path=artifact_path,
            left_artifact_path=left_artifact_path,
            right_artifact_path=right_artifact_path,
            target_path=target_path,
            rules_path=rules_path,
        )
    )


@app.command("observe")
def observe(
    url: str = typer.Option(..., help="Authorized URL to validate and optionally observe."),
    method: str = typer.Option("GET", help="Allowed method: GET, HEAD, or OPTIONS."),
    headers: str | None = typer.Option(None, help="Optional JSON object of request headers."),
    execute: bool = typer.Option(True, "--execute/--plan-only", help="Run the observation after scope validation or only return the plan."),
) -> None:
    parsed_headers = json.loads(headers) if headers else None
    emit(run_observe(url=url, method=method, headers=parsed_headers, execute=execute))


@app.command("recon")
def recon(artifact_path: str = typer.Option(..., help="Normalized artifact path to summarize.")) -> None:
    emit(run_recon(artifact_path=artifact_path))


@app.command("compare-auth")
def compare_auth(
    left_artifact_path: str = typer.Option(..., help="Left normalized artifact path."),
    right_artifact_path: str = typer.Option(..., help="Right normalized artifact path."),
) -> None:
    emit(run_compare_auth(left_artifact_path=left_artifact_path, right_artifact_path=right_artifact_path))


@app.command("mobile-review")
def mobile_review(
    target_path: str = typer.Option(..., help="Local file or directory to review."),
    rules_path: str | None = typer.Option(None, help="Optional YARA rules file path."),
) -> None:
    emit(run_mobile_review(target_path=target_path, rules_path=rules_path))


@app.command("write-finding")
def write_finding(
    title: str = typer.Option(..., help="Finding title."),
    host: str = typer.Option(..., help="Host recorded in the finding scope."),
    endpoint: str = typer.Option(..., help="Endpoint path recorded in the finding scope."),
    method: str = typer.Option("GET", help="Method recorded in the finding scope."),
    auth_context: str = typer.Option("unknown", help="Observed auth context."),
    classification: str = typer.Option("suspected", help="confirmed, suspected, or rejected."),
    artifacts: str = typer.Option("[]", help="JSON array of artifact paths."),
    observations: str = typer.Option("[]", help="JSON array of evidence observations."),
    limitations: str = typer.Option("[]", help="JSON array of limitations."),
    remediation_notes: str = typer.Option("[]", help="JSON array of remediation notes."),
    relative_output_path: str | None = typer.Option(None, help="Optional relative findings path."),
) -> None:
    emit(
        run_write_finding(
            title=title,
            host=host,
            endpoint=endpoint,
            method=method,
            auth_context=auth_context,
            classification=classification,
            artifacts=json.loads(artifacts),
            observations=json.loads(observations),
            limitations=json.loads(limitations),
            remediation_notes=json.loads(remediation_notes),
            relative_output_path=relative_output_path,
        )
    )


@app.command("next-step")
def next_step_command() -> None:
    emit(next_step())


def main() -> None:
    app()


if __name__ == "__main__":
    main()
