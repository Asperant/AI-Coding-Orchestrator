from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from core import report_writer


class ReportWriterTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        self.timestamp = datetime(2026, 5, 17, 12, 34, 56, tzinfo=timezone.utc)

        self.project_root_patch = patch.object(report_writer, "PROJECT_ROOT", self.project_root)
        self.project_root_patch.start()

    def tearDown(self) -> None:
        self.project_root_patch.stop()
        self.temp_dir.cleanup()

    def test_writes_markdown_report_into_reports_dir(self) -> None:
        created_path = report_writer.write_report(
            "# Planner Report",
            "planner-report",
            "reports",
            timestamp=self.timestamp,
        )

        self.assertEqual(
            created_path,
            self.project_root / "reports" / "20260517-123456-planner-report.md",
        )
        self.assertEqual(created_path.read_text(encoding="utf-8"), "# Planner Report")

    def test_creates_reports_dir_if_missing(self) -> None:
        reports_dir = self.project_root / "reports" / "planner"
        self.assertFalse(reports_dir.exists())

        created_path = report_writer.write_report(
            "report body",
            "planner-report",
            "reports/planner",
            timestamp=self.timestamp,
        )

        self.assertTrue(reports_dir.is_dir())
        self.assertEqual(created_path.parent, reports_dir)

    def test_filename_is_timestamped_and_sanitized(self) -> None:
        created_path = report_writer.write_report(
            "report body",
            "Planner Report v1",
            "reports",
            timestamp=self.timestamp,
        )

        self.assertEqual(created_path.name, "20260517-123456-planner-report-v1.md")

    def test_path_traversal_in_report_type_is_sanitized_safely(self) -> None:
        created_path = report_writer.write_report(
            "report body",
            "../secret-plan",
            "reports",
            timestamp=self.timestamp,
        )

        self.assertEqual(created_path.name, "20260517-123456-secret-plan.md")
        self.assertTrue(created_path.is_file())

    def test_returns_created_path(self) -> None:
        created_path = report_writer.write_report(
            "report body",
            "planner-report",
            "reports",
            timestamp=self.timestamp,
        )

        self.assertIsInstance(created_path, Path)

    def test_does_not_write_outside_reports_dir(self) -> None:
        with self.assertRaisesRegex(
            report_writer.ReportWriterError,
            "Reports directory must stay inside the app reports directory:",
        ):
            report_writer.write_report(
                "report body",
                "planner-report",
                "../outside",
                timestamp=self.timestamp,
            )


class ReportWriterCliTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        self.timestamp = datetime(2026, 5, 17, 12, 34, 56, tzinfo=timezone.utc)
        self.fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": ["/tmp/ai-brain", "reports"],
        }
        self.fake_core_status = {
            "checked_count": 4,
            "found_count": 4,
            "missing_count": 0,
            "missing_files": {},
        }

        self.project_root_patch = patch.object(report_writer, "PROJECT_ROOT", self.project_root)
        self.project_root_patch.start()

    def tearDown(self) -> None:
        self.project_root_patch.stop()
        self.temp_dir.cleanup()

    def init_git_repo(self, repo_path: Path) -> Path:
        repo_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init", str(repo_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        return repo_path

    def test_cli_task_plan_and_save_report_writes_report(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with patch("core.report_writer.datetime") as mocked_datetime:
                    mocked_datetime.now.return_value = self.timestamp
                    mocked_datetime.strftime = datetime.strftime
                    with redirect_stdout(stdout):
                        cli.run(["--task", "fix telemetry bug", "--plan", "--save-report"])

        output = stdout.getvalue()
        created_reports = list((self.project_root / "reports").glob("*.md"))

        self.assertIn("Summary:", output)
        self.assertIn("Report saved to:", output)
        self.assertEqual(len(created_reports), 1)
        self.assertIn("Task type: bug fix", created_reports[0].read_text(encoding="utf-8"))

    def test_cli_task_plan_and_save_report_is_blocked_when_report_contains_secret(self) -> None:
        raw_secret = "super-secret-value-987654321"
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with patch.object(
                    cli,
                    "format_planner_report",
                    return_value=(
                        "Summary: security/privacy change task.\n"
                        f'Likely files or areas to inspect: API_TOKEN = "{raw_secret}"\n'
                    ),
                ):
                    with patch("core.report_writer.datetime") as mocked_datetime:
                        mocked_datetime.now.return_value = self.timestamp
                        mocked_datetime.strftime = datetime.strftime
                        with redirect_stdout(stdout):
                            cli.run(["--task", "fix auth bug", "--plan", "--save-report"])

        output = stdout.getvalue()
        created_reports = list((self.project_root / "reports").glob("*.md"))

        self.assertIn("Planner report save blocked because secret-like content was detected. Findings are redacted.", output)
        self.assertIn("Finding: Detected token-style assignment", output)
        self.assertIn("Report saving blocked due to secret-like content detected in the planner report.", output)
        self.assertNotIn("Report saved to:", output)
        self.assertNotIn(raw_secret, output)
        self.assertEqual(len(created_reports), 0)

    def test_cli_review_diff_and_save_report_writes_report(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "review-repo")
        changed_file = repo_path / "config.py"
        changed_file.write_text("FEATURE_FLAG = True\n", encoding="utf-8")
        stdout = StringIO()

        review_config = dict(self.fake_config)
        review_config["approved_paths"] = [str(self.project_root)]

        with patch.object(cli, "load_config", return_value=review_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with patch("core.report_writer.datetime") as mocked_datetime:
                    mocked_datetime.now.return_value = self.timestamp
                    mocked_datetime.strftime = datetime.strftime
                    with redirect_stdout(stdout):
                        cli.run(["--project", str(repo_path), "--review-diff", "--save-report"])

        output = stdout.getvalue()
        created_reports = list((self.project_root / "reports").glob("*.md"))

        self.assertIn("Summary:", output)
        self.assertIn("Decision:", output)
        self.assertIn("Report saved to:", output)
        self.assertEqual(len(created_reports), 1)
        self.assertIn("/reports/", str(created_reports[0]))
        report_text = created_reports[0].read_text(encoding="utf-8")
        self.assertIn("Summary:", report_text)
        self.assertIn("Decision:", report_text)
        self.assertIn("Agents used:", report_text)

    def test_cli_review_diff_and_save_report_does_not_save_when_secret_is_detected(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "secret-review-repo")
        raw_secret = "service-role-secret-123"
        changed_file = repo_path / "config.py"
        changed_file.write_text(
            f"SUPABASE_SERVICE_ROLE_KEY = '{raw_secret}'\n",
            encoding="utf-8",
        )
        stdout = StringIO()

        review_config = dict(self.fake_config)
        review_config["approved_paths"] = [str(self.project_root)]

        with patch.object(cli, "load_config", return_value=review_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with patch("core.report_writer.datetime") as mocked_datetime:
                    mocked_datetime.now.return_value = self.timestamp
                    mocked_datetime.strftime = datetime.strftime
                    with redirect_stdout(stdout):
                        cli.run(["--project", str(repo_path), "--review-diff", "--save-report"])

        output = stdout.getvalue()
        created_reports = list((self.project_root / "reports").glob("*.md"))

        self.assertIn("Decision: Blocked", output)
        self.assertIn("Report saving blocked due to secret-like content detected in the diff.", output)
        self.assertNotIn("Report saved to:", output)
        self.assertNotIn(raw_secret, output)
        self.assertEqual(len(created_reports), 0)

    def test_save_report_without_plan_or_review_diff_gives_clear_error(self) -> None:
        with self.assertRaisesRegex(
            SystemExit,
            (
                "Report writer error: --save-report currently requires "
                "--plan, --review-diff, --run-orchestrator, or --execute-codex."
            ),
        ):
            cli.run(["--save-report"])
