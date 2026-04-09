from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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


@app.command("registry")
def registry() -> None:
    emit(list_agents())


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
