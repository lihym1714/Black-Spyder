from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from tools.opencode_bridge import BridgeReuseError
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
            "registry": {"ecosystem": {"commands": [{"name": "/doctor"}]}, "default_preset": {"name": "opencode-conversation-first"}},
        },
    )
    def test_opencode_up_dry_run_reports_simple_summary(self, mock_connect) -> None:
        result = self.runner.invoke(app, ["opencode", "up", "--dry-run"])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "connected")
        self.assertEqual(payload["command_count"], 1)
        self.assertIn("/analyze", payload["next_step"])
        self.assertTrue(payload["open_code_primary"])

    @patch(
        "tools.simple_entry.connect_host",
        return_value={
            "status": "connected",
            "host": {"host_name": "opencode-host"},
            "registry": {
                "ecosystem": {"commands": [{"name": "/doctor"}, {"name": "/analyze"}]},
                "routes": {"analyze": "/analyze"},
                "default_preset": {"name": "opencode-conversation-first"},
            },
        },
    )
    def test_opencode_up_mentions_execute_next_step(self, mock_connect) -> None:
        result = self.runner.invoke(app, ["opencode", "up", "--dry-run"])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)
        self.assertIn("next_step", payload)

    @patch(
        "tools.simple_entry.connect_host",
        return_value={
            "status": "connected",
            "host": {"host_name": "opencode-host"},
            "registry": {"ecosystem": {"commands": [{"name": "/doctor"}]}, "default_preset": {"name": "opencode-conversation-first"}},
        },
    )
    @patch(
        "tools.simple_entry.ensure_bridge_available",
        return_value={
            "status": "reusing_existing_bridge",
            "bridge_url": "http://127.0.0.1:8787",
            "reused_existing_bridge": True,
        },
    )
    @patch("tools.simple_entry.bridge_main")
    def test_opencode_up_reuses_existing_bridge_without_starting_server(
        self,
        mock_bridge_main,
        mock_ensure_bridge_available,
        mock_connect,
    ) -> None:
        result = self.runner.invoke(app, ["opencode", "up"])

        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "reusing_existing_bridge")
        self.assertTrue(payload["reused_existing_bridge"])
        mock_bridge_main.assert_not_called()

    @patch(
        "tools.simple_entry.connect_host",
        return_value={
            "status": "connected",
            "host": {"host_name": "opencode-host"},
            "registry": {"ecosystem": {"commands": [{"name": "/doctor"}]}, "default_preset": {"name": "opencode-conversation-first"}},
        },
    )
    @patch(
        "tools.simple_entry.ensure_bridge_available",
        side_effect=BridgeReuseError("Port 8787 is already in use by a non-Black-Spyder service; cannot start the OpenCode bridge."),
    )
    @patch("tools.simple_entry.bridge_main")
    def test_opencode_up_reports_clear_error_for_non_bridge_port_owner(
        self,
        mock_bridge_main,
        mock_ensure_bridge_available,
        mock_connect,
    ) -> None:
        result = self.runner.invoke(app, ["opencode", "up"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Port 8787 is already in use", result.stderr)
        mock_bridge_main.assert_not_called()

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
