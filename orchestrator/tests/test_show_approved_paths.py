from contextlib import redirect_stdout
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

import cli


class ShowApprovedPathsCliTests(TestCase):
    def setUp(self) -> None:
        self.fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": ["/tmp/ai-brain", "/tmp/project-a"],
        }

    def test_show_approved_paths_prints_count(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run(["--show-approved-paths"])

        output = stdout.getvalue()

        self.assertIn("Configured approved paths count: 2", output)

    def test_show_approved_paths_lists_configured_paths(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run(["--show-approved-paths"])

        output = stdout.getvalue()

        self.assertIn("Configured approved paths: /tmp/ai-brain, /tmp/project-a", output)

    def test_show_approved_paths_does_not_require_project(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run(["--show-approved-paths"])

        output = stdout.getvalue()

        self.assertIn("AI Coding Orchestrator skeleton ready.", output)
        self.assertNotIn("Project working directory:", output)

    def test_show_approved_paths_does_not_run_project_context_or_git_behavior(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files") as mocked_core:
                with patch.object(cli, "inspect_project_context") as mocked_context:
                    with patch.object(cli, "inspect_git_state") as mocked_git:
                        with redirect_stdout(stdout):
                            cli.run(["--show-approved-paths"])

        mocked_core.assert_not_called()
        mocked_context.assert_not_called()
        mocked_git.assert_not_called()
