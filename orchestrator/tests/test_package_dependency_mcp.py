import os
from unittest import TestCase
from unittest.mock import patch
from io import StringIO

import cli
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, MagicMock
from tools.package_dependency_mcp import MockPackageClient, run_package_dependency_tool


class PackageDependencyMCPTests(TestCase):
    def test_mock_npm_metadata_read_returns_context_block(self):
        client = MockPackageClient(metadata={("npm", "react", None): "react 18 metadata"})
        result = run_package_dependency_tool(
            "package.metadata.read", "npm", "react", client=client
        )
        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        self.assertEqual(len(result["context_blocks"]), 1)
        self.assertEqual(result["context_blocks"][0]["source"], "npm/react")
        self.assertIn("react 18 metadata", result["context_blocks"][0]["content"])

    def test_mock_pypi_metadata_read_returns_context_block(self):
        client = MockPackageClient(metadata={("pypi", "requests", "2.31.0"): "requests 2.31.0 metadata"})
        result = run_package_dependency_tool(
            "package.metadata.read", "pypi", "requests", version="2.31.0", client=client
        )
        self.assertTrue(result["executed"])
        self.assertEqual(result["context_blocks"][0]["source"], "pypi/requests@2.31.0")
        self.assertIn("requests 2.31.0 metadata", result["context_blocks"][0]["content"])

    def test_changelog_read_returns_context_block(self):
        client = MockPackageClient(changelogs={("npm", "vue", None): "Added feature x"})
        result = run_package_dependency_tool(
            "package.changelog.read", "npm", "vue", client=client
        )
        self.assertTrue(result["executed"])
        self.assertEqual(result["context_blocks"][0]["content"], "Added feature x")

    def test_advisory_read_returns_context_block(self):
        client = MockPackageClient(advisories={("pypi", "django", "3.0"): "CVE-2021-1234"})
        result = run_package_dependency_tool(
            "package.advisory.read", "pypi", "django", version="3.0", client=client
        )
        self.assertTrue(result["executed"])
        self.assertEqual(result["context_blocks"][0]["content"], "CVE-2021-1234")

    def test_invalid_ecosystem_blocks(self):
        result = run_package_dependency_tool("package.metadata.read", "ruby", "rails")
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("not supported", result["message"])

    def test_unsafe_package_name_blocks(self):
        result = run_package_dependency_tool("package.metadata.read", "npm", "bad name&;")
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("Invalid package name", result["message"])

    def test_unsafe_version_blocks(self):
        result = run_package_dependency_tool("package.metadata.read", "npm", "react", version="18; rm -rf")
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("Invalid version", result["message"])

    def test_unsafe_token_env_var_blocks(self):
        result = run_package_dependency_tool("package.metadata.read", "npm", "react", token_env_var="MY_TOKEN; echo")
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("Invalid token", result["message"])

    def test_secret_like_package_content_is_blocked(self):
        client = MockPackageClient(metadata={("npm", "react", None): "Some metadata with token: sk-ant-api03-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12"})
        result = run_package_dependency_tool(
            "package.metadata.read", "npm", "react", client=client
        )
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("secret-like content", result["message"].lower())

    def test_missing_token_does_not_crash_or_print_raw_token(self):
        with patch.dict(os.environ, {}, clear=True):
            client = MockPackageClient()
            result = run_package_dependency_tool(
                "package.metadata.read", "npm", "react", token_env_var="MISSING_TOKEN", client=client
            )
            self.assertTrue(result["executed"])
            self.assertFalse(result["blocked"])
            self.assertTrue(any("MISSING_TOKEN is not set" in note for note in result["safety_notes"]))

    @patch("tools.package_dependency_mcp.urllib.request.urlopen")
    def test_cli_integration(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "name": "react",
            "dist-tags": {"latest": "18.2.0"},
            "description": "React is a JavaScript library.",
            "versions": {"18.2.0": {}}
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        with patch.dict(os.environ, {"MY_PKG_TOKEN": "my_secret_token"}):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                cli.run([
                    "--package-read",
                    "--package-tool-name", "package.metadata.read",
                    "--package-ecosystem", "npm",
                    "--package-name", "react",
                    "--package-token-env", "MY_PKG_TOKEN"
                ])
                output = mock_stdout.getvalue()
                self.assertIn("Package tool: package.metadata.read", output)
                self.assertIn("Ecosystem: npm", output)
                self.assertIn("Package: react", output)
                self.assertIn("Executed: yes", output)
                self.assertIn("Blocked: no", output)
                self.assertNotIn("my_secret_token", output)

    @patch("tools.package_dependency_mcp.urllib.request.urlopen")
    def test_real_npm_metadata_read_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "name": "react",
            "dist-tags": {"latest": "18.2.0"},
            "description": "React is a JavaScript library for building user interfaces.",
            "license": "MIT",
            "homepage": "https://reactjs.org/",
            "repository": {"url": "git+https://github.com/facebook/react.git"},
            "versions": {"18.2.0": {}, "18.1.0": {}}
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = run_package_dependency_tool(
            "package.metadata.read", ecosystem="npm", package_name="react"
        )
        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        content = result["context_blocks"][0]["content"]
        self.assertIn("React is a JavaScript library", content)
        self.assertIn("MIT", content)
        self.assertIn("18.2.0", content)

    @patch("tools.package_dependency_mcp.urllib.request.urlopen")
    def test_real_pypi_metadata_read_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "info": {
                "name": "requests",
                "version": "2.31.0",
                "summary": "Python HTTP for Humans.",
                "license": "Apache 2.0",
                "home_page": "https://requests.readthedocs.io",
            },
            "releases": {"2.31.0": [], "2.30.0": []}
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = run_package_dependency_tool(
            "package.metadata.read", ecosystem="pypi", package_name="requests"
        )
        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        content = result["context_blocks"][0]["content"]
        self.assertIn("Python HTTP for Humans", content)
        self.assertIn("2.31.0", content)

    def test_local_manifest_read_package_json(self):
        with TemporaryDirectory() as tmp_dir:
            approved = Path(tmp_dir) / "approved"
            approved.mkdir()
            pkg_json = approved / "package.json"
            pkg_json.write_text('{"name": "test-app", "dependencies": {"react": "18.0.0"}}', encoding="utf-8")
            
            result = run_package_dependency_tool(
                "package.manifest.read",
                source_path=str(pkg_json),
                approved_paths=[str(approved)]
            )
            self.assertTrue(result["executed"])
            self.assertFalse(result["blocked"])
            self.assertIn("react: 18.0.0", result["context_blocks"][0]["content"])

    @patch.dict("sys.modules", {"tomllib": MagicMock(loads=lambda x: {"project": {"name": "test", "dependencies": ["requests", "flask"]}})})
    def test_local_manifest_read_pyproject_toml_with_tomllib(self):
        with TemporaryDirectory() as tmp_dir:
            approved = Path(tmp_dir) / "approved"
            approved.mkdir()
            pyproj = approved / "pyproject.toml"
            pyproj.write_text('[project]\nname="test"\ndependencies=["requests", "flask"]', encoding="utf-8")
            
            result = run_package_dependency_tool(
                "package.manifest.read",
                source_path=str(pyproj),
                approved_paths=[str(approved)]
            )
            self.assertTrue(result["executed"])
            self.assertIn("requests", result["context_blocks"][0]["content"])

    @patch.dict("sys.modules", {"tomllib": None})
    def test_local_manifest_read_pyproject_toml_without_tomllib(self):
        with TemporaryDirectory() as tmp_dir:
            approved = Path(tmp_dir) / "approved"
            approved.mkdir()
            pyproj = approved / "pyproject.toml"
            pyproj.write_text('[project]\nname="test"\ndependencies = [\n"requests",\n"flask"\n]\n[tool.poetry.dependencies]\npytest = "^7.0"', encoding="utf-8")
            
            result = run_package_dependency_tool(
                "package.manifest.read",
                source_path=str(pyproj),
                approved_paths=[str(approved)]
            )
            self.assertTrue(result["executed"])
            content = result["context_blocks"][0]["content"]
            self.assertIn("limited parse - tomllib unavailable", content)
            self.assertIn("requests", content)
            self.assertIn("flask", content)
            self.assertIn('pytest = "^7.0', content)

    def test_local_manifest_read_unapproved_path(self):
        with TemporaryDirectory() as tmp_dir:
            approved = Path(tmp_dir) / "approved"
            approved.mkdir()
            outside = Path(tmp_dir) / "outside.json"
            outside.write_text('{}', encoding="utf-8")
            
            result = run_package_dependency_tool(
                "package.manifest.read",
                source_path=str(outside),
                approved_paths=[str(approved)]
            )
            self.assertFalse(result["executed"])
            self.assertTrue(result["blocked"])
            self.assertIn("not approved", result["message"])

    @patch("tools.package_dependency_mcp.urllib.request.urlopen")
    def test_real_advisory_read_no_vulnerabilities(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"vulns": []}).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = run_package_dependency_tool(
            "package.advisory.read", ecosystem="npm", package_name="lodash"
        )
        self.assertTrue(result["executed"])
        self.assertFalse(result["blocked"])
        content = result["context_blocks"][0]["content"]
        self.assertIn("No vulnerabilities found", content)

    @patch("tools.package_dependency_mcp.urllib.request.urlopen")
    def test_real_advisory_read_with_vulnerabilities(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "vulns": [
                {
                    "id": "GHSA-123",
                    "aliases": ["CVE-2023-1234"],
                    "summary": "Prototype pollution in lodash",
                    "published": "2023-01-01T00:00:00Z",
                    "severity": [{"score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}],
                    "affected": [{"versions": ["4.17.20", "4.17.21"]}]
                }
            ]
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = run_package_dependency_tool(
            "package.advisory.read", ecosystem="npm", package_name="lodash", version="4.17.20"
        )
        self.assertTrue(result["executed"])
        content = result["context_blocks"][0]["content"]
        self.assertIn("Found 1 vulnerabilities", content)
        self.assertIn("ID: GHSA-123", content)
        self.assertIn("Aliases: CVE-2023-1234", content)
        self.assertIn("Severity: CVSS:3.1", content)
        self.assertIn("Affected versions preview: 4.17.20", content)

    @patch("tools.package_dependency_mcp.urllib.request.urlopen")
    def test_real_advisory_read_http_error(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "url", 500, "Internal Server Error", {}, None
        )
        result = run_package_dependency_tool(
            "package.advisory.read", ecosystem="npm", package_name="lodash"
        )
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertIn("HTTP error 500", result["message"])

    def test_changelog_read_unavailable(self):
        result = run_package_dependency_tool(
            "package.changelog.read", ecosystem="npm", package_name="lodash"
        )
        self.assertFalse(result["executed"])
        self.assertTrue(result["blocked"])
        self.assertTrue(result["blocked"])
        self.assertIn("Remote changelog fetching is not implemented", result["message"])

    def test_local_changelog_read_works_for_approved_file(self):
        with TemporaryDirectory() as tmp_dir:
            approved = Path(tmp_dir) / "approved"
            approved.mkdir()
            changelog = approved / "CHANGELOG.md"
            changelog.write_text("# 1.0.0\nInitial release\n# 1.1.0\nAdded feature", encoding="utf-8")
            
            result = run_package_dependency_tool(
                "package.changelog.read",
                ecosystem="local_changelog",
                source_path=str(changelog),
                approved_paths=[str(approved)]
            )
            self.assertTrue(result["executed"])
            self.assertFalse(result["blocked"])
            self.assertIn("Initial release", result["context_blocks"][0]["content"])

    def test_local_changelog_read_version_specific(self):
        with TemporaryDirectory() as tmp_dir:
            approved = Path(tmp_dir) / "approved"
            approved.mkdir()
            changelog = approved / "CHANGELOG.md"
            changelog.write_text("# 1.0.0\nInitial release\n# 1.1.0\nAdded feature\n# 1.2.0\nFixed bug", encoding="utf-8")
            
            result = run_package_dependency_tool(
                "package.changelog.read",
                ecosystem="local_changelog",
                source_path=str(changelog),
                version="1.1.0",
                approved_paths=[str(approved)]
            )
            self.assertTrue(result["executed"])
            content = result["context_blocks"][0]["content"]
            self.assertIn("1.1.0", content)
            self.assertIn("Added feature", content)
            self.assertNotIn("Initial release", content)
            self.assertNotIn("Fixed bug", content)

    def test_local_changelog_read_missing_version(self):
        with TemporaryDirectory() as tmp_dir:
            approved = Path(tmp_dir) / "approved"
            approved.mkdir()
            changelog = approved / "CHANGELOG.md"
            changelog.write_text("# 1.0.0\nInitial release\n# 1.1.0\nAdded feature", encoding="utf-8")
            
            result = run_package_dependency_tool(
                "package.changelog.read",
                ecosystem="local_changelog",
                source_path=str(changelog),
                version="2.0.0",
                approved_paths=[str(approved)]
            )
            self.assertTrue(result["executed"])
            content = result["context_blocks"][0]["content"]
            self.assertIn("Version 2.0.0 section not found", content)
            self.assertIn("Preview", content)
            self.assertIn("Initial release", content)

    def test_local_changelog_unapproved_path_blocks(self):
        with TemporaryDirectory() as tmp_dir:
            approved = Path(tmp_dir) / "approved"
            approved.mkdir()
            outside = Path(tmp_dir) / "CHANGELOG.md"
            outside.write_text('# 1.0.0\nInitial release', encoding="utf-8")
            
            result = run_package_dependency_tool(
                "package.changelog.read",
                ecosystem="local_changelog",
                source_path=str(outside),
                approved_paths=[str(approved)]
            )
            self.assertFalse(result["executed"])
            self.assertTrue(result["blocked"])
            self.assertIn("not approved", result["message"])

    def test_local_changelog_unsupported_file_blocks(self):
        with TemporaryDirectory() as tmp_dir:
            approved = Path(tmp_dir) / "approved"
            approved.mkdir()
            bad_file = approved / "random_file.json"
            bad_file.write_text('{"foo": "bar"}', encoding="utf-8")
            
            result = run_package_dependency_tool(
                "package.changelog.read",
                ecosystem="local_changelog",
                source_path=str(bad_file),
                approved_paths=[str(approved)]
            )
            self.assertFalse(result["executed"])
            self.assertTrue(result["blocked"])
            self.assertIn("Unsupported changelog file type", result["message"])

    def test_local_changelog_huge_file_truncates_or_blocks(self):
        with TemporaryDirectory() as tmp_dir:
            approved = Path(tmp_dir) / "approved"
            approved.mkdir()
            changelog = approved / "CHANGELOG.md"
            changelog.write_text("a" * (1024 * 1024 + 10), encoding="utf-8")
            
            result = run_package_dependency_tool(
                "package.changelog.read",
                ecosystem="local_changelog",
                source_path=str(changelog),
                approved_paths=[str(approved)]
            )
            self.assertFalse(result["executed"])
            self.assertTrue(result["blocked"])
            self.assertIn("too large", result["message"])

    def test_local_changelog_secret_blocked(self):
        with TemporaryDirectory() as tmp_dir:
            approved = Path(tmp_dir) / "approved"
            approved.mkdir()
            changelog = approved / "CHANGELOG.md"
            changelog.write_text("# 1.0.0\nsecret token: sk-ant-api03-abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef12", encoding="utf-8")
            
            result = run_package_dependency_tool(
                "package.changelog.read",
                ecosystem="local_changelog",
                source_path=str(changelog),
                approved_paths=[str(approved)]
            )
            self.assertFalse(result["executed"])
            self.assertTrue(result["blocked"])
            self.assertIn("secret-like content", result["message"].lower())

    def test_cli_package_manifest_read_works_without_package_name(self):
        with patch.object(cli, "load_config", return_value={"approved_paths": [], "ai_brain_path": "", "reports_dir": "", "phase": 1, "read_only": True}):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with patch("tools.package_dependency_mcp.run_package_dependency_tool", return_value={"executed": True, "blocked": False, "context_blocks": [], "message": "ok", "tool_name": "package.manifest.read", "ecosystem": "local_manifest", "package_name": None, "version": None}):
                    cli.run([
                        "--package-read",
                        "--package-tool-name", "package.manifest.read",
                        "--package-ecosystem", "local_manifest",
                        "--package-source-path", "package.json"
                    ])
                    output = mock_stdout.getvalue()
                    self.assertIn("Package tool: package.manifest.read", output)

    def test_cli_package_manifest_read_requires_source_path(self):
        with patch.object(cli, "load_config", return_value={"approved_paths": [], "ai_brain_path": "", "reports_dir": "", "phase": 1, "read_only": True}):
            with self.assertRaises(SystemExit) as cm:
                cli.run([
                    "--package-read",
                    "--package-tool-name", "package.manifest.read",
                    "--package-ecosystem", "local_manifest"
                ])
            self.assertIn("package.manifest.read requires --package-source-path", str(cm.exception))

    def test_cli_package_metadata_read_requires_package_name(self):
        with patch.object(cli, "load_config", return_value={"approved_paths": [], "ai_brain_path": "", "reports_dir": "", "phase": 1, "read_only": True}):
            with self.assertRaises(SystemExit) as cm:
                cli.run([
                    "--package-read",
                    "--package-tool-name", "package.metadata.read",
                    "--package-ecosystem", "npm"
                ])
            self.assertIn("requires --package-name", str(cm.exception))

    def test_cli_package_advisory_read_requires_package_name(self):
        with patch.object(cli, "load_config", return_value={"approved_paths": [], "ai_brain_path": "", "reports_dir": "", "phase": 1, "read_only": True}):
            with self.assertRaises(SystemExit) as cm:
                cli.run([
                    "--package-read",
                    "--package-tool-name", "package.advisory.read",
                    "--package-ecosystem", "npm"
                ])
            self.assertIn("requires --package-name", str(cm.exception))
