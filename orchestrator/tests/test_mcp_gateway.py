from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from orchestration.approval_gate_manager import format_approval_gate_view
from tools.mcp_gateway import (
    evaluate_mcp_request,
    evaluate_mcp_tool_request,
    format_mcp_request_result,
    format_mcp_tool_request_result,
)


class MCPGatewayTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.approved_file = self.approved_root / "notes.txt"
        self.approved_file.write_text("safe", encoding="utf-8")
        self.outside_root = self.root / "outside"
        self.outside_root.mkdir()
        self.outside_file = self.outside_root / "secret.txt"
        self.outside_file.write_text("secret", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_read_tool_allowed_with_approved_path(self) -> None:
        result = evaluate_mcp_tool_request(
            "knowledge_reader",
            "read",
            target_path=str(self.approved_file),
            approved_paths=[str(self.approved_root)],
        )

        self.assertTrue(result["allowed"])
        self.assertIsNone(result["blocked_reason"])
        self.assertFalse(result["approval_required"])
        self.assertEqual(result["risk_level"], "low")

    def test_read_tool_rejected_outside_approved_path(self) -> None:
        result = evaluate_mcp_tool_request(
            "knowledge_reader",
            "read",
            target_path=str(self.outside_file),
            approved_paths=[str(self.approved_root)],
        )

        self.assertFalse(result["allowed"])
        self.assertIn("Target path is outside approved paths:", str(result["blocked_reason"]))

    def test_write_tool_requires_approval(self) -> None:
        result = evaluate_mcp_tool_request(
            "docs_writer",
            "write",
            target_path=str(self.approved_file),
            approved_paths=[str(self.approved_root)],
            approval_confirmed=False,
        )

        self.assertFalse(result["allowed"])
        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "high")
        self.assertEqual(
            result["blocked_reason"],
            "Explicit approval is required before allowing an MCP write request.",
        )
        self.assertIn("mcp_write", list(result["approval_gate"]["blocked_actions"]))

    def test_destructive_tool_blocked_without_approval(self) -> None:
        result = evaluate_mcp_tool_request(
            "repo_cleanup",
            "destructive",
            target_path=str(self.approved_file),
            approved_paths=[str(self.approved_root)],
            approval_confirmed=False,
        )

        self.assertFalse(result["allowed"])
        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "high")
        self.assertEqual(
            result["blocked_reason"],
            "Destructive MCP requests stay blocked until explicit approval is confirmed.",
        )

    def test_unknown_tool_type_blocked(self) -> None:
        result = evaluate_mcp_tool_request(
            "mystery_tool",
            "sync",
            approved_paths=[str(self.approved_root)],
        )

        self.assertFalse(result["allowed"])
        self.assertEqual(result["blocked_reason"], "Unsupported MCP tool type: sync")
        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "high")

    def test_no_target_path_read_tool_can_be_allowed_with_note(self) -> None:
        result = evaluate_mcp_tool_request(
            "knowledge_reader",
            "read",
            approved_paths=[str(self.approved_root)],
        )

        self.assertTrue(result["allowed"])
        self.assertIn(
            "No target path was provided; path approval was not evaluated.",
            list(result["safety_notes"]),
        )

    def test_production_database_admin_service_key_behavior_is_blocked(self) -> None:
        result = evaluate_mcp_tool_request(
            "production database admin tool",
            "read",
            approved_paths=[str(self.approved_root)],
        )

        self.assertFalse(result["allowed"])
        self.assertEqual(
            result["blocked_reason"],
            "Production database, admin, or service-key MCP behavior is not allowed by policy.",
        )
        self.assertTrue(result["approval_required"])

    def test_formatted_result_contains_policy_fields(self) -> None:
        result = evaluate_mcp_tool_request(
            "knowledge_reader",
            "read",
            target_path=str(self.approved_file),
            approved_paths=[str(self.approved_root)],
        )
        output = format_mcp_tool_request_result(result)

        self.assertIn("Allowed: yes", output)
        self.assertIn("Blocked reason: none", output)
        self.assertIn("Approval Gate: Approval required: no", output)
        self.assertIn(format_approval_gate_view(result["approval_gate"]), output)
        self.assertIn("Safety notes:", output)

    def test_registered_read_tool_can_pass_unified_decision(self) -> None:
        result = evaluate_mcp_request(
            "filesystem.read_file",
            "read",
            target_path=str(self.approved_file),
            approved_paths=[str(self.approved_root)],
        )

        self.assertTrue(result["allowed"])
        self.assertFalse(result["blocked"])
        self.assertEqual(result["registry_status"], "passed")
        self.assertEqual(result["gateway_status"], "passed")

    def test_unknown_tool_blocked_before_gateway(self) -> None:
        result = evaluate_mcp_request(
            "knowledge_reader",
            "read",
            target_path=str(self.approved_file),
            approved_paths=[str(self.approved_root)],
        )

        self.assertFalse(result["allowed"])
        self.assertTrue(result["blocked"])
        self.assertEqual(result["registry_status"], "blocked")
        self.assertEqual(result["gateway_status"], "not run")
        self.assertEqual(result["blocked_reason"], "Unknown MCP registry tool: knowledge_reader")

    def test_type_mismatch_blocked(self) -> None:
        result = evaluate_mcp_request(
            "git.diff",
            "write",
            approved_paths=[str(self.approved_root)],
        )

        self.assertFalse(result["allowed"])
        self.assertEqual(result["registry_status"], "blocked")
        self.assertEqual(result["gateway_status"], "not run")
        self.assertEqual(
            result["blocked_reason"],
            "Requested MCP tool type mismatch: requested write, registered read.",
        )

    def test_unified_write_tool_requires_approval(self) -> None:
        result = evaluate_mcp_request(
            "github.issue.comment",
            "write",
            approved_paths=[str(self.approved_root)],
        )

        self.assertFalse(result["allowed"])
        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "medium")
        self.assertEqual(result["registry_status"], "blocked")
        self.assertEqual(result["gateway_status"], "not run")

    def test_unified_destructive_tool_high_risk_and_blocked_without_approval(self) -> None:
        result = evaluate_mcp_request(
            "destructive.git.reset",
            "destructive",
            target_path=str(self.approved_file),
            approved_paths=[str(self.approved_root)],
        )

        self.assertFalse(result["allowed"])
        self.assertEqual(result["risk_level"], "high")
        self.assertTrue(result["approval_required"])
        self.assertEqual(result["registry_status"], "blocked")
        self.assertEqual(result["gateway_status"], "not run")

    def test_unapproved_target_path_still_blocked_by_gateway(self) -> None:
        result = evaluate_mcp_request(
            "filesystem.read_file",
            "read",
            target_path=str(self.outside_file),
            approved_paths=[str(self.approved_root)],
        )

        self.assertFalse(result["allowed"])
        self.assertEqual(result["registry_status"], "passed")
        self.assertEqual(result["gateway_status"], "blocked")
        self.assertIn("Target path is outside approved paths:", str(result["blocked_reason"]))

    def test_unified_formatted_result_contains_decision_fields(self) -> None:
        result = evaluate_mcp_request(
            "filesystem.read_file",
            "read",
            target_path=str(self.approved_file),
            approved_paths=[str(self.approved_root)],
        )
        output = format_mcp_request_result(result)

        self.assertIn("Tool name: filesystem.read_file", output)
        self.assertIn("Blocked: no", output)
        self.assertIn("Registry status: passed", output)
        self.assertIn("Gateway status: passed", output)


class MCPGatewayCliTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.approved_file = self.approved_root / "notes.txt"
        self.approved_file.write_text("safe", encoding="utf-8")
        self.fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": [str(self.approved_root)],
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cli_prints_policy_result(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files") as mocked_core:
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--mcp-check",
                            "--mcp-tool-name",
                            "filesystem.read_file",
                            "--mcp-tool-type",
                            "read",
                            "--mcp-target-path",
                            str(self.approved_file),
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn("Tool name: filesystem.read_file", output)
        self.assertIn("Allowed: yes", output)
        self.assertIn("Blocked: no", output)
        self.assertIn("Registry status: passed", output)
        self.assertIn("Gateway status: passed", output)
        self.assertIn("Approval Gate: Approval required: no", output)
        self.assertIn("Safety notes:", output)
        mocked_core.assert_not_called()
