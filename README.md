# Pronunciation Analyzer

Pronunciation Analyzer is a self-hosted FastAPI application for spoken-English practice and optional PIQ-based interview introduction generation.

## Overview

The application provides:

- pronunciation scoring against reference text
- transcript inspection with word-level feedback
- optional PIQ-style first-person introduction generation using a local Ollama model
- multi-user history and progress tracking

The frontend is served directly by FastAPI and is intended to be accessed from standard web browsers on client machines.

## Architecture

- Backend: FastAPI
- Speech recognition: `speechbrain/asr-wav2vec2-commonvoice-en`
- Optional local text generation: Ollama
- Persistence: local JSON file
- Client model: browser-only thin clients

## Project Structure

```text
pronunciation_app/
├── backend/
│   ├── config.py
│   ├── data/
│   ├── generator.py
│   ├── main.py
│   ├── model.py
│   ├── storage.py
│   ├── utils.py
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── script.js
│   └── style.css
├── scripts/
│   ├── start_app.sh
│   └── start_server.sh
├── .env.example
├── .gitignore
├── launch.command
└── README.md
```

## API Surface

- `GET /`
- `GET /api/health`
- `GET /api/users`
- `POST /api/users`
- `GET /api/users/{user_name}`
- `DELETE /api/users/{user_name}`
- `POST /api/generate-introduction`
- `POST /api/analyze`

## Server Deployment

### What to transfer

Copy the project source tree to the server.

Do not transfer:

- `venv/`
- `__pycache__/`
- `.DS_Store`
- local logs

The included `.gitignore` already reflects the expected exclusions.

### Recommended target layout

Example target path:

```bash
/opt/pronunciation_app
```

### Server setup

```bash
cd /opt/pronunciation_app
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### Environment configuration

Copy the example environment file if you want explicit configuration values:

```bash
cp .env.example .env
```

Supported settings:

- `PRONUNCIATION_APP_HOST`
- `PRONUNCIATION_APP_PORT`
- `PRONUNCIATION_APP_TITLE`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`

Example shell exports:

```bash
export PRONUNCIATION_APP_HOST=0.0.0.0
export PRONUNCIATION_APP_PORT=8000
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_MODEL=qwen2.5:3b
```

### Prime the ASR model once

Run the backend once while internet is available so the SpeechBrain model can populate the local cache:

```bash
cd /opt/pronunciation_app/backend
source ../venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

The downloaded speech model is then reused from:

```text
backend/pretrained_models/
```

### Optional PIQ generator setup

If PIQ-based self-introduction generation is required, install Ollama on the server and pull the model while internet is available:

```bash
ollama pull qwen2.5:3b
```

If this feature is not needed, Ollama is optional.

### Start on the server

Use the server-oriented launcher:

```bash
cd /opt/pronunciation_app
chmod +x scripts/start_server.sh
./scripts/start_server.sh
```

This launcher:

- resolves the project path dynamically
- activates the local virtual environment
- starts Uvicorn without development reload mode

## Local macOS startup

For local desktop use on macOS:

```bash
chmod +x launch.command scripts/start_app.sh
./launch.command
```

This path is intended for operator convenience and may open a browser automatically.

## Thin Client Access

Once the server is running, clients only need a browser and microphone access.

Open:

```text
http://SERVER_IP:8000
```

Example:

```text
http://192.168.1.50:8000
```

Thin clients do not need:

- Python
- Ollama
- SpeechBrain
- model files

## Operational Notes

- Use a fixed LAN IP for the server.
- Keep Ollama local to the server unless there is a specific reason to expose it.
- Back up `backend/data/app_data.json` if retaining history matters.
- For best ASR behavior, avoid unnecessarily long or dense practice paragraphs.

## Scoring Model

Pronunciation scoring is based on transcript similarity rather than phoneme-level assessment.

At a high level:

```text
score = (1 - weighted_error_rate) * 100
```

The comparison layer normalizes punctuation, common numeric forms, and several spoken-number variants before computing alignment.

## Offline Readiness

The system can operate fully offline after preparation if:

- Python dependencies are already installed
- the SpeechBrain model is already cached
- the Ollama model is already pulled, if PIQ generation is enabled
- the application and clients are on the same LAN

## Health Check

```text
GET /api/health
```

Expected response:

```json
{"message":"Pronunciation Analysis API is running"}
```
