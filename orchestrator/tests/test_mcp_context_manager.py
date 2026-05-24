from unittest import TestCase
from unittest.mock import patch

from tools.mcp_context_manager import (
    build_context_block_from_mcp_result,
    compact_context_blocks,
    format_context_blocks,
)


class MCPContextManagerTests(TestCase):
    def test_builds_context_block_from_successful_filesystem_read(self) -> None:
        mcp_result = {
            "executed": True,
            "blocked": False,
            "tool_name": "filesystem.read_file",
            "action": "read",
            "message": "filesystem.read_file completed successfully.",
            "output_text": "safe text",
            "source_path": "/tmp/project/notes.txt",
            "decision": {"allowed": True},
            "safety_notes": [],
        }

        block = build_context_block_from_mcp_result(mcp_result)

        self.assertEqual(block["source_type"], "file")
        self.assertEqual(block["source_name"], "notes.txt")
        self.assertEqual(block["tool_name"], "filesystem.read_file")
        self.assertEqual(block["source_path"], "/tmp/project/notes.txt")
        self.assertEqual(block["content"], "safe text")
        self.assertTrue(block["safe"])
        self.assertFalse(block["blocked"])

    def test_blocks_redacts_secret_like_content(self) -> None:
        mcp_result = {
            "executed": True,
            "blocked": False,
            "tool_name": "git.diff",
            "action": "read",
            "message": "git.diff completed successfully.",
            "output_text": "API_TOKEN=super-secret-token-123",
            "source_path": "/tmp/project",
            "decision": {"allowed": True},
            "safety_notes": [],
        }

        block = build_context_block_from_mcp_result(mcp_result)

        self.assertFalse(block["safe"])
        self.assertTrue(block["blocked"])
        self.assertNotIn("super-secret-token-123", block["content"])
        self.assertIn("blocked", block["content"].lower())

    def test_preserves_source_metadata(self) -> None:
        mcp_result = {
            "executed": True,
            "blocked": False,
            "tool_name": "git.status",
            "action": "read",
            "message": "git.status completed successfully.",
            "output_text": "Git repo: yes",
            "source_path": "/tmp/project",
            "decision": {"allowed": True},
            "safety_notes": [],
        }

        block = build_context_block_from_mcp_result(mcp_result)

        self.assertEqual(block["source_type"], "git")
        self.assertEqual(block["source_name"], "project")
        self.assertEqual(block["tool_name"], "git.status")

    def test_compacts_multiple_blocks_under_char_budget(self) -> None:
        blocks = [
            {
                "source_type": "file",
                "source_name": "a.txt",
                "tool_name": "filesystem.read_file",
                "source_path": "/tmp/a.txt",
                "content": "A" * 60,
                "safe": True,
                "blocked": False,
                "reason": "none",
                "char_count": 60,
            },
            {
                "source_type": "file",
                "source_name": "b.txt",
                "tool_name": "filesystem.read_file",
                "source_path": "/tmp/b.txt",
                "content": "B" * 60,
                "safe": True,
                "blocked": False,
                "reason": "none",
                "char_count": 60,
            },
        ]

        compacted = compact_context_blocks(blocks, max_total_chars=100)

        self.assertEqual(len(compacted), 2)
        self.assertLessEqual(sum(int(block["char_count"]) for block in compacted), 100)
        self.assertTrue(any("TRUNCATED" in str(block["content"]) for block in compacted))

    def test_blocked_blocks_do_not_leak_raw_content(self) -> None:
        blocks = [
            {
                "source_type": "git",
                "source_name": "project",
                "tool_name": "git.diff",
                "source_path": "/tmp/project",
                "content": "API_TOKEN=super-secret-token-123",
                "safe": False,
                "blocked": True,
                "reason": "Secret-like content detected.",
                "char_count": 30,
            }
        ]

        compacted = compact_context_blocks(blocks)

        self.assertEqual(len(compacted), 1)
        self.assertNotIn("super-secret-token-123", str(compacted[0]["content"]))
        self.assertIn("[BLOCKED CONTEXT]", str(compacted[0]["content"]))

    def test_duplicate_content_is_deduped(self) -> None:
        blocks = [
            {
                "source_type": "file",
                "source_name": "a.txt",
                "tool_name": "filesystem.read_file",
                "source_path": "/tmp/a.txt",
                "content": "same content",
                "safe": True,
                "blocked": False,
                "reason": "none",
                "char_count": 12,
            },
            {
                "source_type": "file",
                "source_name": "b.txt",
                "tool_name": "filesystem.read_file",
                "source_path": "/tmp/b.txt",
                "content": "same content",
                "safe": True,
                "blocked": False,
                "reason": "none",
                "char_count": 12,
            },
        ]

        compacted = compact_context_blocks(blocks)

        self.assertEqual(len(compacted), 1)

    def test_formatter_includes_source_tool_status(self) -> None:
        blocks = [
            {
                "source_type": "file",
                "source_name": "notes.txt",
                "tool_name": "filesystem.read_file",
                "source_path": "/tmp/notes.txt",
                "content": "safe text",
                "safe": True,
                "blocked": False,
                "reason": "none",
                "char_count": 9,
            }
        ]

        output = format_context_blocks(blocks)

        self.assertIn("Context blocks: 1", output)
        self.assertIn("source=notes.txt", output)
        self.assertIn("tool=filesystem.read_file", output)
        self.assertIn("status=safe", output)

    def test_no_mcp_execution_occurs(self) -> None:
        mcp_result = {
            "executed": True,
            "blocked": False,
            "tool_name": "filesystem.read_file",
            "action": "read",
            "message": "filesystem.read_file completed successfully.",
            "output_text": "safe text",
            "source_path": "/tmp/project/notes.txt",
            "decision": {"allowed": True},
            "safety_notes": [],
        }

        with patch("tools.mcp_context_manager.guard_text_output") as mocked_guard:
            mocked_guard.return_value = {
                "allowed": True,
                "risk_level": "low",
                "safe_message": "allowed",
                "findings": [],
                "should_block_save": False,
            }
            build_context_block_from_mcp_result(mcp_result)

        mocked_guard.assert_called_once()
