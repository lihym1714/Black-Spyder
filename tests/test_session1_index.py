from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tools import ecosystem


class Session1IndexTests(unittest.TestCase):
    def __init__(self, methodName: str = "runTest") -> None:
        super().__init__(methodName)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(".")
        self.agents_dir = Path(".")
        self.commands_dir = Path(".")
        self.state_dir = Path(".")
        self.original_agents_dir = ecosystem.AGENTS_DIR
        self.original_commands_dir = ecosystem.COMMANDS_DIR
        self.original_index_path = ecosystem.ECOSYSTEM_INDEX_PATH

    def setUp(self) -> None:
        self.temp_dir.cleanup()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.agents_dir = self.root / "agents"
        self.commands_dir = self.root / "commands"
        self.state_dir = self.root / "state"
        self.agents_dir.mkdir(parents=True)
        self.commands_dir.mkdir(parents=True)
        self.state_dir.mkdir(parents=True)

        fixtures_root = Path(__file__).resolve().parents[1]
        for source in sorted((fixtures_root / "agents").glob("*.md")):
            if source.name.endswith(".ko.md"):
                continue
            shutil.copy2(source, self.agents_dir / source.name)
        for source in sorted((fixtures_root / "commands").glob("*.md")):
            shutil.copy2(source, self.commands_dir / source.name)

        self.original_agents_dir = ecosystem.AGENTS_DIR
        self.original_commands_dir = ecosystem.COMMANDS_DIR
        self.original_index_path = ecosystem.ECOSYSTEM_INDEX_PATH

        ecosystem.AGENTS_DIR = self.agents_dir
        ecosystem.COMMANDS_DIR = self.commands_dir
        ecosystem.ECOSYSTEM_INDEX_PATH = self.state_dir / "ecosystem-index-v1.json"

    def tearDown(self) -> None:
        ecosystem.AGENTS_DIR = self.original_agents_dir
        ecosystem.COMMANDS_DIR = self.original_commands_dir
        ecosystem.ECOSYSTEM_INDEX_PATH = self.original_index_path
        self.temp_dir.cleanup()

    def test_session1_index_deterministic_generation(self) -> None:
        first = ecosystem.build_ecosystem_index()
        second = ecosystem.build_ecosystem_index()

        self.assertEqual(first["schema_version"], ecosystem.ECOSYSTEM_INDEX_SCHEMA_VERSION)
        self.assertEqual(first["source_digest"], second["source_digest"])
        self.assertEqual(first["source_files"], second["source_files"])
        self.assertEqual(first["agents"], second["agents"])
        self.assertEqual(first["commands"], second["commands"])

    def test_session1_index_cache_invalidation(self) -> None:
        first = ecosystem.load_ecosystem_index()
        command_file = self.commands_dir / "agents.md"
        command_file.write_text(
            command_file.read_text(encoding="utf-8").replace(
                "List the available Black-Spyder agents and their workflows.",
                "List the available Black-Spyder agents and workflow metadata.",
            ),
            encoding="utf-8",
        )

        second = ecosystem.load_ecosystem_index()

        self.assertNotEqual(first["source_digest"], second["source_digest"])
        self.assertTrue(
            any(
                entry["summary"] == "List the available Black-Spyder agents and workflow metadata."
                for entry in second["commands"]
            )
        )

    def test_session1_index_atomic_write(self) -> None:
        index_path = ecosystem.ECOSYSTEM_INDEX_PATH
        ecosystem.load_ecosystem_index()

        self.assertTrue(index_path.exists())
        self.assertFalse(any(index_path.parent.glob("tmp*")))
        payload = ecosystem.load_cached_ecosystem_index()
        self.assertIsNotNone(payload)
        payload_data = payload if payload is not None else {}
        self.assertEqual(payload_data["schema_version"], ecosystem.ECOSYSTEM_INDEX_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
