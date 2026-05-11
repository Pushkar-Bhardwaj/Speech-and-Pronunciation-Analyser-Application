#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
VENV_DIR="$PROJECT_DIR/venv"
HOST="${PRONUNCIATION_APP_HOST:-127.0.0.1}"
PORT="${PRONUNCIATION_APP_PORT:-8000}"
APP_URL="http://${HOST}:${PORT}"

cd "$PROJECT_DIR"

echo "Starting Pronunciation Analysis App..."

# Activate the Python environment so the backend can use installed packages.
if [ -d "$VENV_DIR" ]; then
  source "$VENV_DIR/bin/activate"
else
  echo "Virtual environment not found at $VENV_DIR"
  echo "Create it first with: python3 -m venv venv"
  exit 1
fi

if command -v ollama >/dev/null 2>&1; then
  if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "Starting Ollama on port 11434..."
    nohup ollama serve >/tmp/pronunciation_app_ollama.log 2>&1 &
    sleep 3
  else
    echo "Ollama is already running."
  fi
else
  echo "Ollama is not installed."
  echo "The pronunciation feature will still work, but the PIQ self-introduction generator will not work until Ollama is installed."
fi

cd "$BACKEND_DIR"
echo "Starting FastAPI server on ${APP_URL} ..."
open "$APP_URL" >/dev/null 2>&1 || true
exec uvicorn main:app --host "$HOST" --port "$PORT"
