import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from orchestration.orchestrator_controller import run_orchestrator
from tools.error_logs_mcp import MockErrorLogsClient
from tools.github_read_mcp import MockGitHubReadClient
import subprocess

class ContextSummaryTests(TestCase):
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

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def init_git_repo(self, repo_path: Path) -> Path:
        repo_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", str(repo_path)], capture_output=True, text=True, check=True)
        return repo_path

    def test_behavior_unchanged_when_no_context_flags_are_provided(self):
        result = run_orchestrator(
            task_text="fix bug",
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
        )
        self.assertNotIn("Context Summary:", result["report_text"])

    def test_plan_output_includes_context_summary_when_local_context_enabled(self):
        repo_path = self.init_git_repo(self.project_root / "local-repo")
        (repo_path / "AGENTS.md").write_text("Agent notes\n", encoding="utf-8")
        
        result = run_orchestrator(
            task_text="fix bug",
            project_path=str(repo_path),
            mode="plan",
            ai_brain_path=str(self.ai_brain_root),
            approved_paths=[str(self.approved_root)],
            include_local_mcp_context=True,
        )
        
        report = result["report_text"]
        self.assertIn("Context Summary:", report)
        self.assertIn("- Local project knowledge: partial", report)
        self.assertIn("- Local git context: available", report)
        self.assertIn("Local MCP Context:", report)
        self.assertNotIn("Agent notes", report.split("Local MCP Context:")[0])  # ensure no raw dump in summary

    def test_plan_output_includes_context_summary_when_github_context_enabled(self):
        client = MockGitHubReadClient(
            issues={("openai/example", 12): {"title": "Fix", "state": "open", "body": "raw github body"}}
        )
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}):
            result = run_orchestrator(
                task_text="fix bug",
                mode="plan",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
                include_github_context=True,
                github_repo="openai/example",
                github_issue_number=12,
                github_read_client=client,
            )
            
        report = result["report_text"]
        self.assertIn("Context Summary:", report)
        self.assertIn("- GitHub context: available", report)
        self.assertIn("- GitHub CI: unknown", report) # Because we didn't mock CI, it's unavailable -> unknown
        self.assertIn("GitHub Context:", report)
        self.assertNotIn("raw github body", report.split("GitHub Context:")[0])

    def test_run_output_includes_context_summary_when_error_context_enabled(self):
        repo_path = self.project_root / "error-repo"
        repo_path.mkdir()
        log_path = repo_path / "dev.log"
        log_path.write_text("raw error logs\n", encoding="utf-8")
        target_file = repo_path / "module.py"
        target_file.write_text("print('safe')\n", encoding="utf-8")

        mocked_exec_result = {
            "executed": True,
            "blocked": False,
            "return_code": 0,
            "timed_out": False,
            "stdout": "",
            "stderr": "",
            "contract": {"can_execute": True},
            "message": "ok",
            "post_review_ran": True,
            "post_review_decision": "Approved",
            "post_review_should_block_save": False,
            "post_review_changed_files": ["module.py"],
        }
        with patch("orchestration.orchestrator_controller.execute_codex_task_with_post_review", return_value=mocked_exec_result):
            result = run_orchestrator(
                project_path=str(repo_path),
                task_text="fix bug",
                mode="run",
                ai_brain_path=str(self.ai_brain_root),
                approved_paths=[str(self.approved_root)],
                allowed_files=["module.py"],
                confirm_codex_prompt=True,
                confirm_codex_execution=True,
                include_error_context=True,
                error_tool_name="local.dev_logs.read",
                error_provider="local",
                error_log_path=str(log_path),
            )
            
        report = result["report_text"]
        self.assertIn("Context Summary:", report)
        self.assertIn("- Error/log context: available", report)
        self.assertIn("Error Context:", report)
        self.assertNotIn("raw error logs", report.split("Error Context:")[0])

    def test_combined_local_github_error_context_summary_shows_all_statuses(self):
        repo_path = self.init_git_repo(self.project_root / "combo-repo")
        log_path = repo_path / "dev.log"
        log_path.write_text("raw log\n", encoding="utf-8")
        target_file = repo_path / "module.py"
        target_file.write_text("print('safe')\n", encoding="utf-8")

        github_client = MockGitHubReadClient(
            issues={("combo/repo", 1): {"title": "Fix", "state": "open", "body": "raw github body"}},
            ci_statuses={"combo/repo": {"status": "success", "summary": "ok", "checks": []}}
        )

        mocked_exec_result = {
            "executed": True, "blocked": False, "return_code": 0, "timed_out": False,
            "stdout": "", "stderr": "", "contract": {"can_execute": True}, "message": "ok",
            "post_review_ran": True, "post_review_decision": "Approved",
            "post_review_should_block_save": False, "post_review_changed_files": ["module.py"],
        }

        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}):
            with patch("orchestration.orchestrator_controller.execute_codex_task_with_post_review", return_value=mocked_exec_result):
                result = run_orchestrator(
                    project_path=str(repo_path),
                    task_text="fix combo bug",
                    mode="run",
                    ai_brain_path=str(self.ai_brain_root),
                    approved_paths=[str(self.approved_root)],
                    allowed_files=["module.py"],
                    confirm_codex_prompt=True,
                    confirm_codex_execution=True,
                    include_local_mcp_context=True,
                    include_github_context=True,
                    github_repo="combo/repo",
                    github_issue_number=1,
                    github_read_client=github_client,
                    include_error_context=True,
                    error_tool_name="local.dev_logs.read",
                    error_provider="local",
                    error_log_path=str(log_path),
                )
        
        report = result["report_text"]
        self.assertIn("Context Summary:", report)
        self.assertIn("- Local project knowledge: unavailable", report)  # no AGENTS.md etc
        self.assertIn("- Local git context: available", report)
        self.assertIn("- GitHub context: available", report)
        self.assertIn("- GitHub CI: passed", report)
        self.assertIn("- Error/log context: available", report)
        self.assertIn("Local MCP Context:", report)
        self.assertIn("GitHub Context:", report)
        self.assertIn("Error Context:", report)
