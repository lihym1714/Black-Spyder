from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import agent_cli, ecosystem


class Session3Tests(unittest.TestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runtime_state_path = Path(".")
        self.original_runtime_state_path = ecosystem.RUNTIME_STATE_PATH

    def setUp(self) -> None:
        self.temp_dir.cleanup()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runtime_state_path = Path(self.temp_dir.name) / "runtime_state.json"
        ecosystem.RUNTIME_STATE_PATH = self.runtime_state_path

    def tearDown(self) -> None:
        ecosystem.RUNTIME_STATE_PATH = self.original_runtime_state_path
        self.temp_dir.cleanup()

    def write_runtime_state(self, payload: dict[str, object]) -> None:
        self.runtime_state_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_session_search_filters_sessions(self) -> None:
        self.write_runtime_state(
            {
                "sessions": [
                    {
                        "session_id": "session-a",
                        "workflow": "observe",
                        "agent": "sec-orchestrator",
                        "status": "completed",
                        "updated_at": "2026-04-09T00:00:00+00:00",
                        "inputs": {"url": "https://loaflex.com/"},
                    },
                    {
                        "session_id": "session-b",
                        "workflow": "recon",
                        "agent": "recon-reader",
                        "status": "completed",
                        "updated_at": "2026-04-09T00:01:00+00:00",
                        "inputs": {"artifact_path": "evidence/normalized/example.json"},
                    },
                ]
            }
        )

        result = ecosystem.search_runtime_sessions(workflow="observe")

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["sessions"][0]["session_id"], "session-a")

    def test_session_resume_uses_saved_run_manifest(self) -> None:
        self.write_runtime_state(
            {
                "sessions": [
                    {
                        "session_id": "session-a",
                        "workflow": "doctor",
                        "agent": "sec-orchestrator",
                        "status": "completed",
                        "updated_at": "2026-04-09T00:00:00+00:00",
                        "inputs": {},
                        "run_manifest": {
                            "schema_version": ecosystem.RUN_MANIFEST_SCHEMA_VERSION,
                            "workflow": "doctor",
                            "agent": "sec-orchestrator",
                            "params": {},
                        },
                    }
                ]
            }
        )

        result = agent_cli.handle_session_resume({"session_id": "session-a"})

        self.assertEqual(result["resumed_from_session_id"], "session-a")
        self.assertEqual(result["run_manifest"]["workflow"], "doctor")
        self.assertIn("result", result)

    def test_session_search_handles_corrupted_state(self) -> None:
        self.runtime_state_path.write_text("{not-json", encoding="utf-8")

        result = ecosystem.search_runtime_sessions()

        self.assertEqual(result, {"count": 0, "sessions": []})

    def test_session_resume_rejects_missing_session(self) -> None:
        self.write_runtime_state({"sessions": []})

        with self.assertRaises(KeyError):
            agent_cli.handle_session_resume({"session_id": "missing"})


if __name__ == "__main__":
    unittest.main()
