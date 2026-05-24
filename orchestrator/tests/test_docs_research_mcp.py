import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from io import StringIO

import cli
from tools.docs_research_mcp import MockDocsResearchClient, run_docs_research_tool

class DocsResearchMCPTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.approved_root = self.root / "approved"
        self.approved_root.mkdir()
        self.local_docs = self.approved_root / "docs"
        self.local_docs.mkdir()
        self.safe_doc = self.local_docs / "api.md"
        self.safe_doc.write_text("API documentation.", encoding="utf-8")
        
        self.unapproved_root = self.root / "unapproved"
        self.unapproved_root.mkdir()
        self.unsafe_doc = self.unapproved_root / "secret.md"
        self.unsafe_doc.write_text("Secret docs.", encoding="utf-8")
        
        self.secret_doc = self.local_docs / "secrets.md"
        self.secret_doc.write_text("API_KEY=sk-ant-api03-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_mock_notebook_search_returns_context_block(self):
        client = MockDocsResearchClient(notebook_searches={"auth": "Mock Notebook auth response"})
        result = run_docs_research_tool(
            "notebook.search", "notebooklm", query="auth", client=client
        )
        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertEqual(len(result["context_blocks"]), 1)
        self.assertEqual(result["context_blocks"][0]["source"], "notebooklm:search:auth")
        self.assertIn("Mock Notebook auth response", result["context_blocks"][0]["content"])

    def test_mock_docs_page_read_returns_context_block(self):
        client = MockDocsResearchClient(docs_pages={"page_123": "Mock page content"})
        result = run_docs_research_tool(
            "docs.page.read", "official_docs", page_id="page_123", client=client
        )
        self.assertTrue(result["executed"])
        self.assertEqual(result["context_blocks"][0]["content"], "Mock page content")

    def test_local_docs_file_read_works_for_approved_path(self):
        result = run_docs_research_tool(
            "docs.page.read", "local_docs", source_path=str(self.safe_doc),
            approved_paths=[str(self.approved_root)]
        )
        self.assertTrue(result["executed"])
        self.assertIn("API documentation.", result["context_blocks"][0]["content"])

    def test_local_docs_search_works_for_approved_path(self):
        result = run_docs_research_tool(
            "docs.search", "local_docs", query="API", source_path=str(self.local_docs),
            approved_paths=[str(self.approved_root)]
        )
        self.assertTrue(result["executed"])
        self.assertIn("api.md:1 - API documentation.", result["context_blocks"][0]["content"])

    def test_local_docs_search_skips_unsupported_files(self):
        binary_file = self.local_docs / "image.png"
        binary_file.write_text("API binary data", encoding="utf-8")
        result = run_docs_research_tool(
            "docs.search", "local_docs", query="API", source_path=str(self.local_docs),
            approved_paths=[str(self.approved_root)]
        )
        self.assertTrue(result["executed"])
        content = result["context_blocks"][0]["content"]
        self.assertIn("api.md:1 - API documentation.", content)
        self.assertNotIn("image.png", content)

    def test_local_docs_page_read_blocks_unsupported_files(self):
        binary_file = self.local_docs / "image.png"
        binary_file.write_text("API binary data", encoding="utf-8")
        result = run_docs_research_tool(
            "docs.page.read", "local_docs", source_path=str(binary_file),
            approved_paths=[str(self.approved_root)]
        )
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("not a supported text file", result["message"])

    def test_secret_like_docs_content_is_blocked(self):
        result = run_docs_research_tool(
            "docs.page.read", "local_docs", source_path=str(self.secret_doc),
            approved_paths=[str(self.approved_root)]
        )
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("secret-like content", result["message"].lower())

    def test_unapproved_local_docs_path_blocks(self):
        result = run_docs_research_tool(
            "docs.page.read", "local_docs", source_path=str(self.unsafe_doc),
            approved_paths=[str(self.approved_root)]
        )
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("not approved", result["message"])

    def test_invalid_provider_blocks(self):
        result = run_docs_research_tool(
            "docs.page.read", "invalid_provider", page_id="123"
        )
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("not supported", result["message"])

    def test_unsafe_token_env_var_blocks(self):
        result = run_docs_research_tool(
            "docs.page.read", "notebooklm", token_env_var="MY_TOKEN; rm -rf"
        )
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("Invalid token", result["message"])

    def test_query_length_and_safety_validation_works(self):
        result_too_long = run_docs_research_tool(
            "notebook.search", "notebooklm", query="a" * 501
        )
        self.assertTrue(result_too_long["blocked"])
        self.assertIn("too long", result_too_long["message"])
        
        result_unsafe = run_docs_research_tool(
            "notebook.search", "notebooklm", query="query & cat /etc/passwd"
        )
        self.assertTrue(result_unsafe["blocked"])
        self.assertIn("unsafe characters", result_unsafe["message"])

    def test_cli_integration(self):
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            cli.run([
                "--docs-research-read",
                "--docs-tool-name", "docs.search",
                "--docs-provider", "mock",
                "--docs-query", "my test query",
            ])
            output = mock_stdout.getvalue()
            self.assertIn("Docs tool: docs.search", output)
            self.assertIn("Provider: mock", output)
            self.assertIn("Query: my test query", output)
            self.assertIn("Executed: no", output)
            self.assertIn("Blocked: yes", output)
            self.assertIn("Real provider is not implemented", output)

    @patch("cli.load_config")
    def test_cli_integration_local_docs_search(self, mock_load_config):
        from core.config_loader import load_config
        real_config = load_config()
        real_config["approved_paths"] = [str(self.approved_root)]
        mock_load_config.return_value = real_config
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            cli.run([
                "--docs-research-read",
                "--docs-tool-name", "docs.search",
                "--docs-provider", "local_docs",
                "--docs-query", "API documentation",
                "--docs-source-path", str(self.local_docs),
                "--project", str(self.approved_root)
            ])
            output = mock_stdout.getvalue()
            self.assertIn("Docs tool: docs.search", output)
            self.assertIn("Provider: local_docs", output)
            self.assertIn("Executed: yes", output)
            self.assertIn("Blocked: no", output)
