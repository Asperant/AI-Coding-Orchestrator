from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from project.project_context_reader import (
    EXPECTED_PROJECT_CONTEXT_FILES,
    ProjectContextReaderError,
    inspect_project_context,
)


class ProjectContextReaderTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def create_file(self, relative_path: Path, content: str = "content") -> None:
        file_path = self.project_root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    def test_detects_found_and_missing_files(self) -> None:
        self.create_file(Path("AGENTS.md"))
        self.create_file(Path("docs") / "product-context.md")
        self.create_file(Path("docs") / "architecture.md")

        result = inspect_project_context(self.project_root)

        self.assertEqual(result["working_directory"], str(self.project_root.resolve()))
        self.assertIn("AGENTS.md", result["found_files"])
        self.assertIn("docs/product-context.md", result["found_files"])
        self.assertIn("docs/architecture.md", result["found_files"])
        self.assertIn("docs/project-map.md", result["missing_files"])
        self.assertEqual(result["project_docs_count"], 3)

    def test_works_with_partial_docs(self) -> None:
        self.create_file(Path("docs") / "risk-registry.md")

        result = inspect_project_context(self.project_root)

        self.assertEqual(result["found_files"], ["docs/risk-registry.md"])
        self.assertEqual(result["project_docs_count"], 1)
        self.assertEqual(
            set(result["missing_files"]),
            {path.as_posix() for path in EXPECTED_PROJECT_CONTEXT_FILES if path.as_posix() != "docs/risk-registry.md"},
        )

    def test_errors_if_working_directory_does_not_exist(self) -> None:
        missing_directory = self.project_root / "missing-project"

        with self.assertRaisesRegex(
            ProjectContextReaderError,
            "Working directory does not exist:",
        ):
            inspect_project_context(missing_directory)

    def test_errors_if_working_directory_is_a_file(self) -> None:
        file_path = self.project_root / "not-a-directory.txt"
        file_path.write_text("content", encoding="utf-8")

        with self.assertRaisesRegex(
            ProjectContextReaderError,
            "Working directory is not a directory:",
        ):
            inspect_project_context(file_path)

    def test_reader_does_not_scan_the_whole_repository(self) -> None:
        self.create_file(Path("AGENTS.md"))
        node_modules_path = self.project_root / "node_modules" / "big-package"
        node_modules_path.mkdir(parents=True, exist_ok=True)
        (node_modules_path / "ignored.txt").write_text("ignored", encoding="utf-8")

        with patch("project.project_context_reader.Path.glob", side_effect=AssertionError("no glob")):
            with patch("project.project_context_reader.Path.rglob", side_effect=AssertionError("no rglob")):
                result = inspect_project_context(self.project_root)

        self.assertIn("AGENTS.md", result["found_files"])
