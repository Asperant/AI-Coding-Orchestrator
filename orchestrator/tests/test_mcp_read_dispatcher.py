from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from tools.git_gateway import GitGatewayError
from tools.mcp_read_dispatcher import (
    format_mcp_read_dispatch_result,
    run_mcp_read_tool,
)


class MCPReadDispatcherTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.approved_file = self.approved_root / "notes.txt"
        self.approved_file.write_text("safe text", encoding="utf-8")
        self.secret_file = self.approved_root / "secret.env"
        self.secret_file.write_text("API_TOKEN=super-secret-token-123\n", encoding="utf-8")
        self.outside_root = self.root / "outside"
        self.outside_root.mkdir()
        self.outside_file = self.outside_root / "outside.txt"
        self.outside_file.write_text("nope", encoding="utf-8")
        self.project_root = self.approved_root / "project"
        self.project_root.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_filesystem_read_allowed_path_works(self) -> None:
        result = run_mcp_read_tool(
            "filesystem.read_file",
            str(self.approved_file),
            [str(self.approved_root)],
        )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertEqual(result["message"], "filesystem.read_file completed successfully.")
        self.assertEqual(result["output_text"], "safe text")

    def test_filesystem_read_secret_like_content_is_blocked_redacted(self) -> None:
        result = run_mcp_read_tool(
            "filesystem.read_file",
            str(self.secret_file),
            [str(self.approved_root)],
        )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("secret-like content was detected", result["message"])
        self.assertNotIn("super-secret-token-123", result["output_text"])
        self.assertIn("blocked", result["output_text"].lower())

    def test_unapproved_path_blocks(self) -> None:
        result = run_mcp_read_tool(
            "filesystem.read_file",
            str(self.outside_file),
            [str(self.approved_root)],
        )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("Target path is outside approved paths:", result["message"])

    def test_git_status_read_works_with_mocked_gateway(self) -> None:
        git_state = {
            "is_git_repo": True,
            "changed_files": ["src/module.py"],
            "status_summary": "1 changed file(s).",
            "diff_text": "",
            "diff_present": False,
        }

        with patch("tools.mcp_read_dispatcher.inspect_git_state", return_value=git_state) as mocked_git:
            result = run_mcp_read_tool(
                "git.status",
                None,
                [str(self.approved_root)],
                project_path=str(self.project_root),
            )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertIn("Status summary: 1 changed file(s).", result["output_text"])
        self.assertIn("Changed files: src/module.py", result["output_text"])
        mocked_git.assert_called_once()

    def test_git_diff_read_works_with_mocked_gateway(self) -> None:
        git_state = {
            "is_git_repo": True,
            "changed_files": ["src/module.py"],
            "status_summary": "1 changed file(s).",
            "diff_text": "diff --git a/src/module.py b/src/module.py\n+print('ok')\n",
            "diff_present": True,
        }

        with patch("tools.mcp_read_dispatcher.inspect_git_state", return_value=git_state) as mocked_git:
            result = run_mcp_read_tool(
                "git.diff",
                None,
                [str(self.approved_root)],
                project_path=str(self.project_root),
            )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertIn("diff --git", result["output_text"])
        mocked_git.assert_called_once()

    def test_git_diff_secret_like_content_is_blocked_redacted(self) -> None:
        git_state = {
            "is_git_repo": True,
            "changed_files": [".env"],
            "status_summary": "1 changed file(s).",
            "diff_text": "diff --git a/.env b/.env\n+API_TOKEN=super-secret-token-123\n",
            "diff_present": True,
        }

        with patch("tools.mcp_read_dispatcher.inspect_git_state", return_value=git_state):
            result = run_mcp_read_tool(
                "git.diff",
                None,
                [str(self.approved_root)],
                project_path=str(self.project_root),
            )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("secret-like content was detected", result["message"])
        self.assertNotIn("super-secret-token-123", result["output_text"])

    def test_git_log_read_works_with_mocked_gateway(self) -> None:
        git_log = {
            "is_git_repo": True,
            "entry_count": 2,
            "log_text": "abc123 First commit\ndef456 Second commit",
        }

        with patch("tools.mcp_read_dispatcher.inspect_git_log", return_value=git_log) as mocked_log:
            result = run_mcp_read_tool(
                "git.log",
                str(self.project_root),
                [str(self.approved_root)],
            )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertIn("abc123 First commit", result["output_text"])
        mocked_log.assert_called_once()

    def test_git_log_no_repo_returns_clear_error(self) -> None:
        with patch(
            "tools.mcp_read_dispatcher.inspect_git_log",
            side_effect=GitGatewayError("Not a git repository."),
        ):
            result = run_mcp_read_tool(
                "git.log",
                str(self.project_root),
                [str(self.approved_root)],
            )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("Not a git repository.", result["message"])

    def test_git_log_secret_like_output_is_blocked_redacted(self) -> None:
        git_log = {
            "is_git_repo": True,
            "entry_count": 1,
            "log_text": "abc123 API_TOKEN=super-secret-token-123",
        }

        with patch("tools.mcp_read_dispatcher.inspect_git_log", return_value=git_log):
            result = run_mcp_read_tool(
                "git.log",
                str(self.project_root),
                [str(self.approved_root)],
            )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("secret-like content was detected", result["message"])
        self.assertNotIn("super-secret-token-123", result["output_text"])

    def test_write_or_destructive_registered_tool_is_blocked(self) -> None:
        result = run_mcp_read_tool(
            "github.issue.comment",
            None,
            [str(self.approved_root)],
        )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertEqual(result["decision"]["registry_status"], "blocked")

    def test_unknown_tool_is_blocked(self) -> None:
        result = run_mcp_read_tool(
            "unknown.tool",
            None,
            [str(self.approved_root)],
        )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertEqual(result["decision"]["gateway_status"], "not run")

    def test_formatter_includes_dispatch_fields(self) -> None:
        result = run_mcp_read_tool(
            "filesystem.read_file",
            str(self.approved_file),
            [str(self.approved_root)],
        )
        output = format_mcp_read_dispatch_result(result)

        self.assertIn("Tool name: filesystem.read_file", output)
        self.assertIn("Executed: yes", output)
        self.assertIn("Decision allowed: yes", output)
        self.assertIn("Output text:", output)


class MCPReadDispatcherCliTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.approved_file = self.approved_root / "notes.txt"
        self.approved_file.write_text("safe text", encoding="utf-8")
        self.fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": [str(self.approved_root)],
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cli_mcp_run_read_filesystem_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "evaluate_mcp_tool_request") as mocked_legacy_gateway:
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--mcp-run-read",
                            "--mcp-tool-name",
                            "filesystem.read_file",
                            "--mcp-target-path",
                            str(self.approved_file),
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn("Tool name: filesystem.read_file", output)
        self.assertIn("Executed: yes", output)
        self.assertIn("safe text", output)
        mocked_legacy_gateway.assert_not_called()

    def test_cli_mcp_run_read_git_diff_works_with_mocked_gateway(self) -> None:
        stdout = StringIO()
        git_state = {
            "is_git_repo": True,
            "changed_files": ["src/module.py"],
            "status_summary": "1 changed file(s).",
            "diff_text": "diff --git a/src/module.py b/src/module.py\n+print('ok')\n",
            "diff_present": True,
        }

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch("tools.mcp_read_dispatcher.inspect_git_state", return_value=git_state) as mocked_git:
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--mcp-run-read",
                            "--mcp-tool-name",
                            "git.diff",
                            "--project",
                            str(self.approved_root),
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn("Tool name: git.diff", output)
        self.assertIn("Executed: yes", output)
        self.assertIn("diff --git", output)
        mocked_git.assert_called_once()

    def test_cli_mcp_run_read_git_log_works_with_mocked_gateway(self) -> None:
        stdout = StringIO()
        git_log = {
            "is_git_repo": True,
            "entry_count": 1,
            "log_text": "abc123 First commit",
        }

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch("tools.mcp_read_dispatcher.inspect_git_log", return_value=git_log) as mocked_log:
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--mcp-run-read",
                            "--mcp-tool-name",
                            "git.log",
                            "--mcp-target-path",
                            str(self.approved_root),
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn("Tool name: git.log", output)
        self.assertIn("Executed: yes", output)
        self.assertIn("abc123 First commit", output)
        mocked_log.assert_called_once()
