from __future__ import annotations

import json
from collections.abc import Mapping

import typer

from tools.ecosystem import ecosystem_doctor, ecosystem_snapshot
from tools.opencode_bridge import (
    BRIDGE_HOST,
    BRIDGE_PORT,
    BridgeReuseError,
    HostRegistrationRequest,
    connect_host,
    ensure_bridge_available,
    main as bridge_main,
)
from tools.agent_runtime import run_autonomous_analysis, run_conversational_analysis

app = typer.Typer(add_completion=False, help="Simplified Black-Spyder entrypoint.")
opencode_app = typer.Typer(add_completion=False, help="OpenCode-oriented shortcuts.")


def emit(data: Mapping[str, object]) -> None:
    typer.echo(json.dumps(data, indent=2))


@app.command("doctor")
def doctor() -> None:
    emit(ecosystem_doctor())


@app.command("analyze")
def analyze(
    goal: str = typer.Option(..., help="Natural-language analysis goal."),
    url: str | None = typer.Option(None, help="Optional target URL."),
    artifact_path: str | None = typer.Option(None, help="Optional normalized artifact path."),
    target_path: str | None = typer.Option(None, help="Optional local artifact directory."),
) -> None:
    emit(
        run_autonomous_analysis(
            goal=goal,
            url=url,
            artifact_path=artifact_path,
            target_path=target_path,
        )
    )


@app.command("converse")
def converse(goal: str = typer.Option(..., help="Conversational natural-language request.")) -> None:
    emit(run_conversational_analysis(goal=goal))


@app.command("up")
def up(dry_run: bool = typer.Option(False, "--dry-run", help="Show the bridge target without starting it.")) -> None:
    bridge_url = f"http://{BRIDGE_HOST}:{BRIDGE_PORT}"
    summary = {
        "status": "ready" if dry_run else "starting",
        "bridge_url": bridge_url,
        "command_count": len(ecosystem_snapshot()["commands"]),
    }
    if dry_run:
        emit(summary)
        return
    try:
        bridge_status = ensure_bridge_available()
    except BridgeReuseError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    summary.update(bridge_status)
    typer.echo(json.dumps(summary, indent=2))
    if bridge_status["reused_existing_bridge"]:
        return
    bridge_main()


@opencode_app.command("up")
def opencode_up(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the OpenCode connection state without starting the bridge."),
    host_name: str = typer.Option("opencode-host", help="Host name to record for the connection."),
    host_version: str = typer.Option("1.0", help="Host version to record for the connection."),
) -> None:
    bridge_url = f"http://{BRIDGE_HOST}:{BRIDGE_PORT}"
    connected = connect_host(
        HostRegistrationRequest(
            host_name=host_name,
            host_version=host_version,
            capabilities=["registry", "execute"],
        )
    )
    summary = {
        "status": connected["status"],
        "open_code_primary": True,
        "bridge_url": bridge_url,
        "host": connected["host"],
        "command_count": len(connected["registry"]["ecosystem"]["commands"]),
        "next_step": "POST /converse first for conversation-style prompts; use /analyze for already structured analysis and /execute only for low-level commands.",
        "default_preset": connected["registry"]["default_preset"],
    }
    if dry_run:
        emit(summary)
        return
    try:
        bridge_status = ensure_bridge_available()
    except BridgeReuseError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    summary.update(bridge_status)
    typer.echo(json.dumps(summary, indent=2))
    if bridge_status["reused_existing_bridge"]:
        return
    bridge_main()


app.add_typer(opencode_app, name="opencode")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
