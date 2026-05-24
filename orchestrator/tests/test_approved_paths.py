from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from core.approved_paths import ApprovedPathError, ensure_approved_path


class ApprovedPathsTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.inside_path = self.approved_root / "project"
        self.inside_path.mkdir()
        self.outside_path = self.root / "outside"
        self.outside_path.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_target_inside_approved_path_is_allowed(self) -> None:
        resolved_path = ensure_approved_path(self.inside_path, [str(self.approved_root)])

        self.assertEqual(resolved_path, self.inside_path.resolve())

    def test_target_equal_to_approved_path_is_allowed(self) -> None:
        resolved_path = ensure_approved_path(self.approved_root, [str(self.approved_root)])

        self.assertEqual(resolved_path, self.approved_root.resolve())

    def test_target_outside_approved_path_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ApprovedPathError,
            "Target path is outside approved paths:",
        ):
            ensure_approved_path(self.outside_path, [str(self.approved_root)])

    def test_missing_or_empty_approved_paths_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ApprovedPathError,
            "Approved paths are missing from configuration.",
        ):
            ensure_approved_path(self.inside_path, None)

        with self.assertRaisesRegex(
            ApprovedPathError,
            "Approved paths are empty.",
        ):
            ensure_approved_path(self.inside_path, [])

    def test_symlink_and_traversal_style_cases_are_handled_safely(self) -> None:
        symlink_path = self.approved_root / "escape-link"
        symlink_path.symlink_to(self.outside_path, target_is_directory=True)

        with self.assertRaisesRegex(
            ApprovedPathError,
            "Target path is outside approved paths:",
        ):
            ensure_approved_path(symlink_path, [str(self.approved_root)])

        traversal_path = self.approved_root / ".." / "outside"
        with self.assertRaisesRegex(
            ApprovedPathError,
            "Target path is outside approved paths:",
        ):
            ensure_approved_path(traversal_path, [str(self.approved_root)])
