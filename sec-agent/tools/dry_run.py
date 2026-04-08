from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.table import Table

from mcp.common import load_scope_policy, utc_now_iso, write_json
from mcp.scope_guard import evaluate_scope


STATE_FILE = PROJECT_ROOT / "state" / "state.json"
SAMPLE_URL = "http://example.local/"
SAMPLE_METHOD = "GET"


def ensure_state_file() -> None:
    if STATE_FILE.exists():
        return
    state = {
        "created_at": utc_now_iso(),
        "current_target": None,
        "observations": [],
        "hypotheses": [],
        "findings": [],
    }
    write_json(STATE_FILE, state)


def main() -> None:
    console = Console()
    policy = load_scope_policy()
    ensure_state_file()

    table = Table(title="sec-agent dry run")
    table.add_column("Setting")
    table.add_column("Value")
    table.add_row("Allowed hosts", ", ".join(policy["allowed_hosts"]))
    table.add_row("Allowed methods", ", ".join(policy["allowed_methods"]))
    table.add_row("Approval-required methods", ", ".join(policy["approval_required_methods"]))
    table.add_row("Request timeout", str(policy["request_timeout_seconds"]))
    table.add_row("State file", str(STATE_FILE))
    console.print(table)

    result = evaluate_scope(SAMPLE_URL, SAMPLE_METHOD, policy)
    console.print("\nScope guard sample result:")
    console.print_json(data=result)

    if result["allowed"]:
        console.print("\nEnvironment ready. Next recommended safe action:")
        console.print_json(
            data={
                "next_action": "Run a single observational GET request with mcp/http_probe.py against an explicitly authorized local endpoint.",
                "sample_command": "python mcp/http_probe.py --url http://localhost:8000/health --method GET",
            }
        )
    else:
        console.print("\nEnvironment not ready for live observation until policy and sample target align.")


if __name__ == "__main__":
    main()
