from contextlib import redirect_stdout
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

import cli
from core.safety import format_safety_scan, guard_text_output, scan_text_for_secrets


class SafetyScanTests(TestCase):
    def test_detects_api_key_token_password_and_service_key_patterns(self) -> None:
        text = "\n".join(
            [
                'OPENAI_API_KEY="sk-live-1234567890"',
                "Authorization: Bearer abcdefghijklmnop",
                'DB_PASSWORD="hunter2"',
                "SUPABASE_SERVICE_ROLE_KEY=service-role-secret-123",
            ]
        )

        result = scan_text_for_secrets(text)
        summaries = [finding["summary"] for finding in result["findings"]]

        self.assertTrue(result["has_findings"])
        self.assertEqual(result["risk_level"], "high")
        self.assertGreaterEqual(len(result["findings"]), 4)
        self.assertTrue(any("API key-style assignment" in summary for summary in summaries))
        self.assertTrue(any("bearer token-style content" in summary for summary in summaries))
        self.assertTrue(any("password-style assignment" in summary for summary in summaries))
        self.assertTrue(any("service/admin secret-style assignment" in summary for summary in summaries))

    def test_detects_private_key_block(self) -> None:
        text = "-----BEGIN PRIVATE KEY-----\nabc123\n-----END PRIVATE KEY-----"

        result = scan_text_for_secrets(text)

        self.assertTrue(result["has_findings"])
        self.assertEqual(result["risk_level"], "high")
        self.assertEqual(result["findings"][0]["type"], "private_key_block")

    def test_returns_no_findings_for_safe_text(self) -> None:
        result = scan_text_for_secrets("Fix telemetry bug in the CLI status output.")

        self.assertFalse(result["has_findings"])
        self.assertEqual(result["risk_level"], "low")
        self.assertEqual(result["findings"], [])

    def test_does_not_leak_raw_secret_in_findings_or_formatted_output(self) -> None:
        raw_secret = "super-secret-value-987654321"
        text = f'API_TOKEN="{raw_secret}"'

        result = scan_text_for_secrets(text)
        formatted_output = format_safety_scan(result)

        self.assertNotIn(raw_secret, formatted_output)
        for finding in result["findings"]:
            self.assertNotIn(raw_secret, str(finding))

    def test_reusable_guard_allows_safe_text(self) -> None:
        result = guard_text_output(
            "Fix telemetry bug in the CLI status output.",
            "Planner report output",
        )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["risk_level"], "low")
        self.assertFalse(result["should_block_save"])
        self.assertIn("allowed", result["safe_message"])

    def test_reusable_guard_blocks_secret_like_text(self) -> None:
        result = guard_text_output(
            'SUPABASE_SERVICE_ROLE_KEY="service-role-secret-123"',
            "Diff review output",
        )

        self.assertFalse(result["allowed"])
        self.assertEqual(result["risk_level"], "high")
        self.assertTrue(result["should_block_save"])
        self.assertGreaterEqual(len(result["findings"]), 1)

    def test_reusable_guard_safe_message_is_redacted(self) -> None:
        raw_secret = "super-secret-value-987654321"
        result = guard_text_output(
            f'API_TOKEN="{raw_secret}"',
            "Codex prompt output",
        )

        self.assertNotIn(raw_secret, result["safe_message"])
        for finding in result["findings"]:
            self.assertNotIn(raw_secret, str(finding))


class SafetyScanCliTests(TestCase):
    def setUp(self) -> None:
        self.fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": ["/tmp/ai-brain", "reports"],
        }
        self.fake_core_status = {
            "checked_count": 4,
            "found_count": 4,
            "missing_count": 0,
            "missing_files": {},
        }

    def test_scan_text_prints_redacted_safe_summaries(self) -> None:
        raw_secret = "super-secret-value-987654321"
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--scan-text", f'API_TOKEN="{raw_secret}"'])

        output = stdout.getvalue()

        self.assertIn("Secret-like findings: yes", output)
        self.assertIn("Finding: Detected token-style assignment", output)
        self.assertNotIn(raw_secret, output)

    def test_scan_text_does_not_require_project_or_git(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with patch.object(cli, "inspect_project_context") as mocked_context:
                    with patch.object(cli, "inspect_git_state") as mocked_git:
                        with redirect_stdout(stdout):
                            cli.run(["--scan-text", "safe text"])

        output = stdout.getvalue()

        self.assertIn("Project context check: not run by default", output)
        self.assertIn("Secret-like findings: no", output)
        mocked_context.assert_not_called()
        mocked_git.assert_not_called()
