from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from orchestration.task_classifier import classify_task


class TaskClassifierTests(TestCase):
    def test_classifies_feature_request(self) -> None:
        result = classify_task("add a new export feature for reports")

        self.assertEqual(result["primary_task_type"], "feature")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["risk_level"], "medium")

    def test_classifies_bug_fix_request(self) -> None:
        result = classify_task("fix telemetry bug causing a crash")

        self.assertEqual(result["primary_task_type"], "bug fix")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["risk_level"], "medium")

    def test_classifies_refactor_request(self) -> None:
        result = classify_task("refactor the config loader to simplify the flow")

        self.assertEqual(result["primary_task_type"], "refactor")
        self.assertEqual(result["risk_level"], "medium")

    def test_classifies_test_request(self) -> None:
        result = classify_task("write smoke tests and unittest coverage for the CLI")

        self.assertEqual(result["primary_task_type"], "test writing")
        self.assertEqual(result["confidence"], "high")

    def test_classifies_database_security_request_as_high_risk(self) -> None:
        result = classify_task("review auth token database migration")

        self.assertEqual(result["primary_task_type"], "security/privacy change")
        self.assertEqual(result["risk_level"], "high")
        self.assertIn("database change", result["secondary_task_types"])

    def test_classifies_ai_pipeline_request(self) -> None:
        result = classify_task("improve model inference fallback and prompt handling")

        self.assertEqual(result["primary_task_type"], "AI pipeline change")
        self.assertEqual(result["confidence"], "high")

    def test_classifies_documentation_request(self) -> None:
        result = classify_task("update the README documentation guide")

        self.assertEqual(result["primary_task_type"], "documentation change")
        self.assertEqual(result["risk_level"], "low")

    def test_classifies_project_assessment_request(self) -> None:
        result = classify_task("review this project and suggest the safest next coding task")

        self.assertEqual(result["primary_task_type"], "project assessment")
        self.assertEqual(result["risk_level"], "low")
        self.assertIn("safest next coding task", result["rationale"])

    def test_classifies_project_onboarding_request(self) -> None:
        result = classify_task("onboard this repo")

        self.assertEqual(result["primary_task_type"], "project assessment")
        self.assertIn(result["confidence"], {"medium", "high"})

    def test_empty_request_returns_unknown_low_confidence(self) -> None:
        result = classify_task("   ")

        self.assertEqual(result["primary_task_type"], "unknown")
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(result["risk_level"], "low")


class CliTaskClassifierTests(TestCase):
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

    def test_task_flag_prints_classification(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--task", "fix telemetry bug"])

        output = stdout.getvalue()

        self.assertIn("Task type: bug fix", output)
        self.assertIn("Confidence: high", output)
        self.assertIn("Risk level: medium", output)
        self.assertIn("Rationale:", output)

    def test_project_and_task_can_be_used_together(self) -> None:
        self.create_project_file("AGENTS.md")
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--project",
                            str(self.project_root),
                            "--task",
                            "update README documentation guide",
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn(f"Project working directory: {self.project_root.resolve()}", output)
        self.assertIn("Found AI-ready files count: 1", output)
        self.assertIn("Task type: documentation change", output)
        self.assertIn("Confidence: high", output)
