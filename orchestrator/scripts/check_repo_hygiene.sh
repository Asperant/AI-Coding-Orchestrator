#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Repository Hygiene Check ==="
echo "[INFO] Project root: $PROJECT_ROOT"
echo ""

if command -v git >/dev/null 2>&1 && [ -d "$PROJECT_ROOT/.git" ]; then
  if git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "== git status --short =="
    git -C "$PROJECT_ROOT" status --short || true
  else
    echo "[INFO] Git metadata is present, but the current workspace is not an active git work tree."
  fi
else
  echo "[INFO] Git is unavailable or this workspace does not expose a live .git repository."
fi

echo ""
echo "== Cache directories =="
find "$PROJECT_ROOT" \
  -path "$PROJECT_ROOT/.venv" -prune -o \
  -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".mypy_cache" -o -name ".ruff_cache" \) \
  -print | sort || true

echo ""
echo "== Local env files =="
find "$PROJECT_ROOT" -maxdepth 2 \( -name ".env" -o -name ".env.*" \) ! -name ".env.example" -print | sort || true

echo ""
echo "== Temp/report/demo artifacts =="
find "$PROJECT_ROOT" -maxdepth 3 \( -path "$PROJECT_ROOT/reports/tmp*" -o -name "*demo-smoke*" \) -print | sort || true

echo ""
echo "== Secret-like prefix scan (file paths only) =="
scan_output="$(grep -RInE '(sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA|OPENSSH|EC|DSA)? ?PRIVATE KEY-----)' "$PROJECT_ROOT" \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude-dir=__pycache__ \
  --exclude=*.pyc \
  --exclude=*.pyo \
  --exclude=*.so 2>/dev/null || true)"

if [ -n "$scan_output" ]; then
  printf '%s\n' "$scan_output" | cut -d: -f1-2
else
  echo "[INFO] No obvious token prefixes detected in scanned files."
fi
