from __future__ import annotations

import shutil
import unittest
import zipfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

from mcp import apk_decompile, mobile_dynamic_verify
from tools import bootstrap
from tools import agent_runtime


class MobileWorkflowTests(unittest.TestCase):
    project_root: Path = Path(".")
    artifacts_dir: Path = Path(".")
    apk_path: Path = Path(".")
    created_paths: list[Path] = []

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]
        self.artifacts_dir = self.project_root / "artifacts" / "test-mobile"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.apk_path = self.artifacts_dir / "sample.apk"
        with zipfile.ZipFile(self.apk_path, "w") as archive:
            archive.writestr("AndroidManifest.xml", "<manifest package='com.example.sample' />")
            archive.writestr("classes.dex", b"dex\n035\x00")
            archive.writestr("res/raw/config.txt", "https://example.local/api")
        self.created_paths: list[Path] = [self.apk_path]

    def tearDown(self) -> None:
        for path in sorted(self.created_paths, reverse=True):
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
        shutil.rmtree(self.artifacts_dir, ignore_errors=True)

    def _track_result_paths(self, result: dict[str, object]) -> None:
        artifact_paths = result.get("artifact_paths", {})
        if isinstance(artifact_paths, dict):
            for rel_path in artifact_paths.values():
                if isinstance(rel_path, str):
                    self.created_paths.append(self.project_root / rel_path)
        decompiled_outputs = result.get("decompiled_outputs", {})
        if isinstance(decompiled_outputs, dict):
            for rel_path in decompiled_outputs.values():
                if isinstance(rel_path, str):
                    self.created_paths.append(self.project_root / rel_path)

    @patch("mcp.apk_decompile.shutil.which", return_value=None)
    def test_run_apk_decompile_writes_evidence_without_optional_tools(self, mock_which: Any) -> None:
        result = apk_decompile.run_apk_decompile("artifacts/test-mobile/sample.apk")
        self._track_result_paths(result)

        self.assertEqual(result["archive_summary"]["contains_android_manifest"], True)
        self.assertIn("raw", result["artifact_paths"])
        self.assertIn("normalized", result["artifact_paths"])
        self.assertEqual(result["decompiled_outputs"], {})
        self.assertTrue(any("jadx" in item for item in result["limitations"]))

    def test_route_workflow_prefers_mobile_decompile_when_apk_path_is_present(self) -> None:
        result = agent_runtime.route_workflow(apk_path="artifacts/test-mobile/sample.apk")

        self.assertEqual(result["workflow"], "mobile-decompile")
        self.assertEqual(result["next_action"]["tool"], "apk_decompile")

    @patch("mcp.mobile_dynamic_verify.shutil.which", return_value=None)
    def test_run_mobile_dynamic_verify_returns_artifacts_when_adb_missing(self, mock_which: Any) -> None:
        result = mobile_dynamic_verify.run_mobile_dynamic_verify("com.example.sample")
        self._track_result_paths(result)

        self.assertEqual(result["available"], False)
        self.assertIn("raw", result["artifact_paths"])
        self.assertIn("normalized", result["artifact_paths"])
        self.assertTrue(any("adb" in item.lower() for item in result["limitations"]))

    @patch("tools.agent_runtime.run_mobile_dynamic_verify")
    def test_run_mobile_verify_records_runtime_artifacts(self, mock_run_mobile_dynamic_verify: Any) -> None:
        temp_raw = self.project_root / "evidence" / "raw" / "fake-mobile-verify.json"
        temp_normalized = self.project_root / "evidence" / "normalized" / "fake-mobile-verify.json"
        self.created_paths.extend([temp_raw, temp_normalized])
        mock_run_mobile_dynamic_verify.return_value = {
            "selected_device": "emulator-5554",
            "installed": True,
            "runtime_state": {"pid": "1234"},
            "device_profile": {"model": "sdk_gphone64"},
            "artifact_paths": {
                "raw": "evidence/raw/fake-mobile-verify.json",
                "normalized": "evidence/normalized/fake-mobile-verify.json",
            },
            "limitations": [],
        }

        result = agent_runtime.run_mobile_verify("com.example.sample")

        self.assertEqual(result["agent"], "mobile-dynamic-verifier")
        self.assertEqual(result["installed"], True)
        self.assertEqual(len(result["artifacts"]), 2)

    def test_attempt_install_returns_none_for_unsupported_linux_optional_tool(self) -> None:
        result = bootstrap.attempt_install("aapt", "Linux")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
