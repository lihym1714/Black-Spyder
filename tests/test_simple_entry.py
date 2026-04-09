from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from tools.simple_entry import app


class SimpleEntryTests(unittest.TestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.runner = CliRunner()

    def setUp(self) -> None:
        self.runner = CliRunner()

    @patch("tools.simple_entry.ecosystem_snapshot", return_value={"commands": [{"name": "/doctor"}, {"name": "/observe-safe"}]})
    def test_up_dry_run_reports_bridge_summary(self, mock_snapshot) -> None:
        result = self.runner.invoke(app, ["up", "--dry-run"])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ready")
        self.assertIn("bridge_url", payload)

    @patch(
        "tools.simple_entry.connect_host",
        return_value={
            "status": "connected",
            "host": {"host_name": "opencode-host"},
            "registry": {"ecosystem": {"commands": [{"name": "/doctor"}]}},
        },
    )
    def test_opencode_up_dry_run_reports_simple_summary(self, mock_connect) -> None:
        result = self.runner.invoke(app, ["opencode", "up", "--dry-run"])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "connected")
        self.assertEqual(payload["command_count"], 1)
        self.assertIn("/analyze", payload["next_step"])

    @patch(
        "tools.simple_entry.connect_host",
        return_value={
            "status": "connected",
            "host": {"host_name": "opencode-host"},
            "registry": {"ecosystem": {"commands": [{"name": "/doctor"}, {"name": "/analyze"}]}, "routes": {"analyze": "/analyze"}},
        },
    )
    def test_opencode_up_mentions_execute_next_step(self, mock_connect) -> None:
        result = self.runner.invoke(app, ["opencode", "up", "--dry-run"])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)
        self.assertIn("next_step", payload)

    @patch(
        "tools.agent_runtime.run_autonomous_analysis",
        return_value={"executed": True, "route": {"workflow": "observe"}, "result": {"phase": "plan"}},
    )
    def test_analyze_command_uses_autonomous_analysis(self, mock_analyze) -> None:
        result = self.runner.invoke(app, ["analyze", "--goal", "Review this target", "--url", "http://localhost:8000/health"])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["executed"])

    @patch(
        "tools.simple_entry.run_conversational_analysis",
        return_value={"analysis_mode": "conversation", "needs_clarification": True},
    )
    def test_converse_command_uses_conversation_layer(self, mock_converse) -> None:
        result = self.runner.invoke(app, ["converse", "--goal", "apk 분석해줘"])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["needs_clarification"])


if __name__ == "__main__":
    unittest.main()
