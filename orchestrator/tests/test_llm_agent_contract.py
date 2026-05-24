from contextlib import redirect_stdout
from io import StringIO
from unittest import TestCase
from unittest.mock import patch

import cli
from agents.llm_agent_contract import (
    format_llm_agent_contract,
    format_llm_agent_contract_view,
    evaluate_llm_agent_contract,
)


class LlmAgentContractTests(TestCase):
    def test_valid_planner_contract_can_run_when_enabled_and_confirmed(self) -> None:
        result = evaluate_llm_agent_contract(
            "Planner",
            "review this project and suggest the safest next coding task",
            context_text="Project context summary.",
            allowed_context_sources=["project_context", "planner_report"],
            approval_confirmed=True,
            llm_enabled=True,
        )

        self.assertTrue(result["can_run_llm_agent"])
        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "medium")
        self.assertEqual(result["fallback_mode"], "deterministic")
        self.assertIn("project_context", result["allowed_context_sources"])
        self.assertIn("Deterministic fallback remains available.", result["execution_summary"])

    def test_missing_approval_blocks(self) -> None:
        result = evaluate_llm_agent_contract(
            "Planner",
            "review this project",
            approval_confirmed=False,
            llm_enabled=True,
        )

        self.assertFalse(result["can_run_llm_agent"])
        self.assertIn("Explicit approval confirmation is required", " ".join(result["blocked_reasons"]))

    def test_llm_disabled_blocks_but_reports_deterministic_fallback(self) -> None:
        result = evaluate_llm_agent_contract(
            "Reviewer",
            "review the diff",
            approval_confirmed=True,
            llm_enabled=False,
        )
        formatted = format_llm_agent_contract(result)

        self.assertFalse(result["can_run_llm_agent"])
        self.assertIn("LLM-backed agent execution is disabled", formatted)
        self.assertIn("Fallback mode: deterministic", formatted)

    def test_unknown_agent_role_blocks(self) -> None:
        result = evaluate_llm_agent_contract(
            "Unknown",
            "review this project",
            approval_confirmed=True,
            llm_enabled=True,
        )

        self.assertFalse(result["can_run_llm_agent"])
        self.assertEqual(result["risk_level"], "high")
        self.assertIn("Unknown agent role", " ".join(result["blocked_reasons"]))

    def test_secret_like_task_blocks_without_raw_secret(self) -> None:
        secret_value = "super-secret-token-123"
        result = evaluate_llm_agent_contract(
            "Security",
            f"review auth issue with API_TOKEN={secret_value}",
            approval_confirmed=True,
            llm_enabled=True,
        )
        formatted = format_llm_agent_contract(result)

        self.assertFalse(result["can_run_llm_agent"])
        self.assertIn("LLM agent task text blocked because secret-like content was detected.", formatted)
        self.assertNotIn(secret_value, formatted)

    def test_secret_like_context_blocks_without_raw_secret(self) -> None:
        secret_value = "super-secret-token-123"
        result = evaluate_llm_agent_contract(
            "Reviewer",
            "review the project",
            context_text=f"Context with API_TOKEN={secret_value}",
            approval_confirmed=True,
            llm_enabled=True,
        )
        formatted = format_llm_agent_contract(result)

        self.assertFalse(result["can_run_llm_agent"])
        self.assertIn("LLM agent context text blocked because secret-like content was detected.", formatted)
        self.assertNotIn(secret_value, formatted)

    def test_too_long_context_blocks(self) -> None:
        result = evaluate_llm_agent_contract(
            "Architect",
            "assess the codebase",
            context_text="a" * 12001,
            approval_confirmed=True,
            llm_enabled=True,
        )

        self.assertFalse(result["can_run_llm_agent"])
        self.assertIn("maximum allowed size of 12000", " ".join(result["blocked_reasons"]))

    def test_allowed_context_sources_are_enforced(self) -> None:
        result = evaluate_llm_agent_contract(
            "Product",
            "review onboarding copy",
            allowed_context_sources=["project_context", "unknown_source"],
            approval_confirmed=True,
            llm_enabled=True,
        )

        self.assertFalse(result["can_run_llm_agent"])
        self.assertIn("Unknown context source is not allowed: unknown_source", " ".join(result["blocked_reasons"]))

    def test_formatter_includes_expected_sections(self) -> None:
        result = evaluate_llm_agent_contract(
            "Planner",
            "review this project",
            approval_confirmed=True,
            llm_enabled=True,
        )
        formatted = format_llm_agent_contract_view(result)

        self.assertIn("Can run LLM agent:", formatted)
        self.assertIn("Approval required:", formatted)
        self.assertIn("Risk level:", formatted)
        self.assertIn("Blocked reasons:", formatted)
        self.assertIn("Allowed context sources:", formatted)
        self.assertIn("Safety requirements:", formatted)
        self.assertIn("Fallback mode: deterministic", formatted)
        self.assertIn("Execution summary:", formatted)


class LlmAgentContractCliTests(TestCase):
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

    def test_cli_prints_contract_result(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with patch.object(cli, "execute_codex_task_with_post_review") as mock_execute_codex:
                    with redirect_stdout(stdout):
                        cli.run(
                            [
                                "--llm-agent-check",
                                "--agent-role",
                                "Planner",
                                "--task",
                                "review this project",
                                "--llm-enabled",
                                "--confirm-llm-agent",
                                "--context-source",
                                "project_context",
                            ]
                        )

        output = stdout.getvalue()

        self.assertIn("Can run LLM agent: yes", output)
        self.assertIn("Approval required: yes", output)
        self.assertIn("Risk level: medium", output)
        self.assertIn("Allowed context sources: project_context", output)
        self.assertIn("Fallback mode: deterministic", output)
        mock_execute_codex.assert_not_called()

    def test_cli_secret_like_context_blocks_without_raw_secret(self) -> None:
        secret_value = "super-secret-token-123"
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--llm-agent-check",
                            "--agent-role",
                            "Reviewer",
                            "--task",
                            "review this project",
                            "--context-text",
                            f"API_TOKEN={secret_value}",
                            "--llm-enabled",
                            "--confirm-llm-agent",
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn("Can run LLM agent: no", output)
        self.assertIn("LLM agent context text blocked because secret-like content was detected.", output)
        self.assertNotIn(secret_value, output)

    def test_cli_requires_agent_role(self) -> None:
        with patch.object(cli, "load_config", return_value=self.fake_config):
            with self.assertRaisesRegex(
                SystemExit,
                "LLM agent contract error: --llm-agent-check requires --agent-role.",
            ):
                cli.run(
                    [
                        "--llm-agent-check",
                        "--task",
                        "review this project",
                    ]
                )
