from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools import bootstrap


class Session4BootstrapTests(unittest.TestCase):
    @patch("tools.bootstrap.install_dependencies")
    @patch("tools.bootstrap.ensure_directories")
    @patch("tools.bootstrap.ensure_venv", return_value=Path("/.venv/bin/python"))
    @patch("tools.bootstrap.ensure_prerequisites", return_value=("macOS", ["python3", "git", "curl", "pip"], []))
    @patch("tools.bootstrap.report_optional_tools")
    @patch("tools.bootstrap.ecosystem_snapshot", return_value={"agents": [], "commands": []})
    @patch(
        "tools.bootstrap.ecosystem_doctor",
        return_value={"status": "ok", "blocking_check_count": 0, "warning_check_count": 1},
    )
    def test_bootstrap_reports_doctor_status(
        self,
        mock_doctor,
        mock_snapshot,
        mock_optional_tools,
        mock_prereqs,
        mock_venv,
        mock_dirs,
        mock_install,
    ) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            bootstrap.bootstrap()

        rendered = output.getvalue()
        self.assertIn("Doctor status: ok", rendered)
        self.assertIn("Ecosystem index generated:", rendered)
        mock_snapshot.assert_called_once()
        mock_doctor.assert_called_once()

    @patch("tools.bootstrap.install_dependencies")
    @patch("tools.bootstrap.ensure_directories")
    @patch("tools.bootstrap.ensure_venv", return_value=Path("/.venv/bin/python"))
    @patch("tools.bootstrap.ensure_prerequisites", return_value=("macOS", ["python3", "git", "curl", "pip"], []))
    @patch("tools.bootstrap.report_optional_tools")
    @patch("tools.bootstrap.ecosystem_snapshot", return_value={"agents": [], "commands": []})
    @patch(
        "tools.bootstrap.ecosystem_doctor",
        return_value={"status": "error", "blocking_check_count": 1, "warning_check_count": 0},
    )
    def test_bootstrap_fails_on_blocking_doctor_issues(
        self,
        mock_doctor,
        mock_snapshot,
        mock_optional_tools,
        mock_prereqs,
        mock_venv,
        mock_dirs,
        mock_install,
    ) -> None:
        with self.assertRaisesRegex(RuntimeError, "Ecosystem doctor reported blocking issues"):
            bootstrap.bootstrap()


if __name__ == "__main__":
    unittest.main()
