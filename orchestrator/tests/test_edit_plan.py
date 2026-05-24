from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from orchestration.approval_gate_manager import format_approval_gate_view
from orchestration.edit_plan import format_edit_plan, generate_edit_plan
from orchestration.task_classifier import classify_task


class EditPlanTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.project_root = self.approved_root / "project"
        self.project_root.mkdir()
        self.file_path = self.project_root / "src" / "module.py"
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text("print('safe')\n", encoding="utf-8")
        self.outside_root = self.root / "outside"
        self.outside_root.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_approved_file_dry_run_works(self) -> None:
        result = generate_edit_plan(
            self.project_root,
            "fix telemetry bug",
            ["src/module.py"],
            [str(self.approved_root)],
            task_classification=classify_task("fix telemetry bug"),
        )

        self.assertTrue(result["dry_run"])
        self.assertFalse(result["edit_allowed_now"])
        self.assertEqual(result["target_files"], [str(self.file_path.resolve())])
        self.assertTrue(result["approval_required"])

    def test_missing_allowed_file_is_reported(self) -> None:
        result = generate_edit_plan(
            self.project_root,
            "fix telemetry bug",
            ["src/missing.py"],
            [str(self.approved_root)],
            task_classification=classify_task("fix telemetry bug"),
        )

        blocked_reasons = [item["reason"] for item in result["blocked_files"]]
        self.assertIn("Target file does not exist:", blocked_reasons[0])

    def test_outside_allowed_file_is_rejected(self) -> None:
        result = generate_edit_plan(
            self.project_root,
            "fix telemetry bug",
            ["../outside/secret.py"],
            [str(self.approved_root)],
            task_classification=classify_task("fix telemetry bug"),
        )

        self.assertIn("outside the approved project path", result["blocked_files"][0]["reason"])

    def test_directory_target_is_rejected(self) -> None:
        result = generate_edit_plan(
            self.project_root,
            "fix telemetry bug",
            ["src"],
            [str(self.approved_root)],
            task_classification=classify_task("fix telemetry bug"),
        )

        self.assertIn("Target path is a directory, not a file:", result["blocked_files"][0]["reason"])

    def test_wildcard_broad_edit_is_rejected(self) -> None:
        result = generate_edit_plan(
            self.project_root,
            "fix telemetry bug",
            ["src/*.py"],
            [str(self.approved_root)],
            task_classification=classify_task("fix telemetry bug"),
        )

        self.assertEqual(
            result["blocked_files"][0]["reason"],
            "Wildcard or broad edit targets are not allowed.",
        )

    def test_approval_required_is_true(self) -> None:
        result = generate_edit_plan(
            self.project_root,
            "update README docs",
            ["src/module.py"],
            [str(self.approved_root)],
            task_classification=classify_task("update README docs"),
        )

        self.assertTrue(result["approval_required"])
        self.assertIn("Request explicit user approval", result["next_required_confirmation"])

    def test_formatted_output_includes_dry_run(self) -> None:
        result = generate_edit_plan(
            self.project_root,
            "fix telemetry bug",
            ["src/module.py"],
            [str(self.approved_root)],
            task_classification=classify_task("fix telemetry bug"),
        )
        output = format_edit_plan(result)

        self.assertIn("Dry run: yes", output)
        self.assertIn("Approval Gate:", output)
        self.assertIn(format_approval_gate_view(result["approval_gate"]), output)


class EditPlanCliTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.project_root = self.root / "project"
        self.project_root.mkdir()
        self.file_path = self.project_root / "src" / "module.py"
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text("print('safe')\n", encoding="utf-8")
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

    def test_cli_output_includes_dry_run_and_no_write(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--project",
                            str(self.project_root),
                            "--task",
                            "fix telemetry bug",
                            "--edit-plan",
                            "--allowed-file",
                            "src/module.py",
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn("Dry run: yes", output)
        self.assertIn("Edit allowed now: no", output)
        self.assertIn("Approval required: yes", output)
        self.assertIn("Approval Gate: Approval required: yes", output)
        self.assertNotIn("Report saved to:", output)
