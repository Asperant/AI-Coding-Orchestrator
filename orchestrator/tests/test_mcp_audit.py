import os
from unittest import TestCase
from unittest.mock import patch
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

import cli
from tools.mcp_read_dispatcher import run_mcp_read_tool
from tools.mcp_controlled_write import run_controlled_write_tool
from tools.mcp_audit import format_mcp_audit_event, format_mcp_audit_events_compact

class MCPAuditTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.safe_doc = self.approved_root / "test.txt"
        self.safe_doc.write_text("Hello World")
        self.secret_doc = self.approved_root / "secret.txt"
        self.secret_doc.write_text("API_KEY=sk-ant-api03-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_audit_event_from_allowed_read_decision(self):
        result = run_mcp_read_tool(
            "filesystem.read_file",
            target_path=str(self.safe_doc),
            approved_paths=[str(self.approved_root)]
        )
        self.assertTrue(result["executed"])
        audit_event = result.get("audit_event")
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event["tool_name"], "filesystem.read_file")
        self.assertEqual(audit_event["action"], "read")
        self.assertTrue(audit_event["allowed"])
        self.assertFalse(audit_event["blocked"])
        self.assertEqual(audit_event["risk_level"], "low")

    def test_audit_event_from_blocked_decision(self):
        result = run_mcp_read_tool(
            "filesystem.read_file",
            target_path="/etc/passwd",
            approved_paths=[str(self.approved_root)]
        )
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        audit_event = result.get("audit_event")
        self.assertIsNotNone(audit_event)
        self.assertFalse(audit_event["allowed"])
        self.assertTrue(audit_event["blocked"])
        self.assertIn("outside approved paths", audit_event["reason"])

    def test_audit_event_from_write_preview(self):
        target = self.approved_root / "out.txt"
        result = run_controlled_write_tool(
            "report.export",
            "Content",
            [str(self.approved_root)],
            target_path=str(target),
            approval_confirmed=False
        )
        self.assertTrue(result["preview_only"])
        audit_event = result.get("audit_event")
        self.assertIsNotNone(audit_event)
        self.assertTrue(audit_event["allowed"])
        self.assertFalse(audit_event["blocked"])
        self.assertEqual(audit_event["reason"], "preview generated")

    def test_audit_event_from_approved_write(self):
        target = self.approved_root / "out.txt"
        result = run_controlled_write_tool(
            "report.export",
            "Content",
            [str(self.approved_root)],
            target_path=str(target),
            approval_confirmed=True,
            dry_run=False
        )
        self.assertTrue(result["executed"])
        audit_event = result.get("audit_event")
        self.assertIsNotNone(audit_event)
        self.assertTrue(audit_event["allowed"])
        self.assertFalse(audit_event["blocked"])
        self.assertIn("Real write completed using", audit_event["reason"])
        self.assertTrue(audit_event["executed"])
        self.assertFalse(audit_event["preview_only"])
        
    def test_secret_like_content_never_appears_in_audit(self):
        result = run_mcp_read_tool(
            "filesystem.read_file",
            target_path=str(self.secret_doc),
            approved_paths=[str(self.approved_root)]
        )
        self.assertTrue(result["blocked"])
        audit_event = result.get("audit_event")
        self.assertIsNotNone(audit_event)
        self.assertNotIn("sk-ant-api", str(audit_event))
        self.assertNotIn("sk-ant-api", format_mcp_audit_event(audit_event))

    @patch("cli.load_config")
    def test_cli_audit_preview_flag(self, mock_load_config):
        mock_load_config.return_value = {
            "approved_paths": [str(self.approved_root)],
            "ai_brain_path": str(self.approved_root),
            "reports_dir": str(self.approved_root),
            "phase": "1",
            "read_only": True
        }
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            cli.run([
                "--mcp-run-read",
                "--mcp-tool-name", "filesystem.read_file",
                "--mcp-target-path", str(self.safe_doc),
                "--mcp-audit-preview"
            ])
            output = mock_stdout.getvalue()
            self.assertIn("--- MCP Audit Preview ---", output)
            self.assertIn("Audit Event ID:", output)
            self.assertIn("Allowed: yes", output)
            self.assertIn("Action: read", output)
            self.assertIn("Tool Name: filesystem.read_file", output)
