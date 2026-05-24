from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from orchestration.approval_gate_manager import (
    evaluate_approval_requirements,
    format_approval_gate_view,
    format_approval_requirements,
)
from orchestration.task_classifier import classify_task


class ApprovalGateManagerTests(TestCase):
    def test_read_only_actions_do_not_require_approval(self) -> None:
        result = evaluate_approval_requirements(
            requested_actions=[
                "status",
                "project_context_check",
                "task_classification",
                "planner_report",
                "git_status_read",
                "git_diff_read",
                "multi_agent_diff_review",
                "save_report",
            ]
        )

        self.assertFalse(result["approval_required"])
        self.assertEqual(result["risk_level"], "low")
        self.assertEqual(result["blocked_actions"], [])

    def test_file_edit_requires_approval(self) -> None:
        result = evaluate_approval_requirements(requested_actions=["file_edit"])

        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "medium")
        self.assertIn("file_edit", result["blocked_actions"])

    def test_new_dependency_requires_approval(self) -> None:
        result = evaluate_approval_requirements(requested_actions=["new_dependency"])

        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "high")
        self.assertIn("New dependencies change supply-chain and runtime risk.", result["reasons"])

    def test_delete_move_rename_requires_approval(self) -> None:
        result = evaluate_approval_requirements(requested_actions=["rename"])

        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "high")
        self.assertIn("rename", result["blocked_actions"])

    def test_database_migration_requires_high_risk_approval(self) -> None:
        result = evaluate_approval_requirements(requested_actions=["database_migration"])

        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "high")
        self.assertIn("database_migration", result["blocked_actions"])

    def test_security_privacy_task_requires_approval(self) -> None:
        result = evaluate_approval_requirements(
            task_classification=classify_task("fix auth bug"),
        )

        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "high")
        self.assertIn("implementation_change", result["blocked_actions"])

    def test_project_assessment_task_does_not_require_approval(self) -> None:
        result = evaluate_approval_requirements(
            task_classification=classify_task("review this project and suggest the safest next coding task"),
            requested_actions=["planner_report"],
        )

        self.assertFalse(result["approval_required"])
        self.assertEqual(result["risk_level"], "low")
        self.assertEqual(result["blocked_actions"], [])

    def test_release_deploy_action_requires_approval(self) -> None:
        result = evaluate_approval_requirements(requested_actions=["release_deploy_action"])

        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "high")
        self.assertIn("release_deploy_action", result["blocked_actions"])

    def test_ai_brain_write_requires_approval(self) -> None:
        result = evaluate_approval_requirements(
            changed_files=["/home/asrin/Desktop/AI-Brain/02-Code/Elite-Coding-Workflow.md"],
        )

        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "high")
        self.assertIn("ai_brain_write", result["blocked_actions"])

    def test_project_docs_write_requires_approval(self) -> None:
        result = evaluate_approval_requirements(changed_files=["docs/project-map.md"])

        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "medium")
        self.assertIn("project_docs_write", result["blocked_actions"])

    def test_codex_execution_requires_approval(self) -> None:
        result = evaluate_approval_requirements(requested_actions=["codex_execution"])

        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "high")
        self.assertIn("codex_execution", result["blocked_actions"])

    def test_mcp_write_requires_approval(self) -> None:
        result = evaluate_approval_requirements(requested_actions=["mcp_write"])

        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "high")
        self.assertIn("mcp_write", result["blocked_actions"])

    def test_mcp_destructive_requires_high_risk_approval(self) -> None:
        result = evaluate_approval_requirements(requested_actions=["mcp_destructive"])

        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "high")
        self.assertIn("mcp_destructive", result["blocked_actions"])

    def test_multiple_reasons_are_returned(self) -> None:
        result = evaluate_approval_requirements(
            task_classification=classify_task("fix auth bug"),
            requested_actions=["file_edit", "codex_execution"],
        )

        self.assertGreaterEqual(len(result["reasons"]), 3)
        self.assertIn("file_edit", result["blocked_actions"])
        self.assertIn("codex_execution", result["blocked_actions"])
        self.assertIn("implementation_change", result["blocked_actions"])

    def test_recommended_user_confirmation_is_clear(self) -> None:
        result = evaluate_approval_requirements(requested_actions=["file_edit", "codex_execution"])
        formatted_output = format_approval_requirements(result)

        self.assertIn("Request explicit user approval before proceeding with:", result["recommended_user_confirmation"])
        self.assertIn("Recommended user confirmation:", formatted_output)

    def test_shared_approval_gate_formatter_matches_cli_format(self) -> None:
        result = evaluate_approval_requirements(requested_actions=["file_edit"])

        self.assertEqual(format_approval_gate_view(result), format_approval_requirements(result))


class ApprovalGateManagerCliTests(TestCase):
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

    def test_check_approval_without_risky_action_prints_no_approval_required(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--check-approval"])

        output = stdout.getvalue()

        self.assertIn("Approval required: no", output)
        self.assertIn("Risk level: low", output)

    def test_check_approval_with_requested_file_edit_prints_approval_required(self) -> None:
        stdout = StringIO()
        expected_result = evaluate_approval_requirements(requested_actions=["file_edit"])

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--check-approval", "--requested-action", "file_edit"])

        output = stdout.getvalue()

        self.assertIn("Approval required: yes", output)
        self.assertIn("Blocked actions: file_edit", output)
        self.assertIn(format_approval_gate_view(expected_result), output)

    def test_security_sensitive_task_prints_approval_required(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--task", "fix auth bug", "--check-approval"])

        output = stdout.getvalue()

        self.assertIn("Approval required: yes", output)
        self.assertIn("Risk level: high", output)
        self.assertIn("Security-sensitive tasks require explicit approval", output)

    def test_check_approval_with_mcp_write_is_approval_required(self) -> None:
        stdout = StringIO()
        expected_result = evaluate_approval_requirements(requested_actions=["mcp_write"])

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--check-approval", "--requested-action", "mcp_write"])

        output = stdout.getvalue()

        self.assertIn("Approval required: yes", output)
        self.assertIn("Blocked actions: mcp_write", output)
        self.assertIn(format_approval_gate_view(expected_result), output)

    def test_check_approval_with_mcp_destructive_is_high_risk(self) -> None:
        stdout = StringIO()
        expected_result = evaluate_approval_requirements(requested_actions=["mcp_destructive"])

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--check-approval", "--requested-action", "mcp_destructive"])

        output = stdout.getvalue()

        self.assertIn("Approval required: yes", output)
        self.assertIn("Risk level: high", output)
        self.assertIn("Blocked actions: mcp_destructive", output)
        self.assertIn(format_approval_gate_view(expected_result), output)

    def test_check_approval_with_codex_execution_is_high_risk(self) -> None:
        stdout = StringIO()
        expected_result = evaluate_approval_requirements(requested_actions=["codex_execution"])

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--check-approval", "--requested-action", "codex_execution"])

        output = stdout.getvalue()

        self.assertIn("Approval required: yes", output)
        self.assertIn("Risk level: high", output)
        self.assertIn("Blocked actions: codex_execution", output)
        self.assertIn(format_approval_gate_view(expected_result), output)
