from pathlib import Path
import sys
from unittest import TestCase
from unittest.mock import patch

import main


class PackagingSmokeTests(TestCase):
    def test_pyproject_exposes_orchestrator_console_script(self) -> None:
        pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        pyproject_text = pyproject_path.read_text(encoding="utf-8")

        self.assertIn("[project.scripts]", pyproject_text)
        self.assertIn('orchestrator = "main:main"', pyproject_text)

    def test_main_entrypoint_forwards_cli_arguments(self) -> None:
        test_argv = ["orchestrator", "--run-orchestrator", "--mode", "status"]

        with patch.object(sys, "argv", test_argv):
            with patch.object(main, "run") as mocked_run:
                main.main()

        mocked_run.assert_called_once_with(["--run-orchestrator", "--mode", "status"])
