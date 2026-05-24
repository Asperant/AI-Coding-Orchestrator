from __future__ import annotations

from unittest import TestCase

from agents.agent_runtime import (
    format_agent_run_summary,
    run_agent_pass,
    run_agent_workflow,
)
from orchestration.multi_agent_review import generate_multi_agent_diff_review
from orchestration.task_classifier import classify_task


class AgentRuntimeTests(TestCase):
    def test_planner_runs_for_plan_mode(self) -> None:
        summary = run_agent_workflow(
            task_text="fix telemetry bug",
            mode="plan",
            task_classification=classify_task("fix telemetry bug"),
        )

        self.assertIn("Planner", summary["agents_used"])
        self.assertEqual(summary["decision_hint"], "Approved")
        self.assertEqual(summary["runtime_mode"], "deterministic")
        self.assertFalse(summary["fallback_used"])

    def test_reviewer_and_tester_always_run_for_diff_review(self) -> None:
        summary = run_agent_workflow(
            task_text="fix telemetry bug",
            mode="review-diff",
            task_classification=classify_task("fix telemetry bug"),
            changed_files=["src/cli.py"],
            diff_text="diff --git a/src/cli.py b/src/cli.py\n+print('hello')\n",
            is_git_repo=True,
            diff_present=True,
        )

        self.assertIn("Reviewer", summary["agents_used"])
        self.assertIn("Tester", summary["agents_used"])

    def test_security_activates_for_auth_token_secret_database_signals(self) -> None:
        summary = run_agent_workflow(
            task_text="fix auth token bug",
            mode="review-diff",
            task_classification=classify_task("fix auth token bug"),
            changed_files=["src/auth/service.py"],
            diff_text="token secret password database user data",
            is_git_repo=True,
            diff_present=True,
        )

        self.assertIn("Security", summary["agents_used"])
        self.assertIn(
            "Security lens flagged auth, secret, database, or user-data related change indicators.",
            summary["consolidated_findings"],
        )

    def test_architect_activates_for_context_services_refactor_signals(self) -> None:
        summary = run_agent_workflow(
            task_text="refactor service boundaries",
            mode="review-diff",
            task_classification=classify_task("refactor service boundaries"),
            changed_files=["src/context/app.py", "src/services/data.py"],
            diff_text="refactor context services architecture",
            is_git_repo=True,
            diff_present=True,
        )

        self.assertIn("Architect", summary["agents_used"])

    def test_product_activates_for_ui_feature_copy_signals(self) -> None:
        summary = run_agent_workflow(
            task_text="add feature onboarding flow",
            mode="review-diff",
            task_classification=classify_task("add feature onboarding flow"),
            changed_files=["docs/product-copy.md"],
            diff_text="labels onboarding result permission product text",
            is_git_repo=True,
            diff_present=True,
        )

        self.assertIn("Product", summary["agents_used"])

    def test_release_activates_for_config_package_deploy_signals(self) -> None:
        summary = run_agent_workflow(
            task_text="review deploy package release",
            mode="review-diff",
            task_classification=classify_task("review deploy package release"),
            changed_files=["package.json", "config/deploy.yaml"],
            diff_text="dependency build deploy migration release",
            is_git_repo=True,
            diff_present=True,
        )

        self.assertIn("Release", summary["agents_used"])

    def test_consolidated_summary_includes_agents_used_and_findings(self) -> None:
        summary = run_agent_workflow(
            task_text="fix telemetry bug",
            mode="review-diff",
            task_classification=classify_task("fix telemetry bug"),
            changed_files=["src/cli.py"],
            diff_text="diff --git a/src/cli.py b/src/cli.py\n+print('hello')\n",
            is_git_repo=True,
            diff_present=True,
        )
        output = format_agent_run_summary(summary)

        self.assertIn("Agents used:", output)
        self.assertIn("Agent runtime mode:", output)
        self.assertIn("Fallback used:", output)
        self.assertIn("Consolidated findings:", output)
        self.assertIn("Decision hint:", output)

    def test_no_llm_api_or_tool_execution_occurs(self) -> None:
        result = run_agent_pass(
            {
                "role": "Reviewer",
                "task_text": "fix telemetry bug",
                "mode": "review-diff",
                "task_classification": classify_task("fix telemetry bug"),
                "changed_files": ["src/cli.py"],
                "diff_text": "diff",
                "is_git_repo": True,
                "diff_present": True,
            }
        )

        self.assertEqual(result["role"], "Reviewer")
        self.assertIn("Reviewer inspected 1 changed file(s).", result["findings"])
        self.assertEqual(result["runtime_mode"], "deterministic")

    def test_mock_runtime_uses_mock_adapter_when_contract_passes(self) -> None:
        summary = run_agent_workflow(
            task_text="fix telemetry bug",
            mode="plan",
            task_classification=classify_task("fix telemetry bug"),
            llm_mode="mock",
            llm_enabled=True,
            llm_approval_confirmed=True,
            context_sources=["project_context"],
            context_text="Small safe planning context.",
            llm_provider="mock",
            llm_model="mock-model",
        )

        self.assertEqual(summary["runtime_mode"], "mock")
        self.assertEqual(summary["llm_adapter_used"], "mock")
        self.assertEqual(summary["llm_provider"], "mock")
        self.assertTrue(summary["provider_available"])
        self.assertEqual(summary["provider_execution_status"], "mock adapter executed")
        self.assertFalse(summary["fallback_used"])
        self.assertIn("Mock Planner output", " ".join(summary["consolidated_findings"]))

    def test_mock_runtime_falls_back_when_approval_missing(self) -> None:
        summary = run_agent_workflow(
            task_text="fix telemetry bug",
            mode="plan",
            task_classification=classify_task("fix telemetry bug"),
            llm_mode="mock",
            llm_enabled=True,
            llm_approval_confirmed=False,
            context_sources=["project_context"],
            context_text="Small safe planning context.",
            llm_provider="mock",
            llm_model="mock-model",
        )

        self.assertEqual(summary["runtime_mode"], "mock")
        self.assertTrue(summary["fallback_used"])
        self.assertIn("deterministic fallback", " ".join(summary["consolidated_findings"]).lower())

    def test_disabled_runtime_uses_deterministic_fallback(self) -> None:
        summary = run_agent_workflow(
            task_text="fix telemetry bug",
            mode="plan",
            task_classification=classify_task("fix telemetry bug"),
            llm_mode="disabled",
            llm_enabled=False,
            llm_approval_confirmed=False,
            context_sources=["project_context"],
            context_text="Small safe planning context.",
            llm_provider="disabled",
        )

        self.assertEqual(summary["runtime_mode"], "disabled")
        self.assertTrue(summary["fallback_used"])
        self.assertEqual(summary["llm_provider"], "disabled")
        self.assertFalse(summary["provider_available"])
        self.assertEqual(summary["provider_execution_status"], "provider disabled")
        self.assertEqual(summary["fallback_reason"], "LLM provider is disabled.")
        self.assertIn("Provider disabled forced deterministic fallback.", " ".join(summary["runtime_notes"]))

    def test_openai_provider_does_not_call_api_and_falls_back_with_clear_note(self) -> None:
        summary = run_agent_workflow(
            task_text="fix telemetry bug",
            mode="plan",
            task_classification=classify_task("fix telemetry bug"),
            llm_mode="openai",
            llm_enabled=True,
            llm_approval_confirmed=True,
            context_sources=["project_context"],
            context_text="Small safe planning context.",
            llm_provider="openai",
            llm_model="gpt-5",
        )

        self.assertEqual(summary["llm_provider"], "openai")
        self.assertFalse(summary["provider_available"])
        self.assertEqual(summary["provider_execution_status"], "real provider unavailable")
        self.assertTrue(summary["fallback_used"])
        self.assertIn("openai adapter refused execution because the provider is unavailable.", " ".join(summary["consolidated_findings"]).lower())

    def test_missing_openai_key_appears_unavailable_without_raw_key(self) -> None:
        secret_value = "sk-live-secret-123"
        summary = run_agent_workflow(
            task_text="fix telemetry bug",
            mode="plan",
            task_classification=classify_task("fix telemetry bug"),
            llm_mode="openai",
            llm_enabled=True,
            llm_approval_confirmed=True,
            context_sources=["project_context"],
            context_text="Small safe planning context.",
            llm_provider="openai",
            llm_model="gpt-5",
            llm_api_key_env_var="OPENAI_API_KEY",
        )
        output = format_agent_run_summary(summary)

        self.assertFalse(summary["provider_available"])
        self.assertIn("Configured API key environment variable is missing or empty.", output)
        self.assertNotIn(secret_value, output)

    def test_secret_like_task_or_context_does_not_leak_raw_secret(self) -> None:
        secret_value = "super-secret-token-123"
        summary = run_agent_workflow(
            task_text=f"fix auth issue with API_TOKEN={secret_value}",
            mode="plan",
            task_classification=classify_task("fix auth issue"),
            llm_mode="mock",
            llm_enabled=True,
            llm_approval_confirmed=True,
            context_sources=["context_text"],
            context_text=f"Context includes API_TOKEN={secret_value}",
        )
        output = format_agent_run_summary(summary)

        self.assertTrue(summary["fallback_used"])
        self.assertNotIn(secret_value, output)
        self.assertIn("secret-like content was detected", output)

    def test_runtime_summary_includes_provider_info(self) -> None:
        summary = run_agent_workflow(
            task_text="fix telemetry bug",
            mode="plan",
            task_classification=classify_task("fix telemetry bug"),
            llm_mode="mock",
            llm_enabled=True,
            llm_approval_confirmed=True,
            context_sources=["project_context"],
            context_text="Small safe planning context.",
            llm_provider="mock",
            llm_model="mock-model",
        )
        output = format_agent_run_summary(summary)

        self.assertIn("LLM provider: mock", output)
        self.assertIn("Provider available: yes", output)
        self.assertIn("Provider execution status: mock adapter executed", output)

    def test_existing_multi_agent_diff_review_behavior_remains_compatible(self) -> None:
        review = generate_multi_agent_diff_review(
            {
                "is_git_repo": True,
                "changed_files": ["src/auth/service.py"],
                "status_summary": "1 changed file(s).",
                "diff_text": "token secret password database user data",
                "diff_present": True,
            },
            task_classification=classify_task("fix auth token bug"),
        )

        self.assertIn("Reviewer", review["agents_used"])
        self.assertIn("Tester", review["agents_used"])
        self.assertIn("Security", review["agents_used"])
        self.assertEqual(review["decision"], "Needs revision")

    def test_openai_runtime_with_mocked_success_uses_adapter_result(self) -> None:
        from unittest.mock import patch
        
        mocked_adapter_result = {
            "executed": True,
            "output_text": "Mocked OpenAI Planner Output",
            "safety_notes": ["Mocked OpenAI safety note"],
            "error": None
        }
        
        with patch("agents.agent_runtime.get_llm_adapter") as mock_get_adapter:
            mock_adapter = mock_get_adapter.return_value
            mock_adapter.run_agent.return_value = mocked_adapter_result
            
            summary = run_agent_workflow(
                task_text="fix telemetry bug",
                mode="plan",
                task_classification=classify_task("fix telemetry bug"),
                llm_mode="openai",
                llm_enabled=True,
                llm_approval_confirmed=True,
                context_sources=["project_context"],
                context_text="Small safe planning context.",
                llm_provider="openai",
                llm_model="gpt-5",
                llm_api_key_env_var="TEST_API_KEY",
            )
            
            self.assertEqual(summary["runtime_mode"], "openai")
            self.assertEqual(summary["llm_adapter_used"], "openai")
            self.assertFalse(summary["fallback_used"])
            self.assertEqual(summary["provider_execution_status"], "openai adapter executed")
            self.assertIn("Mocked OpenAI Planner Output", " ".join(summary["consolidated_findings"]))

    def test_gemini_runtime_with_mocked_success_uses_adapter_result(self) -> None:
        from unittest.mock import patch
        
        mocked_adapter_result = {
            "executed": True,
            "output_text": "Mocked Gemini Planner Output",
            "safety_notes": ["Mocked Gemini safety note"],
            "error": None,
            "fallback_required": False,
            "agent_role": "Planner",
        }
        
        with patch("agents.agent_runtime.get_llm_adapter") as mock_get_adapter:
            mock_adapter = mock_get_adapter.return_value
            mock_adapter.run_agent.return_value = mocked_adapter_result
            
            summary = run_agent_workflow(
                task_text="fix telemetry bug",
                mode="plan",
                task_classification=classify_task("fix telemetry bug"),
                llm_mode="gemini",
                llm_enabled=True,
                llm_approval_confirmed=True,
                context_sources=["project_context"],
                context_text="Small safe planning context.",
                llm_provider="gemini",
                llm_model="gemini-2.5-flash",
                llm_api_key_env_var="TEST_GEMINI_KEY",
            )
            
            self.assertEqual(summary["runtime_mode"], "gemini")
            self.assertEqual(summary["llm_adapter_used"], "gemini")
            self.assertFalse(summary["fallback_used"])
            self.assertEqual(summary["provider_execution_status"], "gemini adapter executed")
            self.assertIn("Mocked Gemini Planner Output", " ".join(summary["consolidated_findings"]))
