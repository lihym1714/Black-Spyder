from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from tools import opencode_bridge


class OpenCodeBridgeTests(unittest.TestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.bridge_state_path = Path(".")
        self.bridge_manifest_path = Path(".")
        self.original_bridge_state_path = opencode_bridge.BRIDGE_STATE_PATH
        self.original_bridge_manifest_path = opencode_bridge.BRIDGE_MANIFEST_PATH
        self.client = TestClient(opencode_bridge.app)

    def setUp(self) -> None:
        self.temp_dir.cleanup()
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_root = Path(self.temp_dir.name)
        self.bridge_state_path = temp_root / "bridge_state.json"
        self.bridge_manifest_path = temp_root / "bridge_manifest.json"
        opencode_bridge.BRIDGE_STATE_PATH = self.bridge_state_path
        opencode_bridge.BRIDGE_MANIFEST_PATH = self.bridge_manifest_path
        self.client = TestClient(opencode_bridge.app)

    def tearDown(self) -> None:
        opencode_bridge.BRIDGE_STATE_PATH = self.original_bridge_state_path
        opencode_bridge.BRIDGE_MANIFEST_PATH = self.original_bridge_manifest_path
        self.temp_dir.cleanup()

    def test_registry_returns_machine_readable_manifest(self) -> None:
        response = self.client.get("/registry")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["bridge_name"], "black-spyder-opencode-bridge")
        self.assertIn("ecosystem", payload)
        self.assertTrue(self.bridge_manifest_path.exists())

    def test_register_host_persists_host_record(self) -> None:
        response = self.client.post(
            "/register-host",
            json={"host_name": "opencode-host", "host_version": "1.0.0", "capabilities": ["registry", "execute"]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "registered")
        state = opencode_bridge.load_bridge_state()
        self.assertEqual(len(state["hosts"]), 1)

    @patch("tools.opencode_bridge.run_named_workflow", return_value={"result": {"status": "ok"}})
    def test_execute_routes_command_and_records_execution(self, mock_run_named_workflow) -> None:
        response = self.client.post(
            "/execute",
            json={"command_name": "/doctor", "params": {}},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        mock_run_named_workflow.assert_called_once_with("/doctor", {})
        self.assertEqual(len(opencode_bridge.load_bridge_state()["executions"]), 1)


if __name__ == "__main__":
    unittest.main()
