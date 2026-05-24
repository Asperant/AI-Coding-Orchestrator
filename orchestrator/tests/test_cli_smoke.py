from contextlib import redirect_stdout
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

import cli


class CliSmokeTests(TestCase):
    def test_run_prints_startup_status_summary(self) -> None:
        fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": ["/tmp/ai-brain", "reports"],
        }
        fake_core_status = {
            "checked_count": 4,
            "found_count": 3,
            "missing_count": 1,
            "missing_files": {"readme_for_ai": "/tmp/ai-brain/README-FOR-AI.md"},
        }
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=fake_core_status):
                with redirect_stdout(stdout):
                    cli.run()

        output = stdout.getvalue()

        self.assertIn("AI Coding Orchestrator skeleton ready.", output)
        self.assertIn("AI-Brain path: /tmp/ai-brain", output)
        self.assertIn("Reports directory: reports", output)
        self.assertIn("Phase: 1", output)
        self.assertIn("Read-only: True", output)
        self.assertIn("Approved paths count: 2", output)
        self.assertIn("AI-Brain core files checked: 4", output)
        self.assertIn("Required core files found: 3", output)
        self.assertIn("Required core files missing: 1", output)
        self.assertIn("Project context check: not run by default", output)

    def test_help_exits_cleanly_and_mentions_recommended_entrypoint(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config") as mocked_config:
            with self.assertRaises(SystemExit) as context:
                with redirect_stdout(stdout):
                    cli.run(["--help"])

        output = stdout.getvalue()

        self.assertEqual(context.exception.code, 0)
        self.assertIn("--run-orchestrator", output)
        self.assertIn("Recommended main entrypoint", output)
        self.assertIn("focused", output)
        self.assertIn("advanced read-only operations", output)
        mocked_config.assert_not_called()
