import argparse

from agents.agent_runtime import format_pre_codex_agent_guidance, run_agent_workflow
from agents.llm_agent_adapter import format_llm_agent_adapter_result, get_llm_adapter
from agents.llm_agent_contract import evaluate_llm_agent_contract, format_llm_agent_contract
from agents.llm_provider_config import format_llm_provider_config, load_llm_provider_config
from brain.ai_brain_reader import inspect_required_core_files
from brain.ai_brain_writer import AIBrainWriterError, write_ai_brain_memory
from brain.memory_sync import (
    build_memory_write_plan,
    format_memory_decision_view,
    format_memory_sync_suggestion,
    suggest_memory_sync,
)
from core.approved_paths import ApprovedPathError, ensure_approved_path
from core.config_loader import ConfigError, load_config
from core.report_writer import ReportWriterError, write_report
from core.safety import format_safety_scan, guard_text_output, scan_text_for_secrets
from orchestration.approval_gate_manager import (
    evaluate_approval_requirements,
    format_approval_requirements,
)
from orchestration.edit_plan import EditPlanError, format_edit_plan, generate_edit_plan
from orchestration.multi_agent_review import (
    format_multi_agent_diff_review,
    generate_multi_agent_diff_review,
    generate_secret_blocked_diff_review,
)
from orchestration.orchestrator_controller import format_orchestrator_result, run_orchestrator
from orchestration.planner_report import format_planner_report, generate_planner_report
from orchestration.task_classifier import classify_task
from project.project_context_reader import ProjectContextReaderError, inspect_project_context
from project.project_docs_writer import ProjectDocsWriterError, write_project_doc
from tools.codex_gateway import format_codex_prompt_package, generate_codex_prompt_package
from tools.codex_execution_contract import (
    evaluate_codex_execution_contract,
    format_codex_execution_contract,
)
from tools.codex_executor import execute_codex_task_with_post_review, format_codex_execution_result
from tools.error_logs_mcp import format_error_logs_result, run_error_logs_tool
from tools.filesystem_gateway import FilesystemGatewayError, read_file
from tools.git_gateway import GitGatewayError, inspect_git_state
from tools.github_read_mcp import format_github_read_result, run_github_read_tool
from tools.mcp_gateway import (
    evaluate_mcp_request,
    evaluate_mcp_tool_request,
    format_mcp_request_result,
    format_mcp_tool_request_result,
)
from tools.mcp_read_dispatcher import (
    format_mcp_read_dispatch_result,
    run_mcp_read_tool,
)
from tools.mcp_registry import (
    evaluate_registered_tool_request,
    format_registered_tool_request_result,
    format_registered_tools_list,
    list_registered_tools,
)
from tools.project_knowledge_mcp import (
    format_project_knowledge_result,
    read_project_knowledge,
)


DIFF_PREVIEW_LIMIT = 4000


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "AI Coding Orchestrator CLI. Recommended main entrypoint: "
            "--run-orchestrator with --mode status|plan|review-diff. "
            "Direct flags remain available for focused or advanced read-only operations."
        )
    )
    parser.add_argument("--project", help="Approved project path for project-aware commands.")
    parser.add_argument("--task", help="Task text used for planning, review, classification, and orchestration.")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--save-report", action="store_true")
    parser.add_argument(
        "--include-local-mcp-context",
        action="store_true",
        help="Include compact local read-only MCP context in orchestrator plan/run reports.",
    )
    parser.add_argument(
        "--include-github-context",
        action="store_true",
        help="Include safe read-only GitHub MCP context in orchestrator plan/run reports; uses gh CLI when configured and available.",
    )
    parser.add_argument(
        "--include-error-context",
        action="store_true",
        help="Include safe error/log context in orchestrator plan/run reports without real external API calls.",
    )
    parser.add_argument(
        "--ai-brain-context-pack",
        action="store_true",
        help="Build and print AI-Brain context pack directly.",
    )
    parser.add_argument(
        "--include-ai-brain-context",
        action="store_true",
        help="Include safe AI-Brain context pack in orchestrator plan/run reports.",
    )
    parser.add_argument(
        "--context-budget",
        type=int,
        default=5000,
        help="Max characters for the context pack.",
    )
    parser.add_argument(
        "--run-orchestrator",
        action="store_true",
        help="Recommended main entrypoint for consolidated read-only orchestration.",
    )
    parser.add_argument(
        "--mode",
        choices=("plan", "review-diff", "status", "run"),
        default="status",
        help="Orchestrator mode for --run-orchestrator. Default: status.",
    )
    parser.add_argument("--git-status", action="store_true")
    parser.add_argument("--git-diff", action="store_true")
    parser.add_argument("--review-diff", action="store_true")
    parser.add_argument("--show-approved-paths", action="store_true", help="Print configured approved paths.")
    parser.add_argument("--check-approval", action="store_true", help="Run approval-gate evaluation only.")
    parser.add_argument("--requested-action", action="append", default=[])
    parser.add_argument("--scan-text", help="Scan text for secret-like content without printing raw secret values.")
    parser.add_argument("--read-file", help="Read an approved file safely; output is blocked if secrets are detected.")
    parser.add_argument("--edit-plan", action="store_true")
    parser.add_argument("--allowed-file", action="append", default=[])
    parser.add_argument("--codex-prompt", action="store_true")
    parser.add_argument("--codex-execution-check", action="store_true")
    parser.add_argument("--execute-codex", action="store_true")
    parser.add_argument("--post-codex-review", action="store_true")
    parser.add_argument("--confirm-codex-prompt", action="store_true")
    parser.add_argument("--confirm-codex-execution", action="store_true")
    parser.add_argument("--codex-timeout", type=int)
    parser.add_argument("--codex-command", default="codex")
    parser.add_argument("--test-command")
    parser.add_argument("--test-timeout", type=int, default=120)
    parser.add_argument("--llm-agent-check", action="store_true")
    parser.add_argument("--llm-agent-adapter-check", action="store_true")
    parser.add_argument("--llm-provider-check", action="store_true")
    parser.add_argument("--agent-role", choices=("Planner", "Reviewer", "Tester", "Security", "Architect", "Product", "Release"))
    parser.add_argument("--agent-runtime", choices=("deterministic", "mock", "disabled", "openai", "gemini"), default="deterministic")
    parser.add_argument("--llm-enabled", action="store_true")
    parser.add_argument("--confirm-llm-agent", action="store_true")
    parser.add_argument("--context-text")
    parser.add_argument("--context-source", action="append", default=[])
    parser.add_argument("--llm-adapter", choices=("disabled", "mock", "openai", "gemini"), default="disabled")
    parser.add_argument("--llm-provider")
    parser.add_argument("--llm-model")
    parser.add_argument("--llm-api-key-env")
    parser.add_argument("--memory-suggest", action="store_true", help="Show read-only memory sync suggestion.")
    parser.add_argument("--memory-plan", action="store_true", help="Show memory suggestion plus safe write plan.")
    parser.add_argument("--write-project-doc")
    parser.add_argument("--content")
    parser.add_argument("--confirm-write", action="store_true")
    parser.add_argument("--write-mode", choices=("append", "create"), default="create")
    parser.add_argument("--write-ai-brain", action="store_true")
    parser.add_argument("--memory-type", choices=("lesson", "decision", "example", "bugfix"))
    parser.add_argument("--memory-path")
    parser.add_argument("--mcp-check", action="store_true", help="Policy-only MCP boundary check. No MCP execution.")
    parser.add_argument("--mcp-list-tools", action="store_true", help="List registered MCP tool metadata only.")
    parser.add_argument("--mcp-registry-check", action="store_true", help="Check registered MCP tool capabilities only.")
    parser.add_argument("--mcp-run-read", action="store_true", help="Run a registered local read-only MCP tool through safe gateways.")
    parser.add_argument("--project-knowledge-read", action="store_true", help="Read known AI-ready project docs safely as project knowledge context.")
    parser.add_argument("--github-read", action="store_true", help="Run the read-only GitHub MCP surface; uses gh CLI when configured and available, otherwise returns safe unavailable/blocked results.")
    parser.add_argument("--error-logs-read", action="store_true", help="Run the error/logs MCP foundation without real external service calls.")
    parser.add_argument("--github-tool-name")
    parser.add_argument("--github-repo")
    parser.add_argument("--github-issue-number")
    parser.add_argument("--github-pr-number")
    parser.add_argument("--github-token-env", default="GITHUB_TOKEN")
    parser.add_argument("--github-client", choices=("mock", "gh"), default="mock")
    parser.add_argument("--error-tool-name")
    parser.add_argument("--error-provider")
    parser.add_argument("--error-issue-id")
    parser.add_argument("--error-log-path")
    parser.add_argument("--error-query")
    parser.add_argument("--error-token-env", default="ERROR_MONITORING_TOKEN")
    parser.add_argument("--package-read", action="store_true")
    parser.add_argument("--package-tool-name")
    parser.add_argument("--package-ecosystem")
    parser.add_argument("--package-name")
    parser.add_argument("--package-version")
    parser.add_argument("--package-token-env")
    parser.add_argument("--package-source-path")
    parser.add_argument("--docs-research-read", action="store_true")
    parser.add_argument("--docs-tool-name")
    parser.add_argument("--docs-provider")
    parser.add_argument("--docs-query")
    parser.add_argument("--docs-source-path")
    parser.add_argument("--docs-page-id")
    parser.add_argument("--docs-token-env")
    parser.add_argument("--figma-read", action="store_true")
    parser.add_argument("--figma-tool-name")
    parser.add_argument("--figma-file-key")
    parser.add_argument("--figma-frame-id")
    parser.add_argument("--figma-component-id")
    parser.add_argument("--figma-token-env")
    parser.add_argument("--ci-status-read", action="store_true")
    parser.add_argument("--ci-provider")
    parser.add_argument("--ci-repo")
    parser.add_argument("--ci-pr-number")
    parser.add_argument("--ci-branch")
    parser.add_argument("--ci-limit", type=int, default=5)
    parser.add_argument("--ci-github-client", default="gh")
    parser.add_argument("--mcp-write-preview", action="store_true")
    parser.add_argument("--mcp-write-tool-name")
    parser.add_argument("--mcp-write-target-path")
    parser.add_argument("--mcp-write-content")
    parser.add_argument("--confirm-mcp-write", action="store_true")
    parser.add_argument("--execute-mcp-write", action="store_true")
    parser.add_argument("--mcp-audit-preview", action="store_true")
    parser.add_argument("--mcp-tool-name")
    parser.add_argument("--mcp-tool-type")
    parser.add_argument("--mcp-target-path")
    parser.add_argument("--confirm-mcp", action="store_true")
    return parser


def run(argv: list[str] | None = None) -> None:
    if argv is None:
        argv = []

    args = _build_parser().parse_args(argv)
    if args.save_report and not (
        args.plan or args.review_diff or args.run_orchestrator or args.execute_codex
    ):
        raise SystemExit(
            "Report writer error: --save-report currently requires --plan, --review-diff, --run-orchestrator, or --execute-codex."
        )
    if args.plan and args.task is None:
        raise SystemExit("Planner report error: --plan requires --task.")
    if (args.git_status or args.git_diff or args.review_diff) and args.project is None:
        raise SystemExit(
            "Git gateway error: --git-status, --git-diff, and --review-diff require --project."
        )
    if args.ai_brain_context_pack and args.project is None:
        raise SystemExit("AI-Brain Context error: --ai-brain-context-pack requires --project.")
    if args.edit_plan and args.project is None:
        raise SystemExit("Edit plan error: --edit-plan requires --project.")
    if args.codex_prompt and args.project is None:
        raise SystemExit("Codex gateway error: --codex-prompt requires --project.")
    if args.codex_prompt and args.task is None:
        raise SystemExit("Codex gateway error: --codex-prompt requires --task.")
    if args.execute_codex and args.project is None:
        raise SystemExit("Codex executor error: --execute-codex requires --project.")
    if args.execute_codex and args.task is None:
        raise SystemExit("Codex executor error: --execute-codex requires --task.")
    if args.execute_codex and not args.allowed_file:
        raise SystemExit("Codex executor error: --execute-codex requires --allowed-file.")
    if args.execute_codex and not args.confirm_codex_prompt:
        raise SystemExit("Codex executor error: --execute-codex requires --confirm-codex-prompt.")
    if args.execute_codex and not args.confirm_codex_execution:
        raise SystemExit("Codex executor error: --execute-codex requires --confirm-codex-execution.")
    if args.save_report and args.execute_codex and not args.post_codex_review:
        raise SystemExit(
            "Report writer error: --save-report with --execute-codex currently requires --post-codex-review."
        )
    if args.codex_execution_check and args.project is None:
        raise SystemExit("Codex execution contract error: --codex-execution-check requires --project.")
    if args.codex_execution_check and args.task is None:
        raise SystemExit("Codex execution contract error: --codex-execution-check requires --task.")
    if args.codex_execution_check and not args.allowed_file:
        raise SystemExit("Codex execution contract error: --codex-execution-check requires --allowed-file.")
    if args.codex_execution_check and not args.confirm_codex_prompt:
        raise SystemExit(
            "Codex execution contract error: --codex-execution-check requires --confirm-codex-prompt."
        )
    if args.llm_agent_check and args.agent_role is None:
        raise SystemExit("LLM agent contract error: --llm-agent-check requires --agent-role.")
    if args.llm_agent_check and args.task is None:
        raise SystemExit("LLM agent contract error: --llm-agent-check requires --task.")
    if args.llm_agent_adapter_check and args.agent_role is None:
        raise SystemExit("LLM agent adapter error: --llm-agent-adapter-check requires --agent-role.")
    if args.llm_agent_adapter_check and args.task is None:
        raise SystemExit("LLM agent adapter error: --llm-agent-adapter-check requires --task.")
    if args.memory_suggest and args.task is None:
        raise SystemExit("Memory sync error: --memory-suggest requires --task.")
    if args.memory_plan and args.task is None:
        raise SystemExit("Memory sync error: --memory-plan requires --task.")
    if args.write_project_doc and args.project is None:
        raise SystemExit("Project docs writer error: --write-project-doc requires --project.")
    if args.write_project_doc and args.content is None:
        raise SystemExit("Project docs writer error: --write-project-doc requires --content.")
    if args.write_ai_brain and args.memory_type is None:
        raise SystemExit("AI-Brain writer error: --write-ai-brain requires --memory-type.")
    if args.write_ai_brain and args.content is None:
        raise SystemExit("AI-Brain writer error: --write-ai-brain requires --content.")
    if args.mcp_check and args.mcp_tool_name is None:
        raise SystemExit("MCP gateway error: --mcp-check requires --mcp-tool-name.")
    if args.mcp_check and args.mcp_tool_type is None:
        raise SystemExit("MCP gateway error: --mcp-check requires --mcp-tool-type.")
    if args.mcp_registry_check and args.mcp_tool_name is None:
        raise SystemExit("MCP registry error: --mcp-registry-check requires --mcp-tool-name.")
    if args.mcp_registry_check and args.mcp_tool_type is None:
        raise SystemExit("MCP registry error: --mcp-registry-check requires --mcp-tool-type.")
    if args.mcp_run_read and args.mcp_tool_name is None:
        raise SystemExit("MCP read dispatcher error: --mcp-run-read requires --mcp-tool-name.")
    if args.project_knowledge_read and args.project is None:
        raise SystemExit("Project knowledge MCP error: --project-knowledge-read requires --project.")
    if args.github_read and args.github_tool_name is None:
        raise SystemExit("GitHub read MCP error: --github-read requires --github-tool-name.")
    if args.github_read and args.github_repo is None:
        raise SystemExit("GitHub read MCP error: --github-read requires --github-repo.")
    if args.error_logs_read and args.error_tool_name is None:
        raise SystemExit("Error/logs MCP error: --error-logs-read requires --error-tool-name.")
    if args.error_logs_read and args.error_provider is None:
        raise SystemExit("Error/logs MCP error: --error-logs-read requires --error-provider.")
    if args.package_read:
        if args.package_tool_name is None:
            raise SystemExit("Package MCP error: --package-read requires --package-tool-name.")
        if args.package_ecosystem is None:
            raise SystemExit("Package MCP error: --package-read requires --package-ecosystem.")
        if args.package_tool_name == "package.manifest.read":
            if args.package_source_path is None:
                raise SystemExit("Package MCP error: package.manifest.read requires --package-source-path.")
        elif args.package_tool_name == "package.changelog.read" and args.package_ecosystem == "local_changelog":
            if args.package_source_path is None:
                raise SystemExit("Package MCP error: local changelog requires --package-source-path.")
        elif args.package_name is None:
            raise SystemExit("Package MCP error: --package-read requires --package-name.")
    if args.docs_research_read and args.docs_tool_name is None:
        raise SystemExit("Docs research error: --docs-research-read requires --docs-tool-name.")
    if args.docs_research_read and args.docs_provider is None:
        raise SystemExit("Docs research error: --docs-research-read requires --docs-provider.")
    if args.figma_read and args.figma_tool_name is None:
        raise SystemExit("Figma MCP error: --figma-read requires --figma-tool-name.")
    if args.mcp_write_preview and args.mcp_write_tool_name is None:
        raise SystemExit("Controlled Write MCP error: --mcp-write-preview requires --mcp-write-tool-name.")
    if args.mcp_write_preview and args.mcp_write_content is None:
        raise SystemExit("Controlled Write MCP error: --mcp-write-preview requires --mcp-write-content.")

    print("AI Coding Orchestrator skeleton ready.")

    try:
        config = load_config()
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    print(f"AI-Brain path: {config['ai_brain_path']}")
    print(f"Reports directory: {config['reports_dir']}")
    print(f"Phase: {config['phase']}")
    print(f"Read-only: {config['read_only']}")
    print(f"Approved paths count: {len(config['approved_paths'])}")

    if args.show_approved_paths:
        print(f"Configured approved paths count: {len(config['approved_paths'])}")
        if config["approved_paths"]:
            print(f"Configured approved paths: {', '.join(config['approved_paths'])}")
        return

    if args.run_orchestrator:
        orchestrator_result = run_orchestrator(
            task_text=args.task,
            mode=args.mode,
            project_path=args.project,
            allowed_files=args.allowed_file,
            confirm_codex_prompt=args.confirm_codex_prompt,
            confirm_codex_execution=args.confirm_codex_execution,
            codex_timeout=args.codex_timeout or 300,
            codex_command=args.codex_command,
            save_report=args.save_report,
            reports_dir=config.get("reports_dir"),
            approved_paths=config["approved_paths"],
            ai_brain_path=config.get("ai_brain_path"),
            include_local_mcp_context=args.include_local_mcp_context,
            include_github_context=args.include_github_context,
            include_error_context=args.include_error_context,
            include_ai_brain_context=args.include_ai_brain_context,
            agent_runtime=args.agent_runtime,
            llm_enabled=args.llm_enabled,
            confirm_llm_agent=args.confirm_llm_agent,
            llm_provider=args.llm_provider,
            llm_model=args.llm_model,
            llm_api_key_env_var=args.llm_api_key_env,
            test_command=args.test_command,
            test_timeout=args.test_timeout,
            github_repo=args.github_repo,
            github_issue_number=args.github_issue_number,
            github_pr_number=args.github_pr_number,
            github_token_env=args.github_token_env or "GITHUB_TOKEN",
            github_client=args.github_client,
            error_tool_name=args.error_tool_name,
            error_provider=args.error_provider,
            error_issue_id=args.error_issue_id,
            error_log_path=args.error_log_path,
            error_token_env=args.error_token_env or "ERROR_MONITORING_TOKEN",
        )

        print(format_orchestrator_result(orchestrator_result))

        if orchestrator_result["errors"]:
            if not orchestrator_result["report_text"]:
                raise SystemExit(f"Orchestrator error: {orchestrator_result['errors'][0]}")
        return

    if args.mcp_check:
        mcp_result = evaluate_mcp_request(
            args.mcp_tool_name or "",
            args.mcp_tool_type or "",
            target_path=args.mcp_target_path,
            approved_paths=config["approved_paths"],
            approval_confirmed=args.confirm_mcp,
        )
        print(format_mcp_request_result(mcp_result))
        return

    if args.mcp_list_tools:
        print(format_registered_tools_list(list_registered_tools()))
        return

    if args.mcp_registry_check:
        registry_result = evaluate_registered_tool_request(
            args.mcp_tool_name or "",
            args.mcp_tool_type or "",
            approval_confirmed=args.confirm_mcp,
        )
        print(format_registered_tool_request_result(registry_result))
        return

    if args.mcp_run_read:
        read_result = run_mcp_read_tool(
            args.mcp_tool_name or "",
            args.mcp_target_path,
            config["approved_paths"],
            project_path=args.project,
        )
        print(format_mcp_read_dispatch_result(read_result))
        if args.mcp_audit_preview and "audit_event" in read_result:
            from tools.mcp_audit import format_mcp_audit_event
            print("\n--- MCP Audit Preview ---")
            print(format_mcp_audit_event(read_result["audit_event"]))
        return

    if args.project_knowledge_read:
        project_knowledge_result = read_project_knowledge(
            args.project or "",
            config["approved_paths"],
        )
        print(format_project_knowledge_result(project_knowledge_result))
        return

    if args.github_read:
        github_read_result = run_github_read_tool(
            args.github_tool_name or "",
            args.github_repo or "",
            issue_number=args.github_issue_number,
            pr_number=args.github_pr_number,
            token_env_var=args.github_token_env or "GITHUB_TOKEN",
            client=args.github_client,
        )
        print(format_github_read_result(github_read_result))
        return

    if args.ci_status_read:
        from tools.ci_status_mcp import run_ci_status_tool, format_ci_status_result
        ci_result = run_ci_status_tool(
            "test.ci_status.read",
            provider=args.ci_provider or "",
            repo=args.ci_repo,
            branch=args.ci_branch,
            pr_number=args.ci_pr_number,
            limit=args.ci_limit,
            github_client=args.ci_github_client,
        )
        print(format_ci_status_result(ci_result))
        return

    if args.error_logs_read:
        error_logs_result = run_error_logs_tool(
            args.error_tool_name or "",
            args.error_provider or "",
            project_path=args.project,
            issue_id=args.error_issue_id,
            log_path=args.error_log_path,
            query=args.error_query,
            token_env_var=args.error_token_env or "ERROR_MONITORING_TOKEN",
            approved_paths=config["approved_paths"],
        )
        print(format_error_logs_result(error_logs_result))
        return

    if args.package_read:
        from tools.package_dependency_mcp import (
            format_package_dependency_result,
            run_package_dependency_tool,
        )
        pkg_result = run_package_dependency_tool(
            args.package_tool_name or "",
            ecosystem=args.package_ecosystem or "",
            package_name=args.package_name or "",
            version=args.package_version,
            token_env_var=args.package_token_env,
            source_path=args.package_source_path,
            project_path=args.project,
            approved_paths=config["approved_paths"],
        )
        print(format_package_dependency_result(pkg_result))
        return

    if args.docs_research_read:
        from tools.docs_research_mcp import (
            format_docs_research_result,
            run_docs_research_tool,
        )
        docs_result = run_docs_research_tool(
            args.docs_tool_name or "",
            args.docs_provider or "",
            query=args.docs_query,
            source_path=args.docs_source_path,
            page_id=args.docs_page_id,
            token_env_var=args.docs_token_env,
            approved_paths=config["approved_paths"],
        )
        print(format_docs_research_result(docs_result))
        return

    if args.figma_read:
        from tools.figma_design_mcp import (
            format_figma_design_result,
            run_figma_design_tool,
        )
        figma_result = run_figma_design_tool(
            args.figma_tool_name or "",
            file_key=args.figma_file_key,
            frame_id=args.figma_frame_id,
            component_id=args.figma_component_id,
            token_env_var=args.figma_token_env,
        )
        print(format_figma_design_result(figma_result))
        return

    if args.mcp_write_preview:
        from tools.mcp_controlled_write import (
            format_controlled_write_result,
            run_controlled_write_tool,
        )
        write_result = run_controlled_write_tool(
            args.mcp_write_tool_name or "",
            args.mcp_write_content or "",
            config["approved_paths"],
            target_path=args.mcp_write_target_path,
            approval_confirmed=args.confirm_mcp_write,
            dry_run=not args.execute_mcp_write,
        )
        print(format_controlled_write_result(write_result))
        if args.mcp_audit_preview and "audit_event" in write_result:
            from tools.mcp_audit import format_mcp_audit_event
            print("\n--- MCP Audit Preview ---")
            print(format_mcp_audit_event(write_result["audit_event"]))
        return

    if args.read_file is not None:
        try:
            file_content = read_file(args.read_file, config["approved_paths"])
        except FilesystemGatewayError as exc:
            raise SystemExit(f"Filesystem gateway error: {exc}") from exc

        file_read_guard_result = guard_text_output(
            file_content,
            "File read output",
        )
        if not file_read_guard_result["allowed"]:
            print(file_read_guard_result["safe_message"])
            for finding in file_read_guard_result["findings"]:
                print(f"Finding: {finding['summary']}")
            return

        print(file_content)
        return

    if args.llm_agent_check:
        llm_agent_contract = evaluate_llm_agent_contract(
            args.agent_role or "",
            args.task or "",
            context_text=args.context_text,
            allowed_context_sources=args.context_source,
            approval_confirmed=args.confirm_llm_agent,
            llm_enabled=args.llm_enabled,
        )
        print(format_llm_agent_contract(llm_agent_contract))
        return

    if args.llm_provider_check:
        llm_provider_config = load_llm_provider_config(
            config,
            provider_override=args.llm_provider,
            model_override=args.llm_model,
            api_key_env_var_override=args.llm_api_key_env,
            enabled_override=True if args.llm_enabled else None,
        )
        print(format_llm_provider_config(llm_provider_config))
        return

    if args.llm_agent_adapter_check:
        llm_provider_config = load_llm_provider_config(
            config,
            provider_override=args.llm_provider,
            model_override=args.llm_model,
            api_key_env_var_override=args.llm_api_key_env,
            enabled_override=True if args.llm_enabled else None,
        )
        llm_agent_contract = evaluate_llm_agent_contract(
            args.agent_role or "",
            args.task or "",
            context_text=args.context_text,
            allowed_context_sources=args.context_source,
            approval_confirmed=args.confirm_llm_agent,
            llm_enabled=args.llm_enabled,
        )
        llm_adapter = get_llm_adapter(args.llm_adapter)
        llm_adapter_result = llm_adapter.run_agent(
            agent_role=args.agent_role or "",
            task_text=args.task or "",
            context_text=args.context_text,
            contract_result=llm_agent_contract,
            provider_config=llm_provider_config,
        )
        print("LLM provider config:")
        print(format_llm_provider_config(llm_provider_config))
        print("LLM agent contract:")
        print(format_llm_agent_contract(llm_agent_contract))
        print("LLM agent adapter result:")
        print(format_llm_agent_adapter_result(llm_adapter_result))
        return

    if args.write_ai_brain:
        try:
            write_result = write_ai_brain_memory(
                config["ai_brain_path"],
                args.memory_type or "",
                args.memory_path,
                args.content or "",
                approval_confirmed=args.confirm_write,
                mode=args.write_mode,
            )
        except AIBrainWriterError as exc:
            raise SystemExit(f"AI-Brain writer error: {exc}") from exc

        if not write_result["written"]:
            raise SystemExit(f"AI-Brain writer error: {write_result['message']}")

        print(f"AI-Brain write action: {write_result['action']}")
        print(f"AI-Brain target: {write_result['target_path']}")
        print(f"AI-Brain message: {write_result['message']}")
        return

    if args.write_project_doc is not None:
        try:
            write_result = write_project_doc(
                args.project,
                args.write_project_doc,
                args.content or "",
                config["approved_paths"],
                approval_confirmed=args.confirm_write,
                mode=args.write_mode,
            )
        except ProjectDocsWriterError as exc:
            raise SystemExit(f"Project docs writer error: {exc}") from exc

        if not write_result["written"]:
            raise SystemExit(f"Project docs writer error: {write_result['message']}")

        print(f"Project docs write action: {write_result['action']}")
        print(f"Project docs target: {write_result['target_path']}")
        print(f"Project docs message: {write_result['message']}")
        return

    core_file_status = inspect_required_core_files(config["ai_brain_path"])
    print(f"AI-Brain core files checked: {core_file_status['checked_count']}")
    print(f"Required core files found: {core_file_status['found_count']}")
    print(f"Required core files missing: {core_file_status['missing_count']}")

    project_context = None
    approved_project_path = None
    if not args.project:
        print("Project context check: not run by default")
    else:
        try:
            approved_project_path = ensure_approved_path(
                args.project,
                config["approved_paths"],
            )
        except ApprovedPathError as exc:
            raise SystemExit(f"Approved path error: {exc}") from exc

        try:
            project_context = inspect_project_context(approved_project_path)
        except ProjectContextReaderError as exc:
            raise SystemExit(f"Project context error: {exc}") from exc

        print(f"Project working directory: {project_context['working_directory']}")
        print(f"Found AI-ready files count: {len(project_context['found_files'])}")
        print(f"Missing AI-ready files count: {len(project_context['missing_files'])}")

        if project_context["found_files"]:
            print(f"Found AI-ready files: {', '.join(project_context['found_files'])}")
        if project_context["missing_files"]:
            print(f"Missing AI-ready files: {', '.join(project_context['missing_files'])}")

    git_state = None
    review_diff_guard_result = None
    git_diff_guard_result = None
    if args.git_status or args.git_diff or args.review_diff:
        try:
            git_state = inspect_git_state(approved_project_path)
        except GitGatewayError as exc:
            raise SystemExit(f"Git gateway error: {exc}") from exc

        print(f"Git repository: {'yes' if git_state['is_git_repo'] else 'no'}")
        print(f"Git status summary: {git_state['status_summary']}")
        print(f"Changed files count: {len(git_state['changed_files'])}")

        if args.review_diff and git_state["diff_present"]:
            review_diff_guard_result = guard_text_output(
                str(git_state["diff_text"]),
                "Diff review output",
            )
        if args.git_diff and git_state["diff_present"]:
            git_diff_guard_result = review_diff_guard_result or guard_text_output(
                str(git_state["diff_text"]),
                "Git diff output",
            )

        if args.git_status and git_state["changed_files"]:
            print(f"Changed files: {', '.join(git_state['changed_files'])}")

        if args.git_diff:
            print(f"Git diff present: {'yes' if git_state['diff_present'] else 'no'}")
            if git_state["diff_present"]:
                if git_diff_guard_result is not None and not git_diff_guard_result["allowed"]:
                    print(git_diff_guard_result["safe_message"])
                    for finding in git_diff_guard_result["findings"]:
                        print(f"Finding: {finding['summary']}")
                else:
                    diff_text = str(git_state["diff_text"])
                    if len(diff_text) > DIFF_PREVIEW_LIMIT:
                        print(
                            "Git diff preview (truncated): "
                            f"{diff_text[:DIFF_PREVIEW_LIMIT]}"
                        )
                    else:
                        print(f"Git diff:\n{diff_text}")

    task_result = classify_task(args.task) if args.task is not None else None
    edit_plan = None
    pre_codex_agent_guidance = None

    if args.edit_plan or args.codex_prompt or args.codex_execution_check or args.execute_codex:
        try:
            edit_plan = generate_edit_plan(
                approved_project_path if approved_project_path is not None else args.project,
                args.task or "",
                args.allowed_file,
                config["approved_paths"],
                task_classification=task_result,
            )
        except EditPlanError as exc:
            raise SystemExit(f"Edit plan error: {exc}") from exc

        if args.edit_plan:
            print(format_edit_plan(edit_plan))

        pre_codex_changed_files = [
            item
            for item in list(edit_plan.get("target_files", []))
            if item != "none"
        ]
        pre_codex_agent_summary = run_agent_workflow(
            task_text=args.task or "",
            mode="pre-codex",
            task_classification=task_result,
            changed_files=pre_codex_changed_files,
            project_context=project_context,
        )
        pre_codex_agent_guidance = format_pre_codex_agent_guidance(pre_codex_agent_summary)

        ai_brain_guidance = None
        if args.include_ai_brain_context:
            from agents.ai_brain_context import build_ai_brain_context_pack, format_ai_brain_guidance_for_codex
            pack = build_ai_brain_context_pack(
                task=args.task or "",
                project_path=str(approved_project_path if approved_project_path is not None else args.project),
                ai_brain_path=config.get("ai_brain_path"),
                approved_paths=config.get("approved_paths", []),
                context_budget=args.context_budget,
            )
            if pack.get("blocked"):
                ai_brain_guidance = "AI-Brain Guidance: Context pack blocked due to secret-like content."
            elif not pack.get("files_read"):
                ai_brain_guidance = "AI-Brain Guidance: Context pack unavailable (files missing or unreadable)."
            else:
                ai_brain_guidance = format_ai_brain_guidance_for_codex(pack)

    if args.codex_prompt:
        codex_prompt_package = generate_codex_prompt_package(
            args.task or "",
            str(approved_project_path if approved_project_path is not None else args.project),
            [] if edit_plan is None else list(edit_plan.get("target_files", [])),
            edit_plan,
            task_classification=task_result,
            approval_confirmed=args.confirm_codex_prompt,
            pre_codex_agent_guidance=pre_codex_agent_guidance,
            ai_brain_guidance=ai_brain_guidance,
        )
        formatted_codex_prompt_package = format_codex_prompt_package(codex_prompt_package)
        codex_prompt_guard_result = guard_text_output(
            formatted_codex_prompt_package,
            "Codex prompt package output",
        )
        if not codex_prompt_guard_result["allowed"]:
            print(codex_prompt_guard_result["safe_message"])
            for finding in codex_prompt_guard_result["findings"]:
                print(f"Finding: {finding['summary']}")
        else:
            print(formatted_codex_prompt_package)

    if args.codex_execution_check:
        codex_prompt_package_for_contract = generate_codex_prompt_package(
            args.task or "",
            str(approved_project_path if approved_project_path is not None else args.project),
            [] if edit_plan is None else list(edit_plan.get("target_files", [])),
            edit_plan,
            task_classification=task_result,
            approval_confirmed=args.confirm_codex_prompt,
            pre_codex_agent_guidance=pre_codex_agent_guidance,
            ai_brain_guidance=ai_brain_guidance,
        )
        codex_execution_contract = evaluate_codex_execution_contract(
            approved_project_path if approved_project_path is not None else str(args.project),
            args.task or "",
            args.allowed_file,
            config["approved_paths"],
            args.confirm_codex_prompt,
            codex_prompt_package=codex_prompt_package_for_contract,
            timeout_seconds=args.codex_timeout,
            ai_brain_path=config["ai_brain_path"],
        )
        print(format_codex_execution_contract(codex_execution_contract))

    if args.execute_codex:
        codex_prompt_package_for_execution = generate_codex_prompt_package(
            args.task or "",
            str(approved_project_path if approved_project_path is not None else args.project),
            [] if edit_plan is None else list(edit_plan.get("target_files", [])),
            edit_plan,
            task_classification=task_result,
            approval_confirmed=args.confirm_codex_prompt,
            pre_codex_agent_guidance=pre_codex_agent_guidance,
            ai_brain_guidance=ai_brain_guidance,
        )
        codex_execution_result = execute_codex_task_with_post_review(
            approved_project_path if approved_project_path is not None else str(args.project),
            args.task or "",
            args.allowed_file,
            config["approved_paths"],
            args.confirm_codex_prompt,
            str(codex_prompt_package_for_execution.get("prompt_text", "")),
            timeout_seconds=args.codex_timeout or 300,
            execute_confirmed=args.confirm_codex_execution,
            codex_command=args.codex_command,
            ai_brain_path=config["ai_brain_path"],
            post_codex_review=args.post_codex_review,
            task_classification=task_result,
            project_context=project_context,
        )
        formatted_codex_execution_result = format_codex_execution_result(codex_execution_result)
        print(formatted_codex_execution_result)
        if args.save_report:
            codex_save_guard_result = guard_text_output(
                formatted_codex_execution_result,
                "Post-Codex execution review save",
            )
            if not codex_save_guard_result["allowed"] or codex_execution_result.get("post_review_should_block_save"):
                print("Report saving blocked due to secret-like content detected in the post-Codex review flow.")
            else:
                try:
                    created_report_path = write_report(
                        formatted_codex_execution_result,
                        "codex-execution-review",
                        config["reports_dir"],
                    )
                except ReportWriterError as exc:
                    raise SystemExit(f"Report writer error: {exc}") from exc

                print(f"Report saved to: {created_report_path}")

    if args.memory_suggest:
        memory_sync_suggestion = suggest_memory_sync(
            args.task or "",
            task_result or classify_task(""),
            changed_files=[] if edit_plan is None else list(edit_plan.get("target_files", [])),
        )
        print(format_memory_sync_suggestion(memory_sync_suggestion))

    if args.memory_plan:
        memory_sync_suggestion = suggest_memory_sync(
            args.task or "",
            task_result or classify_task(""),
            changed_files=[] if edit_plan is None else list(edit_plan.get("target_files", [])),
        )
        memory_write_plan = build_memory_write_plan(
            memory_sync_suggestion,
            args.task or "",
            project_path=str(approved_project_path) if approved_project_path is not None else args.project,
        )
        print(format_memory_decision_view(memory_sync_suggestion, memory_write_plan))

    if args.check_approval:
        approval_gate = evaluate_approval_requirements(
            task_classification=classify_task(args.task) if args.task else None,
            requested_actions=args.requested_action,
        )
        print(format_approval_requirements(approval_gate))
        return

    if args.ai_brain_context_pack:
        from agents.ai_brain_context import build_ai_brain_context_pack, format_ai_brain_context_pack
        pack = build_ai_brain_context_pack(
            task=args.task or "",
            project_path=args.project,
            ai_brain_path=config.get("ai_brain_path"),
            approved_paths=config.get("approved_paths", []),
            context_budget=args.context_budget,
        )
        print(format_ai_brain_context_pack(pack))
        return

    if args.scan_text is not None:
        safety_result = scan_text_for_secrets(args.scan_text)
        print(format_safety_scan(safety_result))

    if args.review_diff:
        if review_diff_guard_result is not None and not review_diff_guard_result["allowed"]:
            review_report = generate_secret_blocked_diff_review(
                git_state,
                review_diff_guard_result,
                task_result,
            )
        else:
            review_report = generate_multi_agent_diff_review(
                git_state,
                task_classification=task_result,
                project_context=project_context,
            )
        formatted_review = format_multi_agent_diff_review(review_report)
        print(formatted_review)
        if args.save_report and review_diff_guard_result is not None and review_diff_guard_result["should_block_save"]:
            print("Report saving blocked due to secret-like content detected in the diff.")
        elif args.save_report:
            try:
                created_report_path = write_report(
                    formatted_review,
                    "multi-agent-diff-review",
                    config["reports_dir"],
                )
            except ReportWriterError as exc:
                raise SystemExit(f"Report writer error: {exc}") from exc

            print(f"Report saved to: {created_report_path}")

    if args.task is not None and not args.review_diff:
        if args.plan:
            planner_report = generate_planner_report(
                args.task,
                task_result,
                project_context=project_context,
                ai_brain_core_summary=core_file_status,
            )
            formatted_report = format_planner_report(planner_report)
            if args.save_report:
                planner_save_guard_result = guard_text_output(
                    formatted_report,
                    "Planner report save",
                )
                if not planner_save_guard_result["allowed"]:
                    print(planner_save_guard_result["safe_message"])
                    for finding in planner_save_guard_result["findings"]:
                        print(f"Finding: {finding['summary']}")
                    print("Report saving blocked due to secret-like content detected in the planner report.")
                    return

            print(formatted_report)
            if args.save_report:
                try:
                    created_report_path = write_report(
                        formatted_report,
                        "planner-report",
                        config["reports_dir"],
                    )
                except ReportWriterError as exc:
                    raise SystemExit(f"Report writer error: {exc}") from exc

                print(f"Report saved to: {created_report_path}")
        elif (
            not args.check_approval
            and not args.edit_plan
            and not args.codex_prompt
            and not args.memory_suggest
            and not args.memory_plan
        ):
            print(f"Task type: {task_result['primary_task_type']}")
            print(f"Confidence: {task_result['confidence']}")
            print(f"Risk level: {task_result['risk_level']}")
            print(f"Rationale: {task_result['rationale']}")
            if task_result["secondary_task_types"]:
                print(f"Secondary task types: {', '.join(task_result['secondary_task_types'])}")
