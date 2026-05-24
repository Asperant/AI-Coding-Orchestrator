from contextlib import redirect_stdout
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

import cli
from tools.mcp_registry import (
    evaluate_registered_tool_request,
    format_registered_tool_request_result,
    get_registered_tool,
    list_registered_tools,
)


class MCPRegistryTests(TestCase):
    def test_list_registered_tools(self) -> None:
        tools = list_registered_tools()

        self.assertGreaterEqual(len(tools), 15)
        self.assertEqual(tools[0]["tool_name"], "destructive.git.reset")
        self.assertIsNotNone(get_registered_tool("filesystem.read_file"))

    def test_known_read_tool_allowed_without_approval(self) -> None:
        result = evaluate_registered_tool_request("filesystem.read_file", "read")

        self.assertTrue(result["allowed"])
        self.assertIsNone(result["blocked_reason"])
        self.assertFalse(result["approval_required"])
        self.assertEqual(result["risk_level"], "low")

    def test_write_tool_requires_approval(self) -> None:
        result = evaluate_registered_tool_request("github.issue.comment", "write")

        self.assertFalse(result["allowed"])
        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "medium")
        self.assertEqual(
            result["blocked_reason"],
            "Explicit approval is required before allowing a registered MCP write tool.",
        )

    def test_destructive_tool_high_risk_and_blocked_without_approval(self) -> None:
        result = evaluate_registered_tool_request("destructive.git.reset", "destructive")

        self.assertFalse(result["allowed"])
        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "high")
        self.assertTrue(result["dangerous"])
        self.assertEqual(
            result["blocked_reason"],
            "Destructive MCP tools stay blocked until explicit approval is confirmed.",
        )

    def test_unknown_tool_blocked(self) -> None:
        result = evaluate_registered_tool_request("unknown.tool", "read")

        self.assertFalse(result["allowed"])
        self.assertEqual(result["blocked_reason"], "Unknown MCP registry tool: unknown.tool")
        self.assertEqual(result["risk_level"], "high")

    def test_requested_type_mismatch_blocked(self) -> None:
        result = evaluate_registered_tool_request("git.diff", "write")

        self.assertFalse(result["allowed"])
        self.assertEqual(
            result["blocked_reason"],
            "Requested MCP tool type mismatch: requested write, registered read.",
        )

    def test_formatted_registry_result_contains_expected_fields(self) -> None:
        result = evaluate_registered_tool_request("git.diff", "read")
        output = format_registered_tool_request_result(result)

        self.assertIn("Tool name: git.diff", output)
        self.assertIn("Allowed: yes", output)
        self.assertIn("Risk level: medium", output)
        self.assertIn("Approval Gate: Approval required: no", output)
        self.assertIn("Safety notes:", output)


class MCPRegistryCliTests(TestCase):
    def setUp(self) -> None:
        self.fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": ["/tmp/approved"],
        }

    def test_cli_list_tools_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "evaluate_mcp_tool_request") as mocked_gateway:
                with redirect_stdout(stdout):
                    cli.run(["--mcp-list-tools"])

        output = stdout.getvalue()

        self.assertIn("Registered MCP tools:", output)
        self.assertIn("filesystem.read_file", output)
        mocked_gateway.assert_not_called()

    def test_cli_registry_check_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "evaluate_mcp_tool_request") as mocked_gateway:
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--mcp-registry-check",
                            "--mcp-tool-name",
                            "github.issue.comment",
                            "--mcp-tool-type",
                            "write",
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn("Tool name: github.issue.comment", output)
        self.assertIn("Allowed: no", output)
        self.assertIn("Approval required: yes", output)
        mocked_gateway.assert_not_called()
