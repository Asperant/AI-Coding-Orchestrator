from pathlib import Path

from core.approved_paths import ApprovedPathError, ensure_approved_path
from core.safety import guard_text_output
from tools.mcp_registry import get_registered_tool


def run_controlled_write_tool(
    tool_name: str,
    content: str,
    approved_paths: list[str],
    target_path: str | None = None,
    approval_confirmed: bool = False,
    dry_run: bool = True,
) -> dict[str, object]:
    result: dict[str, object] = {
        "executed": False,
        "preview_only": True,
        "blocked": False,
        "tool_name": tool_name,
        "target_path": target_path,
        "message": "",
        "preview_text": "",
        "safety_notes": [],
        "approval_confirmed": approval_confirmed,
    }

    tool = get_registered_tool(tool_name)
    if not tool or tool.get("tool_type") != "write":
        result["blocked"] = True
        result["message"] = f"Tool {tool_name} is not a valid registered write tool."
        from tools.mcp_audit import build_audit_event_from_controlled_write_result
        result["audit_event"] = build_audit_event_from_controlled_write_result(result)
        return result

    if not approval_confirmed:
        notes = result["safety_notes"]
        assert isinstance(notes, list)
        notes.append("Execution prevented because approval was not confirmed.")
        dry_run = True

    if target_path:
        path_lower = target_path.lower()
        if any(path_lower.endswith(ext) for ext in (".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp", ".c", ".rb", ".php", ".sh", ".jsx", ".tsx")):
            result["blocked"] = True
            result["message"] = "Controlled Write MCP cannot target code files."
            from tools.mcp_audit import build_audit_event_from_controlled_write_result
            result["audit_event"] = build_audit_event_from_controlled_write_result(result)
            return result
        
        try:
            ensure_approved_path(target_path, approved_paths)
        except ApprovedPathError as e:
            result["blocked"] = True
            result["message"] = f"Target path is not approved: {e}"
            from tools.mcp_audit import build_audit_event_from_controlled_write_result
            result["audit_event"] = build_audit_event_from_controlled_write_result(result)
            return result

    guard_result = guard_text_output(content, f"Controlled write ({tool_name})")
    if not guard_result["allowed"]:
        result["blocked"] = True
        result["message"] = guard_result["safe_message"]
        result["preview_text"] = "[REDACTED]"
        from tools.mcp_audit import build_audit_event_from_controlled_write_result
        result["audit_event"] = build_audit_event_from_controlled_write_result(result)
        return result

    result["preview_text"] = content

    if tool_name.startswith("github."):
        notes = result["safety_notes"]
        assert isinstance(notes, list)
        notes.append("GitHub write tools are currently supported as preview-only.")
        dry_run = True

    if tool_name == "memory.save_proposal":
        notes = result["safety_notes"]
        assert isinstance(notes, list)
        notes.append("memory.save_proposal is currently supported as preview-only.")
        dry_run = True

    if tool_name == "project_docs.append" and not target_path:
        result["blocked"] = True
        result["message"] = "project_docs.append requires a target_path."
        from tools.mcp_audit import build_audit_event_from_controlled_write_result
        result["audit_event"] = build_audit_event_from_controlled_write_result(result)
        return result

    if tool_name == "report.export" and not target_path:
        result["blocked"] = True
        result["message"] = "report.export requires a target_path."
        from tools.mcp_audit import build_audit_event_from_controlled_write_result
        result["audit_event"] = build_audit_event_from_controlled_write_result(result)
        return result

    if dry_run:
        result["message"] = "Successfully generated preview."
        result["preview_only"] = True
        result["executed"] = False
        from tools.mcp_audit import build_audit_event_from_controlled_write_result
        result["audit_event"] = build_audit_event_from_controlled_write_result(result)
        return result

    try:
        if target_path:
            p = Path(target_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            if tool_name == "project_docs.append":
                with p.open("a", encoding="utf-8") as f:
                    f.write("\n" + content)
            elif tool_name == "report.export":
                p.write_text(content, encoding="utf-8")
            else:
                result["blocked"] = True
                result["message"] = f"Write not implemented for tool {tool_name}."
                from tools.mcp_audit import build_audit_event_from_controlled_write_result
                result["audit_event"] = build_audit_event_from_controlled_write_result(result)
                return result

        result["executed"] = True
        result["preview_only"] = False
        result["message"] = f"Real write completed using {tool_name}."
    except Exception as e:
        result["blocked"] = True
        result["message"] = f"Write failed: {e}"

    from tools.mcp_audit import build_audit_event_from_controlled_write_result
    result["audit_event"] = build_audit_event_from_controlled_write_result(result)
    return result


def format_controlled_write_result(result: dict[str, object]) -> str:
    lines = [
        f"Write tool: {result['tool_name']}",
        f"Target path: {result['target_path'] or 'none'}",
        f"Executed: {'yes' if result.get('executed') else 'no'}",
        f"Preview only: {'yes' if result.get('preview_only') else 'no'}",
        f"Blocked: {'yes' if result.get('blocked') else 'no'}",
        f"Message: {result.get('message')}",
    ]
    
    notes = result.get("safety_notes")
    if notes and isinstance(notes, list):
        lines.append(f"Safety notes: {'; '.join(notes)}")
        
    preview = result.get("preview_text")
    if preview is not None:
        lines.append(f"Preview:\n{preview}")
            
    return "\n".join(lines)
