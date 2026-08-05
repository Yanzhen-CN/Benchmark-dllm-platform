#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Platform venv is missing. Run scripts/setup.sh first." >&2
  exit 1
fi

exec "$PYTHON_BIN" -m streamlit run "$ROOT/app.py"

