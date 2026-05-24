from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from brain.ai_brain_reader import (
    AIBrainReaderError,
    REQUIRED_CORE_FILES,
    inspect_required_core_files,
    read_note,
    read_required_core_files,
)


class AIBrainReaderTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.ai_brain_root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_required_core_files(self) -> dict[str, str]:
        expected_contents = {
            "core_rules": "core rules content",
            "readme_for_ai": "readme for ai content",
            "priority_tiers": "priority tiers content",
            "context_budget_rules": "context budget content",
        }

        for logical_name, relative_path in REQUIRED_CORE_FILES.items():
            file_path = self.ai_brain_root / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(expected_contents[logical_name], encoding="utf-8")

        return expected_contents

    def test_reads_required_core_files_with_logical_names(self) -> None:
        expected_contents = self.write_required_core_files()

        loaded_files = read_required_core_files(self.ai_brain_root)

        self.assertEqual(loaded_files, expected_contents)

    def test_read_note_reads_valid_relative_file(self) -> None:
        note_path = self.ai_brain_root / "notes" / "sample.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text("sample note", encoding="utf-8")

        content = read_note(self.ai_brain_root, "notes/sample.md")

        self.assertEqual(content, "sample note")

    def test_read_note_rejects_absolute_path(self) -> None:
        with self.assertRaisesRegex(
            AIBrainReaderError,
            "AI-Brain path must be relative:",
        ):
            read_note(self.ai_brain_root, "/etc/passwd")

    def test_read_note_rejects_escape_path(self) -> None:
        with self.assertRaisesRegex(
            AIBrainReaderError,
            "AI-Brain path escapes configured root:",
        ):
            read_note(self.ai_brain_root, "../outside.md")

    def test_read_note_reports_missing_safe_relative_file_clearly(self) -> None:
        with self.assertRaisesRegex(
            AIBrainReaderError,
            "AI-Brain note not found:",
        ) as context:
            read_note(self.ai_brain_root, "notes/missing.md")

        self.assertIn("notes/missing.md", str(context.exception))

    def test_missing_required_files_are_reported_clearly(self) -> None:
        file_path = self.ai_brain_root / REQUIRED_CORE_FILES["core_rules"]
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("core rules content", encoding="utf-8")

        with self.assertRaisesRegex(
            AIBrainReaderError,
            "Missing required AI-Brain core files:",
        ) as context:
            read_required_core_files(self.ai_brain_root)

        message = str(context.exception)
        self.assertIn("readme_for_ai:", message)
        self.assertIn("priority_tiers:", message)
        self.assertIn("context_budget_rules:", message)

    def test_reader_does_not_scan_the_whole_vault(self) -> None:
        self.write_required_core_files()
        extra_directory = self.ai_brain_root / "deep" / "nested" / "folder"
        extra_directory.mkdir(parents=True, exist_ok=True)
        (extra_directory / "ignored.md").write_text("ignored", encoding="utf-8")

        with patch("brain.ai_brain_reader.Path.glob", side_effect=AssertionError("no glob")):
            with patch("brain.ai_brain_reader.Path.rglob", side_effect=AssertionError("no rglob")):
                loaded_files = read_required_core_files(self.ai_brain_root)

        self.assertEqual(set(loaded_files), set(REQUIRED_CORE_FILES))

    def test_inspect_required_core_files_reports_found_and_missing_counts(self) -> None:
        self.write_required_core_files()
        (self.ai_brain_root / REQUIRED_CORE_FILES["context_budget_rules"]).unlink()

        status = inspect_required_core_files(self.ai_brain_root)

        self.assertEqual(status["checked_count"], 4)
        self.assertEqual(status["found_count"], 3)
        self.assertEqual(status["missing_count"], 1)
        self.assertIn("context_budget_rules", status["missing_files"])
