from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from orchestration.approval_gate_manager import format_approval_gate_view
from tools.codex_execution_contract import (
    format_codex_execution_contract,
    format_codex_execution_contract_view,
    evaluate_codex_execution_contract,
)


class CodexExecutionContractTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.project_root = self.approved_root / "project"
        self.project_root.mkdir()
        self.ai_brain_root = self.approved_root / "ai-brain"
        self.ai_brain_root.mkdir()
        self.allowed_file = self.project_root / "src" / "module.py"
        self.allowed_file.parent.mkdir(parents=True, exist_ok=True)
        self.allowed_file.write_text("print('safe')\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_valid_contract_can_execute(self) -> None:
        result = evaluate_codex_execution_contract(
            self.project_root,
            "fix telemetry bug",
            ["src/module.py"],
            [str(self.approved_root)],
            approval_confirmed=True,
            codex_prompt_package="safe prompt package",
            timeout_seconds=300,
            ai_brain_path=self.ai_brain_root,
        )

        self.assertTrue(result["can_execute"])
        self.assertTrue(result["approval_required"])
        self.assertEqual(result["risk_level"], "high")
        self.assertTrue(result["approval_gate"]["approval_required"])
        self.assertIn(str(self.allowed_file.resolve()), result["allowed_files"])
        self.assertIn("No execution was performed.", result["execution_summary"])
        self.assertEqual(self.allowed_file.read_text(encoding="utf-8"), "print('safe')\n")

    def test_missing_approval_blocks(self) -> None:
        result = evaluate_codex_execution_contract(
            self.project_root,
            "fix telemetry bug",
            ["src/module.py"],
            [str(self.approved_root)],
            approval_confirmed=False,
            ai_brain_path=self.ai_brain_root,
        )

        self.assertFalse(result["can_execute"])
        self.assertIn("Explicit approval confirmation is required", " ".join(result["blocked_reasons"]))

    def test_no_allowed_files_blocks(self) -> None:
        result = evaluate_codex_execution_contract(
            self.project_root,
            "fix telemetry bug",
            [],
            [str(self.approved_root)],
            approval_confirmed=True,
            ai_brain_path=self.ai_brain_root,
        )

        self.assertFalse(result["can_execute"])
        self.assertIn("At least one allowed file is required", " ".join(result["blocked_reasons"]))

    def test_allowed_file_outside_project_blocks(self) -> None:
        outside_file = self.approved_root / "outside.py"
        outside_file.write_text("print('outside')\n", encoding="utf-8")

        result = evaluate_codex_execution_contract(
            self.project_root,
            "fix telemetry bug",
            [str(outside_file)],
            [str(self.approved_root)],
            approval_confirmed=True,
            ai_brain_path=self.ai_brain_root,
        )

        self.assertFalse(result["can_execute"])
        self.assertIn("outside the approved project path", " ".join(result["blocked_reasons"]))

    def test_directory_allowed_file_blocks(self) -> None:
        result = evaluate_codex_execution_contract(
            self.project_root,
            "fix telemetry bug",
            ["src"],
            [str(self.approved_root)],
            approval_confirmed=True,
            ai_brain_path=self.ai_brain_root,
        )

        self.assertFalse(result["can_execute"])
        self.assertIn("directory, not a file", " ".join(result["blocked_reasons"]))

    def test_wildcard_allowed_file_blocks(self) -> None:
        result = evaluate_codex_execution_contract(
            self.project_root,
            "fix telemetry bug",
            ["src/*.py"],
            [str(self.approved_root)],
            approval_confirmed=True,
            ai_brain_path=self.ai_brain_root,
        )

        self.assertFalse(result["can_execute"])
        self.assertIn("Wildcard or broad allowed file", " ".join(result["blocked_reasons"]))

    def test_unapproved_project_blocks(self) -> None:
        outside_project = self.root / "outside-project"
        outside_project.mkdir()

        result = evaluate_codex_execution_contract(
            outside_project,
            "fix telemetry bug",
            ["src/module.py"],
            [str(self.approved_root)],
            approval_confirmed=True,
            ai_brain_path=self.ai_brain_root,
        )

        self.assertFalse(result["can_execute"])
        self.assertIn("Target path is outside approved paths", " ".join(result["blocked_reasons"]))

    def test_secret_like_task_blocks_without_raw_secret(self) -> None:
        secret_value = "super-secret-token-123"
        result = evaluate_codex_execution_contract(
            self.project_root,
            f"fix auth bug with API_TOKEN={secret_value}",
            ["src/module.py"],
            [str(self.approved_root)],
            approval_confirmed=True,
            ai_brain_path=self.ai_brain_root,
        )
        formatted = format_codex_execution_contract(result)

        self.assertFalse(result["can_execute"])
        self.assertIn("Codex execution task text blocked because secret-like content was detected.", formatted)
        self.assertIn("Detected token-style assignment", formatted)
        self.assertNotIn(secret_value, formatted)

    def test_unsafe_prompt_package_blocks_without_raw_secret(self) -> None:
        secret_value = "super-secret-token-123"
        result = evaluate_codex_execution_contract(
            self.project_root,
            "fix telemetry bug",
            ["src/module.py"],
            [str(self.approved_root)],
            approval_confirmed=True,
            codex_prompt_package=f"Prompt body with API_TOKEN={secret_value}",
            ai_brain_path=self.ai_brain_root,
        )
        formatted = format_codex_execution_contract(result)

        self.assertFalse(result["can_execute"])
        self.assertIn("Codex execution prompt package blocked because secret-like content was detected.", formatted)
        self.assertIn("Detected token-style assignment", formatted)
        self.assertNotIn(secret_value, formatted)

    def test_shared_formatter_includes_approval_gate_view(self) -> None:
        result = evaluate_codex_execution_contract(
            self.project_root,
            "fix telemetry bug",
            ["src/module.py"],
            [str(self.approved_root)],
            approval_confirmed=True,
            ai_brain_path=self.ai_brain_root,
        )

        formatted = format_codex_execution_contract_view(result)

        self.assertIn("Approval gate:", formatted)
        self.assertIn(format_approval_gate_view(result["approval_gate"]), formatted)

    def test_timeout_less_than_or_equal_to_zero_blocks(self) -> None:
        result = evaluate_codex_execution_contract(
            self.project_root,
            "fix telemetry bug",
            ["src/module.py"],
            [str(self.approved_root)],
            approval_confirmed=True,
            timeout_seconds=0,
            ai_brain_path=self.ai_brain_root,
        )

        self.assertFalse(result["can_execute"])
        self.assertIn("greater than zero", " ".join(result["blocked_reasons"]))

    def test_timeout_too_high_blocks(self) -> None:
        result = evaluate_codex_execution_contract(
            self.project_root,
            "fix telemetry bug",
            ["src/module.py"],
            [str(self.approved_root)],
            approval_confirmed=True,
            timeout_seconds=601,
            ai_brain_path=self.ai_brain_root,
        )

        self.assertFalse(result["can_execute"])
        self.assertIn("maximum allowed value of 600", " ".join(result["blocked_reasons"]))

    def test_ai_brain_allowed_file_blocks(self) -> None:
        ai_brain_file = self.ai_brain_root / "memory.md"
        ai_brain_file.write_text("memory\n", encoding="utf-8")

        result = evaluate_codex_execution_contract(
            self.ai_brain_root,
            "fix telemetry bug",
            ["memory.md"],
            [str(self.approved_root)],
            approval_confirmed=True,
            ai_brain_path=self.ai_brain_root,
        )

        self.assertFalse(result["can_execute"])
        self.assertIn("Allowed file cannot point into AI-Brain", " ".join(result["blocked_reasons"]))


class CodexExecutionContractCliTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.project_root = self.approved_root / "project"
        self.project_root.mkdir()
        self.ai_brain_root = self.approved_root / "ai-brain"
        self.ai_brain_root.mkdir()
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

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cli_prints_contract_result(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--project",
                            str(self.project_root),
                            "--task",
                            "fix telemetry bug",
                            "--codex-execution-check",
                            "--allowed-file",
                            "src/module.py",
                            "--confirm-codex-prompt",
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn("Can execute: yes", output)
        self.assertIn("Approval gate:", output)
        self.assertIn("Approval required: yes", output)
        self.assertIn("Risk level: high", output)
        self.assertIn("Allowed files:", output)
        self.assertIn("Safety requirements:", output)
        self.assertIn("Execution summary:", output)

    def test_cli_secret_like_task_blocks_without_raw_secret(self) -> None:
        secret_value = "super-secret-token-123"
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--project",
                            str(self.project_root),
                            "--task",
                            f"fix auth bug with API_TOKEN={secret_value}",
                            "--codex-execution-check",
                            "--allowed-file",
                            "src/module.py",
                            "--confirm-codex-prompt",
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn("Can execute: no", output)
        self.assertIn("Codex execution task text blocked because secret-like content was detected.", output)
        self.assertNotIn(secret_value, output)

    def test_cli_requires_explicit_confirmation(self) -> None:
        with patch.object(cli, "load_config", return_value=self.fake_config):
            with self.assertRaisesRegex(
                SystemExit,
                "Codex execution contract error: --codex-execution-check requires --confirm-codex-prompt.",
            ):
                cli.run(
                    [
                        "--project",
                        str(self.project_root),
                        "--task",
                        "fix telemetry bug",
                        "--codex-execution-check",
                        "--allowed-file",
                        "src/module.py",
                    ]
                )
