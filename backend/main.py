from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import APP_TITLE, FRONTEND_DIR
from generator import IntroductionGenerationError, generate_introduction
from model import get_asr_model
from storage import add_analysis, create_user, delete_user, get_user_profile, list_users
from utils import analyze_pronunciation, convert_audio_to_wav, safe_delete_file, transcribe_audio_in_chunks

app = FastAPI(title=APP_TITLE)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


class UserCreateRequest(BaseModel):
    """Payload for user creation."""

    name: str


class IntroductionRequest(BaseModel):
    """Payload for PIQ-based self-introduction generation."""

    name: str = ""
    age: str = ""
    education: str = ""
    city: str = ""
    strengths: str = ""
    weaknesses: str = ""
    hobbies: str = ""
    achievements: str = ""
    experience: str = ""
    motivation: str = ""


@app.on_event("startup")
def load_model_on_startup():
    """Warm the ASR model on startup."""
    get_asr_model()


@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serve the frontend entry point."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
def read_health():
    """Return a health-check response."""
    return {"message": "Pronunciation Analysis API is running"}


@app.get("/api/users")
def get_users():
    """Return the list of saved users."""
    return {"users": list_users()}


@app.post("/api/users")
def add_user(request: UserCreateRequest):
    """Create a user."""
    try:
        user = create_user(request.name)
        return {"message": "User created successfully.", "user": user["name"]}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.delete("/api/users/{user_name}")
def remove_user(user_name: str):
    """Delete a user and associated history."""
    was_deleted = delete_user(user_name)

    if not was_deleted:
        raise HTTPException(status_code=404, detail="User not found.")

    return {"message": "User deleted successfully."}


@app.get("/api/users/{user_name}")
def get_one_user(user_name: str):
    """Return a single user profile."""
    user = get_user_profile(user_name)

    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    return user


@app.post("/api/generate-introduction")
def generate_interview_introduction(request: IntroductionRequest):
    """Generate a self-introduction from PIQ-style details."""
    try:
        generated_text = generate_introduction(request.model_dump())
        return {"generated_text": generated_text}
    except IntroductionGenerationError as error:
        raise HTTPException(status_code=503, detail=str(error))


@app.post("/api/analyze")
async def analyze_audio(
    audio: UploadFile = File(...),
    reference_text: str = Form(...),
    user_name: str = Form(...),
):
    """Analyze recorded speech against a reference paragraph."""
    if not reference_text.strip():
        raise HTTPException(status_code=400, detail="Reference text cannot be empty.")

    if not user_name.strip():
        raise HTTPException(status_code=400, detail="User name cannot be empty.")

    suffix = Path(audio.filename or "recording.wav").suffix or ".wav"
    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_input_path = temp_input.name
    temp_input.close()

    converted_wav_path = None

    try:
        with open(temp_input_path, "wb") as buffer:
            shutil.copyfileobj(audio.file, buffer)

        converted_wav_path = convert_audio_to_wav(temp_input_path)
        model = get_asr_model()
        transcript = transcribe_audio_in_chunks(model, converted_wav_path)
        result = analyze_pronunciation(reference_text, transcript)

        add_analysis(user_name, reference_text, result)

        return result

    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Audio analysis failed: {error}")

    finally:
        safe_delete_file(temp_input_path)
        if converted_wav_path:
            safe_delete_file(converted_wav_path)
