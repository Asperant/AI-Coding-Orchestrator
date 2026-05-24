#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -f "${PROJECT_ROOT}/pyproject.toml" ] || [ ! -d "${PROJECT_ROOT}/src" ]; then
  echo "Project root validation failed. Refusing to clean outside AI-Coding-Orchestrator."
  exit 1
fi

cd "${PROJECT_ROOT}"

echo "Removing generated Python artifacts inside ${PROJECT_ROOT}..."

find "${PROJECT_ROOT}" \
  \( -path "${PROJECT_ROOT}/.git" -o -path "${PROJECT_ROOT}/.venv" -o -path "${PROJECT_ROOT}/reports" \) -prune \
  -o \( -type d -name "__pycache__" -o -type d -name "*.egg-info" \) -print -exec rm -rf {} +

find "${PROJECT_ROOT}" \
  \( -path "${PROJECT_ROOT}/.git" -o -path "${PROJECT_ROOT}/.venv" -o -path "${PROJECT_ROOT}/reports" \) -prune \
  -o -type f -name "*.pyc" -print -exec rm -f {} +

echo "Generated Python artifacts cleaned."
