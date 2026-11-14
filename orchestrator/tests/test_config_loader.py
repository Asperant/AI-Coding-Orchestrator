from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from core import config_loader


class LoadConfigTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.default_config_path = self.root / "default.yaml"
        self.approved_paths_config_path = self.root / "approved_paths.yaml"
        self.ai_brain_path = self.root / "ai-brain"
        self.ai_brain_path.mkdir()

        self.default_path_patch = patch.object(
            config_loader, "DEFAULT_CONFIG_PATH", self.default_config_path
        )
        self.approved_paths_patch = patch.object(
            config_loader, "APPROVED_PATHS_CONFIG_PATH", self.approved_paths_config_path
        )
        self.default_local_path_patch = patch.object(
            config_loader, "DEFAULT_LOCAL_CONFIG_PATH", self.root / "default.local.yaml"
        )
        self.approved_paths_local_patch = patch.object(
            config_loader, "APPROVED_PATHS_LOCAL_CONFIG_PATH", self.root / "approved_paths.local.yaml"
        )

        self.default_path_patch.start()
        self.approved_paths_patch.start()
        self.default_local_path_patch.start()
        self.approved_paths_local_patch.start()

    def tearDown(self) -> None:
        self.default_path_patch.stop()
        self.approved_paths_patch.stop()
        self.default_local_path_patch.stop()
        self.approved_paths_local_patch.stop()
        self.temp_dir.cleanup()

    def write_default_config(self, ai_brain_path: str | Path | None) -> None:
        lines = [
            f"reports_dir: {self.root / 'reports'}",
            "phase: 1",
            "read_only: true",
        ]
        if ai_brain_path is not None:
            lines.insert(0, f"ai_brain_path: {ai_brain_path}")

        self.default_config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def write_approved_paths_config(self, content: str) -> None:
        self.approved_paths_config_path.write_text(content, encoding="utf-8")

    def write_valid_config_files(self) -> None:
        self.write_default_config(self.ai_brain_path)
        self.write_approved_paths_config(
            f"approved_paths:\n  - {self.ai_brain_path}\n  - {self.root / 'reports'}\n"
        )

    def test_loads_default_config_successfully(self) -> None:
        self.write_valid_config_files()

        loaded_config = config_loader.load_config()

        self.assertEqual(loaded_config["ai_brain_path"], str(self.ai_brain_path.resolve()))
        self.assertEqual(loaded_config["reports_dir"], str(self.root / "reports"))
        self.assertEqual(loaded_config["phase"], 1)
        self.assertTrue(loaded_config["read_only"])

    def test_loads_approved_paths_successfully(self) -> None:
        self.write_valid_config_files()

        loaded_config = config_loader.load_config()

        self.assertEqual(
            loaded_config["approved_paths"],
            [str(self.ai_brain_path), str(self.root / "reports")],
        )

    def test_ai_brain_path_env_override_works(self) -> None:
        override_path = self.root / "override-ai-brain"
        override_path.mkdir()
        self.write_valid_config_files()

        with patch.dict("os.environ", {"AI_BRAIN_PATH": str(override_path)}, clear=False):
            loaded_config = config_loader.load_config()

        self.assertEqual(loaded_config["ai_brain_path"], str(override_path.resolve()))

    def test_missing_config_file_raises_clear_config_error(self) -> None:
        self.write_approved_paths_config(f"approved_paths:\n  - {self.ai_brain_path}\n")

        with self.assertRaisesRegex(
            config_loader.ConfigError,
            f"Missing config file: {self.default_config_path}",
        ):
            config_loader.load_config()

    def test_missing_ai_brain_path_raises_clear_config_error(self) -> None:
        self.write_default_config(None)
        self.write_approved_paths_config(f"approved_paths:\n  - {self.ai_brain_path}\n")

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(
                config_loader.ConfigError,
                "Missing ai_brain_path in config/default.yaml \\(or config/default.local.yaml\\) and AI_BRAIN_PATH is not set.",
            ):
                config_loader.load_config()

    def test_nonexistent_ai_brain_path_raises_clear_config_error(self) -> None:
        self.write_default_config(self.root / "missing-ai-brain")
        self.write_approved_paths_config(f"approved_paths:\n  - {self.ai_brain_path}\n")

        with self.assertRaisesRegex(
            config_loader.ConfigError,
            "Configured ai_brain_path does not exist:",
        ):
            config_loader.load_config()

    def test_approved_paths_not_list_raises_clear_config_error(self) -> None:
        self.write_default_config(self.ai_brain_path)
        self.write_approved_paths_config(f"approved_paths: {self.ai_brain_path}\n")

        with self.assertRaisesRegex(
            config_loader.ConfigError,
            "Config value approved_paths must be a list in config/approved_paths.yaml \\(or config/approved_paths.local.yaml\\).",
        ):
            config_loader.load_config()

    def test_relative_config_paths_are_resolved_from_project_root(self) -> None:
        relative_ai_brain = "ai-brain"
        self.write_default_config(relative_ai_brain)
        self.write_approved_paths_config("approved_paths:\n  - ai-brain\n  - reports\n")

        loaded_config = config_loader.load_config()

        self.assertEqual(loaded_config["ai_brain_path"], str(self.ai_brain_path.resolve()))
        self.assertEqual(
            loaded_config["approved_paths"],
            [str(self.ai_brain_path.resolve()), str((self.root / "reports").resolve())],
        )

    def test_local_override_config_files_take_precedence(self) -> None:
        default_local_config_path = self.root / "default.local.yaml"
        approved_paths_local_config_path = self.root / "approved_paths.local.yaml"
        override_ai_brain = self.root / "override-ai-brain"
        override_ai_brain.mkdir()

        self.write_default_config(self.ai_brain_path)
        self.write_approved_paths_config(f"approved_paths:\n  - {self.ai_brain_path}\n")

        default_local_config_path.write_text(
            "\n".join(
                [
                    f"ai_brain_path: {override_ai_brain}",
                    f"reports_dir: {self.root / 'reports'}",
                    "phase: 1",
                    "read_only: true",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        approved_paths_local_config_path.write_text(
            f"approved_paths:\n  - {override_ai_brain}\n",
            encoding="utf-8",
        )

        loaded_config = config_loader.load_config()

        self.assertEqual(loaded_config["ai_brain_path"], str(override_ai_brain.resolve()))
        self.assertEqual(loaded_config["approved_paths"], [str(override_ai_brain.resolve())])

    def test_approved_paths_empty_list_is_valid(self) -> None:
        self.write_default_config(self.ai_brain_path)
        self.write_approved_paths_config("approved_paths: []\n")

        loaded_config = config_loader.load_config()
        self.assertEqual(loaded_config["approved_paths"], [])

    def test_invalid_approved_paths_number_raises_config_error_without_value(self) -> None:
        self.write_default_config(self.ai_brain_path)
        secret_number = 12345
        self.write_approved_paths_config(
            f"approved_paths:\n  - {self.ai_brain_path}\n  - {secret_number}\n"
        )

        with self.assertRaises(config_loader.ConfigError) as ctx:
            config_loader.load_config()

        msg = str(ctx.exception)
        self.assertIn("Invalid approved_paths entry at index 2", msg)
        self.assertIn(str(self.approved_paths_config_path), msg)
        self.assertNotIn(str(secret_number), msg)

    def test_invalid_approved_paths_null_raises_config_error_without_value(self) -> None:
        self.write_default_config(self.ai_brain_path)
        self.write_approved_paths_config("approved_paths:\n  - null\n")

        with self.assertRaises(config_loader.ConfigError) as ctx:
            config_loader.load_config()

        msg = str(ctx.exception)
        self.assertIn("Invalid approved_paths entry at index 1", msg)
        self.assertIn(str(self.approved_paths_config_path), msg)
        self.assertNotIn("null", msg.lower())
        self.assertNotIn("none", msg.lower())

    def test_invalid_approved_paths_whitespace_raises_config_error_without_value(self) -> None:
        self.write_default_config(self.ai_brain_path)
        secret_whitespace = "   "
        self.write_approved_paths_config(f'approved_paths:\n  - "{secret_whitespace}"\n')

        with self.assertRaises(config_loader.ConfigError) as ctx:
            config_loader.load_config()

        msg = str(ctx.exception)
        self.assertIn("Invalid approved_paths entry at index 1", msg)
        self.assertIn(str(self.approved_paths_config_path), msg)

