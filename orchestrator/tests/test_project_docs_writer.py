from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from project.project_docs_writer import ProjectDocsWriterError, write_project_doc


class ProjectDocsWriterTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.project_root = self.approved_root / "project"
        self.project_root.mkdir()
        (self.project_root / "docs").mkdir()
        self.approved_paths = [str(self.approved_root)]

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_create_doc_with_approval_works(self) -> None:
        result = write_project_doc(
            self.project_root,
            "docs/decisions/example.md",
            "# Decision\n",
            self.approved_paths,
            approval_confirmed=True,
            mode="create",
        )

        target_path = self.project_root / "docs" / "decisions" / "example.md"
        self.assertTrue(result["written"])
        self.assertEqual(result["action"], "create")
        self.assertEqual(target_path.read_text(encoding="utf-8"), "# Decision\n")

    def test_append_doc_with_approval_works(self) -> None:
        target_path = self.project_root / "docs" / "risk-registry.md"
        target_path.write_text("Line 1\n", encoding="utf-8")

        result = write_project_doc(
            self.project_root,
            "docs/risk-registry.md",
            "Line 2\n",
            self.approved_paths,
            approval_confirmed=True,
            mode="append",
        )

        self.assertTrue(result["written"])
        self.assertEqual(result["action"], "append")
        self.assertEqual(target_path.read_text(encoding="utf-8"), "Line 1\nLine 2\n")

    def test_no_approval_blocks(self) -> None:
        result = write_project_doc(
            self.project_root,
            "docs/decisions/example.md",
            "# Decision\n",
            self.approved_paths,
            approval_confirmed=False,
            mode="create",
        )

        self.assertFalse(result["written"])
        self.assertIn("requires explicit approval confirmation", result["message"])

    def test_outside_docs_path_blocks(self) -> None:
        with self.assertRaisesRegex(
            ProjectDocsWriterError,
            "Project docs path must stay under project docs/:",
        ):
            write_project_doc(
                self.project_root,
                "README.md",
                "text",
                self.approved_paths,
                approval_confirmed=True,
                mode="create",
            )

    def test_traversal_blocks(self) -> None:
        with self.assertRaisesRegex(
            ProjectDocsWriterError,
            "Project docs path must stay under project docs/:",
        ):
            write_project_doc(
                self.project_root,
                "docs/../secrets.txt",
                "text",
                self.approved_paths,
                approval_confirmed=True,
                mode="create",
            )

    def test_existing_file_in_create_mode_blocks(self) -> None:
        target_path = self.project_root / "docs" / "risk-registry.md"
        target_path.write_text("Line 1\n", encoding="utf-8")

        result = write_project_doc(
            self.project_root,
            "docs/risk-registry.md",
            "Line 2\n",
            self.approved_paths,
            approval_confirmed=True,
            mode="create",
        )

        self.assertFalse(result["written"])
        self.assertIn("Create mode will not overwrite an existing file", result["message"])
        self.assertEqual(target_path.read_text(encoding="utf-8"), "Line 1\n")

    def test_secret_like_content_blocks_and_does_not_write(self) -> None:
        raw_secret = "super-secret-value-987654321"
        result = write_project_doc(
            self.project_root,
            "docs/decisions/example.md",
            f'API_TOKEN="{raw_secret}"',
            self.approved_paths,
            approval_confirmed=True,
            mode="create",
        )

        target_path = self.project_root / "docs" / "decisions" / "example.md"
        self.assertFalse(result["written"])
        self.assertIn("Project docs write blocked because secret-like content was detected.", result["message"])
        self.assertFalse(target_path.exists())

    def test_unapproved_project_path_blocks(self) -> None:
        outside_project = self.root / "outside-project"
        outside_project.mkdir()
        (outside_project / "docs").mkdir()

        with self.assertRaisesRegex(
            ProjectDocsWriterError,
            "Target path is outside approved paths:",
        ):
            write_project_doc(
                outside_project,
                "docs/decisions/example.md",
                "# Decision\n",
                self.approved_paths,
                approval_confirmed=True,
                mode="create",
            )


class ProjectDocsWriterCliTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.project_root = self.root / "project"
        self.project_root.mkdir()
        (self.project_root / "docs").mkdir()
        self.fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": [str(self.project_root)],
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
                            "--project",
                            str(self.project_root),
                            "--write-project-doc",
                            "docs/decisions/example.md",
                            "--content",
                            "# Decision\n",
                            "--confirm-write",
                        ]
                    )

        output = stdout.getvalue()
        target_path = self.project_root / "docs" / "decisions" / "example.md"

        self.assertIn("Project docs write action: create", output)
        self.assertTrue(target_path.exists())
        mocked_core.assert_not_called()

    def test_cli_no_approval_path(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with self.assertRaisesRegex(
                SystemExit,
                "Project docs writer error: Project docs write requires explicit approval confirmation.",
            ):
                with redirect_stdout(stdout):
                    cli.run(
                        [
                            "--project",
                            str(self.project_root),
                            "--write-project-doc",
                            "docs/decisions/example.md",
                            "--content",
                            "# Decision\n",
                        ]
                    )
