from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import cli
from agents.llm_agent_adapter import (
    DisabledLLMAdapter,
    MockLLMAdapter,
    OpenAILLMAdapter,
    format_llm_agent_adapter_result,
)
from agents.llm_agent_contract import evaluate_llm_agent_contract
from agents.llm_provider_config import load_llm_provider_config


class LlmAgentAdapterTests(TestCase):
    def build_openai_provider_config(
        self,
        *,
        env: dict[str, str] | None = None,
        enabled: bool = True,
    ) -> dict[str, object]:
        return load_llm_provider_config(
            {
                "llm_provider": {
                    "provider": "openai",
                    "model": "gpt-5",
                    "api_key_env_var": "OPENAI_API_KEY",
                    "enabled": enabled,
                    "timeout_seconds": 60,
                    "max_context_chars": 12000,
                }
            },
            env=env or {},
        )

    def test_disabled_adapter_refuses_execution(self) -> None:
        contract_result = evaluate_llm_agent_contract(
            "Planner",
            "review this project",
            approval_confirmed=True,
            llm_enabled=True,
        )

        result = DisabledLLMAdapter().run_agent(
            agent_role="Planner",
            task_text="review this project",
            contract_result=contract_result,
        )

        self.assertFalse(result["executed"])
        self.assertTrue(result["fallback_required"])
        self.assertIn("Disabled adapter refused execution", result["output_text"])
        self.assertIn("DisabledLLMAdapter", result["error"])

    def test_mock_adapter_executes_only_when_contract_passes(self) -> None:
        contract_result = evaluate_llm_agent_contract(
            "Reviewer",
            "review the diff",
            approval_confirmed=True,
            llm_enabled=True,
        )

        result = MockLLMAdapter().run_agent(
            agent_role="Reviewer",
            task_text="review the diff",
            contract_result=contract_result,
        )

        self.assertTrue(result["executed"])
        self.assertFalse(result["fallback_required"])
        self.assertEqual(result["agent_role"], "Reviewer")
        self.assertIn("Mock Reviewer output", result["output_text"])
        self.assertIsNone(result["error"])

    def test_mock_adapter_blocks_when_contract_fails(self) -> None:
        contract_result = evaluate_llm_agent_contract(
            "Planner",
            "review this project",
            approval_confirmed=False,
            llm_enabled=True,
        )

        result = MockLLMAdapter().run_agent(
            agent_role="Planner",
            task_text="review this project",
            contract_result=contract_result,
        )

        self.assertFalse(result["executed"])
        self.assertTrue(result["fallback_required"])
        self.assertIn("contract did not pass", result["output_text"])

    def test_secret_like_task_does_not_leak_raw_secret(self) -> None:
        secret_value = "super-secret-token-123"
        contract_result = evaluate_llm_agent_contract(
            "Security",
            f"review auth issue with API_TOKEN={secret_value}",
            approval_confirmed=True,
            llm_enabled=True,
        )

        result = MockLLMAdapter().run_agent(
            agent_role="Security",
            task_text=f"review auth issue with API_TOKEN={secret_value}",
            contract_result=contract_result,
        )
        formatted = format_llm_agent_adapter_result(result)

        self.assertNotIn(secret_value, formatted)
        self.assertIn("fallback", formatted.lower())

    def test_secret_like_context_does_not_leak_raw_secret(self) -> None:
        secret_value = "super-secret-token-123"
        contract_result = evaluate_llm_agent_contract(
            "Reviewer",
            "review this project",
            context_text=f"API_TOKEN={secret_value}",
            approval_confirmed=True,
            llm_enabled=True,
        )

        result = MockLLMAdapter().run_agent(
            agent_role="Reviewer",
            task_text="review this project",
            context_text=f"API_TOKEN={secret_value}",
            contract_result=contract_result,
        )
        formatted = format_llm_agent_adapter_result(result)

        self.assertNotIn(secret_value, formatted)
        self.assertIn("contract blocked", formatted.lower())

    def test_adapter_output_is_formatted(self) -> None:
        contract_result = evaluate_llm_agent_contract(
            "Architect",
            "assess the codebase",
            approval_confirmed=True,
            llm_enabled=True,
        )
        result = MockLLMAdapter().run_agent(
            agent_role="Architect",
            task_text="assess the codebase",
            contract_result=contract_result,
        )
        formatted = format_llm_agent_adapter_result(result)

        self.assertIn("Executed:", formatted)
        self.assertIn("Fallback required:", formatted)
        self.assertIn("Agent role:", formatted)
        self.assertIn("Output text:", formatted)
        self.assertIn("Safety notes:", formatted)
        self.assertIn("Error:", formatted)

    def test_openai_adapter_refuses_when_provider_disabled(self) -> None:
        contract_result = evaluate_llm_agent_contract(
            "Planner",
            "review this project",
            approval_confirmed=True,
            llm_enabled=True,
        )
        provider_config = self.build_openai_provider_config(
            env={"OPENAI_API_KEY": "sk-live-secret-123"},
            enabled=False,
        )

        result = OpenAILLMAdapter().run_agent(
            agent_role="Planner",
            task_text="review this project",
            contract_result=contract_result,
            provider_config=provider_config,
        )

        self.assertFalse(result["executed"])
        self.assertTrue(result["fallback_required"])
        self.assertIn("provider is disabled", result["output_text"].lower())

    def test_openai_adapter_refuses_when_contract_fails(self) -> None:
        contract_result = evaluate_llm_agent_contract(
            "Planner",
            "review this project",
            approval_confirmed=False,
            llm_enabled=True,
        )
        provider_config = self.build_openai_provider_config(
            env={"OPENAI_API_KEY": "sk-live-secret-123"},
        )

        result = OpenAILLMAdapter().run_agent(
            agent_role="Planner",
            task_text="review this project",
            contract_result=contract_result,
            provider_config=provider_config,
        )

        self.assertFalse(result["executed"])
        self.assertIn("contract did not pass", result["output_text"].lower())

    def test_openai_adapter_refuses_when_env_key_missing(self) -> None:
        contract_result = evaluate_llm_agent_contract(
            "Planner",
            "review this project",
            approval_confirmed=True,
            llm_enabled=True,
        )
        provider_config = self.build_openai_provider_config(env={})

        result = OpenAILLMAdapter().run_agent(
            agent_role="Planner",
            task_text="review this project",
            contract_result=contract_result,
            provider_config=provider_config,
        )

        self.assertFalse(result["executed"])
        self.assertIn("provider is unavailable", result["output_text"].lower())

    def test_openai_adapter_handles_missing_sdk(self) -> None:
        contract_result = evaluate_llm_agent_contract(
            "Planner",
            "review this project",
            approval_confirmed=True,
            llm_enabled=True,
        )
        provider_config = self.build_openai_provider_config(
            env={"OPENAI_API_KEY": "sk-live-secret-123"},
        )

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-live-secret-123"}, clear=False):
            with patch("agents.llm_agent_adapter._import_openai_module", side_effect=ImportError):
                result = OpenAILLMAdapter().run_agent(
                    agent_role="Planner",
                    task_text="review this project",
                    contract_result=contract_result,
                    provider_config=provider_config,
                )

        self.assertFalse(result["executed"])
        self.assertIn("sdk is not installed", result["output_text"].lower())

    def test_openai_adapter_mocked_successful_api_response_returns_normalized_output(self) -> None:
        contract_result = evaluate_llm_agent_contract(
            "Reviewer",
            "review the diff",
            approval_confirmed=True,
            llm_enabled=True,
        )
        provider_config = self.build_openai_provider_config(
            env={"OPENAI_API_KEY": "sk-live-secret-123"},
        )

        response = SimpleNamespace(output_text="Concise safe agent summary.")
        client = SimpleNamespace(responses=SimpleNamespace(create=lambda **_: response))
        module = SimpleNamespace(OpenAI=lambda **_: client)

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-live-secret-123"}, clear=False):
            with patch("agents.llm_agent_adapter._import_openai_module", return_value=module):
                result = OpenAILLMAdapter().run_agent(
                    agent_role="Reviewer",
                    task_text="review the diff",
                    contract_result=contract_result,
                    provider_config=provider_config,
                )

        self.assertTrue(result["executed"])
        self.assertFalse(result["fallback_required"])
        self.assertEqual(result["agent_role"], "Reviewer")
        self.assertIn("Concise safe agent summary.", result["output_text"])

    def test_openai_adapter_mocked_api_error_returns_safe_fallback(self) -> None:
        contract_result = evaluate_llm_agent_contract(
            "Reviewer",
            "review the diff",
            approval_confirmed=True,
            llm_enabled=True,
        )
        provider_config = self.build_openai_provider_config(
            env={"OPENAI_API_KEY": "sk-live-secret-123"},
        )

        client = SimpleNamespace(
            responses=SimpleNamespace(create=lambda **_: (_ for _ in ()).throw(RuntimeError("boom")))
        )
        module = SimpleNamespace(OpenAI=lambda **_: client)

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-live-secret-123"}, clear=False):
            with patch("agents.llm_agent_adapter._import_openai_module", return_value=module):
                result = OpenAILLMAdapter().run_agent(
                    agent_role="Reviewer",
                    task_text="review the diff",
                    contract_result=contract_result,
                    provider_config=provider_config,
                )

        self.assertFalse(result["executed"])
        self.assertIn("failed and fell back safely", result["output_text"].lower())
        self.assertIn("RuntimeError", result["error"])

    def test_openai_adapter_secret_like_model_output_is_blocked(self) -> None:
        contract_result = evaluate_llm_agent_contract(
            "Security",
            "review auth issue",
            approval_confirmed=True,
            llm_enabled=True,
        )
        provider_config = self.build_openai_provider_config(
            env={"OPENAI_API_KEY": "sk-live-secret-123"},
        )

        response = SimpleNamespace(output_text="API_TOKEN=super-secret-token-123")
        client = SimpleNamespace(responses=SimpleNamespace(create=lambda **_: response))
        module = SimpleNamespace(OpenAI=lambda **_: client)

        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-live-secret-123"}, clear=False):
            with patch("agents.llm_agent_adapter._import_openai_module", return_value=module):
                result = OpenAILLMAdapter().run_agent(
                    agent_role="Security",
                    task_text="review auth issue",
                    contract_result=contract_result,
                    provider_config=provider_config,
                )
        formatted = format_llm_agent_adapter_result(result)

        self.assertFalse(result["executed"])
        self.assertNotIn("super-secret-token-123", formatted)
        self.assertIn("secret-like content", formatted.lower())

    def test_openai_adapter_raw_api_key_never_appears_in_output(self) -> None:
        secret_value = "sk-live-secret-123"
        contract_result = evaluate_llm_agent_contract(
            "Planner",
            "review this project",
            approval_confirmed=True,
            llm_enabled=True,
        )
        provider_config = self.build_openai_provider_config(env={"OPENAI_API_KEY": secret_value})

        with patch("agents.llm_agent_adapter._import_openai_module", side_effect=ImportError):
            result = OpenAILLMAdapter().run_agent(
                agent_role="Planner",
                task_text="review this project",
                contract_result=contract_result,
                provider_config=provider_config,
            )
        formatted = format_llm_agent_adapter_result(result)

        self.assertNotIn(secret_value, formatted)

    def build_gemini_provider_config(
        self,
        *,
        env: dict[str, str] | None = None,
        enabled: bool = True,
    ) -> dict[str, object]:
        return load_llm_provider_config(
            {
                "llm_provider": {
                    "provider": "gemini",
                    "model": "gemini-2.5-flash",
                    "api_key_env_var": "GEMINI_API_KEY",
                    "enabled": enabled,
                    "timeout_seconds": 60,
                    "max_context_chars": 12000,
                }
            },
            env=env or {},
        )

    def test_gemini_adapter_refuses_when_provider_disabled(self) -> None:
        contract_result = evaluate_llm_agent_contract("Planner", "task", approval_confirmed=True, llm_enabled=True)
        provider_config = self.build_gemini_provider_config(env={"GEMINI_API_KEY": "AIza-secret-123"}, enabled=False)
        from agents.llm_agent_adapter import GeminiLLMAdapter
        result = GeminiLLMAdapter().run_agent(agent_role="Planner", task_text="task", contract_result=contract_result, provider_config=provider_config)
        self.assertFalse(result["executed"])
        self.assertIn("provider is disabled", result["output_text"].lower())

    def test_gemini_adapter_refuses_when_contract_fails(self) -> None:
        contract_result = evaluate_llm_agent_contract("Planner", "task", approval_confirmed=False, llm_enabled=True)
        provider_config = self.build_gemini_provider_config(env={"GEMINI_API_KEY": "AIza-secret-123"})
        from agents.llm_agent_adapter import GeminiLLMAdapter
        result = GeminiLLMAdapter().run_agent(agent_role="Planner", task_text="task", contract_result=contract_result, provider_config=provider_config)
        self.assertFalse(result["executed"])
        self.assertIn("contract did not pass", result["output_text"].lower())

    def test_gemini_adapter_refuses_when_env_key_missing(self) -> None:
        contract_result = evaluate_llm_agent_contract("Planner", "task", approval_confirmed=True, llm_enabled=True)
        provider_config = self.build_gemini_provider_config(env={})
        from agents.llm_agent_adapter import GeminiLLMAdapter
        result = GeminiLLMAdapter().run_agent(agent_role="Planner", task_text="task", contract_result=contract_result, provider_config=provider_config)
        self.assertFalse(result["executed"])
        self.assertIn("provider is unavailable", result["output_text"].lower())

    def test_gemini_adapter_handles_missing_sdk(self) -> None:
        contract_result = evaluate_llm_agent_contract("Planner", "task", approval_confirmed=True, llm_enabled=True)
        provider_config = self.build_gemini_provider_config(env={"GEMINI_API_KEY": "AIza-secret-123"})
        from agents.llm_agent_adapter import GeminiLLMAdapter
        with patch.dict("os.environ", {"GEMINI_API_KEY": "AIza-secret-123"}, clear=False):
            with patch("agents.llm_agent_adapter._import_gemini_module", side_effect=ImportError):
                result = GeminiLLMAdapter().run_agent(agent_role="Planner", task_text="task", contract_result=contract_result, provider_config=provider_config)
        self.assertFalse(result["executed"])
        self.assertIn("sdk is not installed", result["output_text"].lower())

    def test_gemini_adapter_mocked_successful_api_response_returns_normalized_output(self) -> None:
        contract_result = evaluate_llm_agent_contract("Reviewer", "task", approval_confirmed=True, llm_enabled=True)
        provider_config = self.build_gemini_provider_config(env={"GEMINI_API_KEY": "AIza-secret-123"})
        from agents.llm_agent_adapter import GeminiLLMAdapter
        
        response = SimpleNamespace(text="Concise safe agent summary.")
        client_instance = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **_: response))
        module = SimpleNamespace(Client=lambda **_: client_instance)

        with patch.dict("os.environ", {"GEMINI_API_KEY": "AIza-secret-123"}, clear=False):
            with patch("agents.llm_agent_adapter._import_gemini_module", return_value=module):
                result = GeminiLLMAdapter().run_agent(agent_role="Reviewer", task_text="task", contract_result=contract_result, provider_config=provider_config)
        
        self.assertTrue(result["executed"])
        self.assertIn("Concise safe agent summary.", result["output_text"])

    def test_gemini_adapter_mocked_api_error_returns_safe_fallback(self) -> None:
        contract_result = evaluate_llm_agent_contract("Reviewer", "task", approval_confirmed=True, llm_enabled=True)
        provider_config = self.build_gemini_provider_config(env={"GEMINI_API_KEY": "AIza-secret-123"})
        from agents.llm_agent_adapter import GeminiLLMAdapter
        
        client_instance = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **_: (_ for _ in ()).throw(RuntimeError("boom"))))
        module = SimpleNamespace(Client=lambda **_: client_instance)

        with patch.dict("os.environ", {"GEMINI_API_KEY": "AIza-secret-123"}, clear=False):
            with patch("agents.llm_agent_adapter._import_gemini_module", return_value=module):
                result = GeminiLLMAdapter().run_agent(agent_role="Reviewer", task_text="task", contract_result=contract_result, provider_config=provider_config)
        
        self.assertFalse(result["executed"])
        self.assertIn("failed and fell back safely", result["output_text"].lower())

    def test_gemini_adapter_secret_like_model_output_is_blocked(self) -> None:
        contract_result = evaluate_llm_agent_contract("Security", "task", approval_confirmed=True, llm_enabled=True)
        provider_config = self.build_gemini_provider_config(env={"GEMINI_API_KEY": "AIza-secret-123"})
        from agents.llm_agent_adapter import GeminiLLMAdapter
        
        response = SimpleNamespace(text="API_TOKEN=super-secret-token-123")
        client_instance = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **_: response))
        module = SimpleNamespace(Client=lambda **_: client_instance)

        with patch.dict("os.environ", {"GEMINI_API_KEY": "AIza-secret-123"}, clear=False):
            with patch("agents.llm_agent_adapter._import_gemini_module", return_value=module):
                result = GeminiLLMAdapter().run_agent(agent_role="Security", task_text="task", contract_result=contract_result, provider_config=provider_config)
        
        self.assertFalse(result["executed"])
        self.assertNotIn("super-secret-token-123", result["output_text"])
        self.assertIn("secret-like content", str(result["error"]).lower())

    def test_gemini_adapter_raw_api_key_never_appears_in_output(self) -> None:
        secret_value = "AIza-secret-123"
        contract_result = evaluate_llm_agent_contract("Planner", "task", approval_confirmed=True, llm_enabled=True)
        provider_config = self.build_gemini_provider_config(env={"GEMINI_API_KEY": secret_value})
        from agents.llm_agent_adapter import GeminiLLMAdapter
        
        with patch("agents.llm_agent_adapter._import_gemini_module", side_effect=ImportError):
            result = GeminiLLMAdapter().run_agent(agent_role="Planner", task_text="task", contract_result=contract_result, provider_config=provider_config)
        formatted = format_llm_agent_adapter_result(result)
        
        self.assertNotIn(secret_value, formatted)

class LlmAgentAdapterCliTests(TestCase):
    def setUp(self) -> None:
        self.fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": ["/tmp"],
        }
        self.fake_core_status = {
            "checked_count": 4,
            "found_count": 4,
            "missing_count": 0,
            "missing_files": {},
        }

    def test_cli_disabled_adapter_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with patch.object(cli, "execute_codex_task_with_post_review") as mock_execute_codex:
                    with redirect_stdout(stdout):
                        cli.run(
                            [
                                "--llm-agent-adapter-check",
                                "--agent-role",
                                "Planner",
                                "--task",
                                "review this project",
                                "--llm-enabled",
                                "--confirm-llm-agent",
                                "--llm-adapter",
                                "disabled",
                            ]
                        )

        output = stdout.getvalue()

        self.assertIn("LLM agent contract:", output)
        self.assertIn("Can run LLM agent: yes", output)
        self.assertIn("LLM agent adapter result:", output)
        self.assertIn("Executed: no", output)
        self.assertIn("Fallback required: yes", output)
        mock_execute_codex.assert_not_called()

    def test_cli_mock_adapter_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with patch.object(cli, "execute_codex_task_with_post_review") as mock_execute_codex:
                    with redirect_stdout(stdout):
                        cli.run(
                            [
                                "--llm-agent-adapter-check",
                                "--agent-role",
                                "Reviewer",
                                "--task",
                                "review the diff",
                                "--llm-enabled",
                                "--confirm-llm-agent",
                                "--llm-adapter",
                                "mock",
                            ]
                        )

        output = stdout.getvalue()

        self.assertIn("Can run LLM agent: yes", output)
        self.assertIn("Executed: yes", output)
        self.assertIn("Mock Reviewer output", output)
        mock_execute_codex.assert_not_called()

    def test_cli_openai_adapter_path_prints_safe_result_with_mocked_sdk(self) -> None:
        stdout = StringIO()
        response = SimpleNamespace(output_text="Concise safe agent summary.")
        client = SimpleNamespace(responses=SimpleNamespace(create=lambda **_: response))
        module = SimpleNamespace(OpenAI=lambda **_: client)

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with patch.object(cli, "execute_codex_task_with_post_review") as mock_execute_codex:
                    with patch("agents.llm_agent_adapter._import_openai_module", return_value=module):
                        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-live-secret-123"}, clear=False):
                            with redirect_stdout(stdout):
                                cli.run(
                                    [
                                        "--llm-agent-adapter-check",
                                        "--agent-role",
                                        "Reviewer",
                                        "--task",
                                        "review the diff",
                                        "--llm-enabled",
                                        "--confirm-llm-agent",
                                        "--llm-adapter",
                                        "openai",
                                        "--llm-provider",
                                        "openai",
                                        "--llm-model",
                                        "gpt-5",
                                        "--llm-api-key-env",
                                        "OPENAI_API_KEY",
                                    ]
                                )

        output = stdout.getvalue()

        self.assertIn("LLM provider config:", output)
        self.assertIn("Provider: openai", output)
        self.assertIn("LLM agent adapter result:", output)
        self.assertIn("Executed: yes", output)
        self.assertIn("Concise safe agent summary.", output)
        self.assertNotIn("sk-live-secret-123", output)
        mock_execute_codex.assert_not_called()

    def test_cli_secret_like_task_does_not_leak_raw_secret(self) -> None:
        secret_value = "super-secret-token-123"
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--llm-agent-adapter-check",
                            "--agent-role",
                            "Security",
                            "--task",
                            f"review auth issue with API_TOKEN={secret_value}",
                            "--llm-enabled",
                            "--confirm-llm-agent",
                            "--llm-adapter",
                            "mock",
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn("Can run LLM agent: no", output)
        self.assertIn("Executed: no", output)
        self.assertNotIn(secret_value, output)

    def test_cli_requires_agent_role(self) -> None:
        with patch.object(cli, "load_config", return_value=self.fake_config):
            with self.assertRaisesRegex(
                SystemExit,
                "LLM agent adapter error: --llm-agent-adapter-check requires --agent-role.",
            ):
                cli.run(
                    [
                        "--llm-agent-adapter-check",
                        "--task",
                        "review this project",
                    ]
                )
