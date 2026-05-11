from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BACKEND_DIR / "data"

HOST = os.getenv("PRONUNCIATION_APP_HOST", "0.0.0.0")
PORT = int(os.getenv("PRONUNCIATION_APP_PORT", "8000"))
APP_TITLE = os.getenv("PRONUNCIATION_APP_TITLE", "Pronunciation Analyzer")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

PRETRAINED_MODEL_DIR = BACKEND_DIR / "pretrained_models" / "asr-wav2vec2-commonvoice-en"
PRETRAINED_MODEL_ID = "speechbrain/asr-wav2vec2-commonvoice-en"
