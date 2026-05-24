from __future__ import annotations

from pathlib import Path

from project.project_context_reader import EXPECTED_PROJECT_CONTEXT_FILES
from tools.filesystem_gateway import FilesystemGatewayError, read_file
from tools.mcp_context_manager import (
    build_context_block_from_mcp_result,
    compact_context_blocks,
    format_context_blocks,
)
from tools.mcp_gateway import evaluate_mcp_request


def read_project_knowledge(
    project_path: str | Path,
    approved_paths: list[str] | tuple[str, ...] | None,
) -> dict[str, object]:
    decision = evaluate_mcp_request(
        "project_knowledge.read",
        "read",
        target_path=str(project_path),
        approved_paths=approved_paths,
    )
    safety_notes = list(decision.get("safety_notes", []))

    if decision.get("blocked"):
        return {
            "executed": False,
            "blocked": True,
            "found_files": [],
            "missing_files": [],
            "context_blocks": [],
            "message": str(decision.get("blocked_reason") or "Project knowledge read was blocked."),
            "safety_notes": safety_notes,
            "decision": decision,
        }

    project_root = Path(project_path).expanduser().resolve()
    found_files: list[str] = []
    missing_files: list[str] = []
    raw_context_blocks: list[dict[str, object]] = []

    for relative_path in EXPECTED_PROJECT_CONTEXT_FILES:
        relative_path_text = relative_path.as_posix()
        absolute_path = project_root / relative_path
        if not absolute_path.is_file():
            missing_files.append(relative_path_text)
            continue

        found_files.append(relative_path_text)
        try:
            file_content = read_file(absolute_path, approved_paths)
        except FilesystemGatewayError as exc:
            raw_context_blocks.append(
                build_context_block_from_mcp_result(
                    {
                        "executed": False,
                        "blocked": True,
                        "tool_name": "project_knowledge.read",
                        "action": "read",
                        "message": str(exc),
                        "output_text": "",
                        "source_path": str(absolute_path),
                        "decision": decision,
                        "safety_notes": safety_notes,
                    }
                )
            )
            continue

        raw_context_blocks.append(
            build_context_block_from_mcp_result(
                {
                    "executed": True,
                    "blocked": False,
                    "tool_name": "project_knowledge.read",
                    "action": "read",
                    "message": f"Read project knowledge file: {relative_path_text}",
                    "output_text": file_content,
                    "source_path": str(absolute_path),
                    "decision": decision,
                    "safety_notes": safety_notes,
                }
            )
        )

    compacted_context_blocks = compact_context_blocks(raw_context_blocks, max_total_chars=8000)
    message = (
        f"Read {len(found_files)} project knowledge file(s); {len(missing_files)} expected file(s) were missing."
    )

    return {
        "executed": True,
        "blocked": False,
        "found_files": found_files,
        "missing_files": missing_files,
        "context_blocks": compacted_context_blocks,
        "message": message,
        "safety_notes": safety_notes,
        "decision": decision,
    }


def format_project_knowledge_result(result: dict[str, object]) -> str:
    found_files = list(result.get("found_files", []))
    missing_files = list(result.get("missing_files", []))
    context_blocks = list(result.get("context_blocks", []))
    safety_notes = list(result.get("safety_notes", [])) or ["none"]

    return "\n".join(
        [
            f"Executed: {'yes' if result.get('executed') else 'no'}",
            f"Blocked: {'yes' if result.get('blocked') else 'no'}",
            f"Message: {result.get('message') or 'not available'}",
            f"Found docs: {', '.join(found_files) if found_files else 'none'}",
            f"Missing docs: {', '.join(missing_files) if missing_files else 'none'}",
            format_context_blocks(context_blocks),
            f"Safety notes: {'; '.join(str(note) for note in safety_notes)}",
        ]
    )
