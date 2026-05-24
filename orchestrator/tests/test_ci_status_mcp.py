import json
import subprocess
from unittest import TestCase
from unittest.mock import patch, MagicMock

from tools.ci_status_mcp import run_ci_status_tool, MockCiClient

class CiStatusMCPTests(TestCase):
    def test_mock_ci_status_returns_context_block(self):
        client = MockCiClient({("owner/repo", None, None): "Mock passed"})
        result = run_ci_status_tool(
            "test.ci_status.read",
            provider="github_actions",
            repo="owner/repo",
            client=client
        )
        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertEqual(len(result["context_blocks"]), 1)
        self.assertEqual(result["context_blocks"][0]["source"], "github_actions:owner/repo")
        self.assertIn("Mock passed", result["context_blocks"][0]["content"])

    def test_invalid_tool_name_blocks(self):
        result = run_ci_status_tool("invalid.tool", "github_actions", "owner/repo")
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("not allowed", result["message"])

    def test_invalid_repo_format_blocks(self):
        result = run_ci_status_tool("test.ci_status.read", "github_actions", "owner_repo_without_slash")
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("Invalid repo format", result["message"])

    def test_unsafe_branch_blocks(self):
        result = run_ci_status_tool("test.ci_status.read", "github_actions", "owner/repo", branch="main; echo")
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("Invalid branch name", result["message"])

    def test_invalid_limit_bounds_blocks(self):
        result = run_ci_status_tool("test.ci_status.read", "github_actions", "owner/repo", limit=100)
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("Limit must be between 1 and 50", result["message"])

    @patch("tools.ci_status_mcp.shutil.which", return_value=None)
    def test_gh_missing_returns_unavailable(self, mock_which):
        result = run_ci_status_tool("test.ci_status.read", "github_actions", "owner/repo")
        self.assertTrue(result["blocked"])
        self.assertIn("gh CLI is not installed", result["message"])

    @patch("tools.ci_status_mcp.shutil.which", return_value="/usr/bin/gh")
    @patch("tools.ci_status_mcp.subprocess.run")
    def test_real_ci_status_all_success_returns_passed(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"name": "CI", "status": "completed", "conclusion": "success", "headBranch": "main", "event": "push"}
            ])
        )
        result = run_ci_status_tool("test.ci_status.read", "github_actions", "owner/repo")
        self.assertTrue(result["executed"])
        self.assertIn("Overall status: passed", result["content_summary"])
        content = result["context_blocks"][0]["content"]
        self.assertIn("Overall status summary of these runs: passed", content)
        self.assertIn("success", content)

    @patch("tools.ci_status_mcp.shutil.which", return_value="/usr/bin/gh")
    @patch("tools.ci_status_mcp.subprocess.run")
    def test_real_ci_status_failure_returns_failed(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"name": "CI", "status": "completed", "conclusion": "failure", "headBranch": "main", "event": "push"},
                {"name": "Lint", "status": "completed", "conclusion": "success", "headBranch": "main", "event": "push"}
            ])
        )
        result = run_ci_status_tool("test.ci_status.read", "github_actions", "owner/repo")
        self.assertTrue(result["executed"])
        self.assertIn("Overall status: failed", result["content_summary"])
        content = result["context_blocks"][0]["content"]
        self.assertIn("Overall status summary of these runs: failed", content)
        self.assertIn("failure", content)

    @patch("tools.ci_status_mcp.shutil.which", return_value="/usr/bin/gh")
    @patch("tools.ci_status_mcp.subprocess.run")
    def test_real_ci_status_in_progress_returns_running(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"name": "CI", "status": "in_progress", "conclusion": "", "headBranch": "main", "event": "push"}
            ])
        )
        result = run_ci_status_tool("test.ci_status.read", "github_actions", "owner/repo")
        self.assertTrue(result["executed"])
        self.assertIn("Overall status: running", result["content_summary"])
        content = result["context_blocks"][0]["content"]
        self.assertIn("Overall status summary of these runs: running", content)
        self.assertIn("in_progress", content)

    @patch("tools.ci_status_mcp.shutil.which", return_value="/usr/bin/gh")
    @patch("tools.ci_status_mcp.subprocess.run")
    def test_real_ci_status_empty_returns_unknown(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout="[]")
        result = run_ci_status_tool("test.ci_status.read", "github_actions", "owner/repo")
        self.assertTrue(result["executed"])
        self.assertIn("Overall status: unknown", result["content_summary"])
        content = result["context_blocks"][0]["content"]
        self.assertIn("No recent CI runs found", content)

    @patch("tools.ci_status_mcp.shutil.which", return_value="/usr/bin/gh")
    @patch("tools.ci_status_mcp.subprocess.run")
    def test_real_ci_status_auth_error_blocks(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=1, stderr="gh: auth error")
        result = run_ci_status_tool("test.ci_status.read", "github_actions", "owner/repo")
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("auth error", result["message"])

    @patch("tools.ci_status_mcp.shutil.which", return_value="/usr/bin/gh")
    @patch("tools.ci_status_mcp.subprocess.run")
    def test_invalid_json_handled_safely(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(returncode=0, stdout="{invalid json")
        result = run_ci_status_tool("test.ci_status.read", "github_actions", "owner/repo")
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("Invalid JSON", result["message"])

    @patch("tools.ci_status_mcp.shutil.which", return_value="/usr/bin/gh")
    @patch("tools.ci_status_mcp.subprocess.run")
    def test_secret_like_ci_content_redacted(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([
                {"name": "secret token: sk-ant-api03-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12", "status": "completed"}
            ])
        )
        result = run_ci_status_tool("test.ci_status.read", "github_actions", "owner/repo")
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("secret-like content", result["message"].lower())
