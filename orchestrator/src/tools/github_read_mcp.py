from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass

from core.safety import guard_text_output
from tools.mcp_context_manager import (
    build_context_block_from_mcp_result,
    compact_context_blocks,
    format_context_blocks,
)
from tools.mcp_gateway import evaluate_mcp_request


DEFAULT_GITHUB_TOKEN_ENV_VAR = "GITHUB_TOKEN"
DEFAULT_CONTEXT_BUDGET = 8000
DEFAULT_GH_TIMEOUT_SECONDS = 30
SAFE_REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SAFE_ENV_VAR_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")
SUPPORTED_GITHUB_READ_TOOLS = {
    "github.issue.read",
    "github.pr.read",
    "github.pr.changed_files",
    "github.ci.status",
}
SUPPORTED_GITHUB_CLIENTS = {"mock", "gh"}


@dataclass
class GitHubReadCommandResult:
    ok: bool
    stdout: str
    stderr: str
    return_code: int
    timed_out: bool
    unavailable_reason: str | None = None


class MockGitHubReadClient:
    def __init__(
        self,
        *,
        issues: dict[tuple[str, int], dict[str, object]] | None = None,
        pull_requests: dict[tuple[str, int], dict[str, object]] | None = None,
        changed_files: dict[tuple[str, int], list[str]] | None = None,
        ci_statuses: dict[tuple[str, int | None], dict[str, object]] | None = None,
    ) -> None:
        self.issues = issues or {}
        self.pull_requests = pull_requests or {}
        self.changed_files = changed_files or {}
        self.ci_statuses = ci_statuses or {}

    def read_issue(self, repo: str, issue_number: int) -> dict[str, object]:
        return dict(self.issues[(repo, issue_number)])

    def read_pull_request(self, repo: str, pr_number: int) -> dict[str, object]:
        return dict(self.pull_requests[(repo, pr_number)])

    def read_pull_request_changed_files(self, repo: str, pr_number: int) -> list[str]:
        return list(self.changed_files[(repo, pr_number)])

    def read_ci_status(self, repo: str, pr_number: int | None = None) -> dict[str, object]:
        if (repo, pr_number) in self.ci_statuses:
            return dict(self.ci_statuses[(repo, pr_number)])
        return dict(self.ci_statuses[repo])


class GhCliGitHubReadClient:
    def __init__(self, *, timeout_seconds: int = DEFAULT_GH_TIMEOUT_SECONDS) -> None:
        self.timeout_seconds = timeout_seconds

    def _run_json_command(self, args: list[str]) -> object:
        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                shell=False,
                timeout=self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("gh CLI is not installed or not available on PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("gh CLI command timed out.") from exc

        if completed.returncode != 0:
            stderr_text = (completed.stderr or "").strip()
            if "authentication" in stderr_text.lower() or "not logged in" in stderr_text.lower():
                raise RuntimeError("gh CLI authentication is unavailable or not logged in.")
            raise RuntimeError(
                f"gh CLI read command failed with return code {completed.returncode}."
            )

        try:
            return json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError("gh CLI returned invalid JSON for a read-only command.") from exc

    def read_issue(self, repo: str, issue_number: int) -> dict[str, object]:
        payload = self._run_json_command(
            [
                "gh",
                "issue",
                "view",
                str(issue_number),
                "--repo",
                repo,
                "--json",
                "title,body,state,labels,url",
            ]
        )
        if not isinstance(payload, dict):
            raise RuntimeError("gh issue view returned an unexpected payload shape.")
        return dict(payload)

    def read_pull_request(self, repo: str, pr_number: int) -> dict[str, object]:
        payload = self._run_json_command(
            [
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--repo",
                repo,
                "--json",
                "title,body,state,files,url",
            ]
        )
        if not isinstance(payload, dict):
            raise RuntimeError("gh pr view returned an unexpected payload shape.")
        return dict(payload)

    def read_pull_request_changed_files(self, repo: str, pr_number: int) -> list[str]:
        payload = self._run_json_command(
            [
                "gh",
                "pr",
                "view",
                str(pr_number),
                "--repo",
                repo,
                "--json",
                "files",
            ]
        )
        if not isinstance(payload, dict):
            raise RuntimeError("gh pr files view returned an unexpected payload shape.")
        files = payload.get("files", [])
        if not isinstance(files, list):
            raise RuntimeError("gh pr files payload was not a list.")
        changed_files: list[str] = []
        for item in files:
            if isinstance(item, dict):
                changed_files.append(str(item.get("path") or "unknown"))
            else:
                changed_files.append(str(item))
        return changed_files

    def read_ci_status(self, repo: str, pr_number: int | None = None) -> dict[str, object]:
        payload = self._run_json_command(
            [
                "gh",
                "run",
                "list",
                "--repo",
                repo,
                "--limit",
                "5",
                "--json",
                "status,conclusion,name,url",
            ]
        )
        if not isinstance(payload, list):
            raise RuntimeError("gh run list returned an unexpected payload shape.")

        normalized_checks: list[str] = []
        overall_status = "unavailable"
        overall_summary = "No CI runs were returned."

        if payload:
            first_item = payload[0] if isinstance(payload[0], dict) else {}
            overall_status = str(first_item.get("conclusion") or first_item.get("status") or "unknown")
            overall_summary = f"Recent CI runs available: {len(payload)}"

        for item in payload:
            if isinstance(item, dict):
                normalized_checks.append(
                    f"{item.get('name', 'unknown')}: {item.get('conclusion') or item.get('status') or 'unknown'}"
                )
            else:
                normalized_checks.append(str(item))

        return {
            "status": overall_status,
            "summary": overall_summary,
            "checks": normalized_checks,
            "pr_number": pr_number,
        }


def _is_safe_env_var_name(name: str) -> bool:
    return bool(SAFE_ENV_VAR_PATTERN.fullmatch(name))


def _parse_item_id(raw_value: int | str | None, label: str) -> tuple[int | None, str | None]:
    if raw_value in (None, ""):
        return None, f"{label} is required for this GitHub read tool."
    if isinstance(raw_value, int):
        if raw_value > 0:
            return raw_value, None
        return None, f"{label} must be a positive integer."

    raw_text = str(raw_value).strip()
    if not raw_text.isdigit():
        return None, f"{label} must be numeric."

    parsed_value = int(raw_text)
    if parsed_value <= 0:
        return None, f"{label} must be a positive integer."
    return parsed_value, None


def _validation_error_result(
    *,
    tool_name: str,
    repo: str,
    item_id: int | None,
    message: str,
    safety_notes: list[str],
    decision: dict[str, object],
) -> dict[str, object]:
    return {
        "executed": False,
        "blocked": True,
        "tool_name": tool_name,
        "repo": repo,
        "item_id": item_id,
        "content_summary": "not available",
        "raw_content": None,
        "context_blocks": [],
        "message": message,
        "safety_notes": safety_notes,
        "decision": decision,
    }


def _build_issue_text(repo: str, issue_number: int, payload: dict[str, object]) -> tuple[str, str]:
    title = str(payload.get("title") or "Untitled issue")
    state = str(payload.get("state") or "unknown")
    body = str(payload.get("body") or "")
    url = str(payload.get("url") or "")
    labels = payload.get("labels", [])
    label_names = [
        str(item.get("name") or item)
        for item in labels
    ] if isinstance(labels, list) else []
    lines = [
        f"GitHub issue: {repo}#{issue_number}",
        f"Title: {title}",
        f"State: {state}",
    ]
    if label_names:
        lines.append("Labels: " + ", ".join(label_names))
    if url:
        lines.append(f"URL: {url}")
    if body:
        lines.append(f"Body: {body}")
    return f"Issue #{issue_number}: {title}", "\n".join(lines)


def _build_pr_text(repo: str, pr_number: int, payload: dict[str, object]) -> tuple[str, str]:
    title = str(payload.get("title") or "Untitled pull request")
    state = str(payload.get("state") or "unknown")
    body = str(payload.get("body") or "")
    url = str(payload.get("url") or "")
    files = payload.get("files", [])
    file_names = [
        str(item.get("path") or item)
        for item in files
    ] if isinstance(files, list) else []
    lines = [
        f"GitHub pull request: {repo}#{pr_number}",
        f"Title: {title}",
        f"State: {state}",
    ]
    if url:
        lines.append(f"URL: {url}")
    if file_names:
        lines.append("Files: " + ", ".join(file_names[:10]))
    if body:
        lines.append(f"Body: {body}")
    return f"PR #{pr_number}: {title}", "\n".join(lines)


def _build_changed_files_text(repo: str, pr_number: int, changed_files: list[str]) -> tuple[str, str]:
    lines = [f"GitHub PR changed files: {repo}#{pr_number}"]
    if changed_files:
        lines.extend(f"- {file_path}" for file_path in changed_files)
    else:
        lines.append("- none")
    return f"PR #{pr_number} changed files: {len(changed_files)}", "\n".join(lines)


def _build_ci_status_text(repo: str, payload: dict[str, object], pr_number: int | None = None) -> tuple[str, str]:
    status = str(payload.get("status") or "unknown")
    summary = str(payload.get("summary") or "")
    checks = list(payload.get("checks", []))
    lines = [f"GitHub CI status: {repo}", f"Status: {status}"]
    if pr_number is not None:
        lines.append(f"PR number: {pr_number}")
    if summary:
        lines.append(f"Summary: {summary}")
    if checks:
        lines.append("Checks:")
        for check in checks:
            lines.append(f"- {check}")
    return f"CI status: {status}", "\n".join(lines)


def _resolve_github_client(client: object | str | None) -> tuple[object | None, str]:
    if client is None or client == "mock":
        return None, "mock"
    if client == "gh":
        return GhCliGitHubReadClient(), "gh"
    if isinstance(client, GhCliGitHubReadClient):
        return client, "gh"
    return client, "custom"


def run_github_read_tool(
    tool_name: str,
    repo: str,
    *,
    issue_number: int | str | None = None,
    pr_number: int | str | None = None,
    token_env_var: str = DEFAULT_GITHUB_TOKEN_ENV_VAR,
    client: object | str | None = None,
) -> dict[str, object]:
    decision = evaluate_mcp_request(tool_name, "read")
    safety_notes = list(decision.get("safety_notes", []))

    if tool_name not in SUPPORTED_GITHUB_READ_TOOLS:
        return _validation_error_result(
            tool_name=tool_name,
            repo=repo,
            item_id=None,
            message=f"Unsupported GitHub read MCP tool: {tool_name}",
            safety_notes=safety_notes + ["GitHub read foundation only supports registered read-only GitHub tools."],
            decision=decision,
        )

    if decision.get("blocked"):
        return _validation_error_result(
            tool_name=tool_name,
            repo=repo,
            item_id=None,
            message=str(decision.get("blocked_reason") or "GitHub read MCP request was blocked."),
            safety_notes=safety_notes,
            decision=decision,
        )

    normalized_repo = str(repo or "").strip()
    if not SAFE_REPO_PATTERN.fullmatch(normalized_repo):
        return _validation_error_result(
            tool_name=tool_name,
            repo=normalized_repo,
            item_id=None,
            message="GitHub repository must use a safe owner/repo format.",
            safety_notes=safety_notes,
            decision=decision,
        )

    token_env_var_text = str(token_env_var or DEFAULT_GITHUB_TOKEN_ENV_VAR).strip()
    if not _is_safe_env_var_name(token_env_var_text):
        return _validation_error_result(
            tool_name=tool_name,
            repo=normalized_repo,
            item_id=None,
            message="GitHub token environment variable name is not safe.",
            safety_notes=safety_notes,
            decision=decision,
        )

    item_id: int | None = None
    if tool_name == "github.issue.read":
        item_id, error_message = _parse_item_id(issue_number, "issue_number")
        if error_message is not None:
            return _validation_error_result(
                tool_name=tool_name,
                repo=normalized_repo,
                item_id=item_id,
                message=error_message,
                safety_notes=safety_notes,
                decision=decision,
            )
    elif tool_name in {"github.pr.read", "github.pr.changed_files"}:
        item_id, error_message = _parse_item_id(pr_number, "pr_number")
        if error_message is not None:
            return _validation_error_result(
                tool_name=tool_name,
                repo=normalized_repo,
                item_id=item_id,
                message=error_message,
                safety_notes=safety_notes,
                decision=decision,
            )
    elif pr_number not in (None, ""):
        item_id, error_message = _parse_item_id(pr_number, "pr_number")
        if error_message is not None:
            return _validation_error_result(
                tool_name=tool_name,
                repo=normalized_repo,
                item_id=item_id,
                message=error_message,
                safety_notes=safety_notes,
                decision=decision,
            )

    resolved_client, client_mode = _resolve_github_client(client)
    if client_mode != "gh":
        token_value = os.environ.get(token_env_var_text)
        if not token_value:
            return _validation_error_result(
                tool_name=tool_name,
                repo=normalized_repo,
                item_id=item_id,
                message=f"GitHub token environment variable {token_env_var_text} is not set.",
                safety_notes=safety_notes + ["No raw token value was read or printed."],
                decision=decision,
            )
    if resolved_client is None:
        return _validation_error_result(
            tool_name=tool_name,
            repo=normalized_repo,
            item_id=item_id,
            message="Real provider is not implemented/configured for this tool.",
            safety_notes=safety_notes,
            decision=decision,
        )

    try:
        if tool_name == "github.issue.read":
            content_summary, output_text = _build_issue_text(
                normalized_repo,
                int(item_id or 0),
                resolved_client.read_issue(normalized_repo, int(item_id or 0)),
            )
        elif tool_name == "github.pr.read":
            content_summary, output_text = _build_pr_text(
                normalized_repo,
                int(item_id or 0),
                resolved_client.read_pull_request(normalized_repo, int(item_id or 0)),
            )
        elif tool_name == "github.pr.changed_files":
            content_summary, output_text = _build_changed_files_text(
                normalized_repo,
                int(item_id or 0),
                resolved_client.read_pull_request_changed_files(normalized_repo, int(item_id or 0)),
            )
        else:
            content_summary, output_text = _build_ci_status_text(
                normalized_repo,
                resolved_client.read_ci_status(normalized_repo, item_id),
                item_id,
            )
    except Exception as exc:
        client_label = "gh CLI" if client_mode == "gh" else "GitHub mock client"
        return _validation_error_result(
            tool_name=tool_name,
            repo=normalized_repo,
            item_id=item_id,
            message=f"{client_label} failed safely: {exc}",
            safety_notes=safety_notes + ["No raw token value was printed."],
            decision=decision,
        )

    guard_result = guard_text_output(output_text, "GitHub read MCP output")
    blocked = not guard_result["allowed"]
    safe_output = str(guard_result["safe_message"]) if blocked else output_text

    context_block = build_context_block_from_mcp_result(
        {
            "executed": not blocked,
            "blocked": blocked,
            "tool_name": tool_name,
            "action": "read",
            "message": (
                "GitHub read MCP content was blocked because secret-like content was detected."
                if blocked
                else f"{tool_name} completed successfully."
            ),
            "output_text": safe_output,
            "source_path": f"{normalized_repo}#{item_id}" if item_id is not None else normalized_repo,
            "decision": decision,
            "safety_notes": safety_notes,
        }
    )
    context_blocks = compact_context_blocks([context_block], max_total_chars=DEFAULT_CONTEXT_BUDGET)

    final_safety_notes = safety_notes + [
        (
            "gh CLI read-only client: no write or mutation command was used."
            if client_mode == "gh"
            else "Mock GitHub client only: no real API call was performed."
        ),
        "No raw token value was printed.",
    ]
    if blocked:
        final_safety_notes.append("Secret-like GitHub content was blocked or redacted.")

    return {
        "executed": not blocked,
        "blocked": blocked,
        "tool_name": tool_name,
        "repo": normalized_repo,
        "item_id": item_id,
        "content_summary": content_summary,
        "raw_content": None if blocked else output_text,
        "context_blocks": context_blocks,
        "message": (
            "GitHub read MCP content was blocked because secret-like content was detected."
            if blocked
            else f"{tool_name} completed successfully."
        ),
        "safety_notes": final_safety_notes,
        "decision": decision,
    }


def format_github_read_result(result: dict[str, object]) -> str:
    safety_notes = list(result.get("safety_notes", [])) or ["none"]
    return "\n".join(
        [
            f"Executed: {'yes' if result.get('executed') else 'no'}",
            f"Blocked: {'yes' if result.get('blocked') else 'no'}",
            f"Tool name: {result.get('tool_name') or 'unknown'}",
            f"Repo: {result.get('repo') or 'not provided'}",
            f"Item id: {result.get('item_id') if result.get('item_id') is not None else 'none'}",
            f"Content summary: {result.get('content_summary') or 'not available'}",
            f"Message: {result.get('message') or 'not available'}",
            format_context_blocks(list(result.get("context_blocks", []))),
            f"Safety notes: {'; '.join(str(note) for note in safety_notes)}",
        ]
    )
