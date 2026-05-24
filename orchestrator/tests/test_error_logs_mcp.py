from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from tools.error_logs_mcp import (
    MockErrorLogsClient,
    format_error_logs_result,
    run_error_logs_tool,
)


class ErrorLogsMCPTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.project_root = self.approved_root / "project"
        self.project_root.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_mock_error_issue_read_returns_context_block(self) -> None:
        client = MockErrorLogsClient(
            issues={
                ("mock", "demo-app", 17): {
                    "title": "Null pointer in planner",
                    "status": "open",
                    "summary": "Planner crashed on empty context.",
                    "stack_trace": "Traceback line 1\nTraceback line 2\nTraceback line 3",
                }
            }
        )

        result = run_error_logs_tool(
            "error_monitoring.issue.read",
            "mock",
            project_key="demo-app",
            issue_id=17,
            client=client,
        )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertEqual(result["content_summary"], "Issue #17: Null pointer in planner")
        self.assertEqual(len(result["context_blocks"]), 1)
        self.assertEqual(result["context_blocks"][0]["source_type"], "error_monitoring")

    def test_mock_stack_trace_content_is_safely_summarized(self) -> None:
        stack_trace = "\n".join(f"line {index}" for index in range(1, 10))
        client = MockErrorLogsClient(
            issues={
                ("mock", "demo-app", 5): {
                    "title": "Planner failure",
                    "status": "open",
                    "summary": "Planner failed.",
                    "stack_trace": stack_trace,
                }
            }
        )

        result = run_error_logs_tool(
            "error_monitoring.issue.read",
            "mock",
            project_key="demo-app",
            issue_id=5,
            client=client,
        )

        raw_content = str(result["raw_content"])
        self.assertIn("Stack trace summary:", raw_content)
        self.assertIn("(9 total line(s))", raw_content)
        self.assertNotIn("line 9", raw_content)

    def test_local_log_read_works_for_approved_path(self) -> None:
        log_path = self.project_root / "logs" / "dev.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("Server started\nReady\n", encoding="utf-8")

        result = run_error_logs_tool(
            "local.dev_logs.read",
            "local",
            project_path=self.project_root,
            log_path=log_path,
            approved_paths=[str(self.approved_root)],
        )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertIn("Local log: dev.log", result["content_summary"])
        self.assertIn("Server started", str(result["raw_content"]))

    def test_secret_like_local_log_is_blocked_redacted(self) -> None:
        secret_value = "super-secret-token-123"
        log_path = self.project_root / "logs" / "dev.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(f"API_TOKEN={secret_value}\n", encoding="utf-8")

        result = run_error_logs_tool(
            "local.dev_logs.read",
            "local",
            project_path=self.project_root,
            log_path=log_path,
            approved_paths=[str(self.approved_root)],
        )
        formatted = format_error_logs_result(result)

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIsNone(result["raw_content"])
        self.assertNotIn(secret_value, formatted)
        self.assertIn("blocked", formatted.lower())

    def test_unapproved_log_path_blocks(self) -> None:
        outside_log_path = self.root / "outside" / "dev.log"
        outside_log_path.parent.mkdir(parents=True, exist_ok=True)
        outside_log_path.write_text("outside\n", encoding="utf-8")

        result = run_error_logs_tool(
            "local.dev_logs.read",
            "local",
            project_path=self.project_root,
            log_path=outside_log_path,
            approved_paths=[str(self.approved_root)],
        )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("outside approved paths", result["message"])

    def test_invalid_provider_blocks(self) -> None:
        result = run_error_logs_tool(
            "error_monitoring.issue.read",
            "invalid-provider",
            issue_id=1,
        )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("Unsupported provider", result["message"])

    def test_unsafe_token_env_var_blocks(self) -> None:
        result = run_error_logs_tool(
            "error_monitoring.issue.read",
            "sentry",
            issue_id=8,
            token_env_var="sk-live-secret",
        )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("environment variable name is not safe", result["message"])

    def test_missing_token_does_not_crash_and_does_not_print_raw_token(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result = run_error_logs_tool(
                "error_monitoring.issue.read",
                "sentry",
                issue_id=8,
                token_env_var="ERROR_MONITORING_TOKEN",
            )
        formatted = format_error_logs_result(result)

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("ERROR_MONITORING_TOKEN", result["message"])
        self.assertNotIn("sk_", formatted)
        self.assertIn("No raw token value was read or printed.", formatted)

    @patch("tools.error_logs_mcp.urllib.request.urlopen")
    def test_real_sentry_client_returns_issue(self, mock_urlopen) -> None:
        import json
        from unittest.mock import MagicMock
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "title": "Database connection failed",
            "status": "unresolved",
            "culprit": "db.py in connect",
            "metadata": {"value": "Traceback...\nTimeout"}
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        with patch.dict(os.environ, {"ERROR_MONITORING_TOKEN": "safe-token"}):
            result = run_error_logs_tool(
                "error_monitoring.issue.read",
                "sentry",
                issue_id=9,
                token_env_var="ERROR_MONITORING_TOKEN",
            )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertIn("Database connection failed", result["content_summary"])
        self.assertIn("Traceback...", str(result["raw_content"]))

    def test_local_log_search_finds_query(self) -> None:
        log_path = self.project_root / "logs" / "dev.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("Server started\nError: TypeError on line 4\nReady\n", encoding="utf-8")

        result = run_error_logs_tool(
            "local.dev_logs.search",
            "local",
            project_path=self.project_root,
            log_path=log_path,
            query="TypeError",
            approved_paths=[str(self.approved_root)],
        )

        self.assertTrue(result["executed"])
        self.assertIn("dev.log:2 - Error: TypeError on line 4", str(result["raw_content"]))

    def test_local_log_search_missing_query_blocks(self) -> None:
        log_path = self.project_root / "logs" / "dev.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("Server started\n", encoding="utf-8")

        result = run_error_logs_tool(
            "local.dev_logs.search",
            "local",
            project_path=self.project_root,
            log_path=log_path,
            approved_paths=[str(self.approved_root)],
        )

        self.assertFalse(result["executed"])
        self.assertIn("query is required", result["message"])

    def test_local_log_read_blocks_unsupported_extension(self) -> None:
        log_path = self.project_root / "logs" / "binary.bin"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("Server started\n", encoding="utf-8")

        result = run_error_logs_tool(
            "local.dev_logs.read",
            "local",
            project_path=self.project_root,
            log_path=log_path,
            approved_paths=[str(self.approved_root)],
        )

        self.assertFalse(result["executed"])
        self.assertIn("supported log file", result["message"])

    def test_no_file_write_occurs_for_local_log_read(self) -> None:
        log_path = self.project_root / "logs" / "dev.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        original_content = "Server started\n"
        log_path.write_text(original_content, encoding="utf-8")

        run_error_logs_tool(
            "local.dev_logs.read",
            "local",
            project_path=self.project_root,
            log_path=log_path,
            approved_paths=[str(self.approved_root)],
        )

        self.assertEqual(log_path.read_text(encoding="utf-8"), original_content)


class ErrorLogsMCPCLITests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.project_root = self.approved_root / "project"
        self.project_root.mkdir()
        self.log_path = self.project_root / "logs" / "dev.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("Server started\nReady\n", encoding="utf-8")
        self.fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": [str(self.approved_root)],
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cli_error_logs_read_works_for_local_logs(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "write_ai_brain_memory") as mocked_ai_brain_write:
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--error-logs-read",
                            "--error-tool-name",
                            "local.dev_logs.read",
                            "--error-provider",
                            "local",
                            "--project",
                            str(self.project_root),
                            "--error-log-path",
                            str(self.log_path),
                        ]
                    )

        output = stdout.getvalue()
        self.assertIn("Executed: yes", output)
        self.assertIn("Tool name: local.dev_logs.read", output)
        self.assertIn("Provider: local", output)
        self.assertIn("Context blocks:", output)
        mocked_ai_brain_write.assert_not_called()
