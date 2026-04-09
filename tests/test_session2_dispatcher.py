from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import agent_cli, agent_runtime


class Session2DispatcherTests(unittest.TestCase):
    def test_run_manifest_is_deterministic(self) -> None:
        manifest_a = agent_cli.build_run_manifest(
            "/observe-safe",
            {"method": "GET", "url": "https://example.local/", "execute": False},
        )
        manifest_b = agent_cli.build_run_manifest(
            "/observe-safe",
            {"url": "https://example.local/", "execute": False, "method": "GET"},
        )

        self.assertEqual(manifest_a, manifest_b)
        self.assertEqual(manifest_a["schema_version"], agent_cli.RUN_MANIFEST_SCHEMA_VERSION)

    def test_run_named_workflow_uses_dispatch_table(self) -> None:
        with patch("tools.agent_cli.handle_doctor", return_value={"status": "ok"}) as mock_handler:
            original_rule = agent_cli.WORKFLOW_DISPATCH_TABLE["doctor"]
            agent_cli.WORKFLOW_DISPATCH_TABLE["doctor"] = agent_cli.WorkflowDispatchRule((), mock_handler)
            try:
                result = agent_cli.run_named_workflow("/doctor", {})
            finally:
                agent_cli.WORKFLOW_DISPATCH_TABLE["doctor"] = original_rule

        self.assertEqual(result["run_manifest"]["workflow"], "doctor")
        self.assertEqual(result["result"], {"status": "ok"})
        mock_handler.assert_called_once_with({})

    def test_run_named_workflow_rejects_unknown_mapping(self) -> None:
        with patch("tools.agent_cli.get_command") as mock_get_command:
            mock_get_command.return_value = type(
                "Command",
                (),
                {"name": "/bad", "workflow": "missing-workflow", "agent": "sec-orchestrator", "passthrough_args": []},
            )()
            with self.assertRaisesRegex(Exception, "Unsupported workflow mapping"):
                agent_cli.run_named_workflow("/bad", {})

    def test_route_workflow_uses_declarative_rule_order(self) -> None:
        result = agent_runtime.route_workflow(
            url="https://example.local/",
            method="GET",
            artifact_path="evidence/normalized/example.json",
        )

        self.assertEqual(result["workflow"], "recon")
        self.assertEqual(result["next_action"]["tool"], "schema_extract")


if __name__ == "__main__":
    unittest.main()
