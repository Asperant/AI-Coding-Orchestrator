from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from brain.memory_sync import format_memory_decision_view
from orchestration.approval_gate_manager import format_approval_gate_view
from orchestration.planner_report import format_planner_report, generate_planner_report
from orchestration.task_classifier import classify_task


class PlannerReportTests(TestCase):
    def setUp(self) -> None:
        self.ai_brain_core_status = {
            "checked_count": 4,
            "found_count": 4,
            "missing_count": 0,
            "missing_files": {},
        }

    def test_planner_report_for_bug_fix(self) -> None:
        classification = classify_task("fix telemetry bug")

        report = generate_planner_report(
            "fix telemetry bug",
            classification,
            ai_brain_core_summary=self.ai_brain_core_status,
        )

        self.assertEqual(report["task_type"], "bug fix")
        self.assertEqual(report["risk_level"], "medium")
        self.assertIn("Reproduce the current failure", report["suggested_tests"][0])
        self.assertIn("Reproduce the bug", report["smallest_safe_next_action"])
        self.assertEqual(report["memory_docs_update_suggestion"]["destination"], "ai_brain")

    def test_planner_report_for_feature(self) -> None:
        classification = classify_task("add a feature to export reports")

        report = generate_planner_report("add a feature to export reports", classification)

        self.assertEqual(report["task_type"], "feature")
        self.assertIn("happy path", " ".join(report["suggested_tests"]))

    def test_planner_report_for_documentation_task(self) -> None:
        classification = classify_task("update README documentation guide")

        report = generate_planner_report("update README documentation guide", classification)

        self.assertEqual(report["task_type"], "documentation change")
        self.assertIn("README and docs directory", report["likely_files_or_areas_to_inspect"])
        self.assertFalse(report["approval_gate"]["approval_required"])
        self.assertEqual(report["memory_docs_update_suggestion"]["destination"], "none")

    def test_planner_report_for_project_assessment_is_useful(self) -> None:
        classification = classify_task("review this project and suggest the safest next coding task")
        project_context = {
            "working_directory": "/tmp/project",
            "found_files": ["AGENTS.md"],
            "missing_files": ["docs/project-map.md", "docs/test-scenarios.md"],
            "project_docs_count": 1,
        }

        report = generate_planner_report(
            "review this project and suggest the safest next coding task",
            classification,
            project_context=project_context,
        )

        self.assertEqual(report["task_type"], "project assessment")
        self.assertIn("AGENTS.md", report["relevant_project_docs_found"])
        self.assertIn("docs/project-map.md", report["missing_ai_ready_files"])
        self.assertIn("project AI-ready docs and AGENTS.md", report["likely_files_or_areas_to_inspect"])
        self.assertIn("safest next coding task", report["smallest_safe_next_action"])
        self.assertFalse(report["approval_gate"]["approval_required"])

    def test_planner_report_for_high_risk_security_database_task(self) -> None:
        classification = classify_task("review auth token database migration")

        report = generate_planner_report(
            "review auth token database migration",
            classification,
            ai_brain_core_summary={
                "checked_count": 4,
                "found_count": 2,
                "missing_count": 2,
                "missing_files": {"core_rules": "/tmp/core", "readme_for_ai": "/tmp/readme"},
            },
        )

        self.assertEqual(report["task_type"], "security/privacy change")
        self.assertEqual(report["risk_level"], "high")
        self.assertIn("AI-Brain core guidance is incomplete locally", " ".join(report["risks"]))
        self.assertTrue(report["approval_gate"]["approval_required"])

    def test_planner_report_with_project_context(self) -> None:
        classification = classify_task("fix telemetry bug")
        project_context = {
            "working_directory": "/tmp/project",
            "found_files": ["AGENTS.md", "docs/architecture.md"],
            "missing_files": ["docs/project-map.md"],
            "project_docs_count": 2,
        }

        report = generate_planner_report(
            "fix telemetry bug",
            classification,
            project_context=project_context,
        )

        self.assertEqual(report["relevant_project_docs_found"], ["AGENTS.md", "docs/architecture.md"])
        self.assertEqual(report["missing_ai_ready_files"], ["docs/project-map.md"])
        self.assertIn("AGENTS.md", report["likely_files_or_areas_to_inspect"])

    def test_planner_report_without_project_context(self) -> None:
        classification = classify_task("fix telemetry bug")

        report = generate_planner_report("fix telemetry bug", classification)

        self.assertEqual(report["relevant_project_docs_found"], ["Project context was not provided."])
        self.assertEqual(report["missing_ai_ready_files"], ["Project context was not provided."])

    def test_ambiguous_unknown_task_produces_safe_output(self) -> None:
        classification = classify_task("maybe help somehow")

        report = generate_planner_report("maybe help somehow", classification)

        self.assertEqual(report["task_type"], "unknown")
        self.assertEqual(report["confidence"], "low")
        self.assertEqual(report["likely_files_or_areas_to_inspect"], ["unknown"])
        self.assertIn("Clarify the task goal", report["smallest_safe_next_action"])

    def test_formatted_planner_report_contains_required_sections(self) -> None:
        classification = classify_task("fix telemetry bug")
        report = generate_planner_report("fix telemetry bug", classification)

        output = format_planner_report(report)

        self.assertIn("Summary:", output)
        self.assertIn("Task type:", output)
        self.assertIn("Smallest safe next action:", output)
        self.assertIn("Approval Gate:", output)
        self.assertIn("Knowledge Update Proposal:", output)
        self.assertIn("Memory/docs update suggestion:", output)
        self.assertIn("Destination:", output)

    def test_security_auth_planner_report_shows_approval_required(self) -> None:
        classification = classify_task("fix auth bug")
        report = generate_planner_report("fix auth bug", classification)
        output = format_planner_report(report)

        self.assertTrue(report["approval_gate"]["approval_required"])
        self.assertIn("Approval Gate: Approval required: yes", output)
        self.assertIn(
            format_approval_gate_view(report["approval_gate"]),
            output,
        )

    def test_normal_documentation_planner_report_shows_no_approval_required(self) -> None:
        classification = classify_task("update README documentation guide")
        report = generate_planner_report("update README documentation guide", classification)
        output = format_planner_report(report)

        self.assertFalse(report["approval_gate"]["approval_required"])
        self.assertIn("Approval Gate: Approval required: no", output)
        self.assertIn(
            format_approval_gate_view(report["approval_gate"]),
            output,
        )

    def test_project_assessment_planner_report_shows_no_approval_required(self) -> None:
        classification = classify_task("onboard this repo")
        report = generate_planner_report("onboard this repo", classification)

        self.assertEqual(report["task_type"], "project assessment")
        self.assertFalse(report["approval_gate"]["approval_required"])

    def test_planner_report_includes_memory_sync_destination(self) -> None:
        classification = classify_task("fix telemetry bug")
        report = generate_planner_report("fix telemetry bug", classification)
        output = format_planner_report(report)

        self.assertEqual(report["memory_docs_update_suggestion"]["destination"], "ai_brain")
        self.assertIn("Memory/docs update suggestion: Destination: ai_brain", output)
        self.assertIn("Reason:", output)
        self.assertIn("Suggested target:", output)
        self.assertIn("Suggested entry type:", output)
        self.assertIn(
            format_memory_decision_view(report["memory_docs_update_suggestion"]),
            output,
        )

    def test_trivial_task_can_suggest_none(self) -> None:
        classification = classify_task("update README documentation guide")
        report = generate_planner_report("update README documentation guide", classification)

        self.assertEqual(report["memory_docs_update_suggestion"]["destination"], "none")

    def test_memory_section_matches_shared_formatter(self) -> None:
        classification = classify_task("fix telemetry bug")
        report = generate_planner_report("fix telemetry bug", classification)
        output = format_planner_report(report)

        expected_section = (
            "Memory/docs update suggestion: "
            f"{format_memory_decision_view(report['memory_docs_update_suggestion'])}"
        )

        self.assertIn(expected_section, output)

    def test_approval_section_matches_shared_formatter(self) -> None:
        classification = classify_task("fix auth bug")
        report = generate_planner_report("fix auth bug", classification)
        output = format_planner_report(report)

        expected_section = (
            "Approval Gate: "
            f"{format_approval_gate_view(report['approval_gate'])}"
        )

        self.assertIn(expected_section, output)


class PlannerReportCliTests(TestCase):
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

    def create_project_file(self, relative_path: str) -> None:
        file_path = self.project_root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("content", encoding="utf-8")

    def test_cli_task_and_plan_prints_planner_sections(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files", return_value=self.fake_core_status):
                with redirect_stdout(stdout):
                    cli.run(["--task", "fix telemetry bug", "--plan"])

        output = stdout.getvalue()

        self.assertIn("Summary:", output)
        self.assertIn("Task type: bug fix", output)
        self.assertIn("Project context check: not run by default", output)
        self.assertIn("Smallest safe next action:", output)
        self.assertIn("Memory/docs update suggestion: Destination:", output)
        self.assertIn("Suggested target:", output)

    def test_cli_project_task_and_plan_includes_project_context_details(self) -> None:
        self.create_project_file("AGENTS.md")
        self.create_project_file("docs/architecture.md")
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
                            "--plan",
                        ]
                    )

        output = stdout.getvalue()

        self.assertIn(f"Project working directory: {self.project_root.resolve()}", output)
        self.assertIn("Found AI-ready files count: 2", output)
        self.assertIn("Relevant project docs found: AGENTS.md; docs/architecture.md", output)
        self.assertIn("Missing AI-ready files:", output)

    def test_cli_plan_without_task_gives_clear_error(self) -> None:
        with self.assertRaisesRegex(
            SystemExit,
            "Planner report error: --plan requires --task.",
        ):
            cli.run(["--plan"])
