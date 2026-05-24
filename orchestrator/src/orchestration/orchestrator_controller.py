from __future__ import annotations

from pathlib import Path

from agents.agent_runtime import (
    format_agent_run_summary,
    format_pre_codex_agent_guidance,
    run_agent_workflow,
)
from brain.ai_brain_reader import inspect_required_core_files
from brain.memory_sync import suggest_memory_sync
from agents.agent_decision import format_aggregated_decision
from core.approved_paths import ApprovedPathError, ensure_approved_path
from core.report_writer import ReportWriterError, write_report
from core.safety import guard_text_output
from orchestration.edit_plan import format_edit_plan, generate_edit_plan
from orchestration.multi_agent_review import (
    format_multi_agent_diff_review,
    generate_multi_agent_diff_review,
    generate_secret_blocked_diff_review,
)
from orchestration.knowledge_update import (
    format_knowledge_update_with_compatibility,
    generate_knowledge_update_proposal,
    summarize_knowledge_update_proposal,
)
from orchestration.planner_report import format_planner_report, generate_planner_report
from orchestration.task_classifier import classify_task
from project.project_context_reader import ProjectContextReaderError, inspect_project_context
from tools.codex_execution_contract import (
    evaluate_codex_execution_contract,
    format_codex_execution_contract_view,
)
from tools.codex_executor import (
    execute_codex_task_with_post_review,
    format_codex_execution_result,
)
from tools.codex_gateway import format_codex_prompt_package, generate_codex_prompt_package
from tools.error_logs_mcp import format_error_logs_result, run_error_logs_tool
from tools.git_gateway import GitGatewayError, inspect_git_state
from tools.github_read_mcp import run_github_read_tool
from tools.mcp_context_manager import (
    compact_context_blocks,
    build_context_block_from_mcp_result,
    format_context_blocks,
)
from tools.mcp_read_dispatcher import run_mcp_read_tool
from tools.project_knowledge_mcp import read_project_knowledge
from tools.scope_enforcer import (
    enforce_changed_file_scope,
    format_scope_enforcement_result,
)
from tools.test_runner import format_test_result, run_test_command


SUPPORTED_ORCHESTRATOR_MODES = {"plan", "review-diff", "status", "run"}


def _empty_result(mode: str) -> dict[str, object]:
    return {
        "summary": "",
        "mode": mode,
        "task_type": None,
        "task_text": None,
        "changed_files_summary": None,
        "project_context_summary": None,
        "gate_status": None,
        "planner_summary": None,
        "edit_plan_summary": None,
        "codex_execution_summary": None,
        "post_codex_review_decision": None,
        "scope_enforcement_summary": None,
        "scope_status_summary": None,
        "test_execution_summary": None,
        "verification_gate_summary": None,
        "verification_gate_decision": None,
        "verification_test_status": None,
        "next_action_summary": None,
        "memory_docs_summary": None,
        "agent_runtime_summary": None,
        "agent_runtime_mode": None,
        "agent_llm_adapter_used": None,
        "agent_fallback_used": None,
        "agent_llm_provider": None,
        "agent_provider_available": None,
        "agent_provider_execution_status": None,
        "agent_fallback_reason": None,
        "agent_runtime_notes": None,
        "local_mcp_context_summary": None,
        "github_context_summary": None,
        "error_context_summary": None,
        "context_summary": None,
        "multi_agent_decision_summary": None,
        "ai_brain_context_pack_summary": None,
        "project_path": None,
        "codex_status_summary": None,
        "ci_status_summary": None,
        "report_text": "",
        "report_path": None,
        "decision": None,
        "errors": [],
    }


def _summarize_first_line(text: str | None, fallback: str) -> str:
    if not text:
        return fallback
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return first_line or fallback


def _build_coding_run_summary(result: dict[str, object]) -> str:
    ai_brain = "yes" if result.get("ai_brain_context_pack_summary") else "no"
    ci_status = str(result.get("ci_status_summary") or "not run")
    diff_review = str(result.get("post_codex_review_decision") or "not available")
    
    return "\n".join(
        [
            "Coding Run Summary",
            f"- Task: {result.get('task_text') or 'not provided'}",
            f"- Project: {result.get('project_path') or 'not provided'}",
            f"- AI-Brain used: {ai_brain}",
            f"- Codex result: {result.get('codex_status_summary') or 'unknown'}",
            f"- Changed files: {result.get('changed_files_summary') or 'none'}",
            f"- Scope: {result.get('scope_status_summary') or 'unknown'}",
            f"- Diff review: {diff_review}",
            f"- Tests: {result.get('verification_test_status') or 'not run'}",
            f"- CI: {ci_status}",
            f"- Verification: {result.get('verification_gate_decision') or 'not available'}",
            f"- Next action: {result.get('next_action_summary') or 'none'}",
        ]
    )


def format_orchestrator_result(result: dict[str, object]) -> str:
    errors = list(result.get("errors", []))
    error_text = "; ".join(str(item) for item in errors) if errors else "none"
    mode = result.get("mode") or "unknown"

    if mode == "run":
        lines = [
            _build_coding_run_summary(result),
            f"Summary: {result.get('summary') or 'not available'}",
            f"Mode: {mode}",
            f"Task type: {result.get('task_type') or 'not provided'}",
            f"Project context summary: {result.get('project_context_summary') or 'not provided'}",
            f"Gate status: {result.get('gate_status') or 'not available'}",
            f"Planner summary: {result.get('planner_summary') or 'not available'}",
            f"Edit plan summary: {result.get('edit_plan_summary') or 'not available'}",
            f"Codex execution result: {result.get('codex_execution_summary') or 'not available'}",
            f"Post-Codex review decision: {result.get('post_codex_review_decision') or 'not available'}",
            f"Scope enforcement: {result.get('scope_enforcement_summary') or 'not available'}",
            f"Verification Gate: {result.get('verification_gate_summary') or 'not available'}",
            f"Test execution result: {result.get('test_execution_summary') or 'not requested'}",
            f"Memory/docs suggestion: {result.get('memory_docs_summary') or 'not available'}",
        ]
        if result.get("context_summary") is not None:
            lines.append(str(result.get("context_summary")))
        if result.get("local_mcp_context_summary") is not None:
            lines.append(f"Local MCP Context: {result.get('local_mcp_context_summary')}")
        if result.get("github_context_summary") is not None:
            lines.append(f"GitHub Context: {result.get('github_context_summary')}")
        if result.get("error_context_summary") is not None:
            lines.append(f"Error Context: {result.get('error_context_summary')}")
        if result.get("multi_agent_decision_summary") is not None:
            lines.append(f"\n{result['multi_agent_decision_summary']}")
        if result.get("ai_brain_context_pack_summary") is not None:
            lines.append(f"\n{result['ai_brain_context_pack_summary']}")
        lines.extend(
            [
                f"Agent runtime mode: {result.get('agent_runtime_mode') or 'not available'}",
                f"Agent LLM adapter used: {result.get('agent_llm_adapter_used') or 'not available'}",
                f"LLM provider: {result.get('agent_llm_provider') or 'not available'}",
                f"Provider available: {result.get('agent_provider_available') or 'not available'}",
                f"Provider execution status: {result.get('agent_provider_execution_status') or 'not available'}",
                f"Agent fallback used: {result.get('agent_fallback_used') or 'not available'}",
                f"Fallback reason: {result.get('agent_fallback_reason') or 'not available'}",
                f"Agent runtime notes: {result.get('agent_runtime_notes') or 'not available'}",
                f"Agent Runtime Summary: {result.get('agent_runtime_summary') or 'not available'}",
                f"Decision: {result.get('decision') or 'not available'}",
                f"Report path: {result.get('report_path') or 'none'}",
                f"Errors: {error_text}",
            ]
        )
        if result.get("multi_agent_decision_summary"):
            lines.append(f"\n{result['multi_agent_decision_summary']}")
        lines.append(f"Report text:\n{result.get('report_text') or 'none'}")
        return "\n".join(lines)

    lines = [
        f"Summary: {result.get('summary') or 'not available'}",
        f"Mode: {mode}",
        f"Task type: {result.get('task_type') or 'not provided'}",
        f"Project context summary: {result.get('project_context_summary') or 'not provided'}",
        f"Agent runtime mode: {result.get('agent_runtime_mode') or 'not available'}",
        f"Agent LLM adapter used: {result.get('agent_llm_adapter_used') or 'not available'}",
        f"LLM provider: {result.get('agent_llm_provider') or 'not available'}",
        f"Provider available: {result.get('agent_provider_available') or 'not available'}",
        f"Provider execution status: {result.get('agent_provider_execution_status') or 'not available'}",
        f"Agent fallback used: {result.get('agent_fallback_used') or 'not available'}",
        f"Fallback reason: {result.get('agent_fallback_reason') or 'not available'}",
        f"Agent runtime notes: {result.get('agent_runtime_notes') or 'not available'}",
    ]
    if result.get("context_summary") is not None:
        lines.append(str(result.get("context_summary")))
    if result.get("local_mcp_context_summary") is not None:
        lines.append(f"Local MCP Context: {result.get('local_mcp_context_summary')}")
    if result.get("github_context_summary") is not None:
        lines.append(f"GitHub Context: {result.get('github_context_summary')}")
    if result.get("error_context_summary") is not None:
        lines.append(f"Error Context: {result.get('error_context_summary')}")
    lines.extend(
        [
            f"Agent Runtime Summary: {result.get('agent_runtime_summary') or 'not available'}",
            f"Decision: {result.get('decision') or 'not available'}",
            f"Report path: {result.get('report_path') or 'none'}",
            f"Errors: {error_text}",
        ]
    )
    if result.get("multi_agent_decision_summary"):
        lines.append(f"\n{result['multi_agent_decision_summary']}")
    if result.get("ai_brain_context_pack_summary"):
        lines.append(f"\n{result['ai_brain_context_pack_summary']}")
    lines.append(f"Report text:\n{result.get('report_text') or 'none'}")
    return "\n".join(lines)


def _collect_local_mcp_context(
    project_path: str | Path,
    approved_paths: list[str] | tuple[str, ...] | None,
) -> tuple[str, str, list[dict[str, object]], dict[str, object]]:
    project_root = Path(project_path)
    project_knowledge_result = read_project_knowledge(project_root, approved_paths)

    git_mcp_results: list[dict[str, object]] = []
    for tool_name in ("git.status", "git.log"):
        git_mcp_results.append(
            run_mcp_read_tool(
                tool_name,
                str(project_root),
                approved_paths,
                project_path=str(project_root),
            )
        )

    context_blocks = list(project_knowledge_result.get("context_blocks", [])) + [
        build_context_block_from_mcp_result(mcp_result)
        for mcp_result in git_mcp_results
    ]
    compacted_blocks = compact_context_blocks(context_blocks, max_total_chars=8000)
    found_docs = list(project_knowledge_result.get("found_files", []))
    missing_docs = list(project_knowledge_result.get("missing_files", []))
    formatted_context = "\n".join(
        [
            "Project knowledge found docs: " + (", ".join(found_docs) if found_docs else "none"),
            "Project knowledge missing docs: " + (", ".join(missing_docs) if missing_docs else "none"),
            format_context_blocks(compacted_blocks),
        ]
    )
    summary = _summarize_first_line(formatted_context, "none")
    return summary, formatted_context, compacted_blocks, project_knowledge_result


def _build_local_context_signal_lines(
    context_blocks: list[dict[str, object]],
    project_knowledge_result: dict[str, object],
) -> list[str]:
    safe_blocks = [block for block in context_blocks if block.get("safe") and not block.get("blocked")]
    found_docs = list(project_knowledge_result.get("found_files", []))
    missing_docs = list(project_knowledge_result.get("missing_files", []))

    if found_docs:
        knowledge_signal = "found " + ", ".join(found_docs[:3])
    else:
        knowledge_signal = "unavailable or blocked"
    if missing_docs:
        knowledge_signal += "; missing " + ", ".join(missing_docs[:3])

    git_signal_parts: list[str] = []
    git_status_block = next((block for block in safe_blocks if block.get("tool_name") == "git.status"), None)
    if git_status_block is not None:
        status_line = next(
            (
                line.replace("Status summary: ", "").strip()
                for line in str(git_status_block.get("content") or "").splitlines()
                if line.startswith("Status summary: ")
            ),
            "",
        )
        if status_line:
            git_signal_parts.append(status_line)

    git_log_block = next((block for block in safe_blocks if block.get("tool_name") == "git.log"), None)
    if git_log_block is not None:
        log_entries = len(str(git_log_block.get("content") or "").splitlines())
        if log_entries > 0:
            git_signal_parts.append(f"recent history available ({log_entries} line(s))")

    if not git_signal_parts:
        git_signal_parts.append("unavailable or blocked")

    return [
        f"- Local project knowledge: {knowledge_signal}",
        f"- Local git state: {'; '.join(git_signal_parts)}",
    ]


def _collect_github_context(
    *,
    github_repo: str | None,
    github_issue_number: int | str | None,
    github_pr_number: int | str | None,
    github_token_env: str,
    github_read_client: object | None,
) -> tuple[str, str, list[dict[str, object]], dict[str, str]]:
    if not github_repo:
        unavailable_text = "\n".join(
            [
                "GitHub repo: not provided",
                "Issue context: unavailable",
                "PR context: unavailable",
                "PR changed files context: unavailable",
                "CI status context: unavailable",
                "Message: GitHub context was requested, but no --github-repo value was provided.",
                "Context blocks: none",
            ]
        )
        return (
            _summarize_first_line(unavailable_text, "GitHub repo: not provided"),
            unavailable_text,
            [],
            {
                "issue": "unavailable",
                "pr": "unavailable",
                "pr_changed_files": "unavailable",
                "ci": "unavailable",
            },
        )

    request_specs: list[tuple[str, dict[str, object], str]] = []
    if github_issue_number not in (None, ""):
        request_specs.append(
            (
                "github.issue.read",
                {"issue_number": github_issue_number},
                "issue",
            )
        )
    else:
        request_specs.append(("github.issue.read", {}, "issue"))

    if github_pr_number not in (None, ""):
        request_specs.append(
            (
                "github.pr.read",
                {"pr_number": github_pr_number},
                "pr",
            )
        )
        request_specs.append(
            (
                "github.pr.changed_files",
                {"pr_number": github_pr_number},
                "pr_changed_files",
            )
        )
    else:
        request_specs.append(("github.pr.read", {}, "pr"))
        request_specs.append(("github.pr.changed_files", {}, "pr_changed_files"))

    request_specs.append(("github.ci.status", {}, "ci"))

    context_blocks: list[dict[str, object]] = []
    status_map = {
        "issue": "not requested",
        "pr": "not requested",
        "pr_changed_files": "not requested",
        "ci": "not requested",
    }
    messages: list[str] = []

    for tool_name, kwargs, status_key in request_specs:
        if status_key == "issue" and github_issue_number in (None, ""):
            continue
        if status_key in {"pr", "pr_changed_files"} and github_pr_number in (None, ""):
            continue

        github_result = run_github_read_tool(
            tool_name,
            github_repo,
            token_env_var=github_token_env,
            client=github_read_client,
            **kwargs,
        )
        context_blocks.extend(list(github_result.get("context_blocks", [])))
        if github_result.get("executed") and not github_result.get("blocked"):
            status_map[status_key] = "available"
        else:
            status_map[status_key] = "unavailable"
        messages.append(str(github_result.get("message") or f"{tool_name} unavailable."))

    compacted_blocks = compact_context_blocks(context_blocks, max_total_chars=8000)
    formatted_text = "\n".join(
        [
            f"GitHub repo: {github_repo}",
            f"Issue context: {status_map['issue']}",
            f"PR context: {status_map['pr']}",
            f"PR changed files context: {status_map['pr_changed_files']}",
            f"CI status context: {status_map['ci']}",
            "Messages: " + ("; ".join(messages) if messages else "none"),
            format_context_blocks(compacted_blocks),
        ]
    )
    return _summarize_first_line(formatted_text, f"GitHub repo: {github_repo}"), formatted_text, compacted_blocks, status_map


def _collect_error_context(
    *,
    approved_project_path: str | Path | None,
    approved_paths: list[str] | tuple[str, ...] | None,
    error_tool_name: str | None,
    error_provider: str | None,
    error_issue_id: int | str | None,
    error_log_path: str | None,
    error_token_env: str,
    error_read_client: object | None,
) -> tuple[str, str, list[dict[str, object]], dict[str, object]]:
    if not error_tool_name or not error_provider:
        unavailable_result = {
            "executed": False,
            "blocked": True,
            "tool_name": error_tool_name or "not provided",
            "provider": error_provider or "not provided",
            "content_summary": "not available",
            "context_blocks": [],
            "message": "Error context was requested, but --error-tool-name or --error-provider was not provided.",
            "safety_notes": ["No external error monitoring API call was performed."],
        }
        formatted_text = format_error_logs_result(unavailable_result)
        return _summarize_first_line(formatted_text, "not available"), formatted_text, [], unavailable_result

    error_result = run_error_logs_tool(
        error_tool_name,
        error_provider,
        project_path=approved_project_path,
        issue_id=error_issue_id,
        log_path=error_log_path,
        token_env_var=error_token_env,
        approved_paths=approved_paths,
        client=error_read_client,
    )
    formatted_text = format_error_logs_result(error_result)
    return (
        _summarize_first_line(formatted_text, "not available"),
        formatted_text,
        list(error_result.get("context_blocks", [])),
        error_result,
    )


def _build_github_context_signal_lines(
    github_repo: str | None,
    github_status_map: dict[str, str],
    context_blocks: list[dict[str, object]],
) -> list[str]:
    safe_blocks = [block for block in context_blocks if block.get("safe") and not block.get("blocked")]
    ci_status_block = next((block for block in safe_blocks if block.get("tool_name") == "github.ci.status"), None)
    ci_status_detail = None
    if ci_status_block is not None:
        ci_status_detail = next(
            (
                line.replace("Status: ", "").strip()
                for line in str(ci_status_block.get("content") or "").splitlines()
                if line.startswith("Status: ")
            ),
            "",
        )

    repo_prefix = f"repo {github_repo or 'not provided'}; "
    pr_line = (
        f"- GitHub PR: {repo_prefix}{github_status_map.get('pr', 'unavailable')}; "
        f"changed files {github_status_map.get('pr_changed_files', 'unavailable')}"
    )
    ci_suffix = (
        f"{github_status_map.get('ci', 'unavailable')} ({ci_status_detail})"
        if github_status_map.get("ci") == "available" and ci_status_detail
        else github_status_map.get("ci", "unavailable")
    )
    return [
        f"- GitHub issue: {repo_prefix}{github_status_map.get('issue', 'unavailable')}",
        pr_line,
        f"- GitHub CI: {repo_prefix}{ci_suffix}",
    ]


def _build_context_signals_block(
    *,
    local_signal_lines: list[str],
    github_signal_lines: list[str],
    error_signal_lines: list[str],
) -> str | None:
    signal_lines = [
        line for line in [*local_signal_lines, *github_signal_lines, *error_signal_lines] if line
    ]
    if not signal_lines:
        return None
    return "\n".join(["- Context signals:"] + signal_lines)


def _build_error_context_signal_lines(
    error_result: dict[str, object],
) -> list[str]:
    tool_name = str(error_result.get("tool_name") or "")
    is_available = bool(error_result.get("executed")) and not bool(error_result.get("blocked"))
    error_monitoring_status = (
        "available"
        if tool_name == "error_monitoring.issue.read" and is_available
        else "unavailable"
    )
    local_log_status = (
        "available"
        if tool_name == "local.dev_logs.read" and is_available
        else "unavailable"
    )
    return [
        f"- Error context: {error_monitoring_status}",
        f"- Local log context: {local_log_status}",
    ]


def _derive_github_ci_verification_status(
    *,
    include_github_context: bool,
    github_status_map: dict[str, str],
    context_blocks: list[dict[str, object]],
) -> str:
    if not include_github_context:
        return "not run"

    if github_status_map.get("ci") != "available":
        return "unknown"

    safe_blocks = [block for block in context_blocks if block.get("safe") and not block.get("blocked")]
    ci_status_block = next((block for block in safe_blocks if block.get("tool_name") == "github.ci.status"), None)
    if ci_status_block is None:
        return "unknown"

    ci_status_detail = next(
        (
            line.replace("Status: ", "").strip().lower()
            for line in str(ci_status_block.get("content") or "").splitlines()
            if line.startswith("Status: ")
        ),
        "",
    )
    if ci_status_detail == "success":
        return "passed"
    if ci_status_detail in {"failure", "cancelled", "timed_out", "action_required"}:
        return "failed"
    return "unknown"


def _build_context_summary(
    *,
    include_local: bool,
    local_knowledge_result: dict[str, object] | None,
    local_context_blocks: list[dict[str, object]] | None,
    include_github: bool,
    github_status_map: dict[str, str] | None,
    github_ci_status: str,
    include_error: bool,
    error_result: dict[str, object] | None,
) -> str | None:
    if not (include_local or include_github or include_error):
        return None

    local_knowledge = "not requested"
    local_git = "not requested"
    if include_local:
        if local_knowledge_result:
            found = len(list(local_knowledge_result.get("found_files", [])))
            missing = len(list(local_knowledge_result.get("missing_files", [])))
            if found > 0 and missing == 0:
                local_knowledge = "available"
            elif found > 0 and missing > 0:
                local_knowledge = "partial"
            else:
                local_knowledge = "unavailable"
        else:
            local_knowledge = "unavailable"

        if local_context_blocks:
            safe_git_blocks = [
                b for b in local_context_blocks
                if b.get("tool_name") in ("git.status", "git.log")
                and b.get("safe") and not b.get("blocked")
            ]
            local_git = "available" if safe_git_blocks else "unavailable"
        else:
            local_git = "unavailable"

    github_context = "not requested"
    if include_github:
        if github_status_map:
            requested_statuses = [v for k, v in github_status_map.items() if v != "not requested" and k != "ci"]
            if not requested_statuses:
                github_context = "unavailable"
            elif all(s == "available" for s in requested_statuses):
                github_context = "available"
            elif all(s == "unavailable" for s in requested_statuses):
                github_context = "unavailable"
            else:
                github_context = "partial"
        else:
            github_context = "unavailable"

    ci_status = github_ci_status if include_github else "not run"

    error_context = "not requested"
    if include_error:
        if error_result and error_result.get("executed") and not error_result.get("blocked"):
            error_context = "available"
        else:
            error_context = "unavailable"

    return "\n".join([
        "Context Summary:",
        f"- Local project knowledge: {local_knowledge}",
        f"- Local git context: {local_git}",
        f"- GitHub context: {github_context}",
        f"- GitHub CI: {ci_status}",
        f"- Error/log context: {error_context}",
    ])


def _project_context_summary(project_context: dict[str, object] | None) -> str | None:
    if project_context is None:
        return None

    found_count = len(list(project_context.get("found_files", [])))
    missing_count = len(list(project_context.get("missing_files", [])))
    return (
        f"Working directory: {project_context.get('working_directory', '')}; "
        f"found {found_count} AI-ready file(s); missing {missing_count} AI-ready file(s)."
    )


def _status_report_text(
    summary: str,
    task_type: str | None,
    project_context_summary: str | None,
) -> str:
    lines = [
        f"Summary: {summary}",
        "Mode: status",
        f"Task type: {task_type or 'not provided'}",
        f"Project context summary: {project_context_summary or 'not provided'}",
    ]
    return "\n".join(lines)


def _guard_blocked_report_text(
    guard_result: dict[str, object],
    trailing_message: str,
) -> str:
    lines = [str(guard_result["safe_message"])]
    for finding in list(guard_result.get("findings", [])):
        lines.append(f"Finding: {finding['summary']}")
    lines.append(trailing_message)
    return "\n".join(lines)


def _report_name_for_mode(mode: str) -> str:
    if mode == "plan":
        return "planner-report"
    if mode == "review-diff":
        return "multi-agent-diff-review"
    if mode == "run":
        return "coding-run-report"
    return "orchestrator-status"


def _build_verification_gate(
    *,
    post_review_decision: str,
    post_review_message: str,
    scope_enforcement_result: dict[str, object] | None,
    test_result: dict[str, object] | None,
    post_review_should_block_save: bool,
    github_ci_status: str = "not run",
) -> dict[str, str]:
    if scope_enforcement_result is not None and not scope_enforcement_result.get("passed"):
        scope_message = str(
            scope_enforcement_result.get("message")
            or "Changes outside the explicitly allowed files were detected."
        )
        return {
            "diff_review_decision": post_review_decision or "not available",
            "test_status": "not run",
            "ci_status": github_ci_status,
            "final_verification_decision": "Blocked",
            "reason": f"Scope violation detected after Codex execution. {scope_message}",
        }

    if post_review_should_block_save or post_review_decision == "Blocked":
        return {
            "diff_review_decision": post_review_decision or "Blocked",
            "test_status": "not run",
            "ci_status": github_ci_status,
            "final_verification_decision": "Blocked",
            "reason": post_review_message or "Blocked because post-Codex diff review found secret-like or otherwise blocked content.",
        }

    if post_review_decision == "not run":
        return {
            "diff_review_decision": "not run",
            "test_status": "not run",
            "ci_status": github_ci_status,
            "final_verification_decision": "Needs revision",
            "reason": post_review_message or "Verification could not complete because post-Codex review did not run.",
        }

    if test_result is None:
        if github_ci_status == "failed":
            return {
                "diff_review_decision": post_review_decision or "not available",
                "test_status": "not run",
                "ci_status": "failed",
                "final_verification_decision": "Needs revision",
                "reason": "GitHub CI reported a failed status after Codex execution.",
            }
        reason = "Tests not run because no test command was provided."
        if github_ci_status == "passed":
            reason += " GitHub CI passed."
        elif github_ci_status == "unknown":
            reason += " GitHub CI status was unavailable or unknown."
        return {
            "diff_review_decision": post_review_decision or "not available",
            "test_status": "not run",
            "ci_status": github_ci_status,
            "final_verification_decision": post_review_decision or "Needs more context",
            "reason": reason,
        }

    if test_result.get("blocked"):
        return {
            "diff_review_decision": post_review_decision or "not available",
            "test_status": "blocked",
            "ci_status": github_ci_status,
            "final_verification_decision": "Needs revision",
            "reason": str(test_result.get("message") or "Test execution gate was blocked."),
        }

    if test_result.get("timed_out"):
        return {
            "diff_review_decision": post_review_decision or "not available",
            "test_status": "timed out",
            "ci_status": github_ci_status,
            "final_verification_decision": "Needs revision",
            "reason": str(test_result.get("message") or "Test execution timed out."),
        }

    if not test_result.get("passed"):
        return {
            "diff_review_decision": post_review_decision or "not available",
            "test_status": "failed",
            "ci_status": github_ci_status,
            "final_verification_decision": "Needs revision",
            "reason": str(test_result.get("message") or "Test execution did not pass."),
        }

    if github_ci_status == "failed":
        return {
            "diff_review_decision": post_review_decision or "not available",
            "test_status": "passed",
            "ci_status": "failed",
            "final_verification_decision": "Needs revision",
            "reason": "GitHub CI reported a failed status after Codex execution.",
        }

    if post_review_decision in {"Approved", "Approved with changes"}:
        reason = "Post-Codex review completed and the allowed test command passed."
        if github_ci_status == "passed":
            reason += " GitHub CI passed."
        elif github_ci_status == "unknown":
            reason += " GitHub CI status was unavailable or unknown."
        return {
            "diff_review_decision": post_review_decision,
            "test_status": "passed",
            "ci_status": github_ci_status,
            "final_verification_decision": "Approved" if post_review_decision == "Approved" else "Approved with changes",
            "reason": reason,
        }

    reason = "Allowed tests passed, but the diff review still requires follow-up."
    if github_ci_status == "passed":
        reason += " GitHub CI passed."
    elif github_ci_status == "unknown":
        reason += " GitHub CI status was unavailable or unknown."
    return {
        "diff_review_decision": post_review_decision or "not available",
        "test_status": "passed",
        "ci_status": github_ci_status,
        "final_verification_decision": post_review_decision or "Needs more context",
        "reason": reason,
    }


def _format_verification_gate(verification_gate: dict[str, str]) -> str:
    return "\n".join(
        [
            "Verification Gate:",
            f"- Diff review decision: {verification_gate.get('diff_review_decision', 'not available')}",
            f"- Test status: {verification_gate.get('test_status', 'not run')}",
            f"- CI status: {verification_gate.get('ci_status', 'not run')}",
            f"- Final verification decision: {verification_gate.get('final_verification_decision', 'not available')}",
            f"- Reason: {verification_gate.get('reason', 'not available')}",
        ]
    )


def _run_mode_report_text(
    *,
    planner_report_text: str,
    context_summary_text: str | None,
    local_mcp_context_text: str | None,
    github_context_text: str | None,
    error_context_text: str | None,
    agent_runtime_summary_text: str,
    edit_plan_text: str,
    codex_prompt_text: str,
    codex_contract_text: str,
    codex_execution_text: str,
    scope_enforcement_text: str,
    verification_gate_text: str,
    test_result_text: str,
    memory_sync_text: str,
) -> str:
    sections = ["Planner report:\n" + planner_report_text]
    if context_summary_text is not None:
        sections.append(context_summary_text)
    if local_mcp_context_text is not None:
        sections.append("Local MCP Context:\n" + local_mcp_context_text)
    if github_context_text is not None:
        sections.append("GitHub Context:\n" + github_context_text)
    if error_context_text is not None:
        sections.append("Error Context:\n" + error_context_text)
    sections.extend(
        [
            "Agent Runtime Summary:\n" + agent_runtime_summary_text,
            "Edit plan:\n" + edit_plan_text,
            "Codex prompt package:\n" + codex_prompt_text,
            "Codex execution contract:\n" + codex_contract_text,
            "Codex execution result:\n" + codex_execution_text,
            "Scope enforcement result:\n" + scope_enforcement_text,
            verification_gate_text,
            "Test execution result:\n" + test_result_text,
        ]
    )
    if memory_sync_text.startswith("Knowledge Update Proposal:"):
        sections.append(memory_sync_text)
    else:
        sections.append("Memory/docs update suggestion:\n" + memory_sync_text)
    return "\n\n".join(sections)


def _save_report_if_allowed(
    result: dict[str, object],
    *,
    report_text: str,
    report_name: str,
    reports_dir: str | Path | None,
    guard_context_label: str,
    guard_block_message: str,
) -> tuple[str, str | None]:
    if reports_dir is None:
        result["errors"].append("Reports directory was not provided for orchestrator save-report.")
        return report_text, None

    save_guard_result = guard_text_output(report_text, guard_context_label)
    if not save_guard_result["allowed"]:
        result["errors"].append(guard_block_message)
        return (
            _guard_blocked_report_text(save_guard_result, guard_block_message),
            None,
        )

    try:
        saved_report_path = write_report(report_text, report_name, reports_dir)
    except ReportWriterError as exc:
        result["errors"].append(f"Report writer error: {exc}")
        return report_text, None

    return report_text, str(saved_report_path)


def run_orchestrator(
    *,
    task_text: str | None = None,
    project_path: str | None = None,
    mode: str = "status",
    save_report: bool = False,
    ai_brain_path: str | Path | None = None,
    reports_dir: str | Path | None = None,
    approved_paths: list[str] | tuple[str, ...] | None = None,
    allowed_files: list[str] | tuple[str, ...] | None = None,
    confirm_codex_prompt: bool = False,
    confirm_codex_execution: bool = False,
    codex_timeout: int = 300,
    codex_command: str = "codex",
    include_error_context: bool = False,
    include_ai_brain_context: bool = False,
    agent_runtime: str = "deterministic",
    llm_enabled: bool = False,
    confirm_llm_agent: bool = False,
    agent_context_text: str | None = None,
    agent_context_sources: list[str] | tuple[str, ...] | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    llm_api_key_env_var: str | None = None,
    test_command: str | list[str] | tuple[str, ...] | None = None,
    test_timeout: int = 120,
    include_local_mcp_context: bool = False,
    include_github_context: bool = False,
    github_repo: str | None = None,
    github_issue_number: int | str | None = None,
    github_pr_number: int | str | None = None,
    github_token_env: str = "GITHUB_TOKEN",
    github_client: str = "mock",
    github_read_client: object | None = None,
    error_tool_name: str | None = None,
    error_provider: str | None = None,
    error_issue_id: int | str | None = None,
    error_log_path: str | None = None,
    error_token_env: str = "ERROR_MONITORING_TOKEN",
    error_read_client: object | None = None,
) -> dict[str, object]:
    result = _empty_result(mode)
    result["task_text"] = task_text
    result["project_path"] = str(project_path)

    if mode not in SUPPORTED_ORCHESTRATOR_MODES:
        result["errors"].append(f"Unsupported orchestrator mode: {mode}")
        return result

    task_classification = classify_task(task_text) if task_text else None
    if task_classification is not None:
        result["task_type"] = task_classification["primary_task_type"]

    approved_project_path: Path | None = None
    project_context = None
    if project_path is not None:
        try:
            approved_project_path = ensure_approved_path(project_path, approved_paths)
            project_context = inspect_project_context(approved_project_path)
        except (ApprovedPathError, ProjectContextReaderError) as exc:
            result["errors"].append(str(exc))
            return result

        result["project_context_summary"] = _project_context_summary(project_context)

    if mode == "status":
        result["summary"] = "Read-only orchestration status completed."
        result["report_text"] = _status_report_text(
            result["summary"],
            None if task_classification is None else str(task_classification["primary_task_type"]),
            result["project_context_summary"],
        )

    elif mode == "plan":
        if not task_text:
            result["errors"].append("Plan mode requires task text.")
            return result

        ai_brain_core_summary = None
        if ai_brain_path is not None:
            ai_brain_core_summary = inspect_required_core_files(ai_brain_path)

        planner_report = generate_planner_report(
            task_text,
            task_classification or classify_task(""),
            project_context=project_context,
            ai_brain_core_summary=ai_brain_core_summary,
        )
        agent_runtime_summary = run_agent_workflow(
            task_text=task_text,
            mode="plan",
            task_classification=task_classification,
            project_context=project_context,
            llm_mode=agent_runtime,
            llm_enabled=llm_enabled,
            llm_approval_confirmed=confirm_llm_agent,
            context_text=agent_context_text,
            context_sources=list(agent_context_sources or []),
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_api_key_env_var=llm_api_key_env_var,
        )
        result["multi_agent_decision_summary"] = format_aggregated_decision(agent_runtime_summary.get("multi_agent_decision", {}))
        formatted_local_mcp_context = None
        local_mcp_context_blocks_plan: list[dict[str, object]] = []
        local_project_knowledge_result_plan: dict[str, object] = {}
        formatted_github_context = None
        github_context_blocks_plan: list[dict[str, object]] = []
        github_status_map_plan: dict[str, str] = {}
        github_ci_status_plan = "not run"
        formatted_error_context = None
        error_context_result_plan: dict[str, object] = {}
        if include_local_mcp_context and approved_project_path is not None:
            local_mcp_context_summary, formatted_local_mcp_context, local_mcp_context_blocks_plan, local_project_knowledge_result_plan = _collect_local_mcp_context(
                approved_project_path,
                approved_paths,
            )
            result["local_mcp_context_summary"] = local_mcp_context_summary
        if include_github_context:
            github_context_summary, formatted_github_context, github_context_blocks_plan, github_status_map_plan = _collect_github_context(
                github_repo=github_repo,
                github_issue_number=github_issue_number,
                github_pr_number=github_pr_number,
                github_token_env=github_token_env,
                github_read_client=github_read_client if github_read_client is not None else github_client,
            )
            result["github_context_summary"] = github_context_summary
            github_ci_status_plan = _derive_github_ci_verification_status(
                include_github_context=include_github_context,
                github_status_map=github_status_map_plan,
                context_blocks=github_context_blocks_plan,
            )
        if include_error_context:
            error_context_summary, formatted_error_context, _, error_context_result_plan = _collect_error_context(
                approved_project_path=approved_project_path,
                approved_paths=approved_paths,
                error_tool_name=error_tool_name,
                error_provider=error_provider,
                error_issue_id=error_issue_id,
                error_log_path=error_log_path,
                error_token_env=error_token_env,
                error_read_client=error_read_client,
            )
            result["error_context_summary"] = error_context_summary
            
        result["context_summary"] = _build_context_summary(
            include_local=include_local_mcp_context,
            local_knowledge_result=local_project_knowledge_result_plan,
            local_context_blocks=local_mcp_context_blocks_plan,
            include_github=include_github_context,
            github_status_map=github_status_map_plan,
            github_ci_status=github_ci_status_plan,
            include_error=include_error_context,
            error_result=error_context_result_plan,
        )
        result["agent_runtime_mode"] = str(agent_runtime_summary.get("runtime_mode", "deterministic"))
        result["agent_llm_adapter_used"] = str(agent_runtime_summary.get("llm_adapter_used", "none"))
        result["agent_llm_provider"] = str(agent_runtime_summary.get("llm_provider", "disabled"))
        result["agent_provider_available"] = (
            "yes" if agent_runtime_summary.get("provider_available") else "no"
        )
        result["agent_provider_execution_status"] = str(
            agent_runtime_summary.get("provider_execution_status", "not requested")
        )
        result["agent_fallback_used"] = "yes" if agent_runtime_summary.get("fallback_used") else "no"
        result["agent_fallback_reason"] = str(agent_runtime_summary.get("fallback_reason") or "none")
        result["agent_runtime_notes"] = "; ".join(agent_runtime_summary.get("runtime_notes", ["none"]))
        
        formatted_ai_brain_context_pack = None
        if include_ai_brain_context:
            from agents.ai_brain_context import build_ai_brain_context_pack, format_ai_brain_context_pack
            pack = build_ai_brain_context_pack(
                task=task_text,
                project_path=str(project_path) if project_path else "",
                ai_brain_path=str(ai_brain_path) if ai_brain_path else None,
                approved_paths=approved_paths,
                context_budget=5000,
            )
            formatted_ai_brain_context_pack = format_ai_brain_context_pack(pack)
            result["ai_brain_context_pack_summary"] = formatted_ai_brain_context_pack

        result["summary"] = str(planner_report["summary"])
        result["agent_runtime_summary"] = _summarize_first_line(
            format_agent_run_summary(agent_runtime_summary),
            "not available",
        )
        result["report_text"] = "\n\n".join(
            [
                section
                for section in [
                    format_planner_report(planner_report),
                    str(result.get("context_summary")) if result.get("context_summary") else None,
                    (
                        "Local MCP Context:\n" + formatted_local_mcp_context
                        if formatted_local_mcp_context is not None
                        else None
                    ),
                    (
                        "GitHub Context:\n" + formatted_github_context
                        if formatted_github_context is not None
                        else None
                    ),
                    (
                        "Error Context:\n" + formatted_error_context
                        if formatted_error_context is not None
                        else None
                    ),
                    (
                        formatted_ai_brain_context_pack
                        if formatted_ai_brain_context_pack is not None
                        else None
                    ),
                    "Agent Runtime Summary:\n" + format_agent_run_summary(agent_runtime_summary),
                ]
                if section is not None
            ]
        )

    elif mode == "review-diff":
        if project_path is None:
            result["errors"].append("Review-diff mode requires project path.")
            return result

        try:
            git_state = inspect_git_state(
                approved_project_path if approved_project_path is not None else project_path,
                approved_paths=None,
            )
        except GitGatewayError as exc:
            result["errors"].append(str(exc))
            return result

        review_diff_guard_result = None
        if git_state["diff_present"]:
            review_diff_guard_result = guard_text_output(
                str(git_state["diff_text"]),
                "Diff review output",
            )

        if review_diff_guard_result is not None and not review_diff_guard_result["allowed"]:
            review_report = generate_secret_blocked_diff_review(
                git_state,
                review_diff_guard_result,
                task_classification,
            )
        else:
            review_report = generate_multi_agent_diff_review(
                git_state,
                task_classification=task_classification,
                project_context=project_context,
            )

        result["summary"] = str(review_report["summary"])
        result["decision"] = review_report["decision"]
        result["report_text"] = format_multi_agent_diff_review(review_report)
        result["multi_agent_decision_summary"] = review_report.get("multi_agent_decision_summary")

        if save_report and review_diff_guard_result is not None and review_diff_guard_result["should_block_save"]:
            result["errors"].append(
                "Report saving blocked due to secret-like content detected in the diff."
            )
            return result

    else:
        if project_path is None:
            result["errors"].append("Run mode requires project path.")
            return result
        if not task_text:
            result["errors"].append("Run mode requires task text.")
            return result
        if not allowed_files:
            result["errors"].append("Run mode requires at least one allowed file.")
            return result
        if not confirm_codex_prompt:
            result["errors"].append("Run mode requires Codex prompt confirmation.")
            return result
        if not confirm_codex_execution:
            result["errors"].append("Run mode requires Codex execution confirmation.")
            return result

        ai_brain_core_summary = None
        if ai_brain_path is not None:
            ai_brain_core_summary = inspect_required_core_files(ai_brain_path)

        planner_report = generate_planner_report(
            task_text,
            task_classification or classify_task(""),
            project_context=project_context,
            ai_brain_core_summary=ai_brain_core_summary,
        )
        formatted_planner_report = format_planner_report(planner_report)

        edit_plan = generate_edit_plan(
            approved_project_path if approved_project_path is not None else project_path,
            task_text,
            list(allowed_files),
            approved_paths,
            task_classification=task_classification,
        )
        formatted_edit_plan = format_edit_plan(edit_plan)

        pre_codex_agent_summary = run_agent_workflow(
            task_text=task_text,
            mode="pre-codex",
            task_classification=task_classification,
            changed_files=[
                item
                for item in list(edit_plan.get("target_files", []))
                if item != "none"
            ],
            project_context=project_context,
        )
        local_mcp_context_blocks: list[dict[str, object]] = []
        local_project_knowledge_result: dict[str, object] = {
            "found_files": [],
            "missing_files": [],
        }
        formatted_local_mcp_context = None
        formatted_github_context = None
        formatted_error_context = None
        github_status_map: dict[str, str] = {}
        github_context_blocks: list[dict[str, object]] = []
        error_context_blocks: list[dict[str, object]] = []
        error_context_result: dict[str, object] = {
            "executed": False,
            "blocked": True,
            "tool_name": "not requested",
        }
        if include_local_mcp_context and approved_project_path is not None:
            (
                local_mcp_context_summary,
                formatted_local_mcp_context,
                local_mcp_context_blocks,
                local_project_knowledge_result,
            ) = _collect_local_mcp_context(
                approved_project_path,
                approved_paths,
            )
            result["local_mcp_context_summary"] = local_mcp_context_summary
        if include_github_context:
            (
                github_context_summary,
                formatted_github_context,
                github_context_blocks,
                github_status_map,
            ) = _collect_github_context(
                github_repo=github_repo,
                github_issue_number=github_issue_number,
                github_pr_number=github_pr_number,
                github_token_env=github_token_env,
                github_read_client=github_read_client if github_read_client is not None else github_client,
            )
            result["github_context_summary"] = github_context_summary
        if include_error_context:
            (
                error_context_summary,
                formatted_error_context,
                error_context_blocks,
                error_context_result,
            ) = _collect_error_context(
                approved_project_path=approved_project_path,
                approved_paths=approved_paths,
                error_tool_name=error_tool_name,
                error_provider=error_provider,
                error_issue_id=error_issue_id,
                error_log_path=error_log_path,
                error_token_env=error_token_env,
                error_read_client=error_read_client,
            )
            result["error_context_summary"] = error_context_summary

        pre_codex_agent_guidance = format_pre_codex_agent_guidance(pre_codex_agent_summary)
        local_signal_lines: list[str] = []
        github_signal_lines: list[str] = []
        error_signal_lines: list[str] = []
        if include_local_mcp_context:
            local_signal_lines = _build_local_context_signal_lines(
                local_mcp_context_blocks,
                local_project_knowledge_result,
            )
        if include_github_context:
            github_signal_lines = _build_github_context_signal_lines(
                github_repo,
                github_status_map,
                github_context_blocks,
            )
        if include_error_context:
            error_signal_lines = _build_error_context_signal_lines(error_context_result)
        context_signals_block = _build_context_signals_block(
            local_signal_lines=local_signal_lines,
            github_signal_lines=github_signal_lines,
            error_signal_lines=error_signal_lines,
        )
        if context_signals_block is not None:
            pre_codex_agent_guidance += "\n" + context_signals_block

        ai_brain_guidance = None
        formatted_ai_brain_context_pack = None
        if include_ai_brain_context:
            from agents.ai_brain_context import build_ai_brain_context_pack, format_ai_brain_context_pack, format_ai_brain_guidance_for_codex
            pack = build_ai_brain_context_pack(
                task=task_text,
                project_path=str(approved_project_path) if approved_project_path else str(project_path),
                ai_brain_path=str(ai_brain_path) if ai_brain_path else None,
                approved_paths=approved_paths,
                context_budget=5000,
            )
            formatted_ai_brain_context_pack = format_ai_brain_context_pack(pack)
            result["ai_brain_context_pack_summary"] = formatted_ai_brain_context_pack
            
            if pack.get("blocked"):
                ai_brain_guidance = "AI-Brain Guidance: Context pack blocked due to secret-like content."
            elif not pack.get("files_read"):
                ai_brain_guidance = "AI-Brain Guidance: Context pack unavailable (files missing or unreadable)."
            else:
                ai_brain_guidance = format_ai_brain_guidance_for_codex(pack)

        codex_prompt_package = generate_codex_prompt_package(
            task_text,
            str(approved_project_path if approved_project_path is not None else project_path),
            list(edit_plan.get("target_files", [])),
            edit_plan,
            task_classification=task_classification,
            planner_report_summary=str(planner_report["summary"]),
            approval_confirmed=confirm_codex_prompt,
            pre_codex_agent_guidance=pre_codex_agent_guidance,
            ai_brain_guidance=ai_brain_guidance,
        )
        formatted_codex_prompt_package = format_codex_prompt_package(codex_prompt_package)

        codex_execution_contract = evaluate_codex_execution_contract(
            approved_project_path if approved_project_path is not None else str(project_path),
            task_text,
            list(allowed_files),
            approved_paths,
            confirm_codex_prompt,
            codex_prompt_package=codex_prompt_package,
            timeout_seconds=codex_timeout,
            ai_brain_path=ai_brain_path,
        )
        formatted_codex_execution_contract = format_codex_execution_contract_view(
            codex_execution_contract
        )

        codex_execution_result = execute_codex_task_with_post_review(
            approved_project_path if approved_project_path is not None else str(project_path),
            task_text,
            list(allowed_files),
            approved_paths,
            confirm_codex_prompt,
            str(codex_prompt_package.get("prompt_text", "")),
            timeout_seconds=codex_timeout,
            execute_confirmed=confirm_codex_execution,
            codex_command=codex_command,
            ai_brain_path=ai_brain_path,
            post_codex_review=True,
            task_classification=task_classification,
            project_context=project_context,
        )
        formatted_codex_execution_result = format_codex_execution_result(codex_execution_result)
        agent_runtime_summary = run_agent_workflow(
            task_text=task_text,
            mode="run",
            task_classification=task_classification,
            changed_files=[
                item
                for item in list(edit_plan.get("target_files", []))
                if item != "none"
            ],
            project_context=project_context,
            llm_mode=agent_runtime,
            llm_enabled=llm_enabled,
            llm_approval_confirmed=confirm_llm_agent,
            context_text=agent_context_text,
            context_sources=list(agent_context_sources or []),
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_api_key_env_var=llm_api_key_env_var,
        )
        result["multi_agent_decision_summary"] = format_aggregated_decision(agent_runtime_summary.get("multi_agent_decision", {}))
        formatted_agent_runtime_summary = format_agent_run_summary(agent_runtime_summary)
        formatted_test_result = "Not requested."
        formatted_scope_enforcement = "Not available."
        test_result = None
        scope_enforcement_result = None
        if codex_execution_result["executed"] and not codex_execution_result["blocked"]:
            scope_enforcement_result = enforce_changed_file_scope(
                approved_project_path if approved_project_path is not None else str(project_path),
                list(edit_plan.get("target_files", [])),
                list(codex_execution_result.get("post_review_changed_files", [])),
            )
            formatted_scope_enforcement = format_scope_enforcement_result(scope_enforcement_result)
        github_ci_verification_status = _derive_github_ci_verification_status(
            include_github_context=include_github_context,
            github_status_map=github_status_map,
            context_blocks=github_context_blocks,
        )
        
        result["context_summary"] = _build_context_summary(
            include_local=include_local_mcp_context,
            local_knowledge_result=local_project_knowledge_result,
            local_context_blocks=local_mcp_context_blocks,
            include_github=include_github_context,
            github_status_map=github_status_map,
            github_ci_status=github_ci_verification_status,
            include_error=include_error_context,
            error_result=error_context_result,
        )
        
        verification_gate = _build_verification_gate(
            post_review_decision=str(codex_execution_result.get("post_review_decision", "not available")),
            post_review_message=str(codex_execution_result.get("post_review_message", "")),
            scope_enforcement_result=scope_enforcement_result,
            test_result=None,
            post_review_should_block_save=bool(codex_execution_result.get("post_review_should_block_save")),
            github_ci_status=github_ci_verification_status,
        )

        memory_sync_suggestion = suggest_memory_sync(
            task_text,
            task_classification or classify_task(""),
            planner_summary=str(planner_report["summary"]),
            changed_files=[
                item
                for item in list(edit_plan.get("target_files", []))
                if item != "none"
            ],
            findings_or_risks=[str(codex_execution_result.get("message", ""))],
        )

        knowledge_update_proposal = generate_knowledge_update_proposal(
            memory_sync_suggestion,
            task_text,
            findings=[
                str(codex_execution_result.get("message", "")),
                str(verification_gate.get("reason", "")),
            ],
            suggested_tests=[
                str(formatted_test_result),
            ] if test_command else [],
        )

        formatted_memory_sync = format_knowledge_update_with_compatibility(
            knowledge_update_proposal,
            memory_sync_suggestion,
        )
        changed_files_summary = "; ".join(
            [
                str(item)
                for item in list(codex_execution_result.get("post_review_changed_files", []))
                if item and item != "none"
            ]
        ) or "; ".join(
            [
                str(item)
                for item in list(edit_plan.get("target_files", []))
                if item and item != "none"
            ]
        ) or "none"

        result["gate_status"] = (
            "passed"
            if not codex_execution_result["blocked"]
            and not codex_execution_result["timed_out"]
            and codex_execution_result["return_code"] == 0
            else "blocked or failed"
        )
        result["planner_summary"] = _summarize_first_line(
            formatted_planner_report,
            "not available",
        )
        result["edit_plan_summary"] = _summarize_first_line(
            formatted_edit_plan,
            "not available",
        )
        result["codex_execution_summary"] = _summarize_first_line(
            formatted_codex_execution_result,
            "not available",
        )
        result["post_codex_review_decision"] = str(
            codex_execution_result.get("post_review_decision", "not available")
        )
        result["changed_files_summary"] = changed_files_summary
        result["codex_status_summary"] = (
            "blocked" if codex_execution_result["blocked"] else
            "failed" if (codex_execution_result["timed_out"] or codex_execution_result["return_code"] != 0) else
            "passed"
        )
        result["scope_enforcement_summary"] = _summarize_first_line(
            formatted_scope_enforcement,
            "not available",
        )
        post_review_changed_files = [
            str(item)
            for item in list(codex_execution_result.get("post_review_changed_files", []))
            if item and item != "none"
        ]
        if scope_enforcement_result is None or not post_review_changed_files:
            result["scope_status_summary"] = "unknown"
        elif scope_enforcement_result.get("passed"):
            result["scope_status_summary"] = "passed"
        else:
            result["scope_status_summary"] = "failed"
        if test_command:
            if codex_execution_result["blocked"] or codex_execution_result["timed_out"] or codex_execution_result["return_code"] != 0:
                formatted_test_result = "Not run because Codex execution did not complete successfully."
            elif scope_enforcement_result is not None and not scope_enforcement_result["passed"]:
                formatted_test_result = "Not run because scope enforcement detected changes outside the allowed files."
            elif codex_execution_result.get("post_review_should_block_save"):
                formatted_test_result = "Not run because post-Codex review was safety-blocked."
            else:
                test_result = run_test_command(
                    approved_project_path if approved_project_path is not None else str(project_path),
                    test_command,
                    approved_paths,
                    timeout_seconds=test_timeout,
                )
                formatted_test_result = format_test_result(test_result)
        verification_gate = _build_verification_gate(
            post_review_decision=str(codex_execution_result.get("post_review_decision", "not available")),
            post_review_message=str(codex_execution_result.get("post_review_message", "")),
            scope_enforcement_result=scope_enforcement_result,
            test_result=test_result,
            post_review_should_block_save=bool(codex_execution_result.get("post_review_should_block_save")),
            github_ci_status=github_ci_verification_status,
        )
        formatted_verification_gate = _format_verification_gate(verification_gate)
        result["verification_gate_summary"] = (
            f"Final verification decision: {verification_gate.get('final_verification_decision', 'not available')}; "
            f"Test status: {verification_gate.get('test_status', 'not run')}; "
            f"CI status: {verification_gate.get('ci_status', 'not run')}"
        )
        result["verification_gate_decision"] = str(
            verification_gate.get("final_verification_decision", "not available")
        )
        result["verification_test_status"] = str(
            verification_gate.get("test_status", "not run")
        )
        result["ci_status_summary"] = str(
            verification_gate.get("ci_status", "not run")
        )
        result["test_execution_summary"] = _summarize_first_line(
            formatted_test_result,
            "not requested",
        )
        result["memory_docs_summary"] = summarize_knowledge_update_proposal(
            knowledge_update_proposal
        )
        result["agent_runtime_mode"] = str(agent_runtime_summary.get("runtime_mode", "deterministic"))
        result["agent_llm_adapter_used"] = str(agent_runtime_summary.get("llm_adapter_used", "none"))
        result["agent_llm_provider"] = str(agent_runtime_summary.get("llm_provider", "disabled"))
        result["agent_provider_available"] = (
            "yes" if agent_runtime_summary.get("provider_available") else "no"
        )
        result["agent_provider_execution_status"] = str(
            agent_runtime_summary.get("provider_execution_status", "not requested")
        )
        result["agent_fallback_used"] = "yes" if agent_runtime_summary.get("fallback_used") else "no"
        result["agent_fallback_reason"] = str(agent_runtime_summary.get("fallback_reason") or "none")
        result["agent_runtime_notes"] = "; ".join(agent_runtime_summary.get("runtime_notes", ["none"]))
        result["agent_runtime_summary"] = _summarize_first_line(
            formatted_agent_runtime_summary,
            "not available",
        )
        result["report_text"] = _run_mode_report_text(
            planner_report_text=formatted_planner_report,
            context_summary_text=result.get("context_summary") if isinstance(result.get("context_summary"), str) else None,
            local_mcp_context_text=formatted_local_mcp_context,
            github_context_text=formatted_github_context,
            error_context_text=formatted_error_context,
            agent_runtime_summary_text=formatted_agent_runtime_summary,
            edit_plan_text=formatted_edit_plan,
            codex_prompt_text=formatted_codex_prompt_package,
            codex_contract_text=formatted_codex_execution_contract,
            codex_execution_text=formatted_codex_execution_result,
            scope_enforcement_text=formatted_scope_enforcement,
            verification_gate_text=formatted_verification_gate,
            test_result_text=formatted_test_result,
            memory_sync_text=formatted_memory_sync,
        )

        if codex_execution_result["blocked"]:
            result["summary"] = "Coding run stopped before Codex execution."
            result["decision"] = "Blocked"
            result["errors"].append(str(codex_execution_result["message"]))
        elif codex_execution_result["timed_out"] or codex_execution_result["return_code"] != 0:
            result["summary"] = "Coding run finished with Codex execution failure."
            result["decision"] = "Needs revision"
            result["errors"].append(str(codex_execution_result["message"]))
        else:
            result["summary"] = "Coding run completed through post-Codex review."
            result["decision"] = str(codex_execution_result.get("post_review_decision", "not available"))

        if test_result is not None:
            if test_result["blocked"]:
                result["summary"] = "Coding run completed but the test execution gate was blocked."
                result["decision"] = "Needs revision"
                result["errors"].append(str(test_result["message"]))
            elif test_result["timed_out"] or not test_result["passed"]:
                result["summary"] = "Coding run completed but the test execution gate did not pass."
                result["decision"] = "Needs revision"
                result["errors"].append(str(test_result["message"]))
            else:
                result["summary"] = "Coding run completed through post-Codex review and tests passed."

        if scope_enforcement_result is not None and not scope_enforcement_result["passed"]:
            result["summary"] = "Coding run completed with a scope violation after Codex execution."
            result["decision"] = "Blocked"
            result["errors"].append(str(scope_enforcement_result["message"]))
        elif verification_gate.get("final_verification_decision") == "Needs revision":
            result["summary"] = "Coding run completed but verification gates did not pass."
            result["decision"] = "Needs revision"
            verification_reason = str(verification_gate.get("reason") or "Verification gates did not pass.")
            if verification_reason not in result["errors"]:
                result["errors"].append(verification_reason)

        if scope_enforcement_result is not None and not scope_enforcement_result["passed"]:
            result["next_action_summary"] = (
                "Review the out-of-scope changes and revert any files outside the allowed scope manually."
            )
        elif result["decision"] == "Blocked":
            result["next_action_summary"] = str(result["errors"][0] if result["errors"] else "Resolve the blocked gate before retrying.")
        elif result["decision"] == "Needs revision":
            result["next_action_summary"] = str(result["errors"][0] if result["errors"] else verification_gate.get("reason", "Address verification findings before proceeding."))
        elif result["decision"] == "Approved with changes":
            result["next_action_summary"] = str(verification_gate.get("reason", "Apply the listed follow-up changes and rerun focused verification."))
        elif result["decision"] == "Approved":
            result["next_action_summary"] = "Proceed with normal manual verification or handoff."
        else:
            result["next_action_summary"] = str(verification_gate.get("reason", "Review the current run output before proceeding."))

        if codex_execution_result.get("post_review_should_block_save"):
            result["errors"].append(
                "Report saving blocked due to secret-like content detected in the post-Codex review flow."
            )
            if save_report:
                return result

    if save_report:
        guard_context_label = (
            "Planner report save" if mode == "plan" else "Orchestrator report save"
        )
        guard_block_message = (
            "Report saving blocked due to secret-like content detected in the planner report."
            if mode == "plan"
            else (
                "Report saving blocked due to secret-like content detected in the post-Codex review flow."
                if mode == "run"
                else "Report saving blocked due to secret-like content detected in the orchestrator report."
            )
        )
        report_text, report_path = _save_report_if_allowed(
            result,
            report_text=str(result["report_text"]),
            report_name=_report_name_for_mode(mode),
            reports_dir=reports_dir,
            guard_context_label=guard_context_label,
            guard_block_message=guard_block_message,
        )
        result["report_text"] = report_text
        result["report_path"] = report_path

    return result
