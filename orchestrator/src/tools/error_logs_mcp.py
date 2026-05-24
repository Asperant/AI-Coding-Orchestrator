from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from core.approved_paths import ApprovedPathError, ensure_approved_path
from core.safety import guard_text_output
from tools.filesystem_gateway import FilesystemGatewayError, read_file
from tools.mcp_context_manager import (
    build_context_block_from_mcp_result,
    compact_context_blocks,
    format_context_blocks,
)
from tools.mcp_gateway import evaluate_mcp_request


DEFAULT_ERROR_TOKEN_ENV_VAR = "ERROR_MONITORING_TOKEN"
DEFAULT_CONTEXT_BUDGET = 8000
SAFE_ENV_VAR_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")
SUPPORTED_PROVIDERS = {"sentry", "posthog", "local", "mock"}
SUPPORTED_ERROR_LOG_TOOLS = {"error_monitoring.issue.read", "local.dev_logs.read", "local.dev_logs.search"}
LOCAL_LOG_EXTENSIONS = {".log", ".txt", ".out", ".err", ".json", ".ndjson", ".md"}
MAX_FILE_SIZE = 5_000_000
MAX_FILES_SCANNED = 500


class MockErrorLogsClient:
    def __init__(
        self,
        *,
        issues: dict[tuple[str, str | None, int], dict[str, object]] | None = None,
    ) -> None:
        self.issues = issues or {}

    def read_issue(
        self,
        provider: str,
        project_key: str | None,
        issue_id: int,
    ) -> dict[str, object]:
        return dict(self.issues[(provider, project_key, issue_id)])


class RealSentryClient:
    def __init__(self, token: str):
        self.token = token

    def read_issue(self, provider: str, project_key: str | None, issue_id: int) -> dict[str, object]:
        if provider != "sentry":
            raise ValueError(f"RealSentryClient only supports sentry provider, got {provider}")
        
        url = f"https://sentry.io/api/0/issues/{issue_id}/"
        req = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {self.token}',
            'User-Agent': 'AI-Coding-Orchestrator'
        })
        
        try:
            with urllib.request.urlopen(req, timeout=10.0) as response:
                data = json.loads(response.read().decode('utf-8'))
                title = data.get("title", "")
                status = data.get("status", "")
                summary = data.get("culprit", "")
                stack_trace = ""
                metadata = data.get("metadata", {})
                if "value" in metadata:
                    stack_trace = metadata["value"]
                
                return {
                    "title": title,
                    "status": status,
                    "summary": summary,
                    "stack_trace": stack_trace
                }
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ValueError("Issue not found.")
            if e.code in (401, 403):
                raise ValueError("Unauthorized or forbidden to access Sentry.")
            raise ValueError(f"HTTP error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            if isinstance(e.reason, TimeoutError):
                raise ValueError("Network request timed out.")
            raise ValueError(f"Network error: {e.reason}")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON received from registry.")


def _is_safe_env_var_name(name: str) -> bool:
    return bool(SAFE_ENV_VAR_PATTERN.fullmatch(name))


def _blocked_result(
    *,
    tool_name: str,
    provider: str,
    message: str,
    safety_notes: list[str],
    decision: dict[str, object],
) -> dict[str, object]:
    return {
        "executed": False,
        "blocked": True,
        "tool_name": tool_name,
        "provider": provider,
        "content_summary": "not available",
        "raw_content": None,
        "context_blocks": [],
        "message": message,
        "safety_notes": safety_notes,
        "decision": decision,
    }


def _parse_issue_id(issue_id: int | str | None) -> tuple[int | None, str | None]:
    if issue_id in (None, ""):
        return None, "issue_id is required for error monitoring issue reads."
    if isinstance(issue_id, int):
        if issue_id > 0:
            return issue_id, None
        return None, "issue_id must be a positive integer."

    issue_text = str(issue_id).strip()
    if not issue_text.isdigit():
        return None, "issue_id must be numeric."

    issue_value = int(issue_text)
    if issue_value <= 0:
        return None, "issue_id must be a positive integer."
    return issue_value, None


def _summarize_stack_trace(stack_trace: str) -> str:
    lines = [line.rstrip() for line in stack_trace.splitlines() if line.strip()]
    if not lines:
        return "Stack trace summary: none"
    preview_lines = lines[:6]
    suffix = ""
    if len(lines) > len(preview_lines):
        suffix = f" ... ({len(lines)} total line(s))"
    return "Stack trace summary: " + " | ".join(preview_lines) + suffix


def _build_issue_text(
    provider: str,
    project_key: str | None,
    issue_id: int,
    payload: dict[str, object],
) -> tuple[str, str]:
    title = str(payload.get("title") or "Untitled error issue")
    status = str(payload.get("status") or "unknown")
    summary = str(payload.get("summary") or "")
    stack_trace = str(payload.get("stack_trace") or "")

    lines = [
        f"Error monitoring issue: {provider}",
        f"Issue id: {issue_id}",
        f"Title: {title}",
        f"Status: {status}",
    ]
    if project_key:
        lines.append(f"Project key: {project_key}")
    if summary:
        lines.append(f"Summary: {summary}")
    if stack_trace:
        lines.append(_summarize_stack_trace(stack_trace))

    return f"Issue #{issue_id}: {title}", "\n".join(lines)


def _build_local_log_text(log_path: Path, file_content: str) -> tuple[str, str]:
    lines = file_content.splitlines()
    return (
        f"Local log: {log_path.name} ({len(lines)} line(s))",
        file_content,
    )


def _is_safe_log_file(filepath: Path) -> bool:
    if not filepath.is_file():
        return False
    if filepath.suffix.lower() not in LOCAL_LOG_EXTENSIONS:
        return False
    try:
        if filepath.stat().st_size > MAX_FILE_SIZE:
            return False
    except OSError:
        return False
    return True


def _search_local_logs(log_path: Path, query: str) -> str:
    query_lower = query.lower()
    results = []
    files_scanned = 0

    if log_path.is_file():
        targets = [log_path]
    else:
        targets = log_path.rglob("*")

    for filepath in targets:
        if files_scanned >= MAX_FILES_SCANNED:
            break
            
        if not _is_safe_log_file(filepath):
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
                        rel_path = filepath.relative_to(log_path) if log_path.is_dir() else filepath.name
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


def _ensure_log_path_inside_project(
    project_path: str | Path | None,
    log_path: str | Path | None,
    approved_paths: list[str] | tuple[str, ...] | None,
) -> tuple[Path | None, Path | None, str | None]:
    if project_path in (None, ""):
        return None, None, "project_path is required for local.dev_logs.read."
    if log_path in (None, ""):
        return None, None, "log_path is required for local.dev_logs.read."

    try:
        resolved_project_path = ensure_approved_path(project_path, approved_paths)
        resolved_log_path = ensure_approved_path(log_path, approved_paths)
    except ApprovedPathError as exc:
        return None, None, str(exc)

    try:
        resolved_log_path.relative_to(resolved_project_path)
    except ValueError:
        return None, None, "Local log path must stay inside the approved project path."

    return resolved_project_path, resolved_log_path, None


def run_error_logs_tool(
    tool_name: str,
    provider: str,
    *,
    project_key: str | None = None,
    project_path: str | Path | None = None,
    issue_id: int | str | None = None,
    log_path: str | Path | None = None,
    query: str | None = None,
    token_env_var: str = DEFAULT_ERROR_TOKEN_ENV_VAR,
    approved_paths: list[str] | tuple[str, ...] | None = None,
    client: object | None = None,
) -> dict[str, object]:
    target_path = str(log_path) if tool_name in {"local.dev_logs.read", "local.dev_logs.search"} and log_path else None
    decision = evaluate_mcp_request(
        tool_name,
        "read",
        target_path=target_path,
        approved_paths=approved_paths,
    )
    safety_notes = list(decision.get("safety_notes", []))

    if tool_name not in SUPPORTED_ERROR_LOG_TOOLS:
        return _blocked_result(
            tool_name=tool_name,
            provider=provider,
            message=f"Unsupported error/logs MCP tool: {tool_name}",
            safety_notes=safety_notes + ["Only registered read-only error/logs MCP tools are supported."],
            decision=decision,
        )

    if decision.get("blocked"):
        return _blocked_result(
            tool_name=tool_name,
            provider=provider,
            message=str(decision.get("blocked_reason") or "Error/logs MCP request was blocked."),
            safety_notes=safety_notes,
            decision=decision,
        )

    normalized_provider = str(provider or "").strip().lower()
    if normalized_provider not in SUPPORTED_PROVIDERS:
        return _blocked_result(
            tool_name=tool_name,
            provider=normalized_provider or "unknown",
            message=f"Unsupported provider: {provider}",
            safety_notes=safety_notes,
            decision=decision,
        )

    token_env_var_text = str(token_env_var or DEFAULT_ERROR_TOKEN_ENV_VAR).strip()
    if token_env_var_text and not _is_safe_env_var_name(token_env_var_text):
        return _blocked_result(
            tool_name=tool_name,
            provider=normalized_provider,
            message="Error monitoring token environment variable name is not safe.",
            safety_notes=safety_notes,
            decision=decision,
        )

    if tool_name in {"local.dev_logs.read", "local.dev_logs.search"}:
        if normalized_provider != "local":
            return _blocked_result(
                tool_name=tool_name,
                provider=normalized_provider,
                message=f"{tool_name} only supports provider=local.",
                safety_notes=safety_notes,
                decision=decision,
            )

        _, resolved_log_path, log_error = _ensure_log_path_inside_project(
            project_path,
            log_path,
            approved_paths,
        )
        if log_error is not None or resolved_log_path is None:
            return _blocked_result(
                tool_name=tool_name,
                provider=normalized_provider,
                message=log_error or "Local log validation failed.",
                safety_notes=safety_notes,
                decision=decision,
            )
            
        if tool_name == "local.dev_logs.search" and not query:
            return _blocked_result(
                tool_name=tool_name,
                provider=normalized_provider,
                message="query is required for local.dev_logs.search.",
                safety_notes=safety_notes,
                decision=decision,
            )

        try:
            if tool_name == "local.dev_logs.read":
                if not _is_safe_log_file(resolved_log_path):
                    return _blocked_result(
                        tool_name=tool_name,
                        provider=normalized_provider,
                        message="File is not a supported log file or is too large.",
                        safety_notes=safety_notes,
                        decision=decision,
                    )
                file_content = read_file(resolved_log_path, approved_paths)
                content_summary, output_text = _build_local_log_text(resolved_log_path, file_content)
            else:
                output_text = _search_local_logs(resolved_log_path, query)
                content_summary = f"Search matches for '{query}' in {resolved_log_path.name}"
        except Exception as exc:
            return _blocked_result(
                tool_name=tool_name,
                provider=normalized_provider,
                message=str(exc),
                safety_notes=safety_notes,
                decision=decision,
            )

        guard_result = guard_text_output(output_text, "Local dev logs MCP output")
        blocked = not guard_result["allowed"]
        safe_output = str(guard_result["safe_message"]) if blocked else output_text
        context_block = build_context_block_from_mcp_result(
            {
                "executed": not blocked,
                "blocked": blocked,
                "tool_name": tool_name,
                "action": "read",
                "message": (
                    "Local dev log content was blocked because secret-like content was detected."
                    if blocked
                    else f"{tool_name} completed successfully."
                ),
                "output_text": safe_output,
                "source_path": str(resolved_log_path),
                "decision": decision,
                "safety_notes": safety_notes,
            }
        )
        context_blocks = compact_context_blocks([context_block], max_total_chars=DEFAULT_CONTEXT_BUDGET)
        final_safety_notes = safety_notes + [
            "Local file read only: no file write was performed.",
        ]
        if blocked:
            final_safety_notes.append("Secret-like local log content was blocked or redacted.")

        return {
            "executed": not blocked,
            "blocked": blocked,
            "tool_name": tool_name,
            "provider": normalized_provider,
            "content_summary": content_summary,
            "raw_content": None if blocked else output_text,
            "context_blocks": context_blocks,
            "message": (
                "Local dev log content was blocked because secret-like content was detected."
                if blocked
                else f"{tool_name} completed successfully."
            ),
            "safety_notes": final_safety_notes,
            "decision": decision,
        }

    if normalized_provider == "local":
        return _blocked_result(
            tool_name=tool_name,
            provider=normalized_provider,
            message="error_monitoring.issue.read does not support provider=local.",
            safety_notes=safety_notes,
            decision=decision,
        )

    parsed_issue_id, issue_error = _parse_issue_id(issue_id)
    if issue_error is not None or parsed_issue_id is None:
        return _blocked_result(
            tool_name=tool_name,
            provider=normalized_provider,
            message=issue_error or "Issue id validation failed.",
            safety_notes=safety_notes,
            decision=decision,
        )

    if normalized_provider in {"sentry", "posthog"}:
        token_value = os.environ.get(token_env_var_text)
        if not token_value:
            return _blocked_result(
                tool_name=tool_name,
                provider=normalized_provider,
                message=f"Error monitoring token environment variable {token_env_var_text} is not set.",
                safety_notes=safety_notes + ["No raw token value was read or printed."],
                decision=decision,
            )
            
        if client is None and normalized_provider == "sentry":
            client = RealSentryClient(token_value)

    if client is None:
        return _blocked_result(
            tool_name=tool_name,
            provider=normalized_provider,
            message="Real provider is not implemented/configured for this tool.",
            safety_notes=safety_notes,
            decision=decision,
        )

    try:
        payload = client.read_issue(normalized_provider, project_key, parsed_issue_id)
        content_summary, output_text = _build_issue_text(
            normalized_provider,
            project_key,
            parsed_issue_id,
            payload,
        )
    except Exception as exc:
        return _blocked_result(
            tool_name=tool_name,
            provider=normalized_provider,
            message=f"Error/logs mock client failed safely: {exc}",
            safety_notes=safety_notes + ["No raw token value was printed."],
            decision=decision,
        )

    guard_result = guard_text_output(output_text, "Error monitoring MCP output")
    blocked = not guard_result["allowed"]
    safe_output = str(guard_result["safe_message"]) if blocked else output_text
    source_suffix = f"{project_key or 'unknown'}#{parsed_issue_id}"
    context_block = build_context_block_from_mcp_result(
        {
            "executed": not blocked,
            "blocked": blocked,
            "tool_name": tool_name,
            "action": "read",
            "message": (
                "Error monitoring content was blocked because secret-like content was detected."
                if blocked
                else f"{tool_name} completed successfully."
            ),
            "output_text": safe_output,
            "source_path": f"{normalized_provider}:{source_suffix}",
            "decision": decision,
            "safety_notes": safety_notes,
        }
    )
    context_blocks = compact_context_blocks([context_block], max_total_chars=DEFAULT_CONTEXT_BUDGET)
    final_safety_notes = safety_notes + [
        "Mock error monitoring client only: no real API call was performed.",
        "No raw token value was printed.",
    ]
    if blocked:
        final_safety_notes.append("Secret-like error monitoring content was blocked or redacted.")

    return {
        "executed": not blocked,
        "blocked": blocked,
        "tool_name": tool_name,
        "provider": normalized_provider,
        "content_summary": content_summary,
        "raw_content": None if blocked else output_text,
        "context_blocks": context_blocks,
        "message": (
            "Error monitoring content was blocked because secret-like content was detected."
            if blocked
            else f"{tool_name} completed successfully."
        ),
        "safety_notes": final_safety_notes,
        "decision": decision,
    }


def format_error_logs_result(result: dict[str, object]) -> str:
    safety_notes = list(result.get("safety_notes", [])) or ["none"]
    return "\n".join(
        [
            f"Executed: {'yes' if result.get('executed') else 'no'}",
            f"Blocked: {'yes' if result.get('blocked') else 'no'}",
            f"Tool name: {result.get('tool_name') or 'unknown'}",
            f"Provider: {result.get('provider') or 'unknown'}",
            f"Content summary: {result.get('content_summary') or 'not available'}",
            f"Message: {result.get('message') or 'not available'}",
            format_context_blocks(list(result.get('context_blocks', []))),
            f"Safety notes: {'; '.join(str(note) for note in safety_notes)}",
        ]
    )
