from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from tools.filesystem_gateway import FilesystemGatewayError, read_file, write_file


class FilesystemGatewayTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.approved_file = self.approved_root / "notes.txt"
        self.approved_file.write_text("safe file content", encoding="utf-8")
        self.outside_root = self.root / "outside"
        self.outside_root.mkdir()
        self.outside_file = self.outside_root / "secret.txt"
        self.outside_file.write_text("outside content", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_approved_file_read_works(self) -> None:
        content = read_file(self.approved_file, [str(self.approved_root)])

        self.assertEqual(content, "safe file content")

    def test_outside_approved_path_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            FilesystemGatewayError,
            "Target path is outside approved paths:",
        ):
            read_file(self.outside_file, [str(self.approved_root)])

    def test_missing_file_gives_clear_error(self) -> None:
        missing_file = self.approved_root / "missing.txt"

        with self.assertRaisesRegex(
            FilesystemGatewayError,
            "File does not exist:",
        ):
            read_file(missing_file, [str(self.approved_root)])

    def test_directory_read_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            FilesystemGatewayError,
            "Expected a file but received a directory:",
        ):
            read_file(self.approved_root, [str(self.approved_root)])

    def test_write_attempt_is_blocked(self) -> None:
        with self.assertRaisesRegex(
            FilesystemGatewayError,
            "Write operations require explicit approval and are blocked in read-only mode.",
        ):
            write_file(self.approved_file, "new content", [str(self.approved_root)])

    def test_raw_path_traversal_style_attempt_is_rejected(self) -> None:
        traversal_path = self.approved_root / ".." / "outside" / "secret.txt"

        with self.assertRaisesRegex(
            FilesystemGatewayError,
            "Target path is outside approved paths:",
        ):
            read_file(traversal_path, [str(self.approved_root)])


class FilesystemGatewayCliTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.approved_file = self.approved_root / "notes.txt"
        self.approved_file.write_text("safe file content", encoding="utf-8")
        self.fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": [str(self.approved_root)],
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_read_file_cli_prints_file_content_when_approved(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files") as mocked_core:
                with redirect_stdout(stdout):
                    cli.run(["--read-file", str(self.approved_file)])

        output = stdout.getvalue()

        self.assertIn("safe file content", output)
        mocked_core.assert_not_called()

    def test_read_file_cli_blocks_secret_like_content(self) -> None:
        raw_secret = "super-secret-value-987654321"
        self.approved_file.write_text(f'API_TOKEN="{raw_secret}"', encoding="utf-8")
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "inspect_required_core_files") as mocked_core:
                with redirect_stdout(stdout):
                    cli.run(["--read-file", str(self.approved_file)])

        output = stdout.getvalue()

        self.assertIn(
            "File read output blocked because secret-like content was detected. Findings are redacted.",
            output,
        )
        self.assertIn("Finding: Detected token-style assignment", output)
        self.assertNotIn(raw_secret, output)
        self.assertNotIn('API_TOKEN="', output)
        mocked_core.assert_not_called()

    def test_read_file_cli_rejects_unapproved_path(self) -> None:
        stdout = StringIO()
        outside_file = self.root / "outside.txt"
        outside_file.write_text("outside content", encoding="utf-8")

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with self.assertRaisesRegex(
                SystemExit,
                "Filesystem gateway error: Target path is outside approved paths:",
            ):
                with redirect_stdout(stdout):
                    cli.run(["--read-file", str(outside_file)])
