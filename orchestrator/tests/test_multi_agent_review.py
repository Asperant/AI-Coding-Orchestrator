from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from brain.memory_sync import format_memory_decision_view
from orchestration.approval_gate_manager import format_approval_gate_view
from orchestration.multi_agent_review import (
    format_multi_agent_diff_review,
    generate_multi_agent_diff_review,
)
from orchestration.task_classifier import classify_task


class MultiAgentReviewTests(TestCase):
    def test_no_diff_behavior(self) -> None:
        review = generate_multi_agent_diff_review(
            {
                "is_git_repo": True,
                "changed_files": [],
                "status_summary": "Working tree clean.",
                "diff_text": "",
                "diff_present": False,
            }
        )

        self.assertEqual(review["decision"], "Needs more context")
        self.assertIn("No git diff is present", review["summary"])

    def test_basic_changed_file_review(self) -> None:
        review = generate_multi_agent_diff_review(
            {
                "is_git_repo": True,
                "changed_files": ["src/cli.py"],
                "status_summary": "1 changed file(s).",
                "diff_text": "diff --git a/src/cli.py b/src/cli.py\n+print('hello')\n",
                "diff_present": True,
            }
        )

        self.assertEqual(review["decision"], "Approved with changes")
        self.assertIn("Reviewer", review["agents_used"])
        self.assertIn("Tester", review["agents_used"])
        self.assertFalse(review["approval_gate"]["approval_required"])
        self.assertEqual(review["memory_docs_update_suggestion"]["destination"], "project_docs")

    def test_security_lens_activates_for_secret_auth_database_keywords(self) -> None:
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

        self.assertIn("Security", review["agents_used"])
        self.assertEqual(review["decision"], "Needs revision")
        self.assertTrue(review["approval_gate"]["approval_required"])
        self.assertEqual(review["memory_docs_update_suggestion"]["destination"], "both")

    def test_architect_lens_activates_for_context_services_refactor(self) -> None:
        review = generate_multi_agent_diff_review(
            {
                "is_git_repo": True,
                "changed_files": ["src/context/app.py", "src/services/data.py"],
                "status_summary": "2 changed file(s).",
                "diff_text": "refactor context services architecture",
                "diff_present": True,
            },
            task_classification=classify_task("refactor service boundaries"),
        )

        self.assertIn("Architect", review["agents_used"])
        self.assertEqual(review["decision"], "Approved with changes")

    def test_product_lens_activates_for_ui_copy_feature(self) -> None:
        review = generate_multi_agent_diff_review(
            {
                "is_git_repo": True,
                "changed_files": ["docs/product-copy.md"],
                "status_summary": "1 changed file(s).",
                "diff_text": "labels onboarding result permission product text",
                "diff_present": True,
            },
            task_classification=classify_task("add feature onboarding flow"),
        )

        self.assertIn("Product", review["agents_used"])

    def test_release_lens_activates_for_config_package_deploy(self) -> None:
        review = generate_multi_agent_diff_review(
            {
                "is_git_repo": True,
                "changed_files": ["package.json", "config/deploy.yaml"],
                "status_summary": "2 changed file(s).",
                "diff_text": "dependency build deploy migration release",
                "diff_present": True,
            },
            task_classification=classify_task("review deploy package release"),
        )

        self.assertIn("Release", review["agents_used"])
        self.assertEqual(review["decision"], "Needs revision")

    def test_decision_values_are_deterministic(self) -> None:
        doc_review = generate_multi_agent_diff_review(
            {
                "is_git_repo": True,
                "changed_files": ["docs/guide.md"],
                "status_summary": "1 changed file(s).",
                "diff_text": "documentation update",
                "diff_present": True,
            },
            task_classification=classify_task("update documentation guide"),
        )
        non_git_review = generate_multi_agent_diff_review(
            {
                "is_git_repo": False,
                "changed_files": [],
                "status_summary": "Not a git repository.",
                "diff_text": "",
                "diff_present": False,
            }
        )

        self.assertEqual(doc_review["decision"], "Approved")
        self.assertEqual(non_git_review["decision"], "Blocked")

    def test_report_includes_required_sections(self) -> None:
        review = generate_multi_agent_diff_review(
            {
                "is_git_repo": True,
                "changed_files": ["src/cli.py"],
                "status_summary": "1 changed file(s).",
                "diff_text": "diff --git a/src/cli.py b/src/cli.py\n",
                "diff_present": True,
            }
        )
        output = format_multi_agent_diff_review(review)

        self.assertIn("Summary:", output)
        self.assertIn("Decision:", output)
        self.assertIn("Final decision reason:", output)
        self.assertIn("Agents used:", output)
        self.assertIn("Per-agent signals:", output)
        self.assertIn("Required fixes:", output)
        self.assertIn("Approval Gate:", output)
        self.assertIn("Knowledge Update Proposal:", output)
        self.assertIn("Memory/docs update suggestion:", output)
        self.assertIn("Destination:", output)
        self.assertIn("Next small action:", output)

    def test_per_agent_signal_summary_and_tester_note_are_present(self) -> None:
        review = generate_multi_agent_diff_review(
            {
                "is_git_repo": True,
                "changed_files": ["src/cli.py"],
                "status_summary": "1 changed file(s).",
                "diff_text": "diff --git a/src/cli.py b/src/cli.py\n+print('hello')\n",
                "diff_present": True,
            }
        )
        output = format_multi_agent_diff_review(review)

        self.assertIn("Reviewer:", output)
        self.assertIn("Tester:", output)
        self.assertIn("Tester did not execute tests in this review pass.", output)
        self.assertIn("Closest test:", output)

    def test_clean_readme_only_diff_can_still_be_approved(self) -> None:
        review = generate_multi_agent_diff_review(
            {
                "is_git_repo": True,
                "changed_files": ["README.md"],
                "status_summary": "1 changed file(s).",
                "diff_text": "documentation readme update",
                "diff_present": True,
            },
            task_classification=classify_task("update documentation guide"),
        )

        self.assertEqual(review["decision"], "Approved")
        self.assertIn("Approved because", review["final_decision_reason"])

    def test_diff_review_includes_memory_sync_destination(self) -> None:
        review = generate_multi_agent_diff_review(
            {
                "is_git_repo": True,
                "changed_files": ["src/cli.py"],
                "status_summary": "1 changed file(s).",
                "diff_text": "diff --git a/src/cli.py b/src/cli.py\n+print('hello')\n",
                "diff_present": True,
            }
        )
        output = format_multi_agent_diff_review(review)

        self.assertIn("Memory/docs update suggestion: Destination: project_docs", output)
        self.assertIn("Reason:", output)
        self.assertIn("Suggested target:", output)
        self.assertIn("Suggested entry type:", output)
        self.assertIn(
            format_memory_decision_view(review["memory_docs_update_suggestion"]),
            output,
        )

    def test_diff_review_memory_section_matches_shared_formatter(self) -> None:
        review = generate_multi_agent_diff_review(
            {
                "is_git_repo": True,
                "changed_files": ["docs/risk-registry.md"],
                "status_summary": "1 changed file(s).",
                "diff_text": "risk documentation update",
                "diff_present": True,
            },
            task_classification=classify_task("review deploy config"),
        )
        output = format_multi_agent_diff_review(review)

        expected_section = (
            "Memory/docs update suggestion: "
            f"{format_memory_decision_view(review['memory_docs_update_suggestion'])}"
        )

        self.assertIn(expected_section, output)

    def test_diff_review_approval_section_matches_shared_formatter(self) -> None:
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
        output = format_multi_agent_diff_review(review)

        expected_section = (
            "Approval Gate: "
            f"{format_approval_gate_view(review['approval_gate'])}"
        )

        self.assertIn(expected_section, output)


class MultiAgentReviewCliTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        self.fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": [str(self.project_root)],
        }
        self.fake_core_status = {
            "checked_count": 4,
            "found_count": 4,
            "missing_count": 0,
            "missing_files": {},
        }

    def tearDown(self) -> None:
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

    def test_review_diff_without_project_gives_clear_error(self) -> None:
        with self.assertRaisesRegex(
            SystemExit,
            "Git gateway error: --git-status, --git-diff, and --review-diff require --project.",
        ):
            cli.run(["--review-diff"])

    def test_project_outside_approved_paths_is_rejected_before_git(self) -> None:
        outside_root = self.project_root.parent / "outside-review-project"
        outside_root.mkdir(exist_ok=True)

        with patch.object(cli, "inspect_git_state") as mocked_git:
            with patch.object(cli, "load_config", return_value=self.fake_config):
                with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                    with self.assertRaisesRegex(
                        SystemExit,
                        "Approved path error: Target path is outside approved paths:",
                    ):
                        cli.run(["--project", str(outside_root), "--review-diff"])

        mocked_git.assert_not_called()

    def test_non_git_project_returns_clear_message(self) -> None:
        project_dir = self.project_root / "plain-project"
        project_dir.mkdir()
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--project", str(project_dir), "--review-diff"])

        output = stdout.getvalue()

        self.assertIn("Summary: Diff review cannot run because the project is not a git repository.", output)
        self.assertIn("Decision: Blocked", output)

    def test_git_repo_with_diff_prints_consolidated_review(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "review-repo")
        changed_file = repo_path / "config.py"
        changed_file.write_text("FEATURE_FLAG = True\n", encoding="utf-8")
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--project", str(repo_path), "--review-diff", "--task", "fix telemetry bug"])

        output = stdout.getvalue()

        self.assertIn("Decision:", output)
        self.assertIn("Agents used:", output)
        self.assertIn("Changed files: config.py", output)
        self.assertIn("Memory/docs update suggestion: Destination:", output)
        self.assertIn("Suggested target:", output)

    def test_secret_like_diff_blocks_review_safely(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "secret-review-repo")
        raw_secret = "service-role-secret-123"
        changed_file = repo_path / "config.py"
        changed_file.write_text(
            f"SUPABASE_SERVICE_ROLE_KEY = '{raw_secret}'\n",
            encoding="utf-8",
        )
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--project", str(repo_path), "--review-diff"])

        output = stdout.getvalue()

        self.assertIn(
            "Summary: Diff review output blocked because secret-like content was detected. Findings are redacted.",
            output,
        )
        self.assertIn("Decision: Blocked", output)
        self.assertIn("Security", output)
        self.assertIn("Detected service/admin secret-style assignment", output)
        self.assertNotIn(raw_secret, output)

    def test_review_diff_with_git_diff_does_not_print_raw_secret(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "secret-preview-repo")
        raw_secret = "super-secret-value-987654321"
        changed_file = repo_path / "env.py"
        changed_file.write_text(
            f'API_TOKEN = "{raw_secret}"\n',
            encoding="utf-8",
        )
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--project", str(repo_path), "--git-diff", "--review-diff"])

        output = stdout.getvalue()

        self.assertIn("Diff review output blocked because secret-like content was detected.", output)
        self.assertIn("Detected token-style assignment", output)
        self.assertNotIn(raw_secret, output)
