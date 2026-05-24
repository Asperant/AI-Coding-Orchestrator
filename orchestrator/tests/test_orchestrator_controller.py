from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from core import report_writer
import orchestration.orchestrator_controller as orchestrator_controller
from orchestration.orchestrator_controller import format_orchestrator_result, run_orchestrator
from tools.error_logs_mcp import MockErrorLogsClient
from tools.github_read_mcp import MockGitHubReadClient


class OrchestratorControllerTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.project_root = self.approved_root / "project"
        self.project_root.mkdir()
        self.ai_brain_root = self.approved_root / "ai-brain"
        (self.ai_brain_root / "02-Code").mkdir(parents=True)
        (self.ai_brain_root / "CORE-RULES.md").write_text("core", encoding="utf-8")
        (self.ai_brain_root / "README-FOR-AI.md").write_text("readme", encoding="utf-8")
        (self.ai_brain_root / "02-Code" / "AI-Brain-Priority-Tiers.md").write_text("tiers", encoding="utf-8")
        (self.ai_brain_root / "02-Code" / "Context-Budget-Rules.md").write_text("budget", encoding="utf-8")

        self.report_root_patch = patch.object(report_writer, "PROJECT_ROOT", self.root)
        self.report_root_patch.start()

    def tearDown(self) -> None:
        self.report_root_patch.stop()
        self.temp_dir.cleanup()

    def init_git_repo(self, repo_path: Path) -> Path:
        repo_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init", str(repo_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        return repo_path

    def test_status_mode_works(self) -> None:
        (self.project_root / "AGENTS.md").write_text("agent", encoding="utf-8")

        result = run_orchestrator(
            project_path=str(self.project_root),
            mode="status",
            approved_paths=[str(self.approved_root)],
        )

        self.assertEqual(result["mode"], "status")
        self.assertIn("Read-only orchestration status completed.", result["summary"])
        self.assertIn("Mode: status", result["report_text"])
        self.assertEqual(result["errors"], [])

    def test_status_mode_uses_shared_formatter(self) -> None:
        result = run_orchestrator(
            mode="status",
            approved_paths=[str(self.approved_root)],
        )

        output = format_orchestrator_result(result)

        self.assertIn("Summary: Read-only orchestration status completed.", output)
        self.assertIn("Mode: status", output)
        self.assertIn("Task type: not provided", output)
        self.assertIn("Errors: none", output)
        self.assertIn("Report text:", output)

    def test_plan_mode_uses_planner_report(self) -> None:
        result = run_orchestrator(
            task_text="fix telemetry bug",
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
        )

        self.assertEqual(result["mode"], "plan")
        self.assertEqual(result["task_type"], "bug fix")
        self.assertIn("Summary:", result["report_text"])
        self.assertIn("Knowledge Update Proposal:", result["report_text"])
        self.assertIn("Task type: bug fix", result["report_text"])
        self.assertIn("Agent Runtime Summary:", result["report_text"])
        self.assertIn("Planner classified the work as bug fix in plan mode.", result["report_text"])
        self.assertEqual(result["errors"], [])

    def test_plan_mode_uses_shared_formatter(self) -> None:
        result = run_orchestrator(
            task_text="fix telemetry bug",
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
        )

        output = format_orchestrator_result(result)

        self.assertIn("Mode: plan", output)
        self.assertIn("Task type: bug fix", output)
        self.assertIn("Agent runtime mode: deterministic", output)
        self.assertIn("Agent LLM adapter used: none", output)
        self.assertIn("LLM provider: disabled", output)
        self.assertIn("Provider available: no", output)
        self.assertIn("Provider execution status: not requested", output)
        self.assertIn("Agent fallback used: no", output)
        self.assertIn("Fallback reason: none", output)
        self.assertIn("Agent Runtime Summary:", output)
        self.assertIn("Agents used: Planner", output)
        self.assertIn("Errors: none", output)
        self.assertIn("Report text:\nSummary:", output)
        self.assertNotIn("Local MCP Context:", result["report_text"])
        self.assertNotIn("GitHub Context:", result["report_text"])

    def test_plan_mode_with_include_github_context_shows_github_context_section(self) -> None:
        client = MockGitHubReadClient(
            issues={
                ("openai/example", 12): {
                    "title": "Fix planner output",
                    "state": "open",
                    "body": "Planner summary needs cleanup.",
                }
            }
        )

        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
            result = run_orchestrator(
                task_text="fix telemetry bug",
                mode="plan",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
                include_github_context=True,
                github_repo="openai/example",
                github_issue_number=12,
                github_read_client=client,
            )

        self.assertIn("GitHub Context:", result["report_text"])
        self.assertIn("GitHub repo: openai/example", result["report_text"])
        self.assertIn("Issue context: available", result["report_text"])
        self.assertIn("CI status context: unavailable", result["report_text"])
        self.assertIn("Context blocks:", result["report_text"])
        output = format_orchestrator_result(result)
        self.assertIn("GitHub Context: GitHub repo: openai/example", output)

    def test_plan_mode_passes_github_client_gh_into_github_context_collection(self) -> None:
        with patch(
            "orchestration.orchestrator_controller._collect_github_context",
            return_value=(
                "GitHub repo: openai/example",
                "GitHub repo: openai/example\nIssue context: unavailable\nContext blocks: none",
                [],
                {"issue": "unavailable", "pr": "unavailable", "pr_changed_files": "unavailable", "ci": "unavailable"},
            ),
        ) as mocked_collect:
            result = run_orchestrator(
                task_text="fix telemetry bug",
                mode="plan",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
                include_github_context=True,
                github_repo="openai/example",
                github_issue_number=12,
                github_client="gh",
            )

        self.assertIn("GitHub Context:", result["report_text"])
        self.assertEqual(mocked_collect.call_args.kwargs["github_read_client"], "gh")

    def test_plan_mode_github_context_invalid_repo_blocks_safely(self) -> None:
        result = run_orchestrator(
            task_text="fix telemetry bug",
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
            include_github_context=True,
            github_repo="not a repo",
            github_issue_number=12,
        )

        self.assertIn("GitHub Context:", result["report_text"])
        self.assertIn("GitHub repository must use a safe owner/repo format.", result["report_text"])

    def test_plan_mode_github_context_gh_unavailable_returns_safe_context(self) -> None:
        def github_side_effect(tool_name: str, repo: str, **kwargs: object) -> dict[str, object]:
            self.assertEqual(kwargs["client"], "gh")
            return {
                "executed": False,
                "blocked": True,
                "tool_name": tool_name,
                "repo": repo,
                "item_id": kwargs.get("issue_number") or kwargs.get("pr_number"),
                "content_summary": "not available",
                "raw_content": None,
                "context_blocks": [],
                "message": "gh CLI authentication is unavailable or not logged in.",
                "safety_notes": ["No raw token value was printed."],
                "decision": {"allowed": True},
            }

        with patch(
            "orchestration.orchestrator_controller.run_github_read_tool",
            side_effect=github_side_effect,
        ):
            result = run_orchestrator(
                task_text="fix telemetry bug",
                mode="plan",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
                include_github_context=True,
                github_repo="openai/example",
                github_issue_number=12,
                github_client="gh",
            )

        self.assertIn("GitHub Context:", result["report_text"])
        self.assertIn("Issue context: unavailable", result["report_text"])
        self.assertIn("authentication is unavailable", result["report_text"].lower())

    def test_plan_mode_github_context_missing_token_does_not_crash_or_leak(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result = run_orchestrator(
                task_text="fix telemetry bug",
                mode="plan",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
                include_github_context=True,
                github_repo="openai/example",
                github_issue_number=12,
            )

        self.assertEqual(result["errors"], [])
        self.assertIn("GitHub Context:", result["report_text"])
        self.assertIn("GITHUB_TOKEN is not set", result["report_text"])
        self.assertNotIn("ghs_", result["report_text"])

    def test_plan_mode_with_github_client_gh_does_not_report_missing_github_token_when_gh_succeeds(self) -> None:
        def github_side_effect(tool_name: str, repo: str, **kwargs: object) -> dict[str, object]:
            self.assertEqual(kwargs["client"], "gh")
            if tool_name == "github.issue.read":
                return {
                    "executed": True,
                    "blocked": False,
                    "tool_name": tool_name,
                    "repo": repo,
                    "item_id": 12,
                    "content_summary": "Issue #12: Fix planner output",
                    "raw_content": "GitHub issue preview",
                    "context_blocks": [
                        {
                            "source_type": "github",
                            "source_name": "openai/example#12",
                            "tool_name": tool_name,
                            "source_path": "openai/example#12",
                            "content": "GitHub issue preview",
                            "safe": True,
                            "blocked": False,
                            "reason": "none",
                            "char_count": 20,
                        }
                    ],
                    "message": "github.issue.read completed successfully.",
                    "safety_notes": ["gh CLI read-only client: no write or mutation command was used."],
                    "decision": {"allowed": True},
                }
            return {
                "executed": False,
                "blocked": True,
                "tool_name": tool_name,
                "repo": repo,
                "item_id": kwargs.get("pr_number"),
                "content_summary": "not available",
                "raw_content": None,
                "context_blocks": [],
                "message": f"{tool_name} unavailable.",
                "safety_notes": ["none"],
                "decision": {"allowed": True},
            }

        with patch(
            "orchestration.orchestrator_controller.run_github_read_tool",
            side_effect=github_side_effect,
        ):
            with patch.dict(os.environ, {}, clear=True):
                result = run_orchestrator(
                    task_text="fix telemetry bug",
                    mode="plan",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    include_github_context=True,
                    github_repo="openai/example",
                    github_issue_number=12,
                    github_client="gh",
                )

        self.assertIn("GitHub Context:", result["report_text"])
        self.assertIn("Issue context: available", result["report_text"])
        self.assertNotIn("GITHUB_TOKEN is not set", result["report_text"])

    def test_plan_mode_secret_like_mock_github_content_is_blocked_redacted(self) -> None:
        secret_value = "super-secret-token-123"
        client = MockGitHubReadClient(
            issues={
                ("openai/example", 14): {
                    "title": "Investigate token leak",
                    "state": "open",
                    "body": f"API_TOKEN={secret_value}",
                }
            }
        )

        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
            result = run_orchestrator(
                task_text="fix telemetry bug",
                mode="plan",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
                include_github_context=True,
                github_repo="openai/example",
                github_issue_number=14,
                github_read_client=client,
            )

        self.assertIn("GitHub Context:", result["report_text"])
        self.assertNotIn(secret_value, result["report_text"])
        self.assertIn("blocked", result["report_text"].lower())

    def test_plan_mode_gh_issue_context_appears_in_report_when_data_is_available(self) -> None:
        def github_side_effect(tool_name: str, repo: str, **kwargs: object) -> dict[str, object]:
            if tool_name == "github.issue.read":
                return {
                    "executed": True,
                    "blocked": False,
                    "tool_name": tool_name,
                    "repo": repo,
                    "item_id": 12,
                    "content_summary": "Issue #12: Fix planner output",
                    "raw_content": "GitHub issue preview",
                    "context_blocks": [
                        {
                            "source_type": "github",
                            "source_name": "openai/example#12",
                            "tool_name": tool_name,
                            "source_path": "openai/example#12",
                            "content": "GitHub issue preview",
                            "safe": True,
                            "blocked": False,
                            "reason": "none",
                            "char_count": 20,
                        }
                    ],
                    "message": "github.issue.read completed successfully.",
                    "safety_notes": ["gh CLI read-only client: no write or mutation command was used."],
                    "decision": {"allowed": True},
                }
            return {
                "executed": False,
                "blocked": True,
                "tool_name": tool_name,
                "repo": repo,
                "item_id": kwargs.get("pr_number"),
                "content_summary": "not available",
                "raw_content": None,
                "context_blocks": [],
                "message": f"{tool_name} unavailable.",
                "safety_notes": ["none"],
                "decision": {"allowed": True},
            }

        with patch(
            "orchestration.orchestrator_controller.run_github_read_tool",
            side_effect=github_side_effect,
        ):
            result = run_orchestrator(
                task_text="fix telemetry bug",
                mode="plan",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
                include_github_context=True,
                github_repo="openai/example",
                github_issue_number=12,
                github_client="gh",
            )

        self.assertIn("Issue context: available", result["report_text"])
        self.assertIn("Context blocks: 1", result["report_text"])

    def test_plan_mode_without_github_context_keeps_behavior_unchanged(self) -> None:
        with patch(
            "orchestration.orchestrator_controller.run_github_read_tool"
        ) as mocked_github_read:
            result = run_orchestrator(
                task_text="fix telemetry bug",
                mode="plan",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
            )

        self.assertNotIn("GitHub Context:", result["report_text"])
        mocked_github_read.assert_not_called()

    def test_plan_mode_with_include_local_mcp_context_shows_context_section(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "plan-context-repo")
        (repo_path / "AGENTS.md").write_text("Agent notes\n", encoding="utf-8")
        (repo_path / "docs" / "architecture.md").parent.mkdir(parents=True, exist_ok=True)
        (repo_path / "docs" / "architecture.md").write_text("Architecture notes\n", encoding="utf-8")

        result = run_orchestrator(
            task_text="fix telemetry bug",
            project_path=str(repo_path),
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
            include_local_mcp_context=True,
        )

        self.assertIn("Local MCP Context:", result["report_text"])
        self.assertIn("Project knowledge found docs: AGENTS.md, docs/architecture.md", result["report_text"])
        self.assertIn("Project knowledge missing docs:", result["report_text"])
        self.assertIn("Context blocks:", result["report_text"])
        output = format_orchestrator_result(result)
        self.assertIn("Local MCP Context: Project knowledge found docs:", output)

    def test_plan_mode_missing_candidate_files_do_not_fail_with_local_mcp_context(self) -> None:
        repo_path = self.project_root / "empty-context-project"
        repo_path.mkdir()

        result = run_orchestrator(
            task_text="fix telemetry bug",
            project_path=str(repo_path),
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
            include_local_mcp_context=True,
        )

        self.assertEqual(result["errors"], [])
        self.assertIn("Local MCP Context:", result["report_text"])
        self.assertIn("Project knowledge found docs: none", result["report_text"])

    def test_plan_mode_secret_like_project_doc_is_blocked_redacted(self) -> None:
        repo_path = self.project_root / "secret-context-project"
        repo_path.mkdir()
        secret_value = "super-secret-token-123"
        (repo_path / "AGENTS.md").write_text(f"API_TOKEN={secret_value}\n", encoding="utf-8")

        result = run_orchestrator(
            task_text="fix telemetry bug",
            project_path=str(repo_path),
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
            include_local_mcp_context=True,
        )

        self.assertIn("Local MCP Context:", result["report_text"])
        self.assertNotIn(secret_value, result["report_text"])
        self.assertIn("blocked", result["report_text"].lower())

    def test_plan_mode_local_mcp_context_uses_budget_compaction(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "budget-context-repo")
        (repo_path / "AGENTS.md").write_text("B" * 4000, encoding="utf-8")
        (repo_path / "docs" / "architecture.md").parent.mkdir(parents=True, exist_ok=True)
        (repo_path / "docs" / "architecture.md").write_text("A" * 12000, encoding="utf-8")

        with patch(
            "orchestration.orchestrator_controller.compact_context_blocks",
            wraps=orchestrator_controller.compact_context_blocks,
        ) as mocked_compact:
            result = run_orchestrator(
                task_text="fix telemetry bug",
                project_path=str(repo_path),
                mode="plan",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
                include_local_mcp_context=True,
            )

        self.assertIn("Local MCP Context:", result["report_text"])
        mocked_compact.assert_called_once()
        self.assertEqual(mocked_compact.call_args.kwargs["max_total_chars"], 8000)

    def test_plan_mode_avoids_duplicate_direct_file_reads_when_project_knowledge_is_used(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "project-knowledge-primary-repo")
        (repo_path / "AGENTS.md").write_text("Agent notes\n", encoding="utf-8")

        with patch(
            "orchestration.orchestrator_controller.run_mcp_read_tool",
            wraps=orchestrator_controller.run_mcp_read_tool,
        ) as mocked_mcp_read:
            result = run_orchestrator(
                task_text="fix telemetry bug",
                project_path=str(repo_path),
                mode="plan",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
                include_local_mcp_context=True,
            )

        self.assertIn("Local MCP Context:", result["report_text"])
        called_tool_names = [call.args[0] for call in mocked_mcp_read.call_args_list]
        self.assertEqual(called_tool_names, ["git.status", "git.log"])

    def test_plan_mode_with_include_error_context_shows_error_context_section(self) -> None:
        repo_path = self.project_root / "plan-error-context-repo"
        repo_path.mkdir()
        log_path = repo_path / "logs" / "dev.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("Server started\nReady\n", encoding="utf-8")

        result = run_orchestrator(
            task_text="fix telemetry bug",
            project_path=str(repo_path),
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
            include_error_context=True,
            error_tool_name="local.dev_logs.read",
            error_provider="local",
            error_log_path=str(log_path),
        )

        self.assertIn("Error Context:", result["report_text"])
        self.assertIn("Tool name: local.dev_logs.read", result["report_text"])
        self.assertIn("Provider: local", result["report_text"])
        output = format_orchestrator_result(result)
        self.assertIn("Error Context: Executed: yes", output)

    def test_plan_mode_secret_like_error_log_is_blocked_redacted(self) -> None:
        repo_path = self.project_root / "plan-secret-error-context-repo"
        repo_path.mkdir()
        secret_value = "super-secret-token-123"
        log_path = repo_path / "logs" / "dev.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(f"API_TOKEN={secret_value}\n", encoding="utf-8")

        result = run_orchestrator(
            task_text="fix telemetry bug",
            project_path=str(repo_path),
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
            include_error_context=True,
            error_tool_name="local.dev_logs.read",
            error_provider="local",
            error_log_path=str(log_path),
        )

        self.assertIn("Error Context:", result["report_text"])
        self.assertNotIn(secret_value, result["report_text"])
        self.assertIn("blocked", result["report_text"].lower())

    def test_plan_mode_with_mock_runtime_uses_mock_adapter_when_confirmed(self) -> None:
        result = run_orchestrator(
            task_text="fix telemetry bug",
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
            agent_runtime="mock",
            llm_enabled=True,
            confirm_llm_agent=True,
            agent_context_text="Small safe planning context.",
            agent_context_sources=["project_context"],
            llm_provider="mock",
            llm_model="mock-model",
        )

        self.assertEqual(result["agent_runtime_mode"], "mock")
        self.assertEqual(result["agent_llm_adapter_used"], "mock")
        self.assertEqual(result["agent_llm_provider"], "mock")
        self.assertEqual(result["agent_provider_available"], "yes")
        self.assertEqual(result["agent_provider_execution_status"], "mock adapter executed")
        self.assertEqual(result["agent_fallback_used"], "no")
        self.assertIn("Mock Planner output", result["report_text"])

    def test_plan_mode_with_openai_provider_shows_fallback_without_real_execution(self) -> None:
        result = run_orchestrator(
            task_text="fix telemetry bug",
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
            agent_runtime="openai",
            llm_enabled=True,
            confirm_llm_agent=True,
            agent_context_text="Small safe planning context.",
            agent_context_sources=["project_context"],
            llm_provider="openai",
            llm_model="gpt-5",
            llm_api_key_env_var="OPENAI_API_KEY",
        )

        self.assertEqual(result["agent_llm_provider"], "openai")
        self.assertEqual(result["agent_provider_available"], "no")
        self.assertEqual(result["agent_provider_execution_status"], "real provider unavailable")
        self.assertEqual(result["agent_fallback_used"], "yes")
        self.assertIn("Fallback reason: OpenAI provider is unavailable or blocked.", format_orchestrator_result(result))

    def test_plan_mode_missing_openai_key_does_not_leak_raw_key(self) -> None:
        secret_value = "sk-live-secret-123"
        result = run_orchestrator(
            task_text="fix telemetry bug",
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
            agent_runtime="openai",
            llm_enabled=True,
            confirm_llm_agent=True,
            agent_context_text="Small safe planning context.",
            agent_context_sources=["project_context"],
            llm_provider="openai",
            llm_model="gpt-5",
            llm_api_key_env_var="OPENAI_API_KEY",
        )
        output = format_orchestrator_result(result)

        self.assertNotIn(secret_value, output)
        self.assertIn("Configured API key environment variable is missing or empty.", output)

    def test_plan_mode_with_gemini_provider_shows_fallback_without_real_execution(self) -> None:
        result = run_orchestrator(
            task_text="fix telemetry bug",
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
            agent_runtime="gemini",
            llm_enabled=True,
            confirm_llm_agent=True,
            agent_context_text="Small safe planning context.",
            agent_context_sources=["project_context"],
            llm_provider="gemini",
            llm_model="gemini-2.5-flash",
            llm_api_key_env_var="GEMINI_API_KEY",
        )

        self.assertEqual(result["agent_llm_provider"], "gemini")
        self.assertEqual(result["agent_provider_available"], "no")
        self.assertEqual(result["agent_provider_execution_status"], "real provider unavailable")
        self.assertEqual(result["agent_fallback_used"], "yes")
        self.assertIn("Fallback reason: Gemini provider is unavailable or blocked.", format_orchestrator_result(result))

    def test_plan_mode_missing_gemini_key_does_not_leak_raw_key(self) -> None:
        secret_value = "AIza-secret-123"
        result = run_orchestrator(
            task_text="fix telemetry bug",
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
            agent_runtime="gemini",
            llm_enabled=True,
            confirm_llm_agent=True,
            agent_context_text="Small safe planning context.",
            agent_context_sources=["project_context"],
            llm_provider="gemini",
            llm_model="gemini-2.5-flash",
            llm_api_key_env_var="GEMINI_API_KEY",
        )
        output = format_orchestrator_result(result)

        self.assertNotIn(secret_value, output)
        self.assertIn("Configured API key environment variable is missing or empty.", output)

    def test_plan_mode_with_mock_runtime_falls_back_when_not_confirmed(self) -> None:
        result = run_orchestrator(
            task_text="fix telemetry bug",
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
            agent_runtime="mock",
            llm_enabled=True,
            confirm_llm_agent=False,
            agent_context_text="Small safe planning context.",
            agent_context_sources=["project_context"],
        )

        self.assertEqual(result["agent_runtime_mode"], "mock")
        self.assertEqual(result["agent_llm_adapter_used"], "mock")
        self.assertEqual(result["agent_fallback_used"], "yes")
        self.assertIn("deterministic fallback", result["report_text"].lower())

    def test_review_diff_mode_uses_multi_agent_review(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "review-repo")
        changed_file = repo_path / "config.py"
        changed_file.write_text("FEATURE_FLAG = True\n", encoding="utf-8")

        result = run_orchestrator(
            project_path=str(repo_path),
            task_text="fix telemetry bug",
            mode="review-diff",
            approved_paths=[str(self.approved_root)],
        )

        self.assertEqual(result["mode"], "review-diff")
        self.assertIn("Decision:", result["report_text"])
        self.assertIn("Knowledge Update Proposal:", result["report_text"])
        self.assertIn("Agents used:", result["report_text"])
        self.assertIsNotNone(result["decision"])
        self.assertEqual(result["errors"], [])

    def test_review_diff_mode_uses_shared_formatter(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "review-repo-format")
        changed_file = repo_path / "config.py"
        changed_file.write_text("FEATURE_FLAG = True\n", encoding="utf-8")

        result = run_orchestrator(
            project_path=str(repo_path),
            task_text="fix telemetry bug",
            mode="review-diff",
            approved_paths=[str(self.approved_root)],
        )
        output = format_orchestrator_result(result)

        self.assertIn("Mode: review-diff", output)
        self.assertIn("Decision:", output)
        self.assertIn("Report text:\nSummary:", output)

    def test_save_report_writes_only_to_reports(self) -> None:
        result = run_orchestrator(
            task_text="fix telemetry bug",
            mode="plan",
            save_report=True,
            ai_brain_path=str(self.ai_brain_root),
            reports_dir="reports",
            approved_paths=[str(self.approved_root)],
        )

        self.assertIsNotNone(result["report_path"])
        saved_path = Path(str(result["report_path"]))
        self.assertTrue(saved_path.is_file())
        self.assertIn("/reports/", str(saved_path))
        self.assertEqual(saved_path.parent, self.root / "reports")
        self.assertIn(f"Report path: {saved_path}", format_orchestrator_result(result))

    def test_missing_task_for_plan_gives_clear_error(self) -> None:
        result = run_orchestrator(
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
        )

        self.assertEqual(result["errors"], ["Plan mode requires task text."])
        self.assertIn("Errors: Plan mode requires task text.", format_orchestrator_result(result))

    def test_review_diff_without_project_gives_clear_error(self) -> None:
        result = run_orchestrator(
            task_text="fix telemetry bug",
            mode="review-diff",
            approved_paths=[str(self.approved_root)],
        )

        self.assertEqual(result["errors"], ["Review-diff mode requires project path."])

    def test_unapproved_project_is_rejected(self) -> None:
        outside_project = self.root / "outside-project"
        outside_project.mkdir()

        result = run_orchestrator(
            project_path=str(outside_project),
            mode="status",
            approved_paths=[str(self.approved_root)],
        )

        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("Target path is outside approved paths:", result["errors"][0])

    def test_run_mode_missing_allowed_files_blocks(self) -> None:
        result = run_orchestrator(
            project_path=str(self.project_root),
            task_text="fix telemetry bug",
            mode="run",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
        )

        self.assertEqual(result["decision"], None)
        self.assertEqual(result["errors"], ["Run mode requires at least one allowed file."])

    def test_run_mode_missing_confirmations_block(self) -> None:
        result = run_orchestrator(
            project_path=str(self.project_root),
            task_text="fix telemetry bug",
            mode="run",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
            allowed_files=["src/module.py"],
        )

        self.assertEqual(result["errors"], ["Run mode requires Codex prompt confirmation."])

    def test_run_mode_unapproved_project_blocks(self) -> None:
        outside_project = self.root / "outside-run-project"
        outside_project.mkdir()

        result = run_orchestrator(
            project_path=str(outside_project),
            task_text="fix telemetry bug",
            mode="run",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
            allowed_files=["src/module.py"],
            confirm_codex_prompt=True,
            confirm_codex_execution=True,
        )

        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("Target path is outside approved paths:", result["errors"][0])

    def test_run_mode_mocked_successful_codex_execution_runs_full_flow(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")

        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {
                "can_execute": True,
                "approval_required": True,
                "risk_level": "high",
                "approval_gate": {
                    "approval_required": True,
                    "risk_level": "high",
                    "reasons": ["Codex execution requests require explicit approval."],
                    "blocked_actions": ["codex_execution"],
                    "recommended_user_confirmation": "Request explicit user approval before proceeding with: codex_execution.",
                },
                "blocked_reasons": ["none"],
                "allowed_files": [str(target_file.resolve())],
                "safety_requirements": ["No execution is performed by this safety contract."],
                "execution_summary": "All Codex execution safety requirements passed. No execution was performed.",
            },
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved with changes",
            "post_review_report": "Summary: Reviewed 1 changed file(s).\nDecision: Approved with changes",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        mocked_test_result = {
            "ran": True,
            "blocked": False,
            "passed": True,
            "return_code": 0,
            "timed_out": False,
            "stdout": "ok\n",
            "stderr": "",
            "message": "Test command completed successfully.",
        }

        with patch(
            "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
            return_value=mocked_execution_result,
        ) as mocked_executor:
            with patch(
                "orchestration.orchestrator_controller.run_test_command",
                return_value=mocked_test_result,
            ) as mocked_test_runner:
                with patch(
                    "orchestration.orchestrator_controller.write_report"
                ) as mocked_write_report:
                    result = run_orchestrator(
                        project_path=str(self.project_root),
                        task_text="fix telemetry bug",
                        mode="run",
                        ai_brain_path=str(self.ai_brain_root),
                        approved_paths=[str(self.approved_root)],
                        allowed_files=["src/module.py"],
                        confirm_codex_prompt=True,
                        confirm_codex_execution=True,
                        agent_runtime="mock",
                        llm_enabled=True,
                        confirm_llm_agent=True,
                        agent_context_text="Small safe run context.",
                        agent_context_sources=["project_context"],
                        llm_provider="mock",
                        llm_model="mock-model",
                        test_command=["python", "-m", "unittest"],
                    )
                    mocked_write_report.assert_not_called()

        self.assertEqual(result["mode"], "run")
        self.assertEqual(result["decision"], "Approved with changes")
        self.assertEqual(result["summary"], "Coding run completed through post-Codex review and tests passed.")
        self.assertIn("Planner report:", result["report_text"])
        self.assertIn("Edit plan:", result["report_text"])
        self.assertIn("Codex prompt package:", result["report_text"])
        self.assertIn("Pre-Codex Agent Guidance:", result["report_text"])
        self.assertIn("Agents used: Planner; Tester", result["report_text"])
        self.assertIn("Codex execution contract:", result["report_text"])
        self.assertIn("Codex execution result:", result["report_text"])
        self.assertIn("Scope enforcement result:", result["report_text"])
        self.assertIn("Passed: yes", result["report_text"])
        self.assertIn("Verification Gate:", result["report_text"])
        self.assertIn("Final verification decision: Approved with changes", result["report_text"])
        self.assertIn("Test execution result:", result["report_text"])
        self.assertIn("Passed: yes", result["report_text"])
        self.assertIn("Knowledge Update Proposal:", result["report_text"])
        self.assertIn("- Write status: not_written", result["report_text"])
        self.assertIn("Memory/docs update suggestion:", result["report_text"])
        self.assertIn("Agent Runtime Summary:", result["report_text"])
        self.assertIn("Planner classified the work as bug fix in run mode.", result["report_text"])
        self.assertIn("Mock Planner output", result["report_text"])
        self.assertNotIn("Local MCP Context:", result["report_text"])
        self.assertNotIn("Context signals:", result["report_text"])
        mocked_executor.assert_called_once()
        mocked_test_runner.assert_called_once()

        output = format_orchestrator_result(result)
        self.assertIn("Coding Run Summary", output)
        self.assertIn("- Task: fix telemetry bug", output)
        self.assertIn("- Changed files: src/module.py", output)
        self.assertIn("- Scope: passed", output)
        self.assertIn("- Verification: Approved with changes", output)
        self.assertIn("- Tests: passed", output)
        self.assertIn("Mode: run", output)
        self.assertIn("Gate status: passed", output)
        self.assertIn("Planner summary: Summary:", output)
        self.assertIn("Edit plan summary: Dry run: yes", output)
        self.assertIn("Codex execution result: Executed: yes", output)
        self.assertIn("Post-Codex review decision: Approved with changes", output)
        self.assertIn(
            "Verification Gate: Final verification decision: Approved with changes; Test status: passed; CI status: not run",
            output,
        )
        self.assertIn("Test execution result: Ran: yes", output)
        self.assertIn("Knowledge Update Proposal:\n- Destination:", output)
        self.assertIn("Agent runtime mode: mock", output)
        self.assertIn("Agent LLM adapter used: mock", output)
        self.assertIn("LLM provider: mock", output)
        self.assertIn("Provider available: yes", output)
        self.assertIn("Provider execution status: mock adapter executed", output)
        self.assertIn("Agent fallback used: no", output)
        self.assertIn("Agent Runtime Summary:", output)
        self.assertIn("Agents used: Planner", output)

    def test_run_mode_with_include_local_mcp_context_shows_context_section(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "run-context-repo")
        agents_text = "Telemetry workflow agent notes.\n"
        (repo_path / "AGENTS.md").write_text(agents_text, encoding="utf-8")
        (repo_path / "docs" / "project-map.md").parent.mkdir(parents=True, exist_ok=True)
        (repo_path / "docs" / "project-map.md").write_text("Project map notes.\n", encoding="utf-8")
        target_file = repo_path / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")

        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        with patch(
            "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
            return_value=mocked_execution_result,
        ):
            result = run_orchestrator(
                project_path=str(repo_path),
                task_text="fix telemetry bug",
                mode="run",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
                allowed_files=["src/module.py"],
                confirm_codex_prompt=True,
                confirm_codex_execution=True,
                include_local_mcp_context=True,
            )

        self.assertIn("Local MCP Context:", result["report_text"])
        prompt_section = result["report_text"].split("Codex prompt package:\n", 1)[1].split(
            "\n\nCodex execution contract:\n",
            1,
        )[0]
        self.assertIn("Context signals:", prompt_section)
        self.assertIn("- Local project knowledge: found AGENTS.md, docs/project-map.md", prompt_section)
        self.assertIn("- Local git state: 3 changed file(s).", prompt_section)
        self.assertNotIn(agents_text.strip(), prompt_section)
        self.assertIn("Only edit the listed allowed files.", prompt_section)
        self.assertIn("Stop immediately if secrets or credentials are encountered.", prompt_section)
        output = format_orchestrator_result(result)
        self.assertIn("Local MCP Context: Project knowledge found docs:", output)

    def test_run_mode_with_include_github_context_shows_github_context_section(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")
        pr_body = "Implements safe GitHub context support."
        client = MockGitHubReadClient(
            pull_requests={
                ("openai/example", 5): {
                    "title": "Add GitHub context",
                    "state": "open",
                    "review_state": "approved",
                    "body": pr_body,
                }
            },
            changed_files={
                ("openai/example", 5): ["src/module.py"],
            },
            ci_statuses={
                "openai/example": {
                    "status": "success",
                    "summary": "Checks passed.",
                    "checks": ["unit-tests"],
                }
            },
        )

        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
            with patch(
                "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
                return_value=mocked_execution_result,
            ):
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix telemetry bug",
                    mode="run",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                    include_github_context=True,
                    github_repo="openai/example",
                    github_pr_number=5,
                    github_read_client=client,
                )

        self.assertIn("GitHub Context:", result["report_text"])
        self.assertIn("GitHub repo: openai/example", result["report_text"])
        self.assertIn("PR context: available", result["report_text"])
        self.assertIn("CI status context: available", result["report_text"])
        self.assertIn("CI status: passed", result["report_text"])
        self.assertIn("GitHub CI passed.", result["report_text"])
        prompt_section = result["report_text"].split("Codex prompt package:\n", 1)[1].split(
            "\n\nCodex execution contract:\n",
            1,
        )[0]
        self.assertIn(
            "Context signals:",
            prompt_section,
        )
        self.assertIn(
            "- GitHub PR: repo openai/example; available; changed files available",
            prompt_section,
        )
        self.assertIn(
            "- GitHub CI: repo openai/example; available (success)",
            prompt_section,
        )
        self.assertNotIn(pr_body, prompt_section)

    def test_run_mode_with_include_error_context_shows_error_context_section(self) -> None:
        repo_path = self.project_root / "run-error-context-repo"
        repo_path.mkdir()
        log_path = repo_path / "logs" / "dev.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_text = "Server started\nHealth check pending\n"
        log_path.write_text(log_text, encoding="utf-8")
        target_file = repo_path / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")

        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        with patch(
            "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
            return_value=mocked_execution_result,
        ):
            result = run_orchestrator(
                project_path=str(repo_path),
                task_text="fix telemetry bug",
                mode="run",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
                allowed_files=["src/module.py"],
                confirm_codex_prompt=True,
                confirm_codex_execution=True,
                include_error_context=True,
                error_tool_name="local.dev_logs.read",
                error_provider="local",
                error_log_path=str(log_path),
            )

        self.assertIn("Error Context:", result["report_text"])
        prompt_section = result["report_text"].split("Codex prompt package:\n", 1)[1].split(
            "\n\nCodex execution contract:\n",
            1,
        )[0]
        self.assertIn("Context signals:", prompt_section)
        self.assertIn("- Error context: unavailable", prompt_section)
        self.assertIn("- Local log context: available", prompt_section)
        self.assertNotIn(log_text.strip(), prompt_section)

    def test_run_mode_error_monitoring_unavailable_signal_is_safe(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")
        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
                return_value=mocked_execution_result,
            ):
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix telemetry bug",
                    mode="run",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                    include_error_context=True,
                    error_tool_name="error_monitoring.issue.read",
                    error_provider="sentry",
                    error_issue_id=17,
                )

        self.assertIn("Error Context:", result["report_text"])
        self.assertIn("ERROR_MONITORING_TOKEN is not set", result["report_text"])
        self.assertNotIn("sk_", result["report_text"])
        prompt_section = result["report_text"].split("Codex prompt package:\n", 1)[1].split(
            "\n\nCodex execution contract:\n",
            1,
        )[0]
        self.assertIn("- Error context: unavailable", prompt_section)
        self.assertIn("- Local log context: unavailable", prompt_section)

    def test_run_mode_error_monitoring_available_signal_does_not_dump_stack_trace(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")
        stack_trace = "Traceback line 1\nTraceback line 2\nTraceback line 3"
        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }
        client = MockErrorLogsClient(
            issues={
                ("mock", None, 7): {
                    "title": "Planner crash",
                    "status": "open",
                    "summary": "Planner crashed during context build.",
                    "stack_trace": stack_trace,
                }
            }
        )

        with patch(
            "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
            return_value=mocked_execution_result,
        ):
            result = run_orchestrator(
                project_path=str(self.project_root),
                task_text="fix telemetry bug",
                mode="run",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
                allowed_files=["src/module.py"],
                confirm_codex_prompt=True,
                confirm_codex_execution=True,
                include_error_context=True,
                error_tool_name="error_monitoring.issue.read",
                error_provider="mock",
                error_issue_id=7,
                error_read_client=client,
            )

        prompt_section = result["report_text"].split("Codex prompt package:\n", 1)[1].split(
            "\n\nCodex execution contract:\n",
            1,
        )[0]
        self.assertIn("- Error context: available", prompt_section)
        self.assertIn("- Local log context: unavailable", prompt_section)
        self.assertNotIn(stack_trace, prompt_section)

    def test_run_mode_without_error_context_keeps_behavior_unchanged(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")

        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        with patch(
            "orchestration.orchestrator_controller.run_error_logs_tool"
        ) as mocked_error_logs:
            with patch(
                "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
                return_value=mocked_execution_result,
            ):
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix telemetry bug",
                    mode="run",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                )

        self.assertNotIn("Error Context:", result["report_text"])
        mocked_error_logs.assert_not_called()

    def test_run_mode_passes_github_client_gh_into_github_context_collection(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")
        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        with patch(
            "orchestration.orchestrator_controller._collect_github_context",
            return_value=(
                "GitHub repo: openai/example",
                "GitHub repo: openai/example\nPR context: unavailable\nContext blocks: none",
                [],
                {"issue": "not requested", "pr": "unavailable", "pr_changed_files": "unavailable", "ci": "unavailable"},
            ),
        ) as mocked_collect:
            with patch(
                "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
                return_value=mocked_execution_result,
            ):
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix telemetry bug",
                    mode="run",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                    include_github_context=True,
                    github_repo="openai/example",
                    github_pr_number=5,
                    github_client="gh",
                )

        self.assertIn("GitHub Context:", result["report_text"])
        self.assertEqual(mocked_collect.call_args.kwargs["github_read_client"], "gh")

    def test_run_mode_github_context_missing_token_does_not_crash_or_leak(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")
        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
                return_value=mocked_execution_result,
            ):
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix telemetry bug",
                    mode="run",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                    include_github_context=True,
                    github_repo="openai/example",
                    github_issue_number=12,
                )

        self.assertIn("GitHub Context:", result["report_text"])
        self.assertIn("GITHUB_TOKEN is not set", result["report_text"])
        self.assertNotIn("ghs_", result["report_text"])

    def test_run_mode_guidance_includes_repo_and_issue_availability(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")
        issue_body = "Detailed issue body that should not appear in prompt."
        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        def github_side_effect(tool_name: str, repo: str, **kwargs: object) -> dict[str, object]:
            if tool_name == "github.issue.read":
                return {
                    "executed": True,
                    "blocked": False,
                    "tool_name": tool_name,
                    "repo": repo,
                    "item_id": 12,
                    "content_summary": "Issue #12: Fix planner output",
                    "raw_content": issue_body,
                    "context_blocks": [
                        {
                            "source_type": "github",
                            "source_name": "openai/example#12",
                            "tool_name": tool_name,
                            "source_path": "openai/example#12",
                            "content": "GitHub issue preview",
                            "safe": True,
                            "blocked": False,
                            "reason": "none",
                            "char_count": 20,
                        }
                    ],
                    "message": "github.issue.read completed successfully.",
                    "safety_notes": ["gh CLI read-only client: no write or mutation command was used."],
                    "decision": {"allowed": True},
                }
            return {
                "executed": False,
                "blocked": True,
                "tool_name": tool_name,
                "repo": repo,
                "item_id": kwargs.get("pr_number"),
                "content_summary": "not available",
                "raw_content": None,
                "context_blocks": [],
                "message": f"{tool_name} unavailable.",
                "safety_notes": ["none"],
                "decision": {"allowed": True},
            }

        with patch(
            "orchestration.orchestrator_controller.run_github_read_tool",
            side_effect=github_side_effect,
        ):
            with patch(
                "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
                return_value=mocked_execution_result,
            ):
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix telemetry bug",
                    mode="run",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                    include_github_context=True,
                    github_repo="openai/example",
                    github_issue_number=12,
                    github_client="gh",
                )

        prompt_section = result["report_text"].split("Codex prompt package:\n", 1)[1].split(
            "\n\nCodex execution contract:\n",
            1,
        )[0]
        self.assertIn(
            "- GitHub issue: repo openai/example; available",
            prompt_section,
        )
        self.assertIn("- GitHub CI: repo openai/example; unavailable", prompt_section)
        self.assertNotIn(issue_body, prompt_section)

    def test_run_mode_guidance_includes_ci_failure_signal_when_available(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")
        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        client = MockGitHubReadClient(
            ci_statuses={
                "openai/example": {
                    "status": "failure",
                    "summary": "Checks failed.",
                    "checks": ["unit-tests: failure"],
                }
            }
        )

        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
            with patch(
                "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
                return_value=mocked_execution_result,
            ):
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix telemetry bug",
                    mode="run",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                    include_github_context=True,
                    github_repo="openai/example",
                    github_read_client=client,
                )

        prompt_section = result["report_text"].split("Codex prompt package:\n", 1)[1].split(
            "\n\nCodex execution contract:\n",
            1,
        )[0]
        self.assertIn("- GitHub CI: repo openai/example; available (failure)", prompt_section)
        self.assertEqual(result["decision"], "Needs revision")
        self.assertIn("CI status: failed", result["report_text"])
        self.assertIn("GitHub CI reported a failed status", result["report_text"])

    def test_run_mode_verification_gate_ci_unknown_does_not_block(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")
        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        client = MockGitHubReadClient(
            ci_statuses={
                "openai/example": {
                    "status": "neutral",
                    "summary": "Checks completed with unknown overall status.",
                    "checks": ["unit-tests: neutral"],
                }
            }
        )

        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
            with patch(
                "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
                return_value=mocked_execution_result,
            ):
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix telemetry bug",
                    mode="run",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                    include_github_context=True,
                    github_repo="openai/example",
                    github_read_client=client,
                )

        self.assertEqual(result["decision"], "Approved")
        self.assertIn("CI status: unknown", result["report_text"])
        self.assertIn("GitHub CI status was unavailable or unknown.", result["report_text"])

    def test_run_mode_verification_gate_ci_failure_does_not_override_blocked_decision(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")
        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py", "README.md"],
        }
        client = MockGitHubReadClient(
            ci_statuses={
                "openai/example": {
                    "status": "failure",
                    "summary": "Checks failed.",
                    "checks": ["unit-tests: failure"],
                }
            }
        )

        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
            with patch(
                "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
                return_value=mocked_execution_result,
            ):
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix telemetry bug",
                    mode="run",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                    include_github_context=True,
                    github_repo="openai/example",
                    github_read_client=client,
                )

        self.assertEqual(result["decision"], "Blocked")
        self.assertIn("CI status: failed", result["report_text"])
        self.assertIn("Final verification decision: Blocked", result["report_text"])

    def test_run_mode_gh_pr_context_appears_in_report_when_data_is_available(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")
        pr_body = "Sensitive but safe report body"
        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        def github_side_effect(tool_name: str, repo: str, **kwargs: object) -> dict[str, object]:
            if tool_name == "github.pr.read":
                return {
                    "executed": True,
                    "blocked": False,
                    "tool_name": tool_name,
                    "repo": repo,
                    "item_id": 5,
                    "content_summary": "PR #5: Add GitHub context",
                    "raw_content": pr_body,
                    "context_blocks": [
                        {
                            "source_type": "github",
                            "source_name": "openai/example#5",
                            "tool_name": tool_name,
                            "source_path": "openai/example#5",
                            "content": pr_body,
                            "safe": True,
                            "blocked": False,
                            "reason": "none",
                            "char_count": len(pr_body),
                        }
                    ],
                    "message": "github.pr.read completed successfully.",
                    "safety_notes": ["gh CLI read-only client: no write or mutation command was used."],
                    "decision": {"allowed": True},
                }
            if tool_name == "github.pr.changed_files":
                return {
                    "executed": True,
                    "blocked": False,
                    "tool_name": tool_name,
                    "repo": repo,
                    "item_id": 5,
                    "content_summary": "PR #5 changed files: 1",
                    "raw_content": "src/module.py",
                    "context_blocks": [],
                    "message": "github.pr.changed_files completed successfully.",
                    "safety_notes": ["gh CLI read-only client: no write or mutation command was used."],
                    "decision": {"allowed": True},
                }
            return {
                "executed": False,
                "blocked": True,
                "tool_name": tool_name,
                "repo": repo,
                "item_id": kwargs.get("pr_number"),
                "content_summary": "not available",
                "raw_content": None,
                "context_blocks": [],
                "message": f"{tool_name} unavailable.",
                "safety_notes": ["none"],
                "decision": {"allowed": True},
            }

        with patch(
            "orchestration.orchestrator_controller.run_github_read_tool",
            side_effect=github_side_effect,
        ):
            with patch(
                "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
                return_value=mocked_execution_result,
            ):
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix telemetry bug",
                    mode="run",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                    include_github_context=True,
                    github_repo="openai/example",
                    github_pr_number=5,
                    github_client="gh",
                )

        self.assertIn("PR context: available", result["report_text"])
        prompt_section = result["report_text"].split("Codex prompt package:\n", 1)[1].split(
            "\n\nCodex execution contract:\n",
            1,
        )[0]
        self.assertIn(
            "- GitHub PR: repo openai/example; available; changed files available",
            prompt_section,
        )
        self.assertIn("- GitHub CI: repo openai/example; unavailable", prompt_section)
        self.assertNotIn(pr_body, prompt_section)

    def test_run_mode_without_github_context_keeps_behavior_unchanged(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")

        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        with patch(
            "orchestration.orchestrator_controller.run_github_read_tool"
        ) as mocked_github_read:
            with patch(
                "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
                return_value=mocked_execution_result,
            ):
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix telemetry bug",
                    mode="run",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                )

        self.assertNotIn("GitHub Context:", result["report_text"])
        mocked_github_read.assert_not_called()

    def test_run_mode_blocked_local_context_is_not_included_in_pre_codex_guidance(self) -> None:
        repo_path = self.project_root / "run-secret-context-repo"
        repo_path.mkdir()
        secret_value = "super-secret-token-123"
        (repo_path / "AGENTS.md").write_text(f"API_TOKEN={secret_value}\n", encoding="utf-8")
        target_file = repo_path / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")

        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        with patch(
            "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
            return_value=mocked_execution_result,
        ):
            result = run_orchestrator(
                project_path=str(repo_path),
                task_text="fix auth bug",
                mode="run",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
                allowed_files=["src/module.py"],
                confirm_codex_prompt=True,
                confirm_codex_execution=True,
                include_local_mcp_context=True,
            )

        prompt_section = result["report_text"].split("Codex prompt package:\n", 1)[1].split(
            "\n\nCodex execution contract:\n",
            1,
        )[0]
        self.assertIn("Context signals:", prompt_section)
        self.assertIn("- Local project knowledge: found AGENTS.md", prompt_section)
        self.assertIn("missing docs/product-context.md", prompt_section)
        self.assertIn("- Local git state: Not a git repository.", prompt_section)
        self.assertNotIn(secret_value, prompt_section)

    def test_run_mode_failed_codex_execution_reports_failure_safely(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")

        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 1,
            "timed_out": False,
            "stdout": "",
            "stderr": "execution failed\n",
            "contract": {
                "can_execute": True,
                "approval_required": True,
                "risk_level": "high",
                "approval_gate": {
                    "approval_required": True,
                    "risk_level": "high",
                    "reasons": ["Codex execution requests require explicit approval."],
                    "blocked_actions": ["codex_execution"],
                    "recommended_user_confirmation": "Request explicit user approval before proceeding with: codex_execution.",
                },
                "blocked_reasons": ["none"],
                "allowed_files": [str(target_file.resolve())],
                "safety_requirements": ["No execution is performed by this safety contract."],
                "execution_summary": "All Codex execution safety requirements passed. No execution was performed.",
            },
            "message": "Codex command exited with return code 1.",
            "post_review_ran": False,
            "post_review_decision": "not run",
            "post_review_report": "",
            "post_review_message": "Post-Codex review did not run because Codex execution did not complete successfully.",
            "post_review_should_block_save": False,
            "post_review_changed_files": [],
        }

        with patch(
            "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
            return_value=mocked_execution_result,
        ):
            with patch("orchestration.orchestrator_controller.run_test_command") as mocked_test_runner:
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix telemetry bug",
                    mode="run",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                    test_command=["python", "-m", "unittest"],
                )

        self.assertEqual(result["decision"], "Needs revision")
        self.assertIn("Codex command exited with return code 1.", result["errors"][0])
        mocked_test_runner.assert_not_called()
        output = format_orchestrator_result(result)
        self.assertIn("Coding Run Summary", output)
        self.assertIn("- Scope: unknown", output)
        self.assertIn("- Codex result: failed", output)
        self.assertIn("- Verification: Needs revision", output)
        self.assertIn("Gate status: blocked or failed", output)
        self.assertIn("Codex execution result: Executed: yes", output)
        self.assertIn("Post-Codex review decision: not run", output)
        self.assertIn("Final verification decision: Needs revision", result["report_text"])
        self.assertIn(
            "Test execution result: Not run because Codex execution did not complete successfully.",
            output,
        )

    def test_run_mode_save_report_saves_safe_final_report(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")

        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {
                "can_execute": True,
                "approval_required": True,
                "risk_level": "high",
                "approval_gate": {
                    "approval_required": True,
                    "risk_level": "high",
                    "reasons": ["Codex execution requests require explicit approval."],
                    "blocked_actions": ["codex_execution"],
                    "recommended_user_confirmation": "Request explicit user approval before proceeding with: codex_execution.",
                },
                "blocked_reasons": ["none"],
                "allowed_files": [str(target_file.resolve())],
                "safety_requirements": ["No execution is performed by this safety contract."],
                "execution_summary": "All Codex execution safety requirements passed. No execution was performed.",
            },
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        mocked_test_result = {
            "ran": True,
            "blocked": False,
            "passed": True,
            "return_code": 0,
            "timed_out": False,
            "stdout": "ok\n",
            "stderr": "",
            "message": "Test command completed successfully.",
        }

        with patch(
            "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
            return_value=mocked_execution_result,
        ):
            with patch(
                "orchestration.orchestrator_controller.run_test_command",
                return_value=mocked_test_result,
            ):
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix telemetry bug",
                    mode="run",
                    save_report=True,
                    ai_brain_path=str(self.ai_brain_root),
                    reports_dir="reports",
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                    test_command=["python", "-m", "unittest"],
                )

        self.assertIsNotNone(result["report_path"])
        self.assertTrue(Path(str(result["report_path"])).is_file())
        output = format_orchestrator_result(result)
        self.assertIn("Report path:", output)
        self.assertIn("Gate status: passed", output)

    def test_run_mode_secret_like_post_diff_blocks_save_without_leak(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")
        secret_value = "super-secret-token-123"

        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {
                "can_execute": True,
                "approval_required": True,
                "risk_level": "high",
                "approval_gate": {
                    "approval_required": True,
                    "risk_level": "high",
                    "reasons": ["Codex execution requests require explicit approval."],
                    "blocked_actions": ["codex_execution"],
                    "recommended_user_confirmation": "Request explicit user approval before proceeding with: codex_execution.",
                },
                "blocked_reasons": ["none"],
                "allowed_files": [str(target_file.resolve())],
                "safety_requirements": ["No execution is performed by this safety contract."],
                "execution_summary": "All Codex execution safety requirements passed. No execution was performed.",
            },
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Blocked",
            "post_review_report": "Summary: Post-Codex diff review output blocked because secret-like content was detected. Findings are redacted.\nDecision: Blocked\nKey findings: Detected token-style assignment on line 1 for API_TOKEN. Value redacted.",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": True,
            "post_review_changed_files": [".env"],
        }

        with patch(
            "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
            return_value=mocked_execution_result,
        ):
            with patch("orchestration.orchestrator_controller.run_test_command") as mocked_test_runner:
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix auth bug",
                    mode="run",
                    save_report=True,
                    ai_brain_path=str(self.ai_brain_root),
                    reports_dir="reports",
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                    test_command=["python", "-m", "unittest"],
                )

        self.assertIsNone(result["report_path"])
        self.assertIn(
            "Report saving blocked due to secret-like content detected in the post-Codex review flow.",
            result["errors"],
        )
        self.assertIn("Final verification decision: Blocked", result["report_text"])
        mocked_test_runner.assert_not_called()
        self.assertNotIn(secret_value, result["report_text"])

    def test_run_mode_failing_tests_set_final_decision_to_needs_revision(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")

        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }
        mocked_test_result = {
            "ran": True,
            "blocked": False,
            "passed": False,
            "return_code": 1,
            "timed_out": False,
            "stdout": "fail\n",
            "stderr": "",
            "message": "Test command exited with return code 1.",
        }

        with patch(
            "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
            return_value=mocked_execution_result,
        ):
            with patch(
                "orchestration.orchestrator_controller.run_test_command",
                return_value=mocked_test_result,
            ):
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix telemetry bug",
                    mode="run",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                    test_command=["python", "-m", "unittest"],
                )

        self.assertEqual(result["decision"], "Needs revision")
        self.assertIn("Test command exited with return code 1.", result["errors"])
        self.assertIn("Final verification decision: Needs revision", result["report_text"])
        self.assertIn("Passed: no", result["report_text"])
        output = format_orchestrator_result(result)
        self.assertIn("- Verification: Needs revision", output)
        self.assertIn("- Tests: failed", output)

    def test_run_mode_without_test_command_shows_tests_not_run(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")

        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py"],
        }

        with patch(
            "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
            return_value=mocked_execution_result,
        ):
            result = run_orchestrator(
                project_path=str(self.project_root),
                task_text="fix telemetry bug",
                mode="run",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
                allowed_files=["src/module.py"],
                confirm_codex_prompt=True,
                confirm_codex_execution=True,
            )

        self.assertIn("Final verification decision: Approved", result["report_text"])
        self.assertIn("Test status: not run", result["report_text"])
        self.assertIn("Tests not run because no test command was provided.", result["report_text"])
        output = format_orchestrator_result(result)
        self.assertIn("- Test status: not run", output)
        self.assertIn("Report text:\nPlanner report:", output)

    def test_run_mode_scope_violation_prevents_test_execution_and_blocks_decision(self) -> None:
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")

        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_report": "Summary: reviewed\nDecision: Approved",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["src/module.py", "README.md"],
        }

        with patch(
            "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
            return_value=mocked_execution_result,
        ):
            with patch("orchestration.orchestrator_controller.run_test_command") as mocked_test_runner:
                result = run_orchestrator(
                    project_path=str(self.project_root),
                    task_text="fix telemetry bug",
                    mode="run",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["src/module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                    test_command=["python", "-m", "unittest"],
                )

        self.assertEqual(result["decision"], "Blocked")
        self.assertIn("Scope enforcement detected changes outside the explicitly allowed files.", result["errors"])
        self.assertIn("Scope enforcement result:", result["report_text"])
        self.assertIn("Passed: no", result["report_text"])
        self.assertIn("Final verification decision: Blocked", result["report_text"])
        self.assertIn("Scope violation detected after Codex execution.", result["report_text"])
        self.assertIn("Not run because scope enforcement detected changes outside the allowed files.", result["report_text"])
        mocked_test_runner.assert_not_called()
        output = format_orchestrator_result(result)
        self.assertIn("- Scope: failed", output)
        self.assertIn("- Verification: Blocked", output)
        self.assertIn(
            "- Next action: Review the out-of-scope changes and revert any files outside the allowed scope manually.",
            output,
        )

    def test_agents_package_import_works_with_dunder_init(self) -> None:
        from agents import agent_runtime

        self.assertTrue(hasattr(agent_runtime, "run_agent_workflow"))


class OrchestratorControllerCliTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.project_root = self.approved_root / "project"
        self.project_root.mkdir()
        self.ai_brain_root = self.approved_root / "ai-brain"
        (self.ai_brain_root / "02-Code").mkdir(parents=True)
        (self.ai_brain_root / "CORE-RULES.md").write_text("core", encoding="utf-8")
        (self.ai_brain_root / "README-FOR-AI.md").write_text("readme", encoding="utf-8")
        (self.ai_brain_root / "02-Code" / "AI-Brain-Priority-Tiers.md").write_text("tiers", encoding="utf-8")
        (self.ai_brain_root / "02-Code" / "Context-Budget-Rules.md").write_text("budget", encoding="utf-8")

        self.fake_config = {
            "ai_brain_path": str(self.ai_brain_root),
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": [str(self.approved_root)],
        }

        self.report_root_patch = patch.object(report_writer, "PROJECT_ROOT", self.root)
        self.report_root_patch.start()

    def tearDown(self) -> None:
        self.report_root_patch.stop()
        self.temp_dir.cleanup()

    def init_git_repo(self, repo_path: Path) -> Path:
        repo_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init", str(repo_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        return repo_path

    def test_cli_status_mode_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run(["--run-orchestrator", "--mode", "status"])

        output = stdout.getvalue()

        self.assertIn("Summary: Read-only orchestration status completed.", output)
        self.assertIn("Mode: status", output)
        self.assertIn("Report text:", output)

    def test_cli_save_report_writes_under_reports(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run(
                    [
                        "--run-orchestrator",
                        "--mode",
                        "plan",
                        "--task",
                        "fix telemetry bug",
                        "--save-report",
                    ]
                )

        output = stdout.getvalue()
        created_reports = list((self.root / "reports").glob("*.md"))

        self.assertIn("Report path:", output)
        self.assertEqual(len(created_reports), 1)
        self.assertEqual(created_reports[0].parent, self.root / "reports")

    def test_cli_missing_task_for_plan_gives_clear_error(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with self.assertRaisesRegex(
                SystemExit,
                "Orchestrator error: Plan mode requires task text.",
            ):
                with redirect_stdout(stdout):
                    cli.run(["--run-orchestrator", "--mode", "plan"])

        output = stdout.getvalue()
        self.assertIn("Errors: Plan mode requires task text.", output)

    def test_cli_review_diff_without_project_gives_clear_error(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with self.assertRaisesRegex(
                SystemExit,
                "Orchestrator error: Review-diff mode requires project path.",
            ):
                with redirect_stdout(stdout):
                    cli.run(["--run-orchestrator", "--mode", "review-diff", "--task", "fix telemetry bug"])

        output = stdout.getvalue()
        self.assertIn("Errors: Review-diff mode requires project path.", output)

    def test_cli_unapproved_project_is_rejected(self) -> None:
        outside_project = self.root / "outside-project"
        outside_project.mkdir()

        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with self.assertRaisesRegex(
                SystemExit,
                "Orchestrator error: Target path is outside approved paths:",
            ):
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--run-orchestrator",
                            "--mode",
                            "status",
                            "--project",
                            str(outside_project),
                        ]
                    )

        output = stdout.getvalue()
        self.assertIn("Errors: Target path is outside approved paths:", output)

    def test_cli_review_diff_mode_uses_multi_agent_review(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "review-repo")
        changed_file = repo_path / "config.py"
        changed_file.write_text("FEATURE_FLAG = True\n", encoding="utf-8")
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run(
                    [
                        "--run-orchestrator",
                        "--mode",
                        "review-diff",
                        "--project",
                        str(repo_path),
                        "--task",
                        "fix telemetry bug",
                    ]
                )

        output = stdout.getvalue()

        self.assertIn("Mode: review-diff", output)
        self.assertIn("Decision:", output)
        self.assertIn("Agents used:", output)

    def test_cli_run_orchestrator_does_not_use_mcp_or_codex_execution(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "evaluate_mcp_tool_request") as mocked_mcp:
                with patch.object(cli, "generate_codex_prompt_package") as mocked_codex:
                    with redirect_stdout(stdout):
                        cli.run(
                            [
                                "--run-orchestrator",
                                "--mode",
                                "plan",
                                "--task",
                                "fix telemetry bug",
                            ]
                        )

        output = stdout.getvalue()

        self.assertIn("Summary:", output)
        mocked_mcp.assert_not_called()
        mocked_codex.assert_not_called()

    def test_cli_plan_with_local_mcp_context_does_not_use_external_mcp_execution(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "cli-plan-context-repo")
        (repo_path / "AGENTS.md").write_text("Project overview\n", encoding="utf-8")
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "evaluate_mcp_tool_request") as mocked_mcp:
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--run-orchestrator",
                            "--mode",
                            "plan",
                            "--project",
                            str(repo_path),
                            "--task",
                            "fix telemetry bug",
                            "--include-local-mcp-context",
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn("Local MCP Context: Project knowledge found docs: AGENTS.md", output)
        mocked_mcp.assert_not_called()

    def test_cli_plan_with_error_context_shows_safe_section(self) -> None:
        repo_path = self.project_root / "cli-plan-error-context-repo"
        repo_path.mkdir()
        log_path = repo_path / "logs" / "dev.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("Server started\n", encoding="utf-8")
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run(
                    [
                        "--run-orchestrator",
                        "--mode",
                        "plan",
                        "--project",
                        str(repo_path),
                        "--task",
                        "fix telemetry bug",
                        "--include-error-context",
                        "--error-tool-name",
                        "local.dev_logs.read",
                        "--error-provider",
                        "local",
                        "--error-log-path",
                        str(log_path),
                    ]
                )

        output = stdout.getvalue()

        self.assertIn("Error Context: Executed: yes", output)
        self.assertIn("Tool name: local.dev_logs.read", output)

    def test_cli_plan_with_github_context_shows_safe_foundation_only_message(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "evaluate_mcp_tool_request") as mocked_legacy_mcp:
                with patch.dict(os.environ, {}, clear=True):
                    with redirect_stdout(stdout):
                        cli.run(
                            [
                                "--run-orchestrator",
                                "--mode",
                                "plan",
                                "--task",
                                "fix telemetry bug",
                                "--include-github-context",
                                "--github-repo",
                                "openai/example",
                                "--github-issue-number",
                                "12",
                            ]
                        )

        output = stdout.getvalue()

        self.assertIn("GitHub Context: GitHub repo: openai/example", output)
        self.assertIn("GITHUB_TOKEN is not set", output)
        mocked_legacy_mcp.assert_not_called()

    def test_cli_plan_with_github_context_and_gh_client_does_not_report_missing_github_token_when_runner_succeeds(self) -> None:
        stdout = StringIO()
        mocked_result = {
            "summary": "bug fix task; high confidence; medium risk; no project context; 4/4 AI-Brain core files available.",
            "mode": "plan",
            "task_type": "bug fix",
            "project_context_summary": None,
            "agent_runtime_mode": "deterministic",
            "agent_llm_adapter_used": "none",
            "agent_llm_provider": "disabled",
            "agent_provider_available": "no",
            "agent_provider_execution_status": "not requested",
            "agent_fallback_used": "no",
            "agent_fallback_reason": "none",
            "agent_runtime_notes": "Deterministic agent runtime is the default execution path.",
            "github_context_summary": "GitHub repo: openai/example",
            "agent_runtime_summary": "Agents used: Planner",
            "decision": None,
            "report_path": None,
            "errors": [],
            "report_text": (
                "Summary: bug fix task\n\n"
                "GitHub Context:\n"
                "GitHub repo: openai/example\n"
                "Issue context: available\n"
                "Context blocks: 1\n"
            ),
        }

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "run_orchestrator", return_value=mocked_result):
                with patch.dict(os.environ, {}, clear=True):
                    with redirect_stdout(stdout):
                        cli.run(
                            [
                                "--run-orchestrator",
                                "--mode",
                                "plan",
                                "--task",
                                "fix telemetry bug",
                                "--include-github-context",
                                "--github-repo",
                                "openai/example",
                                "--github-issue-number",
                                "12",
                                "--github-client",
                                "gh",
                            ]
                        )

        output = stdout.getvalue()

        self.assertIn("GitHub Context: GitHub repo: openai/example", output)
        self.assertNotIn("GITHUB_TOKEN is not set", output)

    def test_cli_run_mode_missing_allowed_file_blocks(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with self.assertRaisesRegex(
                SystemExit,
                "Orchestrator error: Run mode requires at least one allowed file.",
            ):
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--run-orchestrator",
                            "--mode",
                            "run",
                            "--project",
                            str(self.project_root),
                            "--task",
                            "fix telemetry bug",
                            "--confirm-codex-prompt",
                            "--confirm-codex-execution",
                        ]
                    )

    def test_cli_run_mode_missing_confirmations_block(self) -> None:
        stdout = StringIO()
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with self.assertRaisesRegex(
                SystemExit,
                "Orchestrator error: Run mode requires Codex prompt confirmation.",
            ):
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--run-orchestrator",
                            "--mode",
                            "run",
                            "--project",
                            str(self.project_root),
                            "--task",
                            "fix telemetry bug",
                            "--allowed-file",
                            "src/module.py",
                        ]
                    )

    def test_cli_run_mode_mocked_successful_execution_runs_full_flow(self) -> None:
        stdout = StringIO()
        target_file = self.project_root / "src" / "module.py"
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("print('safe')\n", encoding="utf-8")

        mocked_execution_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "execution ok\n",
            "stderr": "",
            "contract": {
                "can_execute": True,
                "approval_required": True,
                "risk_level": "high",
                "approval_gate": {
                    "approval_required": True,
                    "risk_level": "high",
                    "reasons": ["Codex execution requests require explicit approval."],
                    "blocked_actions": ["codex_execution"],
                    "recommended_user_confirmation": "Request explicit user approval before proceeding with: codex_execution.",
                },
                "blocked_reasons": ["none"],
                "allowed_files": [str(target_file.resolve())],
                "safety_requirements": ["No execution is performed by this safety contract."],
                "execution_summary": "All Codex execution safety requirements passed. No execution was performed.",
            },
            "message": "Codex command completed successfully.",
            "post_review_ran": True,
            "post_review_decision": "Approved with changes",
            "post_review_report": "Summary: Reviewed 1 changed file(s).\nDecision: Approved with changes",
            "post_review_message": "Post-Codex diff review completed.",
            "post_review_should_block_save": False,
        }

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "evaluate_mcp_tool_request") as mocked_mcp:
                with patch(
                    "orchestration.orchestrator_controller.execute_codex_task_with_post_review",
                    return_value=mocked_execution_result,
                ):
                    with patch(
                        "orchestration.orchestrator_controller.run_test_command",
                        return_value={
                            "ran": True,
                            "blocked": False,
                            "passed": True,
                            "return_code": 0,
                            "timed_out": False,
                            "stdout": "ok\n",
                            "stderr": "",
                            "message": "Test command completed successfully.",
                        },
                    ):
                        with redirect_stdout(stdout):
                            cli.run(
                                [
                                    "--run-orchestrator",
                                    "--mode",
                                    "run",
                                    "--project",
                                    str(self.project_root),
                                    "--task",
                                    "fix telemetry bug",
                                    "--allowed-file",
                                    "src/module.py",
                                    "--confirm-codex-prompt",
                                    "--confirm-codex-execution",
                                    "--agent-runtime",
                                    "mock",
                                    "--llm-enabled",
                                    "--confirm-llm-agent",
                                    "--llm-provider",
                                    "mock",
                                    "--llm-model",
                                    "mock-model",
                                    "--test-command",
                                    "python -m unittest",
                                ]
                            )

        output = stdout.getvalue()

        self.assertIn("Mode: run", output)
        self.assertIn("Decision: Approved with changes", output)
        self.assertIn("Gate status: passed", output)
        self.assertIn("Planner summary:", output)
        self.assertIn("Edit plan summary:", output)
        self.assertIn("Codex execution result: Executed: yes", output)
        self.assertIn("Post-Codex review decision: Approved with changes", output)
        self.assertIn("Test execution result: Ran: yes", output)
        self.assertIn("Knowledge Update Proposal:\n- Destination:", output)
        self.assertIn("Agent runtime mode: mock", output)
        self.assertIn("Agent LLM adapter used: mock", output)
        self.assertIn("LLM provider: mock", output)
        self.assertIn("Provider available: yes", output)
        self.assertIn("Provider execution status: mock adapter executed", output)
        self.assertIn("Agent fallback used: no", output)
        self.assertIn("Agent Runtime Summary:", output)
        self.assertIn("Agents used: Planner", output)
        self.assertIn("Planner report:", output)
        self.assertIn("Codex execution result:", output)
        mocked_mcp.assert_not_called()
