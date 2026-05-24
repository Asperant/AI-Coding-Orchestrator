import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol
from typing import Protocol

from core.approved_paths import ApprovedPathError, ensure_approved_path
from core.safety import guard_text_output
from tools.filesystem_gateway import read_file


class PackageClient(Protocol):
    def read_metadata(self, ecosystem: str, package_name: str, version: str | None) -> str:
        ...

    def read_changelog(self, ecosystem: str, package_name: str, version: str | None) -> str:
        ...

    def read_advisory(self, ecosystem: str, package_name: str, version: str | None) -> str:
        ...


class MockPackageClient:
    def __init__(
        self,
        metadata: dict[tuple[str, str, str | None], str] | None = None,
        changelogs: dict[tuple[str, str, str | None], str] | None = None,
        advisories: dict[tuple[str, str, str | None], str] | None = None,
    ):
        self._metadata = metadata or {}
        self._changelogs = changelogs or {}
        self._advisories = advisories or {}

    def read_metadata(self, ecosystem: str, package_name: str, version: str | None) -> str:
        key = (ecosystem, package_name, version)
        if key in self._metadata:
            return self._metadata[key]
        key_no_version = (ecosystem, package_name, None)
        if key_no_version in self._metadata:
            return self._metadata[key_no_version]
        return f"Mock metadata for {package_name} in {ecosystem}"

    def read_changelog(self, ecosystem: str, package_name: str, version: str | None) -> str:
        key = (ecosystem, package_name, version)
        if key in self._changelogs:
            return self._changelogs[key]
        key_no_version = (ecosystem, package_name, None)
        if key_no_version in self._changelogs:
            return self._changelogs[key_no_version]
        return f"Mock changelog for {package_name} in {ecosystem}"

    def read_advisory(self, ecosystem: str, package_name: str, version: str | None) -> str:
        key = (ecosystem, package_name, version)
        if key in self._advisories:
            return self._advisories[key]
        key_no_version = (ecosystem, package_name, None)
        if key_no_version in self._advisories:
            return self._advisories[key_no_version]
        return f"Mock advisory for {package_name} in {ecosystem}"


class RealPackageClient:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def read_metadata(self, ecosystem: str, package_name: str, version: str | None) -> str:
        if ecosystem == "npm":
            return self._read_npm_metadata(package_name, version)
        elif ecosystem == "pypi":
            return self._read_pypi_metadata(package_name, version)
        raise ValueError(f"Real package reading not supported for {ecosystem}")

    def read_changelog(self, ecosystem: str, package_name: str, version: str | None) -> str:
        raise NotImplementedError("Real changelog reading not yet implemented.")

    def read_advisory(self, ecosystem: str, package_name: str, version: str | None) -> str:
        if ecosystem not in ("npm", "pypi"):
            raise ValueError(f"Real advisory reading not supported for {ecosystem}")
            
        url = "https://api.osv.dev/v1/query"
        payload_dict = {
            "package": {
                "name": package_name,
                "ecosystem": "npm" if ecosystem == "npm" else "PyPI"
            }
        }
        if version:
            payload_dict["version"] = version
            
        data = json.dumps(payload_dict).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={
            'Content-Type': 'application/json',
            'User-Agent': 'AI-Coding-Orchestrator'
        })
        
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                resp_data = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            raise ValueError(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            if isinstance(e.reason, TimeoutError):
                raise ValueError("Network request timed out.")
            raise ValueError(f"Network error: {e.reason}")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON received from OSV.")

        vulns = resp_data.get("vulns", [])
        if not vulns:
            return f"No vulnerabilities found for {package_name} in {ecosystem}."
            
        lines = [f"Found {len(vulns)} vulnerabilities for {package_name} in {ecosystem}."]
        
        for i, vuln in enumerate(vulns[:5]):
            vuln_id = vuln.get("id", "Unknown")
            aliases = vuln.get("aliases", [])
            summary = vuln.get("summary", "No summary provided.")
            published = vuln.get("published", "Unknown")
            
            lines.append(f"\nID: {vuln_id}")
            if aliases:
                lines.append(f"Aliases: {', '.join(aliases[:3])}")
            lines.append(f"Published: {published}")
            lines.append(f"Summary: {summary}")
            
            severity = vuln.get("severity", [])
            if severity:
                score = severity[0].get("score", "Unknown")
                lines.append(f"Severity: {score}")
                
            affected = vuln.get("affected", [])
            if affected:
                versions = affected[0].get("versions", [])
                if versions:
                    lines.append(f"Affected versions preview: {', '.join(versions[:3])}")
        
        if len(vulns) > 5:
            lines.append(f"\n... and {len(vulns) - 5} more vulnerabilities.")
            
        return "\n".join(lines)

    def _fetch_json(self, url: str) -> dict:
        req = urllib.request.Request(url, headers={'User-Agent': 'AI-Coding-Orchestrator'})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ValueError("Package not found.")
            raise ValueError(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            if isinstance(e.reason, TimeoutError):
                raise ValueError("Network request timed out.")
            raise ValueError(f"Network error: {e.reason}")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON received from registry.")

    def _read_npm_metadata(self, package_name: str, requested_version: str | None) -> str:
        encoded_name = urllib.parse.quote(package_name, safe='@/')
        url = f"https://registry.npmjs.org/{encoded_name}"
        data = self._fetch_json(url)
        
        name = data.get("name", package_name)
        dist_tags = data.get("dist-tags", {})
        latest_version = dist_tags.get("latest", "unknown")
        
        desc = data.get("description", "No description available.")
        license_str = data.get("license", "unknown")
        if isinstance(license_str, dict):
            license_str = license_str.get("type", "unknown")
            
        homepage = data.get("homepage", "unknown")
        repo = data.get("repository", {})
        repo_url = repo.get("url", "unknown") if isinstance(repo, dict) else str(repo)
        
        versions = list(data.get("versions", {}).keys())
        versions_preview = ", ".join(versions[-10:]) if versions else "none"
        versions_summary = f"{len(versions)} available (latest: {latest_version}). Recent: {versions_preview}"

        lines = [
            f"Ecosystem: npm",
            f"Package: {name}",
            f"Latest version: {latest_version}",
            f"Description: {desc}",
            f"License: {license_str}",
            f"Homepage: {homepage}",
            f"Repository: {repo_url}",
        ]
        
        if requested_version:
            found = "Yes" if requested_version in versions else "No"
            lines.append(f"Requested version ({requested_version}) available: {found}")
            
        lines.append(f"Versions: {versions_summary}")
        return "\n".join(lines)

    def _read_pypi_metadata(self, package_name: str, requested_version: str | None) -> str:
        encoded_name = urllib.parse.quote(package_name)
        url = f"https://pypi.org/pypi/{encoded_name}/json"
        data = self._fetch_json(url)
        
        info = data.get("info", {})
        name = info.get("name", package_name)
        latest_version = info.get("version", "unknown")
        
        desc = info.get("summary", "No description available.")
        license_str = info.get("license", "unknown")
        homepage = info.get("home_page", "unknown")
        project_urls = info.get("project_urls") or {}
        repo_url = project_urls.get("Source", project_urls.get("Repository", "unknown"))
        
        releases = list(data.get("releases", {}).keys())
        versions_preview = ", ".join(releases[-10:]) if releases else "none"
        versions_summary = f"{len(releases)} available (latest: {latest_version}). Recent: {versions_preview}"
        
        lines = [
            f"Ecosystem: PyPI",
            f"Package: {name}",
            f"Latest version: {latest_version}",
            f"Description: {desc}",
            f"License: {license_str}",
            f"Homepage: {homepage}",
            f"Repository: {repo_url}",
        ]
        
        if requested_version:
            found = "Yes" if requested_version in releases else "No"
            lines.append(f"Requested version ({requested_version}) available: {found}")
            
        lines.append(f"Versions: {versions_summary}")
        return "\n".join(lines)



def _read_local_manifest(source_path: str, approved_paths: list[str] | None) -> str:
    try:
        ensure_approved_path(source_path, approved_paths)
    except ApprovedPathError as e:
        raise ValueError(f"Source path is not approved: {e}")
        
    raw_content = read_file(source_path, approved_paths)
    filename = os.path.basename(source_path)
    
    if filename == "package.json":
        try:
            data = json.loads(raw_content)
            deps = data.get("dependencies", {})
            dev_deps = data.get("devDependencies", {})
            lines = [f"Manifest: {filename}", f"Name: {data.get('name', 'unknown')}"]
            lines.append(f"Dependencies ({len(deps)}):")
            for k, v in deps.items():
                lines.append(f"  {k}: {v}")
            lines.append(f"Dev Dependencies ({len(dev_deps)}):")
            for k, v in dev_deps.items():
                lines.append(f"  {k}: {v}")
            return "\n".join(lines)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in package.json")
            
    elif filename == "pyproject.toml":
        try:
            import tomllib
            data = tomllib.loads(raw_content)
            project = data.get("project", {})
            deps = project.get("dependencies", [])
            lines = [f"Manifest: {filename}", f"Name: {project.get('name', 'unknown')}"]
            lines.append(f"Dependencies ({len(deps)}):")
            for dep in deps:
                lines.append(f"  {dep}")
            return "\n".join(lines)
        except ImportError:
            lines = [f"Manifest: {filename} (limited parse - tomllib unavailable)"]
            deps = []
            in_deps = False
            for line in raw_content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line.strip("[]").strip()
                    in_deps = "dependencies" in section
                    continue
                
                if line.startswith("dependencies") and "=" in line:
                    in_deps = True
                    
                if in_deps:
                    clean = line.strip(' ,[]"\'')
                    if clean and not clean.startswith("dependencies"):
                        deps.append(clean)
                        
                if in_deps and line.endswith("]"):
                    in_deps = False
                    
            lines.append(f"Dependencies (approximate: {len(deps)}):")
            for dep in deps:
                lines.append(f"  {dep}")
            return "\n".join(lines)
        except Exception:
            raise ValueError("Failed to parse pyproject.toml")
            
    elif filename == "requirements.txt":
        lines = [f"Manifest: {filename}"]
        deps = [line.strip() for line in raw_content.splitlines() if line.strip() and not line.startswith("#")]
        lines.append(f"Dependencies ({len(deps)}):")
        for dep in deps:
            lines.append(f"  {dep}")
        return "\n".join(lines)
        
    else:
        raise ValueError(f"Unsupported manifest file: {filename}")


def _read_local_changelog(source_path: str, version: str | None, approved_paths: list[str] | None) -> str:
    try:
        ensure_approved_path(source_path, approved_paths)
    except ApprovedPathError as e:
        raise ValueError(f"Source path is not approved: {e}")
        
    filename = os.path.basename(source_path)
    allowed_exts = (".md", ".txt", ".rst")
    allowed_names = ("CHANGELOG.md", "CHANGELOG.txt", "HISTORY.md", "RELEASES.md")
    
    if filename not in allowed_names and not any(filename.lower().endswith(ext) for ext in allowed_exts):
        raise ValueError("Unsupported changelog file type.")
        
    raw_content = read_file(source_path, approved_paths)
    if len(raw_content) > 1024 * 1024:
        raise ValueError("Changelog file is too large.")
        
    if not version:
        return raw_content[:4000] + ("\n... [truncated]" if len(raw_content) > 4000 else "")
        
    lines = raw_content.splitlines()
    output = []
    in_section = False
    
    for line in lines:
        is_header = line.startswith("#") or line.startswith("==") or line.startswith("--") or line.startswith("##")
        if is_header:
            if version in line:
                in_section = True
                output.append(line)
            elif in_section:
                break
        elif in_section:
            output.append(line)
            
    if not output:
        return f"Version {version} section not found in {filename}.\n\nPreview:\n" + raw_content[:1000]
        
    result = "\n".join(output)
    if len(result) > 4000:
        result = result[:4000] + "\n... [truncated]"
    return result


def run_package_dependency_tool(
    tool_name: str,
    ecosystem: str | None = None,
    package_name: str | None = None,
    version: str | None = None,
    token_env_var: str | None = None,
    source_path: str | None = None,
    project_path: str | None = None,
    approved_paths: list[str] | None = None,
    client: PackageClient | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "executed": False,
        "blocked": False,
        "tool_name": tool_name,
        "ecosystem": ecosystem,
        "package_name": package_name,
        "version": version,
        "source_path": source_path,
        "content_summary": None,
        "context_blocks": [],
        "message": "",
        "safety_notes": [],
    }

    allowed_tools = ("package.metadata.read", "package.changelog.read", "package.advisory.read", "package.manifest.read")
    if tool_name not in allowed_tools:
        result["blocked"] = True
        result["message"] = f"Tool {tool_name} is not allowed or supported."
        return result

    if tool_name == "package.manifest.read":
        if not source_path:
            result["blocked"] = True
            result["message"] = "source_path is required for package.manifest.read."
            return result
        
        try:
            content = _read_local_manifest(source_path, approved_paths)
            guard_result = guard_text_output(content, "Manifest content read")
            if not guard_result["allowed"]:
                result["blocked"] = True
                result["message"] = guard_result["safe_message"]
                return result

            result["executed"] = True
            result["message"] = "Successfully read package manifest."
            result["content_summary"] = f"Read manifest from {os.path.basename(source_path)}."
            
            blocks = result["context_blocks"]
            assert isinstance(blocks, list)
            blocks.append({
                "source": f"local_manifest:{source_path}",
                "tool_name": tool_name,
                "content": content,
                "safe": True,
                "blocked": False,
            })
        except Exception as e:
            result["blocked"] = True
            result["message"] = f"Error reading package manifest: {e}"
        return result

    if tool_name == "package.changelog.read" and (ecosystem == "local_changelog" or source_path):
        if not source_path:
            result["blocked"] = True
            result["message"] = "source_path is required for local changelog."
            return result
            
        try:
            content = _read_local_changelog(source_path, version, approved_paths)
            guard_result = guard_text_output(content, "Changelog content read")
            if not guard_result["allowed"]:
                result["blocked"] = True
                result["message"] = guard_result["safe_message"]
                return result

            result["executed"] = True
            result["message"] = "Successfully read local changelog."
            result["content_summary"] = f"Read changelog from {os.path.basename(source_path)}."
            if version:
                result["content_summary"] += f" (Version filter: {version})"
            
            blocks = result["context_blocks"]
            assert isinstance(blocks, list)
            blocks.append({
                "source": f"local_changelog:{source_path}",
                "tool_name": tool_name,
                "content": content,
                "safe": True,
                "blocked": False,
            })
        except Exception as e:
            result["blocked"] = True
            result["message"] = f"Error reading changelog: {e}"
        return result

    if tool_name == "package.changelog.read" and ecosystem in ("npm", "pypi"):
        if client is None:
            result["blocked"] = True
            result["message"] = "Remote changelog fetching is not implemented/configured."
            return result

    # the rest are ecosystem/package operations
    if not ecosystem or not package_name:
        result["blocked"] = True
        result["message"] = f"ecosystem and package_name are required for {tool_name}."
        return result

    allowed_ecosystems = ("npm", "pypi", "mock")
    if ecosystem not in allowed_ecosystems:
        result["blocked"] = True
        result["message"] = f"Ecosystem {ecosystem} is not supported."
        return result

    if not re.match(r"^[a-zA-Z0-9_\-\.\@\/]+$", package_name):
        result["blocked"] = True
        result["message"] = "Invalid package name format."
        return result

    if version and not re.match(r"^[a-zA-Z0-9_\-\.\^\~\*]+$", version):
        result["blocked"] = True
        result["message"] = "Invalid version format."
        return result

    if token_env_var:
        if not re.match(r"^[A-Z0-9_]+$", token_env_var):
            result["blocked"] = True
            result["message"] = "Invalid token environment variable name."
            return result
        
        if token_env_var not in os.environ:
            notes = result["safety_notes"]
            assert isinstance(notes, list)
            notes.append(f"Token env var {token_env_var} is not set. Execution might fail or be limited.")

    if client is None:
        if tool_name in ("package.metadata.read", "package.advisory.read") and ecosystem in ("npm", "pypi"):
            client = RealPackageClient()
        else:
            result["blocked"] = True
            result["message"] = "Real provider is not implemented/configured for this tool."
            return result

    try:
        if tool_name == "package.metadata.read":
            content = client.read_metadata(ecosystem, package_name, version)
        elif tool_name == "package.changelog.read":
            content = client.read_changelog(ecosystem, package_name, version)
        elif tool_name == "package.advisory.read":
            content = client.read_advisory(ecosystem, package_name, version)
        else:
            content = ""
            
        guard_result = guard_text_output(content, "Package content read")
        
        if not guard_result["allowed"]:
            result["blocked"] = True
            result["message"] = guard_result["safe_message"]
            return result

        result["executed"] = True
        result["message"] = "Successfully read package content."
        result["content_summary"] = f"Read {len(content)} characters of package information."
        
        source = f"{ecosystem}/{package_name}"
        if version:
            source += f"@{version}"
            
        blocks = result["context_blocks"]
        assert isinstance(blocks, list)
        blocks.append({
            "source": source,
            "tool_name": tool_name,
            "content": content,
            "safe": True,
            "blocked": False,
        })
        
    except Exception as e:
        result["blocked"] = True
        result["message"] = f"Error reading package content: {e}"

    return result


def format_package_dependency_result(result: dict[str, object]) -> str:
    lines = [
        f"Package tool: {result['tool_name']}",
        f"Ecosystem: {result['ecosystem']}",
        f"Package: {result['package_name']}",
        f"Version: {result['version'] or 'latest'}",
        f"Executed: {'yes' if result.get('executed') else 'no'}",
        f"Blocked: {'yes' if result.get('blocked') else 'no'}",
        f"Message: {result.get('message')}",
    ]
    
    notes = result.get("safety_notes")
    if notes and isinstance(notes, list):
        lines.append(f"Safety notes: {'; '.join(notes)}")
        
    if result.get("content_summary"):
        lines.append(f"Summary: {result['content_summary']}")
        
    blocks = result.get("context_blocks")
    if blocks and isinstance(blocks, list):
        lines.append(f"Context blocks: {len(blocks)}")
        for i, b in enumerate(blocks):
            safe_val = "yes" if b.get("safe") else "no"
            blocked_val = "yes" if b.get("blocked") else "no"
            lines.append(f"Block {i + 1} - source={b.get('source')} safe={safe_val} blocked={blocked_val}")
            
    return "\n".join(lines)
