import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from io import StringIO

import cli
from tools.mcp_controlled_write import run_controlled_write_tool

class MCPControlledWriteTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.reports_dir = self.approved_root / "reports"
        self.reports_dir.mkdir()
        
        self.unapproved_root = self.root / "unapproved"
        self.unapproved_root.mkdir()
        
        self.approved_paths = [str(self.approved_root)]

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_write_tool_without_approval_returns_preview_only(self):
        target = self.reports_dir / "report.md"
        result = run_controlled_write_tool(
            "report.export",
            "Report content",
            self.approved_paths,
            target_path=str(target),
            approval_confirmed=False,
        )
        self.assertTrue(result["preview_only"])
        self.assertFalse(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertEqual(result["preview_text"], "Report content")
        self.assertFalse(target.exists())

    def test_approved_report_export_can_write_to_approved_path(self):
        target = self.reports_dir / "report.md"
        result = run_controlled_write_tool(
            "report.export",
            "Report content",
            self.approved_paths,
            target_path=str(target),
            approval_confirmed=True,
            dry_run=False,
        )
        self.assertFalse(result["preview_only"])
        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), "Report content")

    def test_project_docs_append_blocks_code_file_targets(self):
        target = self.approved_root / "code.py"
        result = run_controlled_write_tool(
            "project_docs.append",
            "Some content",
            self.approved_paths,
            target_path=str(target),
            approval_confirmed=True,
            dry_run=False,
        )
        self.assertTrue(result["blocked"])
        self.assertIn("cannot target code files", result["message"])
        self.assertFalse(target.exists())

    def test_project_docs_append_requires_approved_path(self):
        target = self.unapproved_root / "docs.md"
        result = run_controlled_write_tool(
            "project_docs.append",
            "Some content",
            self.approved_paths,
            target_path=str(target),
            approval_confirmed=True,
            dry_run=False,
        )
        self.assertTrue(result["blocked"])
        self.assertIn("not approved", result["message"])
        self.assertFalse(target.exists())

    def test_github_issue_comment_remains_preview_only(self):
        result = run_controlled_write_tool(
            "github.issue.comment",
            "My comment",
            self.approved_paths,
            approval_confirmed=True,
            dry_run=False,
        )
        self.assertTrue(result["preview_only"])
        self.assertFalse(result["executed"])
        self.assertEqual(result["preview_text"], "My comment")

    def test_secret_like_content_is_blocked_and_redacted(self):
        target = self.reports_dir / "report.md"
        secret_content = "API_KEY=sk-ant-api03-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12"
        result = run_controlled_write_tool(
            "report.export",
            secret_content,
            self.approved_paths,
            target_path=str(target),
            approval_confirmed=True,
            dry_run=False,
        )
        self.assertTrue(result["blocked"])
        self.assertFalse(result["executed"])
        self.assertEqual(result["preview_text"], "[REDACTED]")
        self.assertFalse(target.exists())

    def test_destructive_tool_cannot_be_used_here(self):
        result = run_controlled_write_tool(
            "destructive.git.reset",
            "content",
            self.approved_paths,
            approval_confirmed=True,
            dry_run=False,
        )
        self.assertTrue(result["blocked"])
        self.assertIn("not a valid registered write tool", result["message"])

    @patch("cli.load_config")
    def test_cli_integration(self, mock_load_config):
        mock_load_config.return_value = {
            "ai_brain_path": str(self.approved_root),
            "reports_dir": str(self.reports_dir),
            "phase": "1",
            "read_only": True,
            "approved_paths": [str(self.approved_root)],
        }
        target = self.reports_dir / "report.md"
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            cli.run([
                "--mcp-write-preview",
                "--mcp-write-tool-name", "report.export",
                "--mcp-write-target-path", str(target),
                "--mcp-write-content", "CLI content test"
            ])
            output = mock_stdout.getvalue()
            self.assertIn("Write tool: report.export", output)
            self.assertIn("Preview only: yes", output)
            self.assertIn("Preview:\nCLI content test", output)
            self.assertFalse(target.exists())

    def test_audit_event_records_preview_vs_executed(self):
        target = self.reports_dir / "audit_report.md"
        result_preview = run_controlled_write_tool(
            "report.export",
            "Report content",
            self.approved_paths,
            target_path=str(target),
            approval_confirmed=True,
            dry_run=True,
        )
        self.assertTrue(result_preview["audit_event"]["preview_only"])
        self.assertFalse(result_preview["audit_event"]["executed"])

        result_exec = run_controlled_write_tool(
            "report.export",
            "Report content",
            self.approved_paths,
            target_path=str(target),
            approval_confirmed=True,
            dry_run=False,
        )
        self.assertFalse(result_exec["audit_event"]["preview_only"])
        self.assertTrue(result_exec["audit_event"]["executed"])

    @patch("cli.load_config")
    def test_cli_integration_with_execute(self, mock_load_config):
        mock_load_config.return_value = {
            "ai_brain_path": str(self.approved_root),
            "reports_dir": str(self.reports_dir),
            "phase": "1",
            "read_only": True,
            "approved_paths": [str(self.approved_root)],
        }
        target = self.reports_dir / "report2.md"
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            cli.run([
                "--mcp-write-preview",
                "--mcp-write-tool-name", "report.export",
                "--mcp-write-target-path", str(target),
                "--mcp-write-content", "CLI execute test",
                "--confirm-mcp-write",
                "--execute-mcp-write"
            ])
            output = mock_stdout.getvalue()
            self.assertIn("Write tool: report.export", output)
            self.assertIn("Preview only: no", output)
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(), "CLI execute test")
