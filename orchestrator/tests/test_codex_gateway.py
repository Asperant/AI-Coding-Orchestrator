from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from agents.agent_runtime import format_pre_codex_agent_guidance, run_agent_workflow
from orchestration.approval_gate_manager import format_approval_gate_view
from orchestration.edit_plan import generate_edit_plan
from orchestration.task_classifier import classify_task
from tools.codex_gateway import format_codex_prompt_package, generate_codex_prompt_package


class CodexGatewayTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.project_root = self.approved_root / "project"
        self.project_root.mkdir()
        self.file_path = self.project_root / "src" / "module.py"
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text("print('safe')\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_safe_prompt_package_generated_after_explicit_confirmation(self) -> None:
        task = "fix telemetry bug"
        classification = classify_task(task)
        edit_plan = generate_edit_plan(
            self.project_root,
            task,
            ["src/module.py"],
            [str(self.approved_root)],
            task_classification=classification,
        )

        result = generate_codex_prompt_package(
            task,
            str(self.project_root),
            [str(self.file_path.resolve())],
            edit_plan,
            task_classification=classification,
            approval_confirmed=True,
        )

        self.assertTrue(result["can_generate"])
        self.assertIsNone(result["blocked_reason"])
        self.assertIn(str(self.file_path.resolve()), result["allowed_files"])

    def test_ai_brain_guidance_injected_into_prompt(self) -> None:
        task = "fix telemetry bug"
        classification = classify_task(task)
        edit_plan = generate_edit_plan(
            self.project_root,
            task,
            ["src/module.py"],
            [str(self.approved_root)],
            task_classification=classification,
        )

        result = generate_codex_prompt_package(
            task,
            str(self.project_root),
            [str(self.file_path.resolve())],
            edit_plan,
            task_classification=classification,
            approval_confirmed=True,
            ai_brain_guidance="AI-Brain Guidance: Be extremely safe.",
        )

        self.assertTrue(result["can_generate"])
        self.assertIn("AI-Brain Guidance: Be extremely safe.", result["prompt_text"])
        
        fmt = format_codex_prompt_package(result)
        self.assertIn("AI-Brain Guidance included: yes", fmt)

    def test_blocked_when_no_allowed_files(self) -> None:
        result = generate_codex_prompt_package(
            "fix telemetry bug",
            str(self.project_root),
            [],
            {"approval_required": True, "blocked_files": [{"path": "none", "reason": "none"}], "approval_gate": {}},
            approval_confirmed=True,
        )

        self.assertFalse(result["can_generate"])
        self.assertEqual(
            result["blocked_reason"],
            "No allowed files were provided for a scoped Codex prompt.",
        )

    def test_blocked_when_edit_plan_blocks_file(self) -> None:
        task = "fix telemetry bug"
        classification = classify_task(task)
        edit_plan = generate_edit_plan(
            self.project_root,
            task,
            ["src/missing.py"],
            [str(self.approved_root)],
            task_classification=classification,
        )

        result = generate_codex_prompt_package(
            task,
            str(self.project_root),
            [],
            edit_plan,
            task_classification=classification,
            approval_confirmed=True,
        )

        self.assertFalse(result["can_generate"])
        self.assertEqual(
            result["blocked_reason"],
            "No allowed files were provided for a scoped Codex prompt.",
        )

    def test_blocked_when_approval_not_confirmed(self) -> None:
        task = "fix telemetry bug"
        classification = classify_task(task)
        edit_plan = generate_edit_plan(
            self.project_root,
            task,
            ["src/module.py"],
            [str(self.approved_root)],
            task_classification=classification,
        )

        result = generate_codex_prompt_package(
            task,
            str(self.project_root),
            [str(self.file_path.resolve())],
            edit_plan,
            task_classification=classification,
            approval_confirmed=False,
        )

        self.assertFalse(result["can_generate"])
        self.assertEqual(
            result["blocked_reason"],
            "Explicit confirmation is required before generating a Codex prompt for edit work.",
        )
        formatted = format_codex_prompt_package(result)
        self.assertIn("Approval Gate: Approval required: yes", formatted)
        self.assertIn(format_approval_gate_view(edit_plan["approval_gate"]), formatted)

    def test_prompt_contains_allowed_files_and_safety_rules(self) -> None:
        task = "fix telemetry bug"
        classification = classify_task(task)
        edit_plan = generate_edit_plan(
            self.project_root,
            task,
            ["src/module.py"],
            [str(self.approved_root)],
            task_classification=classification,
        )

        result = generate_codex_prompt_package(
            task,
            str(self.project_root),
            [str(self.file_path.resolve())],
            edit_plan,
            task_classification=classification,
            approval_confirmed=True,
        )

        self.assertIn(str(self.file_path.resolve()), result["prompt_text"])
        self.assertIn("Only edit the listed allowed files.", result["prompt_text"])
        self.assertIn("Stop immediately if secrets or credentials are encountered.", result["prompt_text"])
        self.assertIn(format_approval_gate_view(edit_plan["approval_gate"]), result["prompt_text"])
        self.assertIn("Execution approval status: user already approved this scoped execution.", result["prompt_text"])
        self.assertIn("Do not ask for user approval again for this scoped allowed-file edit.", result["prompt_text"])

    def test_prompt_package_includes_pre_codex_agent_guidance(self) -> None:
        task = "fix auth bug"
        classification = classify_task(task)
        edit_plan = generate_edit_plan(
            self.project_root,
            task,
            ["src/module.py"],
            [str(self.approved_root)],
            task_classification=classification,
        )
        agent_summary = run_agent_workflow(
            task_text=task,
            mode="pre-codex",
            task_classification=classification,
            changed_files=[str(self.file_path.resolve())],
        )
        guidance = format_pre_codex_agent_guidance(agent_summary)

        result = generate_codex_prompt_package(
            task,
            str(self.project_root),
            [str(self.file_path.resolve())],
            edit_plan,
            task_classification=classification,
            approval_confirmed=True,
            pre_codex_agent_guidance=guidance,
        )

        self.assertIn("Pre-Codex Agent Guidance:", result["prompt_text"])
        self.assertIn("Agents used: Planner; Tester; Security", result["prompt_text"])
        self.assertIn("Risk guidance:", result["prompt_text"])
        self.assertIn("Test guidance:", result["prompt_text"])
        self.assertIn("Safety guidance:", result["prompt_text"])
        self.assertIn("Only edit the listed allowed files.", result["prompt_text"])
        self.assertIn("Stop immediately if secrets or credentials are encountered.", result["prompt_text"])

    def test_prompt_does_not_include_broad_permissions(self) -> None:
        task = "fix telemetry bug"
        classification = classify_task(task)
        edit_plan = generate_edit_plan(
            self.project_root,
            task,
            ["src/module.py"],
            [str(self.approved_root)],
            task_classification=classification,
        )

        result = generate_codex_prompt_package(
            task,
            str(self.project_root),
            [str(self.file_path.resolve())],
            edit_plan,
            task_classification=classification,
            approval_confirmed=True,
        )
        formatted = format_codex_prompt_package(result)

        self.assertNotIn("edit any file", result["prompt_text"].lower())
        self.assertNotIn("broad rewrite allowed", result["prompt_text"].lower())
        self.assertIn("Can generate: yes", formatted)
        self.assertIn("Approval Gate: Approval required: yes", formatted)
        self.assertIn("Pre-Codex Agent Guidance included: no", formatted)


class CodexGatewayCliTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.project_root = self.root / "project"
        self.project_root.mkdir()
        self.file_path = self.project_root / "src" / "module.py"
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_path.write_text("print('safe')\n", encoding="utf-8")
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

    def test_cli_prints_prompt_package(self) -> None:
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
                            "--codex-prompt",
                            "--confirm-codex-prompt",
                            "--allowed-file",
                            "src/module.py",
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn("Can generate: yes", output)
        self.assertIn("Prompt text:", output)
        self.assertIn("Pre-Codex Agent Guidance:", output)
        self.assertIn("Agents used: Planner; Tester", output)
        self.assertIn("Only edit the listed allowed files.", output)
        self.assertIn("Approval Gate: Approval required: yes", output)

    def test_cli_codex_prompt_with_secret_like_task_text_blocks_raw_output(self) -> None:
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
                            "--codex-prompt",
                            "--confirm-codex-prompt",
                            "--allowed-file",
                            "src/module.py",
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn("Codex prompt package output blocked because secret-like content was detected.", output)
        self.assertIn("Detected token-style assignment", output)
        self.assertNotIn(secret_value, output)
        self.assertNotIn("Prompt text:", output)
