from contextlib import redirect_stdout
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

import cli
from agents.llm_provider_config import format_llm_provider_config, load_llm_provider_config


class LlmProviderConfigTests(TestCase):
    def test_default_provider_is_disabled(self) -> None:
        result = load_llm_provider_config(config={}, env={})

        self.assertEqual(result["provider"], "disabled")
        self.assertFalse(result["enabled"])
        self.assertFalse(result["available"])
        self.assertFalse(result["api_key_present"])
        self.assertEqual(result["risk_level"], "low")

    def test_allowed_provider_with_env_key_present_is_available(self) -> None:
        result = load_llm_provider_config(
            config={
                "llm_provider": {
                    "provider": "openai",
                    "model": "gpt-5",
                    "api_key_env_var": "OPENAI_API_KEY",
                    "enabled": True,
                    "timeout_seconds": 60,
                    "max_context_chars": 12000,
                }
            },
            env={"OPENAI_API_KEY": "sk-live-secret-123"},
        )

        self.assertEqual(result["provider"], "openai")
        self.assertTrue(result["enabled"])
        self.assertTrue(result["available"])
        self.assertTrue(result["api_key_present"])
        self.assertEqual(result["api_key_env_var"], "OPENAI_API_KEY")

    def test_missing_env_key_is_unavailable_but_raw_key_not_printed(self) -> None:
        secret_value = "sk-live-secret-123"
        result = load_llm_provider_config(
            config={
                "llm_provider": {
                    "provider": "openai",
                    "model": "gpt-5",
                    "api_key_env_var": "OPENAI_API_KEY",
                    "enabled": True,
                }
            },
            env={},
        )
        formatted = format_llm_provider_config(result)

        self.assertFalse(result["available"])
        self.assertIn("missing or empty", formatted)
        self.assertNotIn(secret_value, formatted)

    def test_unknown_provider_is_blocked(self) -> None:
        result = load_llm_provider_config(
            config={
                "llm_provider": {
                    "provider": "anthropic",
                    "model": "claude",
                    "enabled": True,
                }
            },
            env={},
        )

        self.assertEqual(result["risk_level"], "high")
        self.assertIn("Unknown LLM provider", " ".join(result["blocked_reasons"]))

    def test_invalid_timeout_and_max_context_block(self) -> None:
        result = load_llm_provider_config(
            config={
                "llm_provider": {
                    "provider": "mock",
                    "model": "mock-model",
                    "enabled": True,
                    "timeout_seconds": 0,
                    "max_context_chars": 50000,
                }
            },
            env={},
        )

        self.assertFalse(result["available"])
        blocked = " ".join(result["blocked_reasons"])
        self.assertIn("Timeout must be greater than zero", blocked)
        self.assertIn("Max context chars must be greater than zero", blocked)

    def test_raw_api_key_value_never_appears_in_output(self) -> None:
        secret_value = "sk-live-secret-123"
        result = load_llm_provider_config(
            config={
                "llm_provider": {
                    "provider": "openai",
                    "model": "gpt-5",
                    "api_key_env_var": secret_value,
                    "enabled": True,
                }
            },
            env={"OPENAI_API_KEY": secret_value},
        )
        formatted = format_llm_provider_config(result)

        self.assertNotIn(secret_value, formatted)
        self.assertIn("API key env var name is invalid or unsafe.", formatted)

    def test_mock_provider_can_be_available_without_api_key(self) -> None:
        result = load_llm_provider_config(
            config={
                "llm_provider": {
                    "provider": "mock",
                    "model": "mock-model",
                    "enabled": True,
                }
            },
            env={},
        )

        self.assertTrue(result["available"])
        self.assertFalse(result["api_key_present"])

    def test_gemini_provider_with_env_key_present_is_available(self) -> None:
        result = load_llm_provider_config(
            config={
                "llm_provider": {
                    "provider": "gemini",
                    "model": "gemini-2.5-flash",
                    "api_key_env_var": "GEMINI_API_KEY",
                    "enabled": True,
                }
            },
            env={"GEMINI_API_KEY": "AIza-secret-123"},
        )

        self.assertEqual(result["provider"], "gemini")
        self.assertTrue(result["enabled"])
        self.assertTrue(result["available"])
        self.assertTrue(result["api_key_present"])
        self.assertEqual(result["api_key_env_var"], "GEMINI_API_KEY")


class LlmProviderConfigCliTests(TestCase):
    def setUp(self) -> None:
        self.fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": ["/tmp"],
            "llm_provider": {
                "provider": "disabled",
                "model": "",
                "enabled": False,
            },
        }
        self.fake_core_status = {
            "checked_count": 4,
            "found_count": 4,
            "missing_count": 0,
            "missing_files": {},
        }

    def test_cli_prints_safe_provider_status(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with patch.object(cli, "execute_codex_task_with_post_review") as mock_execute_codex:
                    with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-live-secret-123"}, clear=False):
                        with redirect_stdout(stdout):
                            cli.run(
                                [
                                    "--llm-provider-check",
                                    "--llm-provider",
                                    "openai",
                                    "--llm-model",
                                    "gpt-5",
                                    "--llm-api-key-env",
                                    "OPENAI_API_KEY",
                                    "--llm-enabled",
                                ]
                            )

        output = stdout.getvalue()

        self.assertIn("Provider: openai", output)
        self.assertIn("Model: gpt-5", output)
        self.assertIn("Enabled: yes", output)
        self.assertIn("Available: yes", output)
        self.assertIn("API key present: yes", output)
        self.assertIn("API key env var: OPENAI_API_KEY", output)
        self.assertNotIn("sk-live-secret-123", output)
        mock_execute_codex.assert_not_called()

    def test_cli_default_provider_is_disabled(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--llm-provider-check"])

        output = stdout.getvalue()

        self.assertIn("Provider: disabled", output)
        self.assertIn("Available: no", output)
