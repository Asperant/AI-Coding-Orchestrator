from contextlib import redirect_stdout
from io import StringIO
import os
import subprocess
from unittest import TestCase
from unittest.mock import patch

import cli
from tools.github_read_mcp import (
    GhCliGitHubReadClient,
    MockGitHubReadClient,
    format_github_read_result,
    run_github_read_tool,
)


class GitHubReadMCPTests(TestCase):
    def test_valid_issue_read_with_mock_client_returns_context_block(self) -> None:
        client = MockGitHubReadClient(
            issues={
                ("openai/example", 12): {
                    "title": "Fix planner output",
                    "state": "open",
                    "body": "Planner summary needs cleanup.",
                    "comments": ["Looks good."],
                }
            }
        )

        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
            result = run_github_read_tool(
                "github.issue.read",
                "openai/example",
                issue_number=12,
                client=client,
            )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertEqual(result["item_id"], 12)
        self.assertEqual(result["content_summary"], "Issue #12: Fix planner output")
        self.assertEqual(len(result["context_blocks"]), 1)
        self.assertEqual(result["context_blocks"][0]["source_type"], "github")

    def test_valid_pr_read_with_mock_client_returns_context_block(self) -> None:
        client = MockGitHubReadClient(
            pull_requests={
                ("openai/example", 5): {
                    "title": "Add safe MCP path",
                    "state": "open",
                    "review_state": "changes_requested",
                    "body": "Implements safe MCP boundary.",
                }
            }
        )

        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
            result = run_github_read_tool(
                "github.pr.read",
                "openai/example",
                pr_number=5,
                client=client,
            )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertIn("PR #5", result["content_summary"])
        self.assertEqual(result["context_blocks"][0]["tool_name"], "github.pr.read")

    def test_changed_files_read_with_mock_client_works(self) -> None:
        client = MockGitHubReadClient(
            changed_files={
                ("openai/example", 9): ["src/main.py", "tests/test_main.py"],
            }
        )

        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
            result = run_github_read_tool(
                "github.pr.changed_files",
                "openai/example",
                pr_number=9,
                client=client,
            )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertIn("2", result["content_summary"])
        self.assertIn("src/main.py", result["raw_content"])

    def test_ci_status_read_with_mock_client_works(self) -> None:
        client = MockGitHubReadClient(
            ci_statuses={
                "openai/example": {
                    "status": "success",
                    "summary": "All checks passed.",
                    "checks": ["unit-tests", "lint"],
                }
            }
        )

        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
            result = run_github_read_tool(
                "github.ci.status",
                "openai/example",
                client=client,
            )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertEqual(result["content_summary"], "CI status: success")
        self.assertIn("unit-tests", result["raw_content"])

    def test_invalid_repo_is_blocked(self) -> None:
        result = run_github_read_tool(
            "github.issue.read",
            "not a repo",
            issue_number=1,
        )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("owner/repo", result["message"])

    def test_non_numeric_issue_or_pr_is_blocked(self) -> None:
        issue_result = run_github_read_tool(
            "github.issue.read",
            "openai/example",
            issue_number="abc",
        )
        pr_result = run_github_read_tool(
            "github.pr.read",
            "openai/example",
            pr_number="abc",
        )

        self.assertTrue(issue_result["blocked"])
        self.assertIn("issue_number must be numeric.", issue_result["message"])
        self.assertTrue(pr_result["blocked"])
        self.assertIn("pr_number must be numeric.", pr_result["message"])

    def test_unsafe_token_env_var_is_blocked(self) -> None:
        result = run_github_read_tool(
            "github.ci.status",
            "openai/example",
            token_env_var="ghs_live_token",
        )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("environment variable name is not safe", result["message"])

    def test_missing_token_does_not_print_raw_token_and_does_not_crash(self) -> None:
        client = MockGitHubReadClient(
            issues={("openai/example", 12): {"title": "Ignored", "state": "open"}}
        )

        with patch.dict(os.environ, {}, clear=True):
            result = run_github_read_tool(
                "github.issue.read",
                "openai/example",
                issue_number=12,
                client=client,
            )
        output = format_github_read_result(result)

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("GITHUB_TOKEN", result["message"])
        self.assertNotIn("ghs_", output)
        self.assertIn("No raw token value was read or printed.", output)

    def test_gh_client_does_not_require_github_token(self) -> None:
        client = GhCliGitHubReadClient()
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"title":"Fix planner output","body":"Safe body","state":"open","labels":[],"url":"https://example.com"}',
            stderr="",
        )

        with patch("tools.github_read_mcp.subprocess.run", return_value=completed):
            with patch.dict(os.environ, {}, clear=True):
                result = run_github_read_tool(
                    "github.issue.read",
                    "openai/example",
                    issue_number=12,
                    client=client,
                )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertNotIn("GITHUB_TOKEN is not set", result["message"])

    def test_gh_client_with_missing_github_token_can_call_mocked_subprocess(self) -> None:
        client = GhCliGitHubReadClient()
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"title":"Fix planner output","body":"Safe body","state":"open","labels":[],"url":"https://example.com"}',
            stderr="",
        )

        with patch("tools.github_read_mcp.subprocess.run", return_value=completed) as mocked_run:
            with patch.dict(os.environ, {}, clear=True):
                result = run_github_read_tool(
                    "github.issue.read",
                    "openai/example",
                    issue_number=12,
                    client=client,
                )

        self.assertTrue(result["executed"])
        mocked_run.assert_called_once()

    def test_secret_like_github_content_is_blocked_redacted(self) -> None:
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
            result = run_github_read_tool(
                "github.issue.read",
                "openai/example",
                issue_number=14,
                client=client,
            )
        output = format_github_read_result(result)

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIsNone(result["raw_content"])
        self.assertNotIn(secret_value, output)
        self.assertIn("blocked", output.lower())

    def test_no_network_api_call_occurs_without_mock_client(self) -> None:
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
            result = run_github_read_tool(
                "github.pr.read",
                "openai/example",
                pr_number=7,
            )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("Real provider is not implemented", result["message"])

    def test_gh_issue_read_builds_safe_subprocess_args(self) -> None:
        client = GhCliGitHubReadClient()
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"title":"Fix planner output","body":"Safe body","state":"open","labels":[],"url":"https://example.com"}',
            stderr="",
        )

        with patch("tools.github_read_mcp.subprocess.run", return_value=completed) as mocked_run:
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
                result = run_github_read_tool(
                    "github.issue.read",
                    "openai/example",
                    issue_number=12,
                    client=client,
                )

        self.assertTrue(result["executed"])
        mocked_run.assert_called_once()
        self.assertEqual(
            mocked_run.call_args.args[0],
            [
                "gh",
                "issue",
                "view",
                "12",
                "--repo",
                "openai/example",
                "--json",
                "title,body,state,labels,url",
            ],
        )
        self.assertFalse(mocked_run.call_args.kwargs["shell"])

    def test_gh_pr_read_builds_safe_subprocess_args(self) -> None:
        client = GhCliGitHubReadClient()
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"title":"Add safe MCP path","body":"Safe body","state":"open","files":[],"url":"https://example.com"}',
            stderr="",
        )

        with patch("tools.github_read_mcp.subprocess.run", return_value=completed) as mocked_run:
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
                result = run_github_read_tool(
                    "github.pr.read",
                    "openai/example",
                    pr_number=5,
                    client=client,
                )

        self.assertTrue(result["executed"])
        self.assertEqual(
            mocked_run.call_args.args[0],
            [
                "gh",
                "pr",
                "view",
                "5",
                "--repo",
                "openai/example",
                "--json",
                "title,body,state,files,url",
            ],
        )
        self.assertFalse(mocked_run.call_args.kwargs["shell"])

    def test_gh_changed_files_read_builds_safe_subprocess_args(self) -> None:
        client = GhCliGitHubReadClient()
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"files":[{"path":"src/main.py"},{"path":"tests/test_main.py"}]}',
            stderr="",
        )

        with patch("tools.github_read_mcp.subprocess.run", return_value=completed) as mocked_run:
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
                result = run_github_read_tool(
                    "github.pr.changed_files",
                    "openai/example",
                    pr_number=9,
                    client=client,
                )

        self.assertTrue(result["executed"])
        self.assertEqual(
            mocked_run.call_args.args[0],
            [
                "gh",
                "pr",
                "view",
                "9",
                "--repo",
                "openai/example",
                "--json",
                "files",
            ],
        )
        self.assertIn("src/main.py", result["raw_content"])

    def test_gh_ci_status_builds_safe_subprocess_args(self) -> None:
        client = GhCliGitHubReadClient()
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='[{"status":"completed","conclusion":"success","name":"unit-tests","url":"https://example.com"}]',
            stderr="",
        )

        with patch("tools.github_read_mcp.subprocess.run", return_value=completed) as mocked_run:
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
                result = run_github_read_tool(
                    "github.ci.status",
                    "openai/example",
                    pr_number=5,
                    client=client,
                )

        self.assertTrue(result["executed"])
        self.assertEqual(
            mocked_run.call_args.args[0],
            [
                "gh",
                "run",
                "list",
                "--repo",
                "openai/example",
                "--limit",
                "5",
                "--json",
                "status,conclusion,name,url",
            ],
        )
        self.assertFalse(mocked_run.call_args.kwargs["shell"])

    def test_missing_gh_binary_handled_safely(self) -> None:
        client = GhCliGitHubReadClient()

        with patch("tools.github_read_mcp.subprocess.run", side_effect=FileNotFoundError()):
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
                result = run_github_read_tool(
                    "github.issue.read",
                    "openai/example",
                    issue_number=12,
                    client=client,
                )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("gh CLI failed safely", result["message"])
        self.assertIn("not installed", result["message"])

    def test_gh_auth_error_handled_safely(self) -> None:
        client = GhCliGitHubReadClient()
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="authentication required: not logged in",
        )

        with patch("tools.github_read_mcp.subprocess.run", return_value=completed):
            with patch.dict(os.environ, {}, clear=True):
                result = run_github_read_tool(
                    "github.issue.read",
                    "openai/example",
                    issue_number=12,
                    client=client,
                )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("authentication", result["message"].lower())

    def test_parsed_json_becomes_context_block(self) -> None:
        client = GhCliGitHubReadClient()
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"title":"Fix planner output","body":"Safe body","state":"open","labels":[],"url":"https://example.com"}',
            stderr="",
        )

        with patch("tools.github_read_mcp.subprocess.run", return_value=completed):
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
                result = run_github_read_tool(
                    "github.issue.read",
                    "openai/example",
                    issue_number=12,
                    client=client,
                )

        self.assertEqual(len(result["context_blocks"]), 1)
        self.assertEqual(result["context_blocks"][0]["source_type"], "github")
        self.assertEqual(result["context_blocks"][0]["tool_name"], "github.issue.read")

    def test_secret_like_gh_content_is_blocked_redacted(self) -> None:
        client = GhCliGitHubReadClient()
        secret_value = "super-secret-token-123"
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"title":"Investigate token leak","body":"API_TOKEN=' + secret_value + '","state":"open","labels":[],"url":"https://example.com"}',
            stderr="",
        )

        with patch("tools.github_read_mcp.subprocess.run", return_value=completed):
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
                result = run_github_read_tool(
                    "github.issue.read",
                    "openai/example",
                    issue_number=12,
                    client=client,
                )
        output = format_github_read_result(result)

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertNotIn(secret_value, output)

    def test_no_write_or_mutation_command_is_used(self) -> None:
        client = GhCliGitHubReadClient()
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"title":"Fix planner output","body":"Safe body","state":"open","labels":[],"url":"https://example.com"}',
            stderr="",
        )

        with patch("tools.github_read_mcp.subprocess.run", return_value=completed) as mocked_run:
            with patch.dict(os.environ, {"GITHUB_TOKEN": "ghs_test_token"}):
                run_github_read_tool(
                    "github.issue.read",
                    "openai/example",
                    issue_number=12,
                    client=client,
                )

        command = mocked_run.call_args.args[0]
        self.assertNotIn("api", command)
        self.assertNotIn("comment", command)
        self.assertNotIn("edit", command)
        self.assertNotIn("merge", command)


class GitHubReadMCPCLITests(TestCase):
    def setUp(self) -> None:
        self.fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": ["/tmp/approved"],
        }

    def test_cli_github_read_works_with_patched_runner(self) -> None:
        stdout = StringIO()
        mocked_result = {
            "executed": True,
            "blocked": False,
            "tool_name": "github.issue.read",
            "repo": "openai/example",
            "item_id": 12,
            "content_summary": "Issue #12: Fix planner output",
            "raw_content": None,
            "context_blocks": [
                {
                    "source_type": "github",
                    "source_name": "openai/example#12",
                    "tool_name": "github.issue.read",
                    "source_path": "openai/example#12",
                    "content": "GitHub issue preview",
                    "safe": True,
                    "blocked": False,
                    "reason": "none",
                    "char_count": 20,
                }
            ],
            "message": "github.issue.read completed successfully.",
            "safety_notes": ["Mock GitHub client only: no real API call was performed."],
            "decision": {"allowed": True},
        }

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "run_github_read_tool", return_value=mocked_result) as mocked_runner:
                with patch.object(cli, "read_project_knowledge") as mocked_project_knowledge:
                    with redirect_stdout(stdout):
                        cli.run(
                            [
                                "--github-read",
                                "--github-tool-name",
                                "github.issue.read",
                                "--github-repo",
                                "openai/example",
                                "--github-issue-number",
                                "12",
                            ]
                        )

        output = stdout.getvalue()

        self.assertIn("Executed: yes", output)
        self.assertIn("Tool name: github.issue.read", output)
        self.assertIn("Context blocks: 1", output)
        mocked_runner.assert_called_once()
        mocked_project_knowledge.assert_not_called()

    def test_cli_github_read_passes_selected_client(self) -> None:
        stdout = StringIO()
        mocked_result = {
            "executed": False,
            "blocked": True,
            "tool_name": "github.issue.read",
            "repo": "openai/example",
            "item_id": 12,
            "content_summary": "not available",
            "raw_content": None,
            "context_blocks": [],
            "message": "safe foundation-only result",
            "safety_notes": ["none"],
            "decision": {"allowed": True},
        }

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "run_github_read_tool", return_value=mocked_result) as mocked_runner:
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--github-read",
                            "--github-tool-name",
                            "github.issue.read",
                            "--github-repo",
                            "openai/example",
                            "--github-issue-number",
                            "12",
                            "--github-client",
                            "gh",
                        ]
                    )

        self.assertEqual(mocked_runner.call_args.kwargs["client"], "gh")
