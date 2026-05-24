from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from core import report_writer


class EndToEndOrchestratorTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.ai_brain_root = self.approved_root / "ai-brain"
        (self.ai_brain_root / "02-Code").mkdir(parents=True)
        (self.ai_brain_root / "CORE-RULES.md").write_text("core", encoding="utf-8")
        (self.ai_brain_root / "README-FOR-AI.md").write_text("readme", encoding="utf-8")
        (self.ai_brain_root / "02-Code" / "AI-Brain-Priority-Tiers.md").write_text("tiers", encoding="utf-8")
        (self.ai_brain_root / "02-Code" / "Context-Budget-Rules.md").write_text("budget", encoding="utf-8")

        self.fake_config = {
            "ai_brain_path": str(self.ai_brain_root),
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": [str(self.approved_root)],
        }

        self.report_root_patch = patch.object(report_writer, "PROJECT_ROOT", self.root)
        self.report_root_patch.start()

    def tearDown(self) -> None:
        self.report_root_patch.stop()
        self.temp_dir.cleanup()

    def _init_git_repo(self, repo_path: Path) -> Path:
        repo_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init", str(repo_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        return repo_path

    def _run_cli(self, argv: list[str]) -> str:
        stdout = StringIO()
        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "evaluate_mcp_tool_request") as mocked_mcp:
                with patch.object(cli, "generate_codex_prompt_package") as mocked_codex:
                    with redirect_stdout(stdout):
                        cli.run(argv)
        mocked_mcp.assert_not_called()
        mocked_codex.assert_not_called()
        return stdout.getvalue()

    def test_orchestrator_status_e2e(self) -> None:
        output = self._run_cli(["--run-orchestrator", "--mode", "status"])

        self.assertIn("Summary: Read-only orchestration status completed.", output)
        self.assertIn("Mode: status", output)
        self.assertIn("Project context summary: not provided", output)
        self.assertIn("Report text:", output)

    def test_orchestrator_plan_with_task_e2e(self) -> None:
        output = self._run_cli(
            ["--run-orchestrator", "--mode", "plan", "--task", "fix telemetry bug"]
        )

        self.assertIn("Mode: plan", output)
        self.assertIn("Task type: bug fix", output)
        self.assertIn("Summary:", output)
        self.assertIn("Suggested tests:", output)
        self.assertIn("Approval Gate:", output)

    def test_orchestrator_plan_save_report_e2e(self) -> None:
        output = self._run_cli(
            [
                "--run-orchestrator",
                "--mode",
                "plan",
                "--task",
                "fix telemetry bug",
                "--save-report",
            ]
        )

        created_reports = list((self.root / "reports").glob("*.md"))

        self.assertIn("Mode: plan", output)
        self.assertIn("Report path:", output)
        self.assertEqual(len(created_reports), 1)
        self.assertEqual(created_reports[0].parent, self.root / "reports")
        self.assertFalse((self.ai_brain_root / "reports").exists())
        self.assertFalse((self.approved_root / "reports").exists())

    def test_orchestrator_review_diff_clean_repo_e2e(self) -> None:
        repo_path = self._init_git_repo(self.approved_root / "clean-repo")

        output = self._run_cli(
            [
                "--run-orchestrator",
                "--mode",
                "review-diff",
                "--project",
                str(repo_path),
                "--task",
                "fix telemetry bug",
            ]
        )

        self.assertIn("Mode: review-diff", output)
        self.assertIn("Decision: Needs more context", output)
        self.assertIn("Summary: No git diff is present, so review context is incomplete.", output)
        self.assertIn("Project context summary:", output)

    def test_orchestrator_review_diff_clean_repo_save_report_e2e(self) -> None:
        repo_path = self._init_git_repo(self.approved_root / "clean-save-repo")

        output = self._run_cli(
            [
                "--run-orchestrator",
                "--mode",
                "review-diff",
                "--project",
                str(repo_path),
                "--task",
                "fix telemetry bug",
                "--save-report",
            ]
        )

        created_reports = list((self.root / "reports").glob("*.md"))

        self.assertIn("Mode: review-diff", output)
        self.assertIn("Decision: Needs more context", output)
        self.assertIn("Report path:", output)
        self.assertEqual(len(created_reports), 1)
        self.assertEqual(created_reports[0].parent, self.root / "reports")
        saved_report_text = created_reports[0].read_text(encoding="utf-8")
        self.assertIn("Summary:", saved_report_text)
        self.assertIn("Decision: Needs more context", saved_report_text)
        self.assertIn("Agents used:", saved_report_text)
        self.assertIn("Approval Gate:", saved_report_text)
        self.assertFalse((self.ai_brain_root / "reports").exists())
        self.assertFalse((self.approved_root / "reports").exists())

    def test_orchestrator_review_diff_simple_diff_e2e(self) -> None:
        repo_path = self._init_git_repo(self.approved_root / "diff-repo")
        (repo_path / "telemetry.py").write_text("ENABLED = True\n", encoding="utf-8")

        output = self._run_cli(
            [
                "--run-orchestrator",
                "--mode",
                "review-diff",
                "--project",
                str(repo_path),
                "--task",
                "fix telemetry bug",
            ]
        )

        self.assertIn("Mode: review-diff", output)
        self.assertIn("Decision:", output)
        self.assertIn("Agents used:", output)
        self.assertIn("Changed files:", output)
        self.assertIn("telemetry.py", output)

    def test_orchestrator_review_diff_simple_diff_save_report_e2e(self) -> None:
        repo_path = self._init_git_repo(self.approved_root / "diff-save-repo")
        (repo_path / "telemetry.py").write_text("ENABLED = True\n", encoding="utf-8")

        output = self._run_cli(
            [
                "--run-orchestrator",
                "--mode",
                "review-diff",
                "--project",
                str(repo_path),
                "--task",
                "fix telemetry bug",
                "--save-report",
            ]
        )

        created_reports = list((self.root / "reports").glob("*.md"))

        self.assertIn("Mode: review-diff", output)
        self.assertIn("Decision:", output)
        self.assertIn("Report path:", output)
        self.assertEqual(len(created_reports), 1)
        self.assertEqual(created_reports[0].parent, self.root / "reports")
        saved_report_text = created_reports[0].read_text(encoding="utf-8")
        self.assertIn("Summary:", saved_report_text)
        self.assertIn("Agents used:", saved_report_text)
        self.assertIn("Changed files:", saved_report_text)
        self.assertIn("telemetry.py", saved_report_text)
        self.assertIn("Suggested tests:", saved_report_text)
        self.assertFalse((self.ai_brain_root / "reports").exists())
        self.assertFalse((self.approved_root / "reports").exists())

    def test_orchestrator_secret_like_diff_is_blocked_and_not_saved(self) -> None:
        repo_path = self._init_git_repo(self.approved_root / "secret-diff-repo")
        secret_value = "super-secret-token-123"
        (repo_path / ".env").write_text(f"API_TOKEN={secret_value}\n", encoding="utf-8")

        output = self._run_cli(
            [
                "--run-orchestrator",
                "--mode",
                "review-diff",
                "--project",
                str(repo_path),
                "--task",
                "fix auth bug",
                "--save-report",
            ]
        )

        created_reports = list((self.root / "reports").glob("*.md"))

        self.assertIn("Mode: review-diff", output)
        self.assertIn("Decision: Blocked", output)
        self.assertIn("secret-like content was detected", output)
        self.assertIn("Detected token-style assignment", output)
        self.assertNotIn(secret_value, output)
        self.assertNotIn("Report saved to:", output)
        self.assertIn("Report path: none", output)
        self.assertEqual(created_reports, [])
        self.assertFalse((self.root / "reports").exists())
        self.assertFalse((self.ai_brain_root / "reports").exists())
        self.assertFalse((self.approved_root / "reports").exists())

    def test_orchestrator_unapproved_project_is_rejected_before_project_and_git_inspection(self) -> None:
        outside_project = self.root / "outside-project"
        outside_project.mkdir()
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch("orchestration.orchestrator_controller.inspect_project_context") as mocked_project_context:
                with patch("orchestration.orchestrator_controller.inspect_git_state") as mocked_git_state:
                    with self.assertRaisesRegex(
                        SystemExit,
                        "Orchestrator error: Target path is outside approved paths:",
                    ):
                        with redirect_stdout(stdout):
                            cli.run(
                                [
                                    "--run-orchestrator",
                                    "--mode",
                                    "review-diff",
                                    "--project",
                                    str(outside_project),
                                    "--task",
                                    "fix telemetry bug",
                                ]
                            )

        output = stdout.getvalue()

        self.assertIn("Errors: Target path is outside approved paths:", output)
        mocked_project_context.assert_not_called()
        mocked_git_state.assert_not_called()
