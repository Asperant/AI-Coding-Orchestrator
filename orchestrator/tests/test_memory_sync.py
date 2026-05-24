from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from brain.memory_sync import (
    build_memory_write_plan,
    format_memory_decision_view,
    format_memory_sync_suggestion,
    suggest_memory_sync,
)
from orchestration.task_classifier import classify_task


class MemorySyncSuggestionTests(TestCase):
    def test_reusable_lesson_suggests_ai_brain(self) -> None:
        task = "fix telemetry bug"
        result = suggest_memory_sync(
            task,
            classify_task(task),
            planner_summary="Root cause pattern found in telemetry retry workflow.",
        )

        self.assertEqual(result["destination"], "ai_brain")
        self.assertEqual(result["suggested_entry_type"], "bugfix")
        self.assertTrue(result["approval_required"])

    def test_project_specific_risk_suggests_project_docs(self) -> None:
        task = "review deploy config"
        result = suggest_memory_sync(
            task,
            classify_task(task),
            changed_files=["docs/risk-registry.md"],
            findings_or_risks=["Project risk around deploy rollback path."],
        )

        self.assertEqual(result["destination"], "project_docs")
        self.assertEqual(result["suggested_entry_type"], "risk")
        self.assertEqual(result["suggested_target"], "docs/risk-registry.md")

    def test_mixed_reusable_and_project_specific_suggests_both(self) -> None:
        task = "fix auth bug"
        result = suggest_memory_sync(
            task,
            classify_task(task),
            planner_summary="Reusable guardrail decision for auth failures.",
            changed_files=["src/auth/service.py"],
            findings_or_risks=["Project-specific risk in auth module path."],
        )

        self.assertEqual(result["destination"], "both")
        self.assertTrue(result["approval_required"])

    def test_trivial_task_suggests_none(self) -> None:
        task = "update README documentation guide"
        result = suggest_memory_sync(
            task,
            classify_task(task),
        )

        self.assertEqual(result["destination"], "none")
        self.assertEqual(result["suggested_entry_type"], "none")
        self.assertFalse(result["approval_required"])

    def test_approval_required_when_destination_is_not_none(self) -> None:
        task = "refactor config loader"
        result = suggest_memory_sync(
            task,
            classify_task(task),
            planner_summary="Decision on reusable config boundary.",
        )

        self.assertNotEqual(result["destination"], "none")
        self.assertTrue(result["approval_required"])

    def test_formatted_output_contains_suggestion(self) -> None:
        task = "fix telemetry bug"
        result = suggest_memory_sync(
            task,
            classify_task(task),
            planner_summary="Root cause pattern found in telemetry retry workflow.",
        )
        output = format_memory_sync_suggestion(result)

        self.assertIn("Destination: ai_brain", output)
        self.assertIn("Suggested entry type: bugfix", output)

    def test_shared_decision_view_formats_suggestion(self) -> None:
        task = "fix telemetry bug"
        result = suggest_memory_sync(
            task,
            classify_task(task),
            planner_summary="Root cause pattern found in telemetry retry workflow.",
        )

        output = format_memory_decision_view(result)

        self.assertIn("Destination: ai_brain", output)
        self.assertIn("Reason:", output)
        self.assertIn("Suggested target:", output)
        self.assertIn("Approval required: yes", output)


class MemoryWritePlanTests(TestCase):
    def test_ai_brain_suggestion_creates_ai_brain_write_plan(self) -> None:
        task = "fix telemetry bug"
        suggestion = suggest_memory_sync(
            task,
            classify_task(task),
            planner_summary="Reusable bugfix lesson for telemetry retry handling.",
        )

        result = build_memory_write_plan(suggestion, task)

        self.assertTrue(result["can_write_plan"])
        self.assertEqual(result["destinations"], ["ai_brain"])
        self.assertTrue(str(result["proposed_ai_brain_target"]).startswith("07-Examples/"))
        self.assertIsNone(result["proposed_project_docs_target"])

    def test_project_docs_suggestion_creates_project_docs_write_plan(self) -> None:
        task = "review deploy config"
        suggestion = suggest_memory_sync(
            task,
            classify_task(task),
            changed_files=["docs/risk-registry.md"],
            findings_or_risks=["Project risk around deploy rollback path."],
        )

        result = build_memory_write_plan(
            suggestion,
            task,
            project_path="/tmp/project",
        )

        self.assertTrue(result["can_write_plan"])
        self.assertEqual(result["destinations"], ["project_docs"])
        self.assertEqual(result["proposed_project_docs_target"], "docs/risk-registry.md")
        self.assertIsNone(result["proposed_ai_brain_target"])

    def test_both_suggestion_creates_both_targets(self) -> None:
        task = "fix auth bug"
        suggestion = suggest_memory_sync(
            task,
            classify_task(task),
            planner_summary="Reusable auth guardrail decision.",
            changed_files=["src/auth/service.py"],
            findings_or_risks=["Project-specific risk in auth module path."],
        )

        result = build_memory_write_plan(
            suggestion,
            task,
            project_path="/tmp/project",
        )

        self.assertTrue(result["can_write_plan"])
        self.assertEqual(result["destinations"], ["ai_brain", "project_docs"])
        self.assertIsNotNone(result["proposed_ai_brain_target"])
        self.assertIsNotNone(result["proposed_project_docs_target"])

    def test_none_suggestion_creates_no_write_plan(self) -> None:
        task = "update README documentation guide"
        suggestion = suggest_memory_sync(task, classify_task(task))

        result = build_memory_write_plan(suggestion, task)

        self.assertFalse(result["can_write_plan"])
        self.assertEqual(result["destinations"], [])
        self.assertIsNone(result["proposed_ai_brain_target"])
        self.assertIsNone(result["proposed_project_docs_target"])
        self.assertFalse(result["approval_required"])

    def test_approval_required_true_when_write_plan_exists(self) -> None:
        task = "refactor config loader"
        suggestion = suggest_memory_sync(
            task,
            classify_task(task),
            planner_summary="Reusable decision on config boundary.",
        )

        result = build_memory_write_plan(suggestion, task)

        self.assertTrue(result["can_write_plan"])
        self.assertTrue(result["approval_required"])

    def test_decision_view_with_none_destination_shows_no_write_plan(self) -> None:
        task = "update README documentation guide"
        suggestion = suggest_memory_sync(task, classify_task(task))
        write_plan = build_memory_write_plan(suggestion, task)

        output = format_memory_decision_view(suggestion, write_plan)

        self.assertIn("Destination: none", output)
        self.assertIn("Can write plan: no", output)
        self.assertIn("Write plan destinations: none", output)
        self.assertIn("Write plan approval required: no", output)
        self.assertIn("Next command hint: No write command suggested.", output)


class MemorySyncCliTests(TestCase):
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

    def test_cli_prints_suggestion(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--task", "fix telemetry bug", "--memory-suggest"])

        output = stdout.getvalue()

        self.assertIn("Destination:", output)
        self.assertIn("Suggested target:", output)
        self.assertIn("Approval required:", output)
        self.assertNotIn("Can write plan:", output)

    def test_cli_prints_memory_plan_without_writing_files(self) -> None:
        stdout = StringIO()
        docs_target = self.project_root / "docs" / "risk-registry.md"
        ai_brain_target = self.project_root / "07-Examples"

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--project",
                            str(self.project_root),
                            "--task",
                            "review deploy config",
                            "--memory-plan",
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn("Destination:", output)
        self.assertIn("Suggested target:", output)
        self.assertIn("Suggested entry type:", output)
        self.assertIn("Can write plan:", output)
        self.assertIn("Write plan destinations:", output)
        self.assertIn("Proposed AI-Brain target:", output)
        self.assertIn("Approval required:", output)
        self.assertIn("Write plan approval required: yes", output)
        self.assertIn("<content-to-review>", output)
        self.assertFalse(docs_target.exists())
        self.assertFalse(ai_brain_target.exists())
