#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APPROVED_PATHS_FILE="$PROJECT_ROOT/config/approved_paths.yaml"
DEFAULT_CONFIG_FILE="$PROJECT_ROOT/config/default.yaml"

TEST_COMMAND="PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -p test_*.py"
EXPECTED_SENTENCE="The smoke tests validate the README."
TASK_TEXT="Add this exact sentence to README.md: \"$EXPECTED_SENTENCE\""

echo "=== AI-Coding-Orchestrator Demo E2E ==="
echo "This script creates a local smoke repo and runs the main orchestrator workflow."
echo "It does not push to GitHub, does not write AI-Brain, and does not call external providers."
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 is required."
  exit 1
fi

if [ ! -f "$PROJECT_ROOT/src/main.py" ]; then
  echo "[ERROR] src/main.py was not found. Run this script from the AI-Coding-Orchestrator repository."
  exit 1
fi

if [ ! -f "$APPROVED_PATHS_FILE" ]; then
  echo "[ERROR] config/approved_paths.yaml was not found."
  exit 1
fi

if [ ! -f "$DEFAULT_CONFIG_FILE" ]; then
  echo "[ERROR] config/default.yaml was not found."
  exit 1
fi

if [ ! -d "$PROJECT_ROOT/.git" ]; then
  echo "[ERROR] Current directory is not the AI-Coding-Orchestrator git repository root."
  exit 1
fi

mapfile -t APPROVED_PATHS < <(sed -n 's/^  - //p' "$APPROVED_PATHS_FILE")

is_path_approved() {
  target_path="$1"
  for approved_root in "${APPROVED_PATHS[@]}"; do
    case "$target_path" in
      "$approved_root"|"$approved_root"/*)
        return 0
        ;;
    esac
  done
  return 1
}

select_demo_repo() {
  home_dir="${HOME:-}"
  candidate_paths="
/tmp/ai-coding-orchestrator-demo-smoke
${home_dir}/Desktop/orchestrator-codex-e2e-smoke
${home_dir}/Desktop/codex-orchestrator-smoke
${PROJECT_ROOT}/reports/tmp/demo-smoke
"

  while IFS= read -r candidate; do
    if [ -n "$candidate" ] && is_path_approved "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done <<EOF
$candidate_paths
EOF

  return 1
}

if ! DEMO_REPO="$(select_demo_repo)"; then
  echo "[ERROR] No safe approved demo path is configured."
  echo "[INFO] Add one of these paths, or a similar dedicated smoke repo path, to config/approved_paths.yaml:"
  echo "  - /tmp/ai-coding-orchestrator-demo-smoke"
  echo "  - $HOME/Desktop/orchestrator-codex-e2e-smoke"
  echo "  - $PROJECT_ROOT/reports/tmp/demo-smoke"
  exit 1
fi

AI_BRAIN_PATH="${AI_BRAIN_PATH:-$(sed -n 's/^ai_brain_path: //p' "$DEFAULT_CONFIG_FILE" | head -n 1)}"
if [[ "$AI_BRAIN_PATH" == "../"* ]]; then
  AI_BRAIN_PATH="$PROJECT_ROOT/config/$AI_BRAIN_PATH"
fi

CODEX_STATUS="missing"
if command -v codex >/dev/null 2>&1; then
  CODEX_STATUS="available"
fi

echo "[INFO] Project root: $PROJECT_ROOT"
echo "[INFO] Demo repo path: $DEMO_REPO"
echo "[INFO] Codex CLI: $CODEX_STATUS"
if [ -n "${AI_BRAIN_PATH:-}" ] && [ -d "$AI_BRAIN_PATH" ]; then
  echo "[INFO] AI-Brain path: available at $AI_BRAIN_PATH"
else
  echo "[INFO] AI-Brain path: unavailable"
fi
echo ""

if [ "$CODEX_STATUS" != "available" ]; then
  echo "[ERROR] Codex CLI is not available in PATH."
  echo "[INFO] Install/authenticate Codex first, then rerun this demo."
  exit 1
fi

case "$DEMO_REPO" in
  /tmp/ai-coding-orchestrator-demo-smoke|"$HOME"/Desktop/orchestrator-codex-e2e-smoke|"$HOME"/Desktop/codex-orchestrator-smoke|"$PROJECT_ROOT"/reports/tmp/demo-smoke)
    ;;
  *)
    echo "[ERROR] Refusing to reset an unexpected demo path: $DEMO_REPO"
    exit 1
    ;;
esac

echo "[INFO] Resetting demo repository."
rm -rf "$DEMO_REPO"
mkdir -p "$DEMO_REPO/tests"

cat >"$DEMO_REPO/README.md" <<'EOF'
# Demo Smoke Repo

This repository is used for the AI-Coding-Orchestrator end-to-end smoke demo.
EOF

cat >"$DEMO_REPO/tests/test_readme.py" <<EOF
from pathlib import Path
from unittest import TestCase


class ReadmeSmokeTests(TestCase):
    def test_readme_mentions_smoke_validation(self) -> None:
        content = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("$EXPECTED_SENTENCE", content)
EOF

if command -v git >/dev/null 2>&1; then
  (
    cd "$DEMO_REPO"
    git init >/dev/null 2>&1
    git add README.md tests/test_readme.py

    if git config user.name >/dev/null 2>&1 && git config user.email >/dev/null 2>&1; then
      git commit -m "Initial smoke repo state" >/dev/null 2>&1 || true
      echo "[INFO] Git initial state committed."
    else
      echo "[INFO] Git user.name/user.email not configured. Continuing without an initial commit."
    fi
  )
else
  echo "[INFO] git is not available. Continuing without git initialization."
fi

ORCHESTRATOR_COMMAND=(
  python3
  src/main.py
  --run-orchestrator
  --mode
  run
  --project
  "$DEMO_REPO"
  --task
  "$TASK_TEXT"
  --allowed-file
  README.md
  --confirm-codex-prompt
  --confirm-codex-execution
  --include-ai-brain-context
  --test-command
  "$TEST_COMMAND"
)

echo ""
echo "[INFO] Running orchestrator demo command:"
printf 'PYTHONPATH=src'
for arg in "${ORCHESTRATOR_COMMAND[@]}"; do
  printf ' %q' "$arg"
done
printf '\n\n'

(
  cd "$PROJECT_ROOT"
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src "${ORCHESTRATOR_COMMAND[@]}"
)

echo ""
echo "[DONE] Demo finished."
echo "[INFO] Inspect these sections in the output:"
echo "  - Coding Run Summary"
echo "  - Scope enforcement result"
echo "  - Test execution result"
echo "  - Verification Gate"
