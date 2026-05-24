from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import cli
from tools.project_knowledge_mcp import (
    format_project_knowledge_result,
    read_project_knowledge,
)


class ProjectKnowledgeMCPTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.project_root = self.approved_root / "project"
        self.project_root.mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_project_file(self, relative_path: str, content: str) -> None:
        file_path = self.project_root / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    def test_reads_existing_project_docs_safely(self) -> None:
        self._write_project_file("AGENTS.md", "Agent instructions")
        self._write_project_file("docs/architecture.md", "Architecture notes")

        result = read_project_knowledge(
            self.project_root,
            [str(self.approved_root)],
        )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertIn("AGENTS.md", result["found_files"])
        self.assertIn("docs/architecture.md", result["found_files"])
        self.assertGreaterEqual(len(result["context_blocks"]), 2)

    def test_missing_docs_are_reported_but_not_fatal(self) -> None:
        self._write_project_file("AGENTS.md", "Agent instructions")

        result = read_project_knowledge(
            self.project_root,
            [str(self.approved_root)],
        )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertIn("AGENTS.md", result["found_files"])
        self.assertIn("docs/product-context.md", result["missing_files"])

    def test_secret_like_doc_content_is_blocked_redacted(self) -> None:
        secret_value = "super-secret-token-123"
        self._write_project_file("AGENTS.md", f"API_TOKEN={secret_value}\n")

        result = read_project_knowledge(
            self.project_root,
            [str(self.approved_root)],
        )
        formatted = format_project_knowledge_result(result)

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertNotIn(secret_value, formatted)
        self.assertIn("blocked", formatted.lower())

    def test_unapproved_project_path_blocks(self) -> None:
        outside_project = self.root / "outside-project"
        outside_project.mkdir()

        result = read_project_knowledge(
            outside_project,
            [str(self.approved_root)],
        )

        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertEqual(result["found_files"], [])
        self.assertEqual(result["context_blocks"], [])

    def test_context_budget_compaction_works(self) -> None:
        self._write_project_file("AGENTS.md", "A" * 6000)
        self._write_project_file("docs/architecture.md", "B" * 6000)

        result = read_project_knowledge(
            self.project_root,
            [str(self.approved_root)],
        )

        total_chars = sum(int(block["char_count"]) for block in result["context_blocks"])
        self.assertLessEqual(total_chars, 8000)
        self.assertTrue(
            any("TRUNCATED" in str(block["content"]) for block in result["context_blocks"])
        )

    def test_formatter_includes_found_missing_and_context_preview(self) -> None:
        self._write_project_file("AGENTS.md", "Agent instructions")

        result = read_project_knowledge(
            self.project_root,
            [str(self.approved_root)],
        )
        output = format_project_knowledge_result(result)

        self.assertIn("Found docs: AGENTS.md", output)
        self.assertIn("Missing docs:", output)
        self.assertIn("Context blocks:", output)


class ProjectKnowledgeMCPCLITests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.project_root = self.approved_root / "project"
        self.project_root.mkdir()
        (self.project_root / "AGENTS.md").write_text("Agent instructions", encoding="utf-8")
        self.fake_config = {
            "ai_brain_path": "/tmp/ai-brain",
            "reports_dir": "reports",
            "phase": 1,
            "read_only": True,
            "approved_paths": [str(self.approved_root)],
        }

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cli_project_knowledge_read_works(self) -> None:
        stdout = StringIO()

        with patch.object(cli, "load_config", return_value=self.fake_config):
            with patch.object(cli, "write_ai_brain_memory") as mocked_ai_brain_write:
                with patch.object(cli, "evaluate_mcp_tool_request") as mocked_legacy_mcp:
                    with redirect_stdout(stdout):
                        cli.run(
                            [
                                "--project-knowledge-read",
                                "--project",
                                str(self.project_root),
                            ]
                        )

        output = stdout.getvalue()

        self.assertIn("Executed: yes", output)
        self.assertIn("Found docs: AGENTS.md", output)
        self.assertIn("Context blocks:", output)
        mocked_ai_brain_write.assert_not_called()
        mocked_legacy_mcp.assert_not_called()
