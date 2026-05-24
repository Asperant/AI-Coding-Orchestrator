from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli


class CliProjectContextTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        self.fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": [str(self.project_root)],
        }
        self.fake_core_status = {
            "checked_count": 4,
            "found_count": 4,
            "missing_count": 0,
            "missing_files": {},
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def create_project_file(self, relative_path: str) -> None:
        file_path = self.project_root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("content", encoding="utf-8")

    def test_default_cli_still_does_not_run_project_context_check(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run([])

        output = stdout.getvalue()

        self.assertIn("Project context check: not run by default", output)
        self.assertNotIn("Project working directory:", output)

    def test_project_flag_runs_project_context_check(self) -> None:
        self.create_project_file("AGENTS.md")
        self.create_project_file("docs/product-context.md")
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--project", str(self.project_root)])

        output = stdout.getvalue()

        self.assertIn(f"Project working directory: {self.project_root.resolve()}", output)
        self.assertIn("Found AI-ready files count: 2", output)
        self.assertIn("Missing AI-ready files count: 5", output)
        self.assertIn("Found AI-ready files: AGENTS.md, docs/product-context.md", output)

    def test_missing_project_path_gives_clear_error(self) -> None:
        missing_project = self.project_root / "missing-project"

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with self.assertRaisesRegex(
                    SystemExit,
                    "Project context error: Working directory does not exist:",
                ):
                    cli.run(["--project", str(missing_project)])

    def test_file_instead_of_directory_gives_clear_error(self) -> None:
        file_path = self.project_root / "project.txt"
        file_path.write_text("content", encoding="utf-8")

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with self.assertRaisesRegex(
                    SystemExit,
                    "Project context error: Working directory is not a directory:",
                ):
                    cli.run(["--project", str(file_path)])

    def test_project_outside_approved_paths_is_rejected_before_context_check(self) -> None:
        outside_root = self.project_root.parent / "outside-project"
        outside_root.mkdir(exist_ok=True)

        with patch.object(cli, "inspect_project_context") as mocked_context:
            with self.assertRaisesRegex(
                SystemExit,
                "Approved path error: Target path is outside approved paths:",
            ):
                cli.run(["--project", str(outside_root)])

        mocked_context.assert_not_called()
