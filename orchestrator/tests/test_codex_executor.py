from __future__ import annotations

import subprocess
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from core import report_writer
from tools.codex_executor import (
    execute_codex_task,
    execute_codex_task_with_post_review,
    format_codex_execution_result,
)


class CodexExecutorTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.project_root = self.approved_root / "project"
        self.project_root.mkdir()
        self.ai_brain_root = self.approved_root / "ai-brain"
        self.ai_brain_root.mkdir()
        self.ai_brain_file = self.ai_brain_root / "memory.md"
        self.ai_brain_file.write_text("brain\n", encoding="utf-8")
        self.allowed_file = self.project_root / "src" / "module.py"
        self.allowed_file.parent.mkdir(parents=True, exist_ok=True)
        self.allowed_file.write_text("print('safe')\n", encoding="utf-8")
        self.prompt_text = "Codex Task Package\nTask: fix telemetry bug"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _codex_subprocess_side_effect(self, completed: subprocess.CompletedProcess[str]):
        real_run = subprocess.run

        def side_effect(*args, **kwargs):
            command = args[0] if args else kwargs.get("args")
            if command and isinstance(command, list) and command[0] == "/usr/bin/codex":
                return completed
            return real_run(*args, **kwargs)

        return side_effect

    def test_contract_failure_blocks_execution(self) -> None:
        with patch("tools.codex_executor.shutil.which") as mocked_which:
            with patch("tools.codex_executor.subprocess.run") as mocked_run:
                result = execute_codex_task(
                    self.project_root,
                    "fix telemetry bug",
                    [],
                    [str(self.approved_root)],
                    approval_confirmed=True,
                    prompt_package_text=self.prompt_text,
                    execute_confirmed=True,
                    ai_brain_path=self.ai_brain_root,
                )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("safety contract did not pass", result["message"])
        mocked_which.assert_not_called()
        mocked_run.assert_not_called()

    def test_missing_execute_confirmation_blocks_execution(self) -> None:
        with patch("tools.codex_executor.shutil.which") as mocked_which:
            with patch("tools.codex_executor.subprocess.run") as mocked_run:
                result = execute_codex_task(
                    self.project_root,
                    "fix telemetry bug",
                    ["src/module.py"],
                    [str(self.approved_root)],
                    approval_confirmed=True,
                    prompt_package_text=self.prompt_text,
                    execute_confirmed=False,
                    ai_brain_path=self.ai_brain_root,
                )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("confirmation is required", result["message"])
        mocked_which.assert_not_called()
        mocked_run.assert_not_called()

    def test_missing_codex_binary_returns_clean_error(self) -> None:
        with patch("tools.codex_executor.shutil.which", return_value=None):
            with patch("tools.codex_executor.subprocess.run") as mocked_run:
                result = execute_codex_task(
                    self.project_root,
                    "fix telemetry bug",
                    ["src/module.py"],
                    [str(self.approved_root)],
                    approval_confirmed=True,
                    prompt_package_text=self.prompt_text,
                    execute_confirmed=True,
                    ai_brain_path=self.ai_brain_root,
                )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("Codex command was not found on PATH", result["message"])
        mocked_run.assert_not_called()

    def test_subprocess_success_captures_stdout_and_return_code(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["/usr/bin/codex"],
            returncode=0,
            stdout="execution ok\n",
            stderr="",
        )

        with patch("tools.codex_executor.shutil.which", return_value="/usr/bin/codex"):
            with patch("tools.codex_executor.subprocess.run", return_value=completed) as mocked_run:
                result = execute_codex_task(
                    self.project_root,
                    "fix telemetry bug",
                    ["src/module.py"],
                    [str(self.approved_root)],
                    approval_confirmed=True,
                    prompt_package_text=self.prompt_text,
                    execute_confirmed=True,
                    timeout_seconds=120,
                    ai_brain_path=self.ai_brain_root,
                )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertEqual(result["return_code"], 0)
        self.assertEqual(result["stdout"], "execution ok\n")
        self.assertEqual(result["stderr"], "")
        self.assertEqual(self.ai_brain_file.read_text(encoding="utf-8"), "brain\n")
        mocked_run.assert_called_once()
        args, kwargs = mocked_run.call_args
        command_list = args[0]
        self.assertEqual(command_list[0], "/usr/bin/codex")
        self.assertEqual(command_list[1], "exec")
        self.assertEqual(command_list[2], "-")
        self.assertEqual(command_list[3], "--cd")
        self.assertEqual(command_list[4], str(self.project_root.resolve()))
        self.assertEqual(command_list[5], "--sandbox")
        self.assertEqual(command_list[6], "workspace-write")
        self.assertEqual(command_list[7], "--ephemeral")
        self.assertNotIn("--ask-for-approval", command_list)
        self.assertNotIn("--danger-full-access", command_list)
        self.assertEqual(kwargs["cwd"], self.project_root.resolve())
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["timeout"], 120)
        self.assertEqual(kwargs["input"], self.prompt_text)

    def test_subprocess_failure_captures_stderr_and_return_code(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["/usr/bin/codex"],
            returncode=2,
            stdout="",
            stderr="execution failed\n",
        )

        with patch("tools.codex_executor.shutil.which", return_value="/usr/bin/codex"):
            with patch("tools.codex_executor.subprocess.run", return_value=completed):
                result = execute_codex_task(
                    self.project_root,
                    "fix telemetry bug",
                    ["src/module.py"],
                    [str(self.approved_root)],
                    approval_confirmed=True,
                    prompt_package_text=self.prompt_text,
                    execute_confirmed=True,
                    ai_brain_path=self.ai_brain_root,
                )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertEqual(result["return_code"], 2)
        self.assertEqual(result["stderr"], "execution failed\n")
        self.assertIn("return code 2", result["message"])

    def test_timeout_is_handled(self) -> None:
        timeout_error = subprocess.TimeoutExpired(
            cmd=["/usr/bin/codex"],
            timeout=300,
            output="partial output",
            stderr="timeout stderr",
        )

        with patch("tools.codex_executor.shutil.which", return_value="/usr/bin/codex"):
            with patch("tools.codex_executor.subprocess.run", side_effect=timeout_error):
                result = execute_codex_task(
                    self.project_root,
                    "fix telemetry bug",
                    ["src/module.py"],
                    [str(self.approved_root)],
                    approval_confirmed=True,
                    prompt_package_text=self.prompt_text,
                    execute_confirmed=True,
                    ai_brain_path=self.ai_brain_root,
                )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertTrue(result["timed_out"])
        self.assertIsNone(result["return_code"])
        self.assertEqual(result["stdout"], "partial output")
        self.assertEqual(result["stderr"], "timeout stderr")

    def test_secret_like_task_blocks_without_raw_secret(self) -> None:
        secret_value = "super-secret-token-123"
        result = execute_codex_task(
            self.project_root,
            f"fix auth bug with API_TOKEN={secret_value}",
            ["src/module.py"],
            [str(self.approved_root)],
            approval_confirmed=True,
            prompt_package_text=self.prompt_text,
            execute_confirmed=True,
            ai_brain_path=self.ai_brain_root,
        )
        formatted = format_codex_execution_result(result)

        self.assertTrue(result["blocked"])
        self.assertIn("Can execute: no", formatted)
        self.assertIn("Detected token-style assignment", formatted)
        self.assertNotIn(secret_value, formatted)

    def test_unsafe_prompt_package_blocks_without_raw_secret(self) -> None:
        secret_value = "super-secret-token-123"
        result = execute_codex_task(
            self.project_root,
            "fix telemetry bug",
            ["src/module.py"],
            [str(self.approved_root)],
            approval_confirmed=True,
            prompt_package_text=f"Prompt body with API_TOKEN={secret_value}",
            execute_confirmed=True,
            ai_brain_path=self.ai_brain_root,
        )
        formatted = format_codex_execution_result(result)

        self.assertTrue(result["blocked"])
        self.assertIn("Codex execution prompt package blocked because secret-like content was detected.", formatted)
        self.assertNotIn(secret_value, formatted)

    def test_invalid_timeout_blocks_execution(self) -> None:
        with patch("tools.codex_executor.shutil.which") as mocked_which:
            with patch("tools.codex_executor.subprocess.run") as mocked_run:
                result = execute_codex_task(
                    self.project_root,
                    "fix telemetry bug",
                    ["src/module.py"],
                    [str(self.approved_root)],
                    approval_confirmed=True,
                    prompt_package_text=self.prompt_text,
                    execute_confirmed=True,
                    timeout_seconds=0,
                    ai_brain_path=self.ai_brain_root,
                )

        self.assertTrue(result["blocked"])
        self.assertIn("greater than zero", format_codex_execution_result(result))
        mocked_which.assert_not_called()
        mocked_run.assert_not_called()

    def test_successful_execution_triggers_post_diff_review(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["/usr/bin/codex"],
            returncode=0,
            stdout="execution ok\n",
            stderr="",
        )
        git_state = {
            "is_git_repo": True,
            "changed_files": ["telemetry.py"],
            "status_summary": "1 changed file(s).",
            "diff_text": "diff --git a/telemetry.py b/telemetry.py\n+ENABLED = True\n",
            "diff_present": True,
        }

        with patch("tools.codex_executor.shutil.which", return_value="/usr/bin/codex"):
            with patch("tools.codex_executor.inspect_git_state", return_value=git_state):
                with patch(
                    "tools.codex_executor.subprocess.run",
                    side_effect=self._codex_subprocess_side_effect(completed),
                ):
                    result = execute_codex_task_with_post_review(
                        self.project_root,
                        "fix telemetry bug",
                        ["src/module.py"],
                        [str(self.approved_root)],
                        approval_confirmed=True,
                        prompt_package_text=self.prompt_text,
                        execute_confirmed=True,
                        ai_brain_path=self.ai_brain_root,
                        post_codex_review=True,
                    )

        self.assertTrue(result["executed"])
        self.assertTrue(result["post_review_ran"])
        self.assertIn("Decision:", result["post_review_report"])
        self.assertIn("Final decision reason:", result["post_review_report"])
        self.assertIn("Per-agent signals:", result["post_review_report"])
        self.assertIn("Changed files:", result["post_review_report"])

    def test_blocked_execution_does_not_trigger_post_review(self) -> None:
        result = execute_codex_task_with_post_review(
            self.project_root,
            "fix telemetry bug",
            [],
            [str(self.approved_root)],
            approval_confirmed=True,
            prompt_package_text=self.prompt_text,
            execute_confirmed=True,
            ai_brain_path=self.ai_brain_root,
            post_codex_review=True,
        )

        self.assertFalse(result["post_review_ran"])
        self.assertEqual(result["post_review_decision"], "not run")

    def test_failed_execution_does_not_trigger_post_review(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["/usr/bin/codex"],
            returncode=1,
            stdout="",
            stderr="execution failed\n",
        )

        with patch("tools.codex_executor.shutil.which", return_value="/usr/bin/codex"):
            with patch(
                "tools.codex_executor.subprocess.run",
                side_effect=self._codex_subprocess_side_effect(completed),
            ):
                result = execute_codex_task_with_post_review(
                    self.project_root,
                    "fix telemetry bug",
                    ["src/module.py"],
                    [str(self.approved_root)],
                    approval_confirmed=True,
                    prompt_package_text=self.prompt_text,
                    execute_confirmed=True,
                    ai_brain_path=self.ai_brain_root,
                    post_codex_review=True,
                )

        self.assertFalse(result["post_review_ran"])
        self.assertIn("did not complete successfully", result["post_review_message"])

    def test_non_git_project_returns_clear_post_review_message(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["/usr/bin/codex"],
            returncode=0,
            stdout="execution ok\n",
            stderr="",
        )
        git_state = {
            "is_git_repo": False,
            "changed_files": [],
            "status_summary": "Not a git repository.",
            "diff_text": "",
            "diff_present": False,
        }

        with patch("tools.codex_executor.shutil.which", return_value="/usr/bin/codex"):
            with patch("tools.codex_executor.inspect_git_state", return_value=git_state):
                with patch(
                    "tools.codex_executor.subprocess.run",
                    side_effect=self._codex_subprocess_side_effect(completed),
                ):
                    result = execute_codex_task_with_post_review(
                        self.project_root,
                        "fix telemetry bug",
                        ["src/module.py"],
                        [str(self.approved_root)],
                        approval_confirmed=True,
                        prompt_package_text=self.prompt_text,
                        execute_confirmed=True,
                        ai_brain_path=self.ai_brain_root,
                        post_codex_review=True,
                    )

        self.assertTrue(result["post_review_ran"])
        self.assertEqual(result["post_review_decision"], "Blocked")
        self.assertIn("not a git repository", result["post_review_message"])
        self.assertIn("Diff review cannot run because the project is not a git repository.", result["post_review_report"])

    def test_secret_like_diff_blocks_review_without_raw_secret(self) -> None:
        secret_value = "super-secret-token-123"
        completed = subprocess.CompletedProcess(
            args=["/usr/bin/codex"],
            returncode=0,
            stdout="execution ok\n",
            stderr="",
        )
        git_state = {
            "is_git_repo": True,
            "changed_files": [".env"],
            "status_summary": "1 changed file(s).",
            "diff_text": f"diff --git a/.env b/.env\n+API_TOKEN={secret_value}\n",
            "diff_present": True,
        }

        with patch("tools.codex_executor.shutil.which", return_value="/usr/bin/codex"):
            with patch("tools.codex_executor.inspect_git_state", return_value=git_state):
                with patch(
                    "tools.codex_executor.subprocess.run",
                    side_effect=self._codex_subprocess_side_effect(completed),
                ):
                    result = execute_codex_task_with_post_review(
                        self.project_root,
                        "fix auth bug",
                        ["src/module.py"],
                        [str(self.approved_root)],
                        approval_confirmed=True,
                        prompt_package_text=self.prompt_text,
                        execute_confirmed=True,
                        ai_brain_path=self.ai_brain_root,
                        post_codex_review=True,
                    )

        formatted = format_codex_execution_result(result)
        self.assertTrue(result["post_review_ran"])
        self.assertEqual(result["post_review_decision"], "Blocked")
        self.assertTrue(result["post_review_should_block_save"])
        self.assertIn("secret-like content was detected", formatted)
        self.assertIn("Security: Secret-like diff content was blocked", formatted)
        self.assertNotIn(secret_value, formatted)


class CodexExecutorCliTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.project_root = self.approved_root / "project"
        self.project_root.mkdir()
        self.ai_brain_root = self.approved_root / "ai-brain"
        self.ai_brain_root.mkdir()
        self.ai_brain_file = self.ai_brain_root / "memory.md"
        self.ai_brain_file.write_text("brain\n", encoding="utf-8")
        self.allowed_file = self.project_root / "src" / "module.py"
        self.allowed_file.parent.mkdir(parents=True, exist_ok=True)
        self.allowed_file.write_text("print('safe')\n", encoding="utf-8")
        self.fake_config = {
            "ai_brain_path": str(self.ai_brain_root),
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": [str(self.approved_root)],
        }
        self.fake_core_status = {
            "checked_count": 4,
            "found_count": 4,
            "missing_count": 0,
            "missing_files": {},
        }
        self.project_root_patch = patch.object(report_writer, "PROJECT_ROOT", self.root)
        self.project_root_patch.start()

    def tearDown(self) -> None:
        self.project_root_patch.stop()
        self.temp_dir.cleanup()

    def _codex_subprocess_side_effect(self, completed: subprocess.CompletedProcess[str]):
        real_run = subprocess.run

        def side_effect(*args, **kwargs):
            command = args[0] if args else kwargs.get("args")
            if command and isinstance(command, list) and command[0] == "/usr/bin/codex":
                return completed
            return real_run(*args, **kwargs)

        return side_effect

    def test_cli_without_execute_confirmation_blocks(self) -> None:
        with patch.object(cli, "load_config", return_value=self.fake_config):
            with self.assertRaisesRegex(
                SystemExit,
                "Codex executor error: --execute-codex requires --confirm-codex-execution.",
            ):
                cli.run(
                    [
                        "--project",
                        str(self.project_root),
                        "--task",
                        "fix telemetry bug",
                        "--execute-codex",
                        "--allowed-file",
                        "src/module.py",
                        "--confirm-codex-prompt",
                    ]
                )

    def test_cli_with_mocked_executor_path_prints_result(self) -> None:
        stdout = StringIO()
        completed = subprocess.CompletedProcess(
            args=["/usr/bin/codex"],
            returncode=0,
            stdout="execution ok\n",
            stderr="",
        )

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with patch("tools.codex_executor.shutil.which", return_value="/usr/bin/codex"):
                    with patch(
                        "tools.codex_executor.subprocess.run",
                        side_effect=self._codex_subprocess_side_effect(completed),
                    ):
                        with redirect_stdout(stdout):
                            cli.run(
                                [
                                    "--project",
                                    str(self.project_root),
                                    "--task",
                                    "fix telemetry bug",
                                    "--execute-codex",
                                    "--allowed-file",
                                    "src/module.py",
                                    "--confirm-codex-prompt",
                                    "--confirm-codex-execution",
                                ]
                            )

        output = stdout.getvalue()

        self.assertIn("Executed: yes", output)
        self.assertIn("Blocked: no", output)
        self.assertIn("Return code: 0", output)
        self.assertIn("Stdout: execution ok", output)
        self.assertEqual(self.ai_brain_file.read_text(encoding="utf-8"), "brain\n")

    def test_cli_save_report_saves_combined_report_only_when_safe(self) -> None:
        stdout = StringIO()
        completed = subprocess.CompletedProcess(
            args=["/usr/bin/codex"],
            returncode=0,
            stdout="execution ok\n",
            stderr="",
        )
        git_state = {
            "is_git_repo": True,
            "changed_files": ["telemetry.py"],
            "status_summary": "1 changed file(s).",
            "diff_text": "diff --git a/telemetry.py b/telemetry.py\n+ENABLED = True\n",
            "diff_present": True,
        }

        execution_config = dict(self.fake_config)
        execution_config["approved_paths"] = [str(self.approved_root)]

        with patch.object(cli, "load_config", return_value=execution_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with patch("tools.codex_executor.inspect_git_state", return_value=git_state):
                    with patch("tools.codex_executor.shutil.which", return_value="/usr/bin/codex"):
                        with patch(
                            "tools.codex_executor.subprocess.run",
                            side_effect=self._codex_subprocess_side_effect(completed),
                        ):
                            with redirect_stdout(stdout):
                                cli.run(
                                    [
                                        "--project",
                                        str(self.project_root),
                                        "--task",
                                        "fix telemetry bug",
                                        "--execute-codex",
                                        "--post-codex-review",
                                        "--save-report",
                                        "--allowed-file",
                                        "src/module.py",
                                        "--confirm-codex-prompt",
                                        "--confirm-codex-execution",
                                    ]
                                )

        output = stdout.getvalue()
        created_reports = list((self.root / "reports").glob("*.md"))

        self.assertIn("Executed: yes", output)
        self.assertIn("Post-Codex review decision:", output)
        self.assertIn("Report saved to:", output)
        self.assertEqual(len(created_reports), 1)
        saved_text = created_reports[0].read_text(encoding="utf-8")
        self.assertIn("Executed: yes", saved_text)
        self.assertIn("Post-Codex review report:", saved_text)
        self.assertIn("Decision:", saved_text)

    def test_cli_save_report_does_not_save_if_review_is_safety_blocked(self) -> None:
        secret_value = "super-secret-token-123"
        stdout = StringIO()
        completed = subprocess.CompletedProcess(
            args=["/usr/bin/codex"],
            returncode=0,
            stdout="execution ok\n",
            stderr="",
        )
        git_state = {
            "is_git_repo": True,
            "changed_files": [".env"],
            "status_summary": "1 changed file(s).",
            "diff_text": f"diff --git a/.env b/.env\n+API_TOKEN={secret_value}\n",
            "diff_present": True,
        }

        execution_config = dict(self.fake_config)
        execution_config["approved_paths"] = [str(self.approved_root)]

        with patch.object(cli, "load_config", return_value=execution_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with patch("tools.codex_executor.inspect_git_state", return_value=git_state):
                    with patch("tools.codex_executor.shutil.which", return_value="/usr/bin/codex"):
                        with patch(
                            "tools.codex_executor.subprocess.run",
                            side_effect=self._codex_subprocess_side_effect(completed),
                        ):
                            with redirect_stdout(stdout):
                                cli.run(
                                    [
                                        "--project",
                                        str(self.project_root),
                                        "--task",
                                        "fix auth bug",
                                        "--execute-codex",
                                        "--post-codex-review",
                                        "--save-report",
                                        "--allowed-file",
                                        "src/module.py",
                                        "--confirm-codex-prompt",
                                        "--confirm-codex-execution",
                                    ]
                                )

        output = stdout.getvalue()
        created_reports = list((self.root / "reports").glob("*.md"))

        self.assertIn("Post-Codex review decision: Blocked", output)
        self.assertIn("Report saving blocked due to secret-like content detected in the post-Codex review flow.", output)
        self.assertNotIn("Report saved to:", output)
        self.assertNotIn(secret_value, output)
        self.assertEqual(created_reports, [])
