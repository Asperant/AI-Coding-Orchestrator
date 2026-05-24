import os
import re
from pathlib import Path
from typing import Protocol

from core.approved_paths import ApprovedPathError, ensure_approved_path
from core.safety import guard_text_output
from tools.filesystem_gateway import read_file

ALLOWED_EXTENSIONS = {
    ".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml", 
    ".py", ".js", ".ts", ".tsx", ".jsx"
}
MAX_FILE_SIZE = 1_000_000
MAX_FILES_SCANNED = 1000

def _is_safe_text_file(filepath: Path) -> bool:
    if not filepath.is_file():
        return False
    if filepath.suffix.lower() not in ALLOWED_EXTENSIONS:
        return False
    try:
        if filepath.stat().st_size > MAX_FILE_SIZE:
            return False
    except OSError:
        return False
    return True

def _search_local_docs(source_path: str, query: str, approved_paths: list[str]) -> str:
    source = Path(source_path).resolve()
    query_lower = query.lower()
    results = []
    files_scanned = 0

    if source.is_file():
        targets = [source]
    else:
        targets = source.rglob("*")

    for filepath in targets:
        if files_scanned >= MAX_FILES_SCANNED:
            break
            
        if not _is_safe_text_file(filepath):
            continue

        files_scanned += 1
        
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if query_lower in line.lower():
                    snippet = line.strip()
                    if len(snippet) > 200:
                        snippet = snippet[:197] + "..."
                        
                    guard_result = guard_text_output(snippet, "search snippet")
                    if not guard_result["allowed"]:
                        snippet = "[REDACTED secret-like content]"
                        
                    try:
                        rel_path = filepath.relative_to(source) if source.is_dir() else filepath.name
                    except ValueError:
                        rel_path = filepath.name
                        
                    results.append(f"{rel_path}:{i+1} - {snippet}")
                    if len(results) >= 50:
                        break
            if len(results) >= 50:
                break
        except Exception:
            continue
            
    if not results:
        return "No matches found."
    return "\n".join(results)



class DocsResearchClient(Protocol):
    def search_notebook(self, query: str) -> str:
        ...

    def search_docs(self, query: str) -> str:
        ...

    def read_docs_page(self, page_id: str) -> str:
        ...


class MockDocsResearchClient:
    def __init__(
        self,
        notebook_searches: dict[str, str] | None = None,
        docs_searches: dict[str, str] | None = None,
        docs_pages: dict[str, str] | None = None,
    ):
        self._notebook_searches = notebook_searches or {}
        self._docs_searches = docs_searches or {}
        self._docs_pages = docs_pages or {}

    def search_notebook(self, query: str) -> str:
        return self._notebook_searches.get(query, f"Mock notebook search results for: {query}")

    def search_docs(self, query: str) -> str:
        return self._docs_searches.get(query, f"Mock docs search results for: {query}")

    def read_docs_page(self, page_id: str) -> str:
        return self._docs_pages.get(page_id, f"Mock docs page content for: {page_id}")


def run_docs_research_tool(
    tool_name: str,
    provider: str,
    query: str | None = None,
    source_path: str | None = None,
    page_id: str | None = None,
    token_env_var: str | None = None,
    client: DocsResearchClient | None = None,
    approved_paths: list[str] | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "executed": False,
        "blocked": False,
        "tool_name": tool_name,
        "provider": provider,
        "query": query,
        "content_summary": None,
        "context_blocks": [],
        "message": "",
        "safety_notes": [],
    }
    
    if approved_paths is None:
        approved_paths = []

    allowed_tools = ("notebook.search", "docs.search", "docs.page.read")
    if tool_name not in allowed_tools:
        result["blocked"] = True
        result["message"] = f"Tool {tool_name} is not allowed or supported."
        return result

    allowed_providers = ("notebooklm", "local_docs", "official_docs", "mock")
    if provider not in allowed_providers:
        result["blocked"] = True
        result["message"] = f"Provider {provider} is not supported."
        return result

    if query is not None:
        if len(query) > 500:
            result["blocked"] = True
            result["message"] = "Query is too long."
            return result
        if not re.match(r"^[\w\s\-\.\?\!\"\'\,]+$", query):
            result["blocked"] = True
            result["message"] = "Query contains unsafe characters."
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

    if provider == "local_docs" and source_path:
        try:
            ensure_approved_path(source_path, approved_paths)
        except ApprovedPathError as e:
            result["blocked"] = True
            result["message"] = f"Source path is not approved: {e}"
            return result

    if client is None:
        if provider != "local_docs":
            result["blocked"] = True
            result["message"] = "Real provider is not implemented/configured for this tool."
            return result

    try:
        content = ""
        source_identifier = ""
        
        if provider == "local_docs":
            if not source_path:
                result["blocked"] = True
                result["message"] = "Local docs provider requires source_path."
                return result
                
            path_obj = Path(source_path).resolve()
            
            if tool_name == "docs.search":
                if not query:
                    result["blocked"] = True
                    result["message"] = "docs.search requires a query."
                    return result
                content = _search_local_docs(source_path, query, approved_paths)
                source_identifier = f"local_docs:search:{source_path}"
                
            elif tool_name == "docs.page.read":
                if not _is_safe_text_file(path_obj):
                    result["blocked"] = True
                    result["message"] = "File is not a supported text file or is too large."
                    return result
                content = path_obj.read_text(encoding="utf-8", errors="replace")
                source_identifier = f"local_docs:page:{source_path}"
                
            else:
                result["blocked"] = True
                result["message"] = f"Tool {tool_name} not supported by local_docs provider."
                return result
        else:
            if tool_name == "notebook.search":
                content = client.search_notebook(query or "")
                source_identifier = f"{provider}:search:{query}"
            elif tool_name == "docs.search":
                content = client.search_docs(query or "")
                source_identifier = f"{provider}:search:{query}"
            elif tool_name == "docs.page.read":
                content = client.read_docs_page(page_id or "")
                source_identifier = f"{provider}:page:{page_id}"
            else:
                content = ""
                
        guard_result = guard_text_output(content, "Docs research content")
        if not guard_result["allowed"]:
            result["blocked"] = True
            result["message"] = guard_result["safe_message"]
            return result

        result["executed"] = True
        result["message"] = "Successfully read docs/research content."
        result["content_summary"] = f"Read {len(content)} characters."
        
        blocks = result["context_blocks"]
        assert isinstance(blocks, list)
        blocks.append({
            "source": source_identifier,
            "tool_name": tool_name,
            "content": content,
            "safe": True,
            "blocked": False,
        })
        
    except Exception as e:
        result["blocked"] = True
        result["message"] = f"Error reading docs/research content: {e}"

    return result

def format_docs_research_result(result: dict[str, object]) -> str:
    lines = [
        f"Docs tool: {result['tool_name']}",
        f"Provider: {result['provider']}",
        f"Query: {result['query'] or 'none'}",
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
