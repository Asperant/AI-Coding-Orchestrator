from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from tools.test_runner import format_test_result, run_test_command


class TestRunnerTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.project_root = self.approved_root / "project"
        self.project_root.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_allowed_unittest_command_runs_with_mocked_subprocess(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python", "-m", "unittest"],
            returncode=0,
            stdout="ok\n",
            stderr="",
        )

        with patch("tools.test_runner.subprocess.run", return_value=completed) as mocked_run:
            result = run_test_command(
                self.project_root,
                ["python", "-m", "unittest"],
                [str(self.approved_root)],
            )

        self.assertTrue(result["ran"])
        self.assertFalse(result["blocked"])
        self.assertTrue(result["passed"])
        self.assertEqual(result["return_code"], 0)
        args, kwargs = mocked_run.call_args
        self.assertEqual(args[0], ["python", "-m", "unittest"])
        self.assertEqual(kwargs["cwd"], self.project_root.resolve())
        self.assertFalse(kwargs["shell"])

    def test_allowed_npm_test_command_runs_with_mocked_subprocess(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["npm", "test"],
            returncode=0,
            stdout="pass\n",
            stderr="",
        )

        with patch("tools.test_runner.subprocess.run", return_value=completed):
            result = run_test_command(
                self.project_root,
                ["npm", "test"],
                [str(self.approved_root)],
            )

        self.assertTrue(result["ran"])
        self.assertTrue(result["passed"])

    def test_safe_env_prefix_works(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["python", "-m", "unittest"],
            returncode=0,
            stdout="ok\n",
            stderr="",
        )

        with patch("tools.test_runner.subprocess.run", return_value=completed) as mocked_run:
            result = run_test_command(
                self.project_root,
                ["PYTHONDONTWRITEBYTECODE=1", "python", "-m", "unittest"],
                [str(self.approved_root)],
            )

        self.assertTrue(result["ran"])
        self.assertFalse(result["blocked"])
        args, kwargs = mocked_run.call_args
        self.assertEqual(args[0], ["python", "-m", "unittest"])
        self.assertIn("PYTHONDONTWRITEBYTECODE", kwargs["env"])
        self.assertEqual(kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1")

    def test_unsafe_env_value_blocks(self) -> None:
        with patch("tools.test_runner.subprocess.run") as mocked_run:
            result = run_test_command(
                self.project_root,
                ["PYTHONDONTWRITEBYTECODE=0", "python", "-m", "unittest"],
                [str(self.approved_root)],
            )

        self.assertFalse(result["ran"])
        self.assertTrue(result["blocked"])
        mocked_run.assert_not_called()

    def test_unsafe_env_var_blocks(self) -> None:
        with patch("tools.test_runner.subprocess.run") as mocked_run:
            result = run_test_command(
                self.project_root,
                ["SECRET=abc", "python", "-m", "unittest"],
                [str(self.approved_root)],
            )

        self.assertFalse(result["ran"])
        self.assertTrue(result["blocked"])
        mocked_run.assert_not_called()

    def test_shell_chaining_after_env_prefix_blocks(self) -> None:
        with patch("tools.test_runner.subprocess.run") as mocked_run:
            result = run_test_command(
                self.project_root,
                "PYTHONDONTWRITEBYTECODE=1 python -m unittest && rm -rf /",
                [str(self.approved_root)],
            )

        self.assertFalse(result["ran"])
        self.assertTrue(result["blocked"])
        mocked_run.assert_not_called()

    def test_unsafe_shell_command_is_blocked(self) -> None:
        with patch("tools.test_runner.subprocess.run") as mocked_run:
            result = run_test_command(
                self.project_root,
                "python -m unittest && rm -rf /",
                [str(self.approved_root)],
            )

        self.assertFalse(result["ran"])
        self.assertTrue(result["blocked"])
        self.assertIn("Unsafe shell syntax", result["message"])
        mocked_run.assert_not_called()

    def test_unapproved_project_blocks(self) -> None:
        outside_project = self.root / "outside"
        outside_project.mkdir()

        with patch("tools.test_runner.subprocess.run") as mocked_run:
            result = run_test_command(
                outside_project,
                ["python", "-m", "unittest"],
                [str(self.approved_root)],
            )

        self.assertFalse(result["ran"])
        self.assertTrue(result["blocked"])
        self.assertIn("outside approved paths", result["message"])
        mocked_run.assert_not_called()

    def test_timeout_is_handled(self) -> None:
        timeout_error = subprocess.TimeoutExpired(
            cmd=["pytest"],
            timeout=120,
            output="partial",
            stderr="timeout stderr",
        )

        with patch("tools.test_runner.subprocess.run", side_effect=timeout_error):
            result = run_test_command(
                self.project_root,
                ["pytest"],
                [str(self.approved_root)],
            )

        self.assertTrue(result["ran"])
        self.assertFalse(result["blocked"])
        self.assertFalse(result["passed"])
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["stdout"], "partial")
        self.assertEqual(result["stderr"], "timeout stderr")

    def test_failing_test_sets_passed_false(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["pytest"],
            returncode=1,
            stdout="failed\n",
            stderr="trace\n",
        )

        with patch("tools.test_runner.subprocess.run", return_value=completed):
            result = run_test_command(
                self.project_root,
                ["pytest"],
                [str(self.approved_root)],
            )

        self.assertTrue(result["ran"])
        self.assertFalse(result["blocked"])
        self.assertFalse(result["passed"])
        self.assertEqual(result["return_code"], 1)
        self.assertIn("return code 1", result["message"])

    def test_invalid_timeout_is_blocked(self) -> None:
        with patch("tools.test_runner.subprocess.run") as mocked_run:
            result = run_test_command(
                self.project_root,
                ["pytest"],
                [str(self.approved_root)],
                timeout_seconds=0,
            )

        self.assertFalse(result["ran"])
        self.assertTrue(result["blocked"])
        self.assertIn("greater than zero", result["message"])
        mocked_run.assert_not_called()

    def test_formatter_includes_result_fields(self) -> None:
        formatted = format_test_result(
            {
                "ran": True,
                "blocked": False,
                "passed": True,
                "return_code": 0,
                "timed_out": False,
                "stdout": "ok",
                "stderr": "",
                "message": "Test command completed successfully.",
            }
        )

        self.assertIn("Ran: yes", formatted)
        self.assertIn("Passed: yes", formatted)
        self.assertIn("Stdout: ok", formatted)
