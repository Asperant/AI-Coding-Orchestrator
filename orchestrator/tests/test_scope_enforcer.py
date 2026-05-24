from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from tools.scope_enforcer import enforce_changed_file_scope, format_scope_enforcement_result


class ScopeEnforcerTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.project_root = self.root / "project"
        self.project_root.mkdir()
        (self.project_root / "src" / "nested").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_allowed_changed_file_passes(self) -> None:
        result = enforce_changed_file_scope(
            self.project_root,
            ["src/module.py"],
            ["src/module.py"],
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["violations"], ["none"])

    def test_extra_changed_file_outside_allowed_files_fails(self) -> None:
        result = enforce_changed_file_scope(
            self.project_root,
            ["src/module.py"],
            ["src/module.py", "README.md"],
        )

        self.assertFalse(result["passed"])
        self.assertIn("outside the explicitly allowed scope", " ".join(result["violations"]))

    def test_nested_allowed_file_passes(self) -> None:
        result = enforce_changed_file_scope(
            self.project_root,
            ["src/nested/module.py"],
            ["src/nested/module.py"],
        )

        self.assertTrue(result["passed"])

    def test_path_traversal_changed_file_fails_safely(self) -> None:
        result = enforce_changed_file_scope(
            self.project_root,
            ["src/module.py"],
            ["../outside.py"],
        )

        self.assertFalse(result["passed"])
        self.assertIn("outside the approved project scope", " ".join(result["violations"]))

    def test_formatter_includes_scope_fields(self) -> None:
        formatted = format_scope_enforcement_result(
            {
                "passed": False,
                "violations": ["scope violation"],
                "allowed_files": ["/tmp/project/src/module.py"],
                "changed_files": ["/tmp/project/README.md"],
                "message": "Scope enforcement detected changes outside the explicitly allowed files.",
            }
        )

        self.assertIn("Passed: no", formatted)
        self.assertIn("Violations: scope violation", formatted)
