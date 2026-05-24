#!/usr/bin/env bash
set -e

echo "=== MCP Live Validation Suite ==="
echo "This script validates the real MCP connectors without relying on mock data."

RUN_MCP_LIVE_READS=${RUN_MCP_LIVE_READS:-0}
RUN_MCP_LIVE_WRITES=${RUN_MCP_LIVE_WRITES:-0}
RUN_FIGMA_LIVE_CHECK=${RUN_FIGMA_LIVE_CHECK:-0}
RUN_SENTRY_LIVE_CHECK=${RUN_SENTRY_LIVE_CHECK:-0}

export PYTHONPATH=${PYTHONPATH:-src}
PROJECT_ROOT=${PROJECT_ROOT:-.}

echo ""
echo "[INFO] Current Configuration:"
echo "RUN_MCP_LIVE_READS=$RUN_MCP_LIVE_READS"
echo "RUN_MCP_LIVE_WRITES=$RUN_MCP_LIVE_WRITES"
echo "RUN_FIGMA_LIVE_CHECK=$RUN_FIGMA_LIVE_CHECK"
echo "RUN_SENTRY_LIVE_CHECK=$RUN_SENTRY_LIVE_CHECK"
echo ""

if [ "$RUN_MCP_LIVE_READS" -eq 0 ] && [ "$RUN_MCP_LIVE_WRITES" -eq 0 ] && [ "$RUN_FIGMA_LIVE_CHECK" -eq 0 ] && [ "$RUN_SENTRY_LIVE_CHECK" -eq 0 ]; then
  echo "You are running in Dry Run / Checklist mode."
  echo "To execute real tests, set the relevant environment variables to 1."
  echo "For example:"
  echo "  RUN_MCP_LIVE_READS=1 scripts/check_mcp_live_connectors.sh"
  echo ""
fi

run_cmd() {
  local cmd="$1"
  local skip="$2"
  echo "> $cmd"
  if [ "$skip" -eq 1 ]; then
    echo "  [SKIPPED]"
  else
    eval "$cmd" || echo "  [FAILED or BLOCKED safely]"
  fi
  echo ""
}

echo "=== System Registry ==="
run_cmd "python3 src/main.py --mcp-list-tools" 0

echo "=== Git and Filesystem Reads ==="
skip_read=$(( RUN_MCP_LIVE_READS == 1 ? 0 : 1 ))

if [ "$skip_read" -eq 0 ] && git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  run_cmd "python3 src/main.py --mcp-run-read --mcp-tool-name git.status --mcp-target-path \"$PROJECT_ROOT\" --project \"$PROJECT_ROOT\"" 0
  run_cmd "python3 src/main.py --mcp-run-read --mcp-tool-name git.diff --mcp-target-path \"$PROJECT_ROOT\" --project \"$PROJECT_ROOT\"" 0
  run_cmd "python3 src/main.py --mcp-run-read --mcp-tool-name git.log --mcp-target-path \"$PROJECT_ROOT\" --project \"$PROJECT_ROOT\"" 0
elif [ "$skip_read" -eq 0 ]; then
  echo "  [SKIPPED] $PROJECT_ROOT is not a git repository."
else
  run_cmd "python3 src/main.py --mcp-run-read --mcp-tool-name git.status --mcp-target-path \"$PROJECT_ROOT\" --project \"$PROJECT_ROOT\"" 1
  run_cmd "python3 src/main.py --mcp-run-read --mcp-tool-name git.diff --mcp-target-path \"$PROJECT_ROOT\" --project \"$PROJECT_ROOT\"" 1
  run_cmd "python3 src/main.py --mcp-run-read --mcp-tool-name git.log --mcp-target-path \"$PROJECT_ROOT\" --project \"$PROJECT_ROOT\"" 1
fi
run_cmd "python3 src/main.py --project-knowledge-read --project \"$PROJECT_ROOT\"" "$skip_read"

echo "=== Docs Research Reads ==="
run_cmd "python3 src/main.py --docs-research-read --docs-tool-name docs.search --docs-provider local_docs --docs-query test --docs-source-path \"$PROJECT_ROOT\"" "$skip_read"
echo "[INFO] Note: If README.md contains secrets, it may be blocked. This is a SAFE and EXPECTED outcome."
run_cmd "python3 src/main.py --docs-research-read --docs-tool-name docs.page.read --docs-provider local_docs --docs-source-path README.md" "$skip_read"

echo "=== Local Dev Logs Reads ==="
if [ "$skip_read" -eq 0 ]; then
  mkdir -p reports/tmp && echo "test log" > reports/tmp/test.log
  run_cmd "python3 src/main.py --error-logs-read --error-tool-name local.dev_logs.search --error-provider local --error-query test --project \"$PROJECT_ROOT\" --error-log-path reports/tmp" 0
  rm -rf reports/tmp
else
  run_cmd "python3 src/main.py --error-logs-read --error-tool-name local.dev_logs.search --error-provider local --error-query test --project \"$PROJECT_ROOT\"" 1
fi

echo "=== Package Dependency MCP Reads ==="
run_cmd "python3 src/main.py --package-read --package-tool-name package.metadata.read --package-ecosystem npm --package-name react" "$skip_read"
run_cmd "python3 src/main.py --package-read --package-tool-name package.metadata.read --package-ecosystem pypi --package-name requests" "$skip_read"
run_cmd "python3 src/main.py --package-read --package-tool-name package.advisory.read --package-ecosystem npm --package-name lodash --package-version 4.17.20" "$skip_read"

if [ -f "$PROJECT_ROOT/package.json" ]; then
  run_cmd "python3 src/main.py --package-read --package-tool-name package.manifest.read --package-ecosystem local_manifest --package-source-path \"$PROJECT_ROOT/package.json\" --project \"$PROJECT_ROOT\"" "$skip_read"
elif [ -f "$PROJECT_ROOT/pyproject.toml" ]; then
  run_cmd "python3 src/main.py --package-read --package-tool-name package.manifest.read --package-ecosystem local_manifest --package-source-path \"$PROJECT_ROOT/pyproject.toml\" --project \"$PROJECT_ROOT\"" "$skip_read"
elif [ -f "$PROJECT_ROOT/requirements.txt" ]; then
  run_cmd "python3 src/main.py --package-read --package-tool-name package.manifest.read --package-ecosystem local_manifest --package-source-path \"$PROJECT_ROOT/requirements.txt\" --project \"$PROJECT_ROOT\"" "$skip_read"
else
  echo "[INFO] No package.json, pyproject.toml, or requirements.txt found for manifest test"
fi

echo "=== GitHub CI and Issues via gh ==="
if [ "$skip_read" -eq 0 ]; then
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    run_cmd "python3 src/main.py --ci-status-read --ci-provider github_actions --ci-repo cli/cli --ci-github-client gh" 0
    run_cmd "python3 src/main.py --github-read --github-tool-name github.issue.read --github-repo cli/cli --github-issue-number 1 --github-client gh" 0
  else
    echo "  [SKIPPED] gh not installed or not authenticated."
  fi
else
  run_cmd "python3 src/main.py --ci-status-read --ci-provider github_actions --ci-repo cli/cli --ci-github-client gh" 1
  run_cmd "python3 src/main.py --github-read --github-tool-name github.issue.read --github-repo cli/cli --github-issue-number 1 --github-client gh" 1
fi

echo "=== Figma Frame Read ==="
skip_figma=$(( RUN_FIGMA_LIVE_CHECK == 1 ? 0 : 1 ))
if [ -z "$FIGMA_TOKEN" ] && [ "$skip_figma" -eq 0 ]; then
  echo "  [SKIPPED] FIGMA_TOKEN not set."
else
  run_cmd "python3 src/main.py --figma-read --figma-tool-name figma.frame.read --figma-file-key 123 --figma-frame-id 456 --figma-token-env FIGMA_TOKEN" "$skip_figma"
fi

echo "=== Error Monitoring Read ==="
skip_sentry=$(( RUN_SENTRY_LIVE_CHECK == 1 ? 0 : 1 ))
if [ -z "$ERROR_MONITORING_TOKEN" ] && [ "$skip_sentry" -eq 0 ]; then
  echo "  [SKIPPED] ERROR_MONITORING_TOKEN not set."
else
  run_cmd "python3 src/main.py --error-logs-read --error-tool-name error_monitoring.issue.read --error-provider sentry --error-issue-id 123 --error-token-env ERROR_MONITORING_TOKEN" "$skip_sentry"
fi

echo "=== Controlled Write Preview ==="
run_cmd "python3 src/main.py --mcp-write-preview --mcp-write-tool-name report.export --mcp-write-target-path reports/test.md --mcp-write-content 'test'" 0

echo "=== Controlled Local Write ==="
skip_write=$(( RUN_MCP_LIVE_WRITES == 1 ? 0 : 1 ))
run_cmd "python3 src/main.py --mcp-write-preview --mcp-write-tool-name report.export --mcp-write-target-path reports/test_live.md --mcp-write-content 'live test' --confirm-mcp-write --execute-mcp-write" "$skip_write"

echo "Done."
