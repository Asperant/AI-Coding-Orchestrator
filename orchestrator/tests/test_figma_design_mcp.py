import os
from unittest import TestCase
from unittest.mock import patch
from io import StringIO

import cli
from tools.figma_design_mcp import MockFigmaDesignClient, run_figma_design_tool


class FigmaDesignMCPTests(TestCase):
    def test_mock_frame_read_returns_context_block(self):
        client = MockFigmaDesignClient(frames={("file1", "frame1"): "Frame 1 data"})
        result = run_figma_design_tool(
            "figma.frame.read", "file1", frame_id="frame1", client=client
        )
        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertEqual(len(result["context_blocks"]), 1)
        self.assertEqual(result["context_blocks"][0]["source"], "figma:frame:file1/frame1")
        self.assertIn("Frame 1 data", result["context_blocks"][0]["content"])

    def test_mock_component_read_returns_context_block(self):
        client = MockFigmaDesignClient(components={("file2", "comp2"): "Comp 2 data"})
        result = run_figma_design_tool(
            "figma.component.read", "file2", component_id="comp2", client=client
        )
        self.assertTrue(result["executed"])
        self.assertEqual(result["context_blocks"][0]["source"], "figma:component:file2/comp2")
        self.assertIn("Comp 2 data", result["context_blocks"][0]["content"])

    def test_mock_tokens_read_returns_context_block(self):
        client = MockFigmaDesignClient(tokens={"file3": "Tokens data"})
        result = run_figma_design_tool(
            "figma.tokens.read", "file3", client=client
        )
        self.assertTrue(result["executed"])
        self.assertEqual(result["context_blocks"][0]["source"], "figma:tokens:file3")
        self.assertIn("Tokens data", result["context_blocks"][0]["content"])

    def test_invalid_file_key_blocks(self):
        result = run_figma_design_tool("figma.tokens.read", "invalid key!@#")
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("Invalid file key", result["message"])

    def test_invalid_frame_id_blocks(self):
        result = run_figma_design_tool("figma.frame.read", "file1", frame_id="bad id$%^")
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("Invalid frame ID", result["message"])

    def test_unsafe_token_env_var_blocks(self):
        invalid_names = [
            "MY_TOKEN; rm -rf",
            "FIGMA TOKEN",
            "FIGMA-TOKEN",
            "$(FIGMA_TOKEN)",
            "FIGMA_TOKEN=abc",
            "../FIGMA_TOKEN"
        ]
        for invalid in invalid_names:
            result = run_figma_design_tool("figma.tokens.read", "file1", token_env_var=invalid)
            self.assertFalse(result["executed"])
            self.assertTrue(result["blocked"])
            self.assertIn("Invalid token", result["message"])

    def test_safe_token_env_var_accepted(self):
        valid_names = ["FIGMA_TOKEN", "FIGMATOKEN", "figma_token", "My_Token_123"]
        for valid in valid_names:
            with patch.dict(os.environ, {valid: "test"}, clear=True):
                client = MockFigmaDesignClient()
                result = run_figma_design_tool("figma.tokens.read", "file1", token_env_var=valid, client=client)
                self.assertTrue(result["executed"])
                self.assertFalse(result["blocked"])

    def test_missing_token_does_not_crash_or_print_raw_token(self):
        with patch.dict(os.environ, {}, clear=True):
            client = MockFigmaDesignClient()
            result = run_figma_design_tool(
                "figma.tokens.read", "file1", token_env_var="MISSING_TOKEN", client=client
            )
            self.assertTrue(result["executed"])
            self.assertFalse(result["blocked"])
            self.assertTrue(any("MISSING_TOKEN is not set" in note for note in result["safety_notes"]))

    def test_secret_like_design_content_is_blocked(self):
        client = MockFigmaDesignClient(tokens={"file1": "API_KEY=sk-ant-api03-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12"})
        result = run_figma_design_tool(
            "figma.tokens.read", "file1", client=client
        )
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("secret-like content", result["message"].lower())

    def test_cli_integration(self):
        with patch.dict(os.environ, {"FIGMA_TOKEN": "my_secret_token"}):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                cli.run([
                    "--figma-read",
                    "--figma-tool-name", "figma.tokens.read",
                    "--figma-file-key", "testfile",
                    "--figma-token-env", "FIGMA_TOKEN"
                ])
                output = mock_stdout.getvalue()
                self.assertIn("Figma tool: figma.tokens.read", output)
                self.assertIn("File key: testfile", output)
                self.assertIn("Executed: no", output)
                self.assertIn("Blocked: yes", output)
                self.assertIn("unavailable natively", output)
                self.assertNotIn("my_secret_token", output)

    @patch("tools.figma_design_mcp.urllib.request.urlopen")
    def test_real_client_frame_read(self, mock_urlopen):
        import json
        from unittest.mock import MagicMock
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "nodes": {
                "frame1": {
                    "document": {
                        "name": "Header",
                        "type": "FRAME",
                        "children": [{}, {}],
                        "fills": [{}],
                        "absoluteBoundingBox": {"width": 100, "height": 50}
                    }
                }
            }
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        with patch.dict(os.environ, {"FIGMA_TOKEN": "real-token"}):
            result = run_figma_design_tool(
                "figma.frame.read", "file1", frame_id="frame1", token_env_var="FIGMA_TOKEN"
            )

        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertIn("Name: Header", result["context_blocks"][0]["content"])
        self.assertIn("Children: 2", result["context_blocks"][0]["content"])

    @patch("tools.figma_design_mcp.urllib.request.urlopen")
    def test_real_client_component_read(self, mock_urlopen):
        import json
        from unittest.mock import MagicMock
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "nodes": {
                "comp1": {
                    "document": {
                        "name": "Button",
                        "type": "COMPONENT",
                        "children": [],
                        "fills": []
                    },
                    "componentId": "c_123"
                }
            }
        }).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        with patch.dict(os.environ, {"FIGMA_TOKEN": "real-token"}):
            result = run_figma_design_tool(
                "figma.component.read", "file1", component_id="comp1", token_env_var="FIGMA_TOKEN"
            )

        self.assertTrue(result["executed"])
        self.assertIn("Component ID: c_123", result["context_blocks"][0]["content"])

    def test_missing_token_blocks_real_client(self):
        with patch.dict(os.environ, {}, clear=True):
            result = run_figma_design_tool(
                "figma.frame.read", "file1", frame_id="frame1", token_env_var="FIGMA_TOKEN"
            )
            self.assertFalse(result["executed"])
            self.assertTrue(result["blocked"])
            self.assertIn("token is missing", result["message"])

    def test_cli_integration_real(self):
        with patch.dict(os.environ, {"FIGMA_TOKEN": "my_secret_token"}):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch("tools.figma_design_mcp.RealFigmaClient.read_frame") as mock_read:
                    mock_read.return_value = "Name: Main\nType: FRAME"
                    cli.run([
                        "--figma-read",
                        "--figma-tool-name", "figma.frame.read",
                        "--figma-file-key", "testfile",
                        "--figma-frame-id", "testframe",
                        "--figma-token-env", "FIGMA_TOKEN"
                    ])
                    output = mock_stdout.getvalue()
                    self.assertIn("Figma tool: figma.frame.read", output)
                    self.assertIn("Executed: yes", output)
                    self.assertNotIn("my_secret_token", output)
