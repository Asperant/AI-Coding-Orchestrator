from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from brain.ai_brain_writer import AIBrainWriterError, write_ai_brain_memory


class AIBrainWriterTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.ai_brain_root = Path(self.temp_dir.name)
        (self.ai_brain_root / "02-Code").mkdir()
        (self.ai_brain_root / "05-Agents").mkdir()
        (self.ai_brain_root / "06-Decisions").mkdir()
        (self.ai_brain_root / "07-Examples").mkdir()
        (self.ai_brain_root / "CORE-RULES.md").write_text("core", encoding="utf-8")
        (self.ai_brain_root / "README-FOR-AI.md").write_text("readme", encoding="utf-8")
        (self.ai_brain_root / "Home.md").write_text("home", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_lesson_append_with_approval_works(self) -> None:
        result = write_ai_brain_memory(
            self.ai_brain_root,
            "lesson",
            None,
            "Lesson entry\n",
            approval_confirmed=True,
            mode="append",
        )

        target_path = self.ai_brain_root / "02-Code" / "Lessons-Learned.md"
        self.assertTrue(result["written"])
        self.assertEqual(result["action"], "append")
        self.assertEqual(target_path.read_text(encoding="utf-8"), "Lesson entry\n")

    def test_decision_create_with_approval_works(self) -> None:
        result = write_ai_brain_memory(
            self.ai_brain_root,
            "decision",
            "decision-example.md",
            "# Decision\n",
            approval_confirmed=True,
            mode="create",
        )

        target_path = self.ai_brain_root / "06-Decisions" / "decision-example.md"
        self.assertTrue(result["written"])
        self.assertEqual(result["action"], "create")
        self.assertEqual(target_path.read_text(encoding="utf-8"), "# Decision\n")

    def test_no_approval_blocks(self) -> None:
        result = write_ai_brain_memory(
            self.ai_brain_root,
            "lesson",
            None,
            "Lesson entry\n",
            approval_confirmed=False,
            mode="append",
        )

        self.assertFalse(result["written"])
        self.assertIn("requires explicit approval confirmation", result["message"])

    def test_core_rules_write_blocks(self) -> None:
        with self.assertRaisesRegex(
            AIBrainWriterError,
            "AI-Brain write target is blocked: CORE-RULES.md",
        ):
            write_ai_brain_memory(
                self.ai_brain_root,
                "decision",
                "../CORE-RULES.md",
                "# Decision\n",
                approval_confirmed=True,
                mode="create",
            )

    def test_agents_write_blocks(self) -> None:
        with self.assertRaisesRegex(
            AIBrainWriterError,
            "AI-Brain write target is blocked: 05-Agents/agent-note.md",
        ):
            write_ai_brain_memory(
                self.ai_brain_root,
                "decision",
                "../05-Agents/agent-note.md",
                "# Decision\n",
                approval_confirmed=True,
                mode="create",
            )

    def test_traversal_blocks(self) -> None:
        with self.assertRaisesRegex(
            AIBrainWriterError,
            "AI-Brain write target escapes configured root:",
        ):
            write_ai_brain_memory(
                self.ai_brain_root,
                "decision",
                "../../../outside.md",
                "# Decision\n",
                approval_confirmed=True,
                mode="create",
            )

    def test_existing_decision_create_blocks(self) -> None:
        target_path = self.ai_brain_root / "06-Decisions" / "decision-example.md"
        target_path.write_text("old", encoding="utf-8")

        result = write_ai_brain_memory(
            self.ai_brain_root,
            "decision",
            "decision-example.md",
            "# Decision\n",
            approval_confirmed=True,
            mode="create",
        )

        self.assertFalse(result["written"])
        self.assertIn("Create mode will not overwrite an existing AI-Brain file", result["message"])
        self.assertEqual(target_path.read_text(encoding="utf-8"), "old")

    def test_secret_like_content_blocks_and_does_not_write(self) -> None:
        raw_secret = "super-secret-value-987654321"
        result = write_ai_brain_memory(
            self.ai_brain_root,
            "decision",
            "decision-example.md",
            f'API_TOKEN="{raw_secret}"',
            approval_confirmed=True,
            mode="create",
        )

        target_path = self.ai_brain_root / "06-Decisions" / "decision-example.md"
        self.assertFalse(result["written"])
        self.assertIn("AI-Brain write blocked because secret-like content was detected.", result["message"])
        self.assertFalse(target_path.exists())


class AIBrainWriterCliTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.ai_brain_root = Path(self.temp_dir.name)
        (self.ai_brain_root / "02-Code").mkdir()
        (self.ai_brain_root / "05-Agents").mkdir()
        (self.ai_brain_root / "06-Decisions").mkdir()
        (self.ai_brain_root / "07-Examples").mkdir()
        self.fake_config = {
            "ai_brain_path": str(self.ai_brain_root),
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": [str(self.ai_brain_root)],
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cli_happy_path(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files") as mocked_core:
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--write-ai-brain",
                            "--memory-type",
                            "decision",
                            "--memory-path",
                            "decision-example.md",
                            "--content",
                            "# Decision\n",
                            "--confirm-write",
                        ]
                    )

        output = stdout.getvalue()
        target_path = self.ai_brain_root / "06-Decisions" / "decision-example.md"

        self.assertIn("AI-Brain write action: create", output)
        self.assertTrue(target_path.exists())
        mocked_core.assert_not_called()

    def test_cli_no_approval_path(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with self.assertRaisesRegex(
                SystemExit,
                "AI-Brain writer error: AI-Brain write requires explicit approval confirmation.",
            ):
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--write-ai-brain",
                            "--memory-type",
                            "decision",
                            "--memory-path",
                            "decision-example.md",
                            "--content",
                            "# Decision\n",
                        ]
                    )
