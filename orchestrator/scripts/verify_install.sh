#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${PROJECT_ROOT}/.venv"

cd "${PROJECT_ROOT}"

if [ ! -d "${VENV_DIR}" ]; then
  python3 -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

echo "Installing editable package with build isolation..."
if ! python -m pip install -e .; then
  echo "Normal editable install failed."
  echo "Retrying without build isolation for offline or network-restricted environments..."
  if ! python -m pip install -e . --no-build-isolation; then
    echo "Fallback editable install also failed."
    echo "Make sure the virtual environment already has local packaging tools and project dependencies available."
    echo "Minimum local requirements for offline fallback typically include: setuptools, wheel, and PyYAML."
    echo "Retry commands:"
    echo "  python -m pip install --upgrade pip setuptools wheel"
    echo "  python -m pip install PyYAML"
    echo "  python -m pip install -e . --no-build-isolation"
    echo "Direct Python fallback remains available:"
    echo "  PYTHONPATH=src python3 src/main.py --run-orchestrator --mode status"
    exit 1
  fi
fi

echo "Running installed command checks..."
orchestrator --help
orchestrator --run-orchestrator --mode status

echo "Install verification completed."
