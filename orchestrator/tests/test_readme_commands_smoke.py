from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from core import report_writer


class ReadmeCommandSmokeTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.timestamp = datetime(2026, 5, 18, 12, 34, 56, tzinfo=timezone.utc)
        self.ai_brain_root = self.root / "ai-brain"
        (self.ai_brain_root / "02-Code").mkdir(parents=True)
        (self.ai_brain_root / "CORE-RULES.md").write_text("core", encoding="utf-8")
        (self.ai_brain_root / "README-FOR-AI.md").write_text("readme", encoding="utf-8")
        (self.ai_brain_root / "02-Code" / "AI-Brain-Priority-Tiers.md").write_text("tiers", encoding="utf-8")
        (self.ai_brain_root / "02-Code" / "Context-Budget-Rules.md").write_text("budget", encoding="utf-8")

        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.approved_file = self.approved_root / "notes.txt"
        self.approved_file.write_text("safe", encoding="utf-8")
        
        self.module_dir = self.approved_root / "src"
        self.module_dir.mkdir()
        self.module_file = self.module_dir / "module.py"
        self.module_file.write_text("print('safe')", encoding="utf-8")

        self.fake_config = {
            "ai_brain_path": str(self.ai_brain_root),
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": [str(self.approved_root), str(self.ai_brain_root)],
        }
        self.fake_core_status = {
            "checked_count": 4,
            "found_count": 4,
            "missing_count": 0,
            "missing_files": {},
        }
        self.report_root_patch = patch.object(report_writer, "PROJECT_ROOT", self.root)
        self.report_root_patch.start()

    def tearDown(self) -> None:
        self.report_root_patch.stop()
        self.temp_dir.cleanup()

    def test_run_orchestrator_status_command_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run(["--run-orchestrator", "--mode", "status"])

        output = stdout.getvalue()

        self.assertIn("Summary: Read-only orchestration status completed.", output)
        self.assertIn("Mode: status", output)
        self.assertIn("Report text:", output)

    def test_run_orchestrator_plan_command_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run(["--run-orchestrator", "--mode", "plan", "--task", "fix telemetry bug"])

        output = stdout.getvalue()

        self.assertIn("Mode: plan", output)
        self.assertIn("Task type: bug fix", output)
        self.assertIn("Report text:", output)
        self.assertIn("Suggested tests:", output)

    def test_run_orchestrator_plan_with_mock_provider_visibility_works(self) -> None:
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
                        "--agent-runtime",
                        "mock",
                        "--llm-enabled",
                        "--confirm-llm-agent",
                        "--llm-provider",
                        "mock",
                        "--llm-model",
                        "mock-model",
                    ]
                )

        output = stdout.getvalue()

        self.assertIn("Agent runtime mode: mock", output)
        self.assertIn("LLM provider: mock", output)
        self.assertIn("Provider available: yes", output)
        self.assertIn("Provider execution status: mock adapter executed", output)

    def test_run_orchestrator_plan_with_openai_provider_visibility_only_works(self) -> None:
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
                        "--agent-runtime",
                        "mock",
                        "--llm-enabled",
                        "--confirm-llm-agent",
                        "--llm-provider",
                        "openai",
                        "--llm-model",
                        "gpt-5",
                        "--llm-api-key-env",
                        "OPENAI_API_KEY",
                    ]
                )

        output = stdout.getvalue()

        self.assertIn("LLM provider: openai", output)
        self.assertIn("Provider available: no", output)
        self.assertIn("Provider execution status: real provider unavailable", output)
        self.assertIn("Fallback reason: OpenAI provider is unavailable or blocked.", output)
        self.assertNotIn("sk-", output)

    def test_run_orchestrator_plan_save_report_command_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch("core.report_writer.datetime") as mocked_datetime:
                mocked_datetime.now.return_value = self.timestamp
                mocked_datetime.strftime = datetime.strftime
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
        self.assertFalse((self.root / "approved" / "reports").exists())
        self.assertFalse((self.ai_brain_root / "reports").exists())

    def test_codex_prompt_command_with_ai_brain_guidance_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run(
                    [
                        "--codex-prompt",
                        "--task",
                        "fix telemetry bug",
                        "--project",
                        str(self.approved_root),
                        "--allowed-file",
                        "src/module.py",
                        "--confirm-codex-prompt",
                        "--include-ai-brain-context",
                    ]
                )

        output = stdout.getvalue()
        self.assertIn("AI-Brain Guidance included: yes", output)
        self.assertIn("AI-Brain Guidance:", output)

    def test_codex_prompt_command_without_ai_brain_guidance_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run(
                    [
                        "--codex-prompt",
                        "--task",
                        "fix telemetry bug",
                        "--project",
                        str(self.approved_root),
                        "--allowed-file",
                        "src/module.py",
                        "--confirm-codex-prompt",
                    ]
                )

        output = stdout.getvalue()
        self.assertIn("AI-Brain Guidance included: no", output)
        self.assertNotIn("AI-Brain Guidance:", output)

    def test_show_approved_paths_command_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run(["--show-approved-paths"])

        output = stdout.getvalue()

        self.assertIn("Configured approved paths count: 2", output)
        self.assertIn(str(self.approved_root), output)

    def test_check_approval_file_edit_command_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--check-approval", "--requested-action", "file_edit"])

        output = stdout.getvalue()

        self.assertIn("Approval required: yes", output)
        self.assertIn("Blocked actions: file_edit", output)

    def test_memory_suggest_command_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--memory-suggest", "--task", "fix telemetry bug"])

        output = stdout.getvalue()

        self.assertIn("Destination:", output)
        self.assertIn("Suggested target:", output)
        self.assertIn("Approval required:", output)

    def test_memory_plan_command_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--memory-plan", "--task", "review deploy config"])

        output = stdout.getvalue()

        self.assertIn("Destination:", output)
        self.assertIn("Can write plan:", output)
        self.assertIn("Next command hint:", output)

    def test_direct_plan_save_report_command_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with patch("core.report_writer.datetime") as mocked_datetime:
                    mocked_datetime.now.return_value = self.timestamp
                    mocked_datetime.strftime = datetime.strftime
                    with redirect_stdout(stdout):
                        cli.run(["--task", "fix telemetry bug", "--plan", "--save-report"])

        output = stdout.getvalue()
        created_reports = list((self.root / "reports").glob("*.md"))

        self.assertIn("Report saved to:", output)
        self.assertEqual(len(created_reports), 1)
        self.assertEqual(created_reports[0].parent, self.root / "reports")
        self.assertFalse((self.root / "approved" / "reports").exists())
        self.assertFalse((self.ai_brain_root / "reports").exists())

    def test_mcp_check_policy_only_command_with_approved_read_target_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run(
                    [
                        "--mcp-check",
                        "--mcp-tool-name",
                        "filesystem.read_file",
                        "--mcp-tool-type",
                        "read",
                        "--mcp-target-path",
                        str(self.approved_file),
                    ]
                )

        output = stdout.getvalue()

        self.assertIn("Tool name: filesystem.read_file", output)
        self.assertIn("Allowed: yes", output)
        self.assertIn("Approval Gate: Approval required: no", output)
        self.assertIn("Policy check only: no real MCP tool was executed.", output)

    def test_save_report_without_plan_review_or_orchestrator_gives_clear_error(self) -> None:
        with self.assertRaisesRegex(
            SystemExit,
            (
                "Report writer error: --save-report currently requires "
                "--plan, --review-diff, --run-orchestrator, or --execute-codex."
            ),
        ):
            cli.run(["--save-report"])

    def test_mcp_list_tools_smoke(self) -> None:
        stdout = StringIO()
        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run(["--mcp-list-tools"])
        output = stdout.getvalue()
        self.assertIn("filesystem.read_file", output)
        self.assertNotIn("mock data returned", output)

    def test_mcp_check_destructive_tool_reports_disabled(self) -> None:
        stdout = StringIO()
        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run([
                    "--mcp-check",
                    "--mcp-tool-name", "destructive.git.reset",
                    "--mcp-tool-type", "destructive"
                ])
        output = stdout.getvalue()
        self.assertIn("destructive.git.reset", output)
        self.assertIn("high", output)
        self.assertIn("Blocked: yes", output)

    def test_mcp_figma_missing_token_smoke(self) -> None:
        stdout = StringIO()
        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.dict("os.environ", {}, clear=True):
                with redirect_stdout(stdout):
                    cli.run([
                        "--figma-read",
                        "--figma-tool-name", "figma.frame.read",
                        "--figma-file-key", "fkey",
                        "--figma-frame-id", "fid",
                        "--figma-token-env", "NONEXISTENT_TOKEN"
                    ])
        output = stdout.getvalue()
        self.assertIn("Figma tool: figma.frame.read", output)
        self.assertIn("Blocked: yes", output)

    def test_mcp_docs_local_search_smoke(self) -> None:
        stdout = StringIO()
        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run([
                    "--docs-research-read",
                    "--docs-tool-name", "docs.search",
                    "--docs-provider", "local_docs",
                    "--docs-query", "test",
                    "--docs-source-path", str(self.approved_root)
                ])
        output = stdout.getvalue()
        self.assertIn("docs.search", output)
        self.assertIn("Executed: yes", output)

    def test_mcp_error_local_search_smoke(self) -> None:
        stdout = StringIO()
        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run([
                    "--error-logs-read",
                    "--error-tool-name", "local.dev_logs.search",
                    "--error-provider", "local",
                    "--error-query", "error",
                    "--project", str(self.approved_root),
                    "--error-log-path", str(self.approved_root)
                ])
        output = stdout.getvalue()
        self.assertIn("local.dev_logs.search", output)
        self.assertIn("Executed: yes", output)

    def test_mcp_github_unavailable_smoke(self) -> None:
        stdout = StringIO()
        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch("shutil.which", return_value=None):
                with redirect_stdout(stdout):
                    cli.run([
                        "--github-read",
                        "--github-tool-name", "github.issue.read",
                        "--github-repo", "org/repo",
                        "--github-issue", "1"
                    ])
        output = stdout.getvalue()
        self.assertIn("github.issue.read", output)
        self.assertIn("Blocked: yes", output)

    def test_mcp_controlled_write_preview_smoke(self) -> None:
        stdout = StringIO()
        with patch.object(cli, "load_config", return_value=self.fake_config):
            with redirect_stdout(stdout):
                cli.run([
                    "--mcp-write-preview",
                    "--mcp-write-tool-name", "memory.save_proposal",
                    "--mcp-write-target-path", str(self.approved_file),
                    "--mcp-write-content", "test content"
                ])
        output = stdout.getvalue()
        self.assertIn("memory.save_proposal", output)
        self.assertIn("Preview only: yes", output)
        self.assertIn("preview-only", output)

    def test_live_validation_script_exists_and_executable(self) -> None:
        import os
        script_path = Path("scripts/check_mcp_live_connectors.sh")
        self.assertTrue(script_path.exists(), "Live validation script does not exist.")
        self.assertTrue(os.access(script_path, os.X_OK), "Live validation script is not executable.")

    def test_demo_e2e_script_exists_and_executable(self) -> None:
        import os

        script_path = Path("scripts/demo_e2e_orchestrator.sh")
        self.assertTrue(script_path.exists(), "Demo E2E script does not exist.")
        self.assertTrue(os.access(script_path, os.X_OK), "Demo E2E script is not executable.")

    def test_demo_e2e_script_contains_safe_orchestrator_flags(self) -> None:
        content = Path("scripts/demo_e2e_orchestrator.sh").read_text(encoding="utf-8")

        self.assertIn("--include-ai-brain-context", content)
        self.assertIn("--test-command", content)
        self.assertIn("PYTHONDONTWRITEBYTECODE=1", content)

    def test_demo_e2e_script_uses_one_canonical_expected_sentence(self) -> None:
        content = Path("scripts/demo_e2e_orchestrator.sh").read_text(encoding="utf-8")

        self.assertIn('EXPECTED_SENTENCE="The smoke tests validate the README."', content)
        self.assertIn('TASK_TEXT="Add this exact sentence to README.md: \\"$EXPECTED_SENTENCE\\""', content)
        self.assertIn('self.assertIn("$EXPECTED_SENTENCE", content)', content)

    def test_demo_e2e_script_task_and_test_expectation_match(self) -> None:
        content = Path("scripts/demo_e2e_orchestrator.sh").read_text(encoding="utf-8")

        self.assertIn('Add this exact sentence to README.md:', content)
        self.assertIn('The smoke tests validate the README.', content)
        self.assertNotIn('The smoke tests also validate this README.', content)

    def test_demo_e2e_script_does_not_push_to_github(self) -> None:
        content = Path("scripts/demo_e2e_orchestrator.sh").read_text(encoding="utf-8")

        self.assertNotIn("git push", content)

    def test_repo_hygiene_script_exists_and_is_safe(self) -> None:
        import os

        script_path = Path("scripts/check_repo_hygiene.sh")
        self.assertTrue(script_path.exists(), "Repo hygiene script does not exist.")
        self.assertTrue(os.access(script_path, os.X_OK), "Repo hygiene script is not executable.")
        content = script_path.read_text(encoding="utf-8")
        self.assertIn("git status --short", content)
        self.assertNotIn("git push", content)
        self.assertNotIn("git reset", content)
        self.assertNotIn("rm -rf", content)

    def test_gitignore_contains_publish_hygiene_ignores(self) -> None:
        content = Path(".gitignore").read_text(encoding="utf-8")

        self.assertIn("__pycache__/", content)
        self.assertIn("*.pyc", content)
        self.assertIn(".pytest_cache/", content)
        self.assertIn(".mypy_cache/", content)
        self.assertIn(".ruff_cache/", content)
        self.assertIn(".venv/", content)
        self.assertIn("venv/", content)
        self.assertIn(".env", content)
        self.assertIn(".env.*", content)
        self.assertIn("!.env.example", content)
        self.assertIn("config/*.local.yaml", content)
        self.assertIn("reports/tmp/", content)
        self.assertIn(".DS_Store", content)
        self.assertIn(".idea/", content)
        self.assertIn(".vscode/", content)

    def test_env_example_exists_with_placeholder_only_values(self) -> None:
        content = Path(".env.example").read_text(encoding="utf-8")

        self.assertIn("AI_BRAIN_PATH=/path/to/AI-Brain", content)
        self.assertIn("OPENAI_API_KEY=your_openai_api_key_here", content)
        self.assertIn("FIGMA_TOKEN=optional_figma_token_here", content)
        self.assertIn("ERROR_MONITORING_TOKEN=optional_error_monitoring_token_here", content)
        self.assertIn("GITHUB_TOKEN=optional_github_token_here", content)
        self.assertNotIn("REPORTS_DIR=", content)
        self.assertNotIn("/home/asrin/Desktop/AI-Brain", content)
        self.assertNotIn("sk-live-", content)
        self.assertNotIn("ghp_", content)

    def test_tracked_config_files_contain_no_personal_paths(self) -> None:
        for path_text in (
            "config/default.yaml",
            "config/default.example.yaml",
            "config/approved_paths.yaml",
            "config/approved_paths.example.yaml",
        ):
            content = Path(path_text).read_text(encoding="utf-8")
            self.assertNotIn("/home/asrin", content)
            self.assertNotIn("/Desktop/", content)

    def test_root_log_artifacts_are_not_present(self) -> None:
        self.assertFalse(Path("output.log").exists())
        self.assertFalse(Path("test_failures.log").exists())

    def test_live_validation_script_safe_default(self) -> None:
        import subprocess
        script_path = Path("scripts/check_mcp_live_connectors.sh")
        result = subprocess.run([str(script_path)], capture_output=True, text=True, env={})
        self.assertEqual(result.returncode, 0)
        self.assertIn("Dry Run / Checklist mode", result.stdout)
        self.assertNotIn("FAILED", result.stdout) # Because it should just print SKIPPED
        self.assertIn("[SKIPPED]", result.stdout)

    def test_readme_references_live_validation_script(self) -> None:
        readme_path = Path("README.md")
        self.assertTrue(readme_path.exists())
        content = readme_path.read_text(encoding="utf-8")
        self.assertIn("scripts/check_mcp_live_connectors.sh", content)
        self.assertIn("MCP Live Validation", content)

    def test_readme_references_demo_e2e_script(self) -> None:
        content = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("## Demo E2E script", content)
        self.assertIn("bash scripts/demo_e2e_orchestrator.sh", content)
        self.assertIn("no GitHub push", content)
        self.assertIn("no AI-Brain write", content)

    def test_readme_mentions_approved_paths_for_demo_onboarding(self) -> None:
        content = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("approved local paths", content)
        self.assertIn("orchestrator --show-approved-paths", content)
        self.assertIn("PYTHONPATH=src python3 src/main.py --show-approved-paths", content)

    def test_readme_explains_public_safe_config_setup(self) -> None:
        content = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("config/default.example.yaml", content)
        self.assertIn("config/approved_paths.example.yaml", content)
        self.assertIn("config/default.local.yaml", content)
        self.assertIn("config/approved_paths.local.yaml", content)

    def test_readme_includes_demo_success_output_excerpt(self) -> None:
        content = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("Coding Run Summary:", content)
        self.assertIn("- Scope: passed", content)
        self.assertIn("- Tests: passed", content)
        self.assertTrue(
            "Verification: Approved" in content
            or "Final verification decision: Approved" in content
        )
        self.assertIn("Write status: not_written", content)

    def test_readme_positions_ai_brain_to_codex_product(self) -> None:
        content = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("AI-Coding-Orchestrator", content)
        self.assertIn("connects a personal AI-Brain to OpenAI Codex", content)
        self.assertIn("local-first, approval-gated orchestration", content.lower())

    def test_readme_includes_safety_and_ai_brain_sections(self) -> None:
        content = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("## Safety model", content)
        self.assertIn("## AI-Brain integration", content)
        self.assertIn("AI-Brain cannot be edited by Codex.", content)
        self.assertIn("Runtime mock data is disabled in normal product flows.", content)

    def test_readme_includes_full_run_with_test_gate_command(self) -> None:
        content = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("## Demo: full run with test gate", content)
        self.assertIn("--run-orchestrator --mode run", content)
        self.assertIn("--include-ai-brain-context", content)
        self.assertIn(
            '--test-command "PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_*.py"',
            content,
        )

    def test_readme_states_knowledge_update_is_not_auto_written(self) -> None:
        content = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("Knowledge Update Proposal", content)
        self.assertIn("The **Knowledge Update Proposal is not auto-written**.", content)

    def test_readme_states_github_push_not_automated(self) -> None:
        content = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("GitHub push/publishing is not part of the current automated flow.", content)

    def test_readme_license_status_is_accurate(self) -> None:
        content = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("## License", content)
        self.assertIn("This project is licensed under the MIT License.", content)
        self.assertIn("See [LICENSE](../LICENSE) for the full text.", content)

    def test_license_file_exists_with_mit_text(self) -> None:
        content = Path("../LICENSE").read_text(encoding="utf-8")

        self.assertIn("MIT License", content)
        self.assertIn("Permission is hereby granted, free of charge", content)
        self.assertIn("Asrın Dündar", content)

    def test_readme_safety_claims_remain_present(self) -> None:
        content = Path("README.md").read_text(encoding="utf-8")

        self.assertIn("AI-Brain cannot be edited by Codex.", content)
        self.assertIn("Runtime mock data is disabled in normal product flows.", content)
        self.assertIn("the demo does not call external providers", content)
        self.assertIn("Codex CLI and authentication must be available for real execution", content)
        self.assertIn("project path must be approved", content)

    def test_cli_help_text_no_longer_calls_github_mock_only(self) -> None:
        content = Path("src/cli.py").read_text(encoding="utf-8")

        self.assertNotIn("mock-only GitHub MCP context", content)
        self.assertNotIn("mock-only GitHub read MCP foundation", content)
        self.assertIn("read-only GitHub MCP context", content)
        self.assertIn("uses gh CLI when configured and available", content)

    def test_live_validation_script_content_flags(self) -> None:
        script_path = Path("scripts/check_mcp_live_connectors.sh")
        content = script_path.read_text(encoding="utf-8")
        
        self.assertIn("--docs-source-path", content)
        self.assertIn("docs.search", content)
        
        self.assertIn("local.dev_logs.search", content)
        self.assertIn("--error-provider local", content)
        
        self.assertIn("rev-parse --is-inside-work-tree", content)
        
        self.assertIn("package.json", content)
        self.assertIn("pyproject.toml", content)
        self.assertIn("requirements.txt", content)
        self.assertIn("--package-ecosystem local_manifest", content)

class RootReadmeAndAIBrainSmokeTests(TestCase):
    def test_root_readme_exists_and_mentions_components(self) -> None:
        content = Path("../README.md").read_text(encoding="utf-8")
        self.assertIn("ai-brain/", content)
        self.assertIn("orchestrator/", content)

    def test_root_readme_has_product_tagline(self) -> None:
        content = Path("../README.md").read_text(encoding="utf-8")
        self.assertIn("An AI-Brain-guided Codex orchestration system", content)

    def test_root_readme_mentions_key_workflows(self) -> None:
        content = Path("../README.md").read_text(encoding="utf-8")
        self.assertIn("AI-Brain Guidance", content)
        self.assertIn("Verification Gate", content)

    def test_root_readme_mentions_limitations(self) -> None:
        content = Path("../README.md").read_text(encoding="utf-8")
        self.assertIn("Knowledge Update Proposal is not automatically written", content)
        self.assertIn("No GitHub push automation", content)

    def test_root_readme_mentions_license_and_links(self) -> None:
        content = Path("../README.md").read_text(encoding="utf-8")
        self.assertIn("MIT License", content)
        self.assertIn("orchestrator/README.md", content)

    def test_ai_brain_public_files_contain_no_anima(self) -> None:
        ai_brain_dir = Path("../ai-brain")
        for md_file in ai_brain_dir.rglob("*.md"):
            if ".private-archive" in md_file.parts or ".obsidian" in md_file.parts:
                continue
            content = md_file.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("Anima", content, f"Found Anima in {md_file}")

    def test_ai_brain_public_files_do_not_include_personal_notes(self) -> None:
        ai_brain_dir = Path("../ai-brain")
        for md_file in ai_brain_dir.rglob("*.md"):
            if ".private-archive" in md_file.parts or ".obsidian" in md_file.parts:
                continue
            self.assertNotEqual(md_file.name, "Codex-Test-Note.md")
            self.assertNotEqual(md_file.name, "AI-Brain-Status.md")

    def test_gitignore_ignores_private_archive(self) -> None:
        content = Path("../.gitignore").read_text(encoding="utf-8")
        self.assertIn("ai-brain/.private-archive/", content)

    def test_ai_brain_profile_files_are_templates(self) -> None:
        profile = Path("../ai-brain/02-Code/Global-AI-Profile.md")
        rules = Path("../ai-brain/02-Code/My-AI-Coding-Rules.md")
        
        self.assertTrue(profile.exists())
        self.assertTrue(rules.exists())
        
        profile_content = profile.read_text(encoding="utf-8")
        rules_content = rules.read_text(encoding="utf-8")
        
        self.assertIn("Template", profile_content)
        self.assertIn("Template", rules_content)
        self.assertIn("[Your preferred workflow]", rules_content)
        self.assertIn("[Your coding standards]", rules_content)

