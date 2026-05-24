import json
import os
import re
import urllib.error
import urllib.request
from typing import Protocol

from core.safety import guard_text_output


class FigmaDesignClient(Protocol):
    def read_frame(self, file_key: str, frame_id: str) -> str:
        ...

    def read_component(self, file_key: str, component_id: str) -> str:
        ...

    def read_tokens(self, file_key: str) -> str:
        ...


class MockFigmaDesignClient:
    def __init__(
        self,
        frames: dict[tuple[str, str], str] | None = None,
        components: dict[tuple[str, str], str] | None = None,
        tokens: dict[str, str] | None = None,
    ):
        self._frames = frames or {}
        self._components = components or {}
        self._tokens = tokens or {}

    def read_frame(self, file_key: str, frame_id: str) -> str:
        return self._frames.get((file_key, frame_id), f"Mock frame content for: {file_key}/{frame_id}")

    def read_component(self, file_key: str, component_id: str) -> str:
        return self._components.get((file_key, component_id), f"Mock component content for: {file_key}/{component_id}")

    def read_tokens(self, file_key: str) -> str:
        return self._tokens.get(file_key, f"Mock tokens content for: {file_key}")


class RealFigmaClient:
    def __init__(self, token: str):
        self.token = token
        
    def _fetch_node(self, file_key: str, node_id: str) -> dict[str, object]:
        # Clean the node_id if needed, but usually we pass it directly
        url = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={node_id}"
        req = urllib.request.Request(url, headers={
            'X-Figma-Token': self.token,
            'User-Agent': 'AI-Coding-Orchestrator'
        })
        try:
            with urllib.request.urlopen(req, timeout=10.0) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ValueError("File or node not found.")
            if e.code in (401, 403):
                raise ValueError("Unauthorized or forbidden to access Figma file.")
            raise ValueError(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            if isinstance(e.reason, TimeoutError):
                raise ValueError("Network request timed out.")
            raise ValueError(f"Network error: {e.reason}")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON received from Figma.")
            
    def _extract_summary(self, data: dict[str, object], node_id: str) -> str:
        nodes = data.get("nodes", {})
        # Note: the key in 'nodes' might have URL-decoded colons instead of url-encoded %3A
        node_id_decoded = urllib.parse.unquote(node_id) if "%" in node_id else node_id.replace("%3A", ":")
        
        # If not found directly, try to find a key matching after unquoting
        node_data = None
        if node_id in nodes:
            node_data = nodes[node_id]
        elif node_id_decoded in nodes:
            node_data = nodes[node_id_decoded]
        else:
            raise ValueError(f"Node {node_id} not found in response.")
            
        if not isinstance(node_data, dict):
            raise ValueError("Invalid node data format.")
            
        document = node_data.get("document", {})
        if not isinstance(document, dict):
            raise ValueError("Invalid document data format.")
            
        name = document.get("name", "Unknown")
        type_ = document.get("type", "Unknown")
        children = document.get("children", [])
        fills = document.get("fills", [])
        bbox = document.get("absoluteBoundingBox", {})
        
        summary = [
            f"Name: {name}",
            f"Type: {type_}",
            f"Children: {len(children) if isinstance(children, list) else 0}",
            f"Fills: {len(fills) if isinstance(fills, list) else 0}"
        ]
        
        if bbox and isinstance(bbox, dict):
            w = bbox.get("width", 0)
            h = bbox.get("height", 0)
            summary.append(f"Size: {w}x{h}")
            
        component_id = node_data.get("componentId")
        if component_id:
            summary.append(f"Component ID: {component_id}")
            
        return "\n".join(summary)

    def read_frame(self, file_key: str, frame_id: str) -> str:
        data = self._fetch_node(file_key, frame_id)
        return self._extract_summary(data, frame_id)

    def read_component(self, file_key: str, component_id: str) -> str:
        data = self._fetch_node(file_key, component_id)
        return self._extract_summary(data, component_id)

    def read_tokens(self, file_key: str) -> str:
        raise NotImplementedError("Tokens endpoint is not supported yet.")


def run_figma_design_tool(
    tool_name: str,
    file_key: str | None = None,
    frame_id: str | None = None,
    component_id: str | None = None,
    token_env_var: str | None = None,
    client: FigmaDesignClient | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "executed": False,
        "blocked": False,
        "tool_name": tool_name,
        "file_key": file_key,
        "item_id": frame_id or component_id,
        "content_summary": None,
        "context_blocks": [],
        "message": "",
        "safety_notes": [],
    }

    allowed_tools = ("figma.frame.read", "figma.component.read", "figma.tokens.read")
    if tool_name not in allowed_tools:
        result["blocked"] = True
        result["message"] = f"Tool {tool_name} is not allowed or supported."
        return result

    if file_key:
        if not re.match(r"^[a-zA-Z0-9_\-]+$", file_key):
            result["blocked"] = True
            result["message"] = "Invalid file key format."
            return result

    if frame_id:
        if not re.match(r"^[a-zA-Z0-9_\-\:]+$", frame_id):
            result["blocked"] = True
            result["message"] = "Invalid frame ID format."
            return result
            
    if component_id:
        if not re.match(r"^[a-zA-Z0-9_\-\:]+$", component_id):
            result["blocked"] = True
            result["message"] = "Invalid component ID format."
            return result

    if token_env_var:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", token_env_var):
            result["blocked"] = True
            result["message"] = "Invalid token environment variable name."
            return result
        if token_env_var not in os.environ:
            notes = result["safety_notes"]
            assert isinstance(notes, list)
            notes.append(f"Token env var {token_env_var} is not set. Execution might fail or be limited.")

    if client is None:
        if token_env_var and token_env_var in os.environ:
            if tool_name in ("figma.frame.read", "figma.component.read"):
                client = RealFigmaClient(os.environ[token_env_var])
            elif tool_name == "figma.tokens.read":
                result["blocked"] = True
                result["message"] = "Tool figma.tokens.read is unavailable natively."
                return result

    if client is None:
        result["blocked"] = True
        result["message"] = "Real provider is not implemented/configured or token is missing."
        return result

    try:
        content = ""
        source = ""
        
        if tool_name == "figma.frame.read":
            if not file_key or not frame_id:
                result["blocked"] = True
                result["message"] = "Tool figma.frame.read requires file_key and frame_id."
                return result
            content = client.read_frame(file_key, frame_id)
            source = f"figma:frame:{file_key}/{frame_id}"
            
        elif tool_name == "figma.component.read":
            if not file_key or not component_id:
                result["blocked"] = True
                result["message"] = "Tool figma.component.read requires file_key and component_id."
                return result
            content = client.read_component(file_key, component_id)
            source = f"figma:component:{file_key}/{component_id}"
            
        elif tool_name == "figma.tokens.read":
            if not file_key:
                result["blocked"] = True
                result["message"] = "Tool figma.tokens.read requires file_key."
                return result
            content = client.read_tokens(file_key)
            source = f"figma:tokens:{file_key}"
            
        else:
            content = ""
            
        guard_result = guard_text_output(content, "Figma design content")
        if not guard_result["allowed"]:
            result["blocked"] = True
            result["message"] = guard_result["safe_message"]
            return result

        result["executed"] = True
        result["message"] = "Successfully read Figma design content."
        result["content_summary"] = f"Read {len(content)} characters of design data."
        
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
        result["message"] = f"Error reading Figma design content: {e}"

    return result


def format_figma_design_result(result: dict[str, object]) -> str:
    lines = [
        f"Figma tool: {result['tool_name']}",
        f"File key: {result['file_key'] or 'none'}",
        f"Item ID: {result['item_id'] or 'none'}",
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
