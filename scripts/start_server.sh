#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${PROJECT_DIR}/backend"
VENV_DIR="${PROJECT_DIR}/venv"

HOST="${PRONUNCIATION_APP_HOST:-0.0.0.0}"
PORT="${PRONUNCIATION_APP_PORT:-8000}"

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Virtual environment not found at ${VENV_DIR}."
  echo "Create it on the server with: python3 -m venv venv"
  exit 1
fi

source "${VENV_DIR}/bin/activate"

cd "${BACKEND_DIR}"
exec uvicorn main:app --host "${HOST}" --port "${PORT}"
