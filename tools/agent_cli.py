from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.ecosystem import ecosystem_doctor, ecosystem_snapshot, get_command, get_runtime_session, list_runtime_sessions
from tools.agent_runtime import (
    list_agents,
    next_step,
    route_workflow,
    run_compare_auth,
    run_mobile_review,
    run_observe,
    run_recon,
    run_write_finding,
)

app = typer.Typer(add_completion=False, help="Run the Black-Spyder executable agent workflows.")


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


def run_named_workflow(command_name: str, params: dict[str, Any]) -> dict[str, Any]:
    command = get_command(command_name)
    reject_unknown_params(command_name, params)
    workflow = command.workflow
    if workflow == "registry":
        return list_agents()
    if workflow == "commands":
        return {"commands": ecosystem_snapshot()["commands"]}
    if workflow == "ecosystem":
        return ecosystem_snapshot()
    if workflow == "observe":
        if "url" not in params:
            raise typer.BadParameter("/observe-safe requires url=<value>")
        return run_observe(
            url=str(params["url"]),
            method=str(params.get("method", "GET")),
            headers=require_dict_param(params, "headers"),
            execute=require_bool_param(params, "execute", True),
        )
    if workflow == "recon":
        if "artifact_path" not in params:
            raise typer.BadParameter("/recon requires artifact_path=<value>")
        return run_recon(artifact_path=str(params["artifact_path"]))
    if workflow == "compare-auth":
        if "left_artifact_path" not in params or "right_artifact_path" not in params:
            raise typer.BadParameter("/compare-auth requires left_artifact_path=<value> and right_artifact_path=<value>")
        return run_compare_auth(
            left_artifact_path=str(params["left_artifact_path"]),
            right_artifact_path=str(params["right_artifact_path"]),
        )
    if workflow == "mobile-review":
        if "target_path" not in params:
            raise typer.BadParameter("/mobile-review requires target_path=<value>")
        rules_path = params.get("rules_path")
        return run_mobile_review(
            target_path=str(params["target_path"]),
            rules_path=str(rules_path) if rules_path is not None else None,
        )
    if workflow == "write-finding":
        required = {"title", "host", "endpoint", "artifacts", "observations"}
        missing = sorted(required - params.keys())
        if missing:
            raise typer.BadParameter(f"/write-finding missing required args: {', '.join(missing)}")
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
    if workflow == "next-step":
        return next_step()
    if workflow == "sessions":
        return list_runtime_sessions()
    if workflow == "session-show":
        if "session_id" not in params:
            raise typer.BadParameter("/session-show requires session_id=<value>")
        return get_runtime_session(str(params["session_id"]))
    if workflow == "doctor":
        return ecosystem_doctor()
    raise typer.BadParameter(f"Unsupported workflow mapping: {workflow}")


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


@app.command("session-show")
def session_show(session_id: str = typer.Option(..., help="Runtime session ID to inspect.")) -> None:
    emit(get_runtime_session(session_id))


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
