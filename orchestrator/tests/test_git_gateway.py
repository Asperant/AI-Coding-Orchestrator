from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import MagicMock, patch

import cli
from tools.git_gateway import GitGatewayError, inspect_git_log, inspect_git_state


class GitGatewayTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

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

    def test_non_existing_project_path_gives_clear_error(self) -> None:
        missing_path = self.root / "missing-project"

        with self.assertRaisesRegex(
            GitGatewayError,
            "Project path does not exist:",
        ):
            inspect_git_state(missing_path)

    def test_file_path_gives_clear_error(self) -> None:
        file_path = self.root / "project.txt"
        file_path.write_text("content", encoding="utf-8")

        with self.assertRaisesRegex(
            GitGatewayError,
            "Project path is not a directory:",
        ):
            inspect_git_state(file_path)

    def test_non_git_directory_is_reported_clearly(self) -> None:
        project_dir = self.root / "plain-project"
        project_dir.mkdir()

        git_state = inspect_git_state(project_dir)

        self.assertFalse(git_state["is_git_repo"])
        self.assertEqual(git_state["status_summary"], "Not a git repository.")
        self.assertFalse(git_state["diff_present"])

    def test_git_repo_with_no_changes_reports_no_diff(self) -> None:
        repo_path = self.init_git_repo(self.root / "clean-repo")

        git_state = inspect_git_state(repo_path)

        self.assertTrue(git_state["is_git_repo"])
        self.assertEqual(git_state["changed_files"], [])
        self.assertEqual(git_state["status_summary"], "Working tree clean.")
        self.assertFalse(git_state["diff_present"])
        self.assertEqual(git_state["diff_text"], "")

    def test_git_repo_with_changed_file_reports_changed_file_and_diff(self) -> None:
        repo_path = self.init_git_repo(self.root / "changed-repo")
        changed_file = repo_path / "telemetry.log"
        changed_file.write_text("line one\nline two\n", encoding="utf-8")

        git_state = inspect_git_state(repo_path)

        self.assertTrue(git_state["is_git_repo"])
        self.assertEqual(git_state["changed_files"], ["telemetry.log"])
        self.assertEqual(git_state["status_summary"], "1 changed file(s).")
        self.assertTrue(git_state["diff_present"])
        self.assertIn("telemetry.log", git_state["diff_text"])
        self.assertIn("+line one", git_state["diff_text"])

    def test_no_mutating_git_command_is_used(self) -> None:
        repo_path = self.root / "repo"
        repo_path.mkdir()
        completed_processes = [
            MagicMock(returncode=0, stdout="true\n", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]

        with patch("tools.git_gateway.subprocess.run", side_effect=completed_processes) as mocked_run:
            inspect_git_state(repo_path)

        banned_git_subcommands = {
            "add",
            "commit",
            "reset",
            "checkout",
            "stash",
            "branch",
            "merge",
            "rebase",
            "clean",
        }
        for call in mocked_run.call_args_list:
            command = call.args[0]
            self.assertEqual(command[0], "git")
            self.assertEqual(command[1], "-C")
            self.assertEqual(command[2], str(repo_path.resolve()))
            self.assertNotIn(command[3], banned_git_subcommands)

    def test_git_log_read_works_with_mocked_subprocess(self) -> None:
        repo_path = self.root / "log-repo"
        repo_path.mkdir()
        completed_processes = [
            MagicMock(returncode=0, stdout="true\n", stderr=""),
            MagicMock(returncode=0, stdout="abc123 First commit\n", stderr=""),
        ]

        with patch("tools.git_gateway.subprocess.run", side_effect=completed_processes) as mocked_run:
            result = inspect_git_log(repo_path)

        self.assertTrue(result["is_git_repo"])
        self.assertEqual(result["entry_count"], 1)
        self.assertEqual(result["log_text"], "abc123 First commit")
        first_command = mocked_run.call_args_list[0].args[0]
        second_command = mocked_run.call_args_list[1].args[0]
        self.assertEqual(first_command[3:], ["rev-parse", "--is-inside-work-tree"])
        self.assertEqual(second_command[3:], ["log", "--oneline", "-n", "20"])
        self.assertFalse(mocked_run.call_args_list[1].kwargs["shell"])

    def test_git_log_no_repo_returns_clear_error(self) -> None:
        project_dir = self.root / "plain-project"
        project_dir.mkdir()

        with self.assertRaisesRegex(GitGatewayError, "Not a git repository."):
            inspect_git_log(project_dir)

    def test_git_log_with_no_commits_returns_clear_error(self) -> None:
        repo_path = self.root / "empty-log-repo"
        repo_path.mkdir()
        completed_processes = [
            MagicMock(returncode=0, stdout="true\n", stderr=""),
            MagicMock(
                returncode=128,
                stdout="",
                stderr="fatal: your current branch 'main' does not have any commits yet",
            ),
        ]

        with patch("tools.git_gateway.subprocess.run", side_effect=completed_processes):
            with self.assertRaisesRegex(GitGatewayError, "Git repository has no commits yet."):
                inspect_git_log(repo_path)

    def test_git_log_uses_no_mutating_git_command(self) -> None:
        repo_path = self.root / "log-repo-safe"
        repo_path.mkdir()
        completed_processes = [
            MagicMock(returncode=0, stdout="true\n", stderr=""),
            MagicMock(returncode=0, stdout="abc123 First commit\n", stderr=""),
        ]

        with patch("tools.git_gateway.subprocess.run", side_effect=completed_processes) as mocked_run:
            inspect_git_log(repo_path)

        banned_git_subcommands = {
            "add",
            "commit",
            "reset",
            "checkout",
            "stash",
            "branch",
            "merge",
            "rebase",
            "clean",
        }
        for call in mocked_run.call_args_list:
            command = call.args[0]
            self.assertEqual(command[0], "git")
            self.assertEqual(command[1], "-C")
            self.assertEqual(command[2], str(repo_path.resolve()))
            self.assertNotIn(command[3], banned_git_subcommands)


class GitGatewayCliTests(TestCase):
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

    def test_git_status_without_project_gives_clear_error(self) -> None:
        with self.assertRaisesRegex(
            SystemExit,
            "Git gateway error: --git-status, --git-diff, and --review-diff require --project.",
        ):
            cli.run(["--git-status"])

    def test_git_diff_without_project_gives_clear_error(self) -> None:
        with self.assertRaisesRegex(
            SystemExit,
            "Git gateway error: --git-status, --git-diff, and --review-diff require --project.",
        ):
            cli.run(["--git-diff"])

    def test_cli_git_status_prints_repo_summary(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "status-repo")
        (repo_path / "notes.txt").write_text("hello\n", encoding="utf-8")
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--project", str(repo_path), "--git-status"])

        output = stdout.getvalue()

        self.assertIn("Git repository: yes", output)
        self.assertIn("Changed files count: 1", output)
        self.assertIn("Changed files: notes.txt", output)

    def test_cli_git_diff_prints_diff_presence(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "diff-repo")
        (repo_path / "notes.txt").write_text("hello\n", encoding="utf-8")
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--project", str(repo_path), "--git-diff"])

        output = stdout.getvalue()

        self.assertIn("Git diff present: yes", output)
        self.assertIn("diff --git", output)

    def test_cli_git_diff_with_secret_like_content_blocks_raw_diff(self) -> None:
        repo_path = self.init_git_repo(self.project_root / "secret-diff-repo")
        secret_value = "super-secret-token-123"
        (repo_path / ".env").write_text(f"API_TOKEN={secret_value}\n", encoding="utf-8")
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--project", str(repo_path), "--git-diff"])

        output = stdout.getvalue()

        self.assertIn("Git diff present: yes", output)
        self.assertIn("Git diff output blocked because secret-like content was detected.", output)
        self.assertIn("Detected token-style assignment", output)
        self.assertNotIn(secret_value, output)
        self.assertNotIn("diff --git", output)

    def test_unapproved_project_is_rejected_before_context_or_git_calls(self) -> None:
        outside_root = self.project_root.parent / "outside-git-project"
        outside_root.mkdir(exist_ok=True)

        with patch.object(cli, "inspect_project_context") as mocked_context:
            with patch.object(cli, "inspect_git_state") as mocked_git:
                with patch.object(cli, "load_config", return_value=self.fake_config):
                    with patch.object(
                        cli,
                        "inspect_required_core_files",
                        return_value=self.fake_core_status,
                    ):
                        with self.assertRaisesRegex(
                            SystemExit,
                            "Approved path error: Target path is outside approved paths:",
                        ):
                            cli.run(["--project", str(outside_root), "--git-status"])

        mocked_context.assert_not_called()
        mocked_git.assert_not_called()
