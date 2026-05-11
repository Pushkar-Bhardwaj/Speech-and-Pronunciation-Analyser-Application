from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from config import DATA_DIR

DATA_FILE = DATA_DIR / "app_data.json"


def ensure_data_file_exists() -> None:
    """Ensure the persistent JSON store exists."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not DATA_FILE.exists():
        DATA_FILE.write_text(json.dumps({"users": []}, indent=2))


def load_data() -> dict[str, Any]:
    """Load application data from disk."""
    ensure_data_file_exists()
    return json.loads(DATA_FILE.read_text())


def save_data(data: dict[str, Any]) -> None:
    """Persist application data to disk."""
    ensure_data_file_exists()
    DATA_FILE.write_text(json.dumps(data, indent=2))


def normalize_user_name(name: str) -> str:
    """Normalize a user name for consistent storage and lookup."""
    return " ".join(name.strip().split())


def find_user(data: dict[str, Any], name: str) -> dict[str, Any] | None:
    """Return a stored user record by name."""
    cleaned_name = normalize_user_name(name).lower()

    for user in data["users"]:
        if user["name"].lower() == cleaned_name:
            return user

    return None


def list_users() -> list[str]:
    """Return all user names."""
    data = load_data()
    return [user["name"] for user in data["users"]]


def create_user(name: str) -> dict[str, Any]:
    """Create a user if it does not already exist."""
    cleaned_name = normalize_user_name(name)
    if not cleaned_name:
        raise ValueError("User name cannot be empty.")

    data = load_data()
    existing_user = find_user(data, cleaned_name)

    if existing_user is not None:
        return existing_user

    new_user = {
        "name": cleaned_name,
        "analyses": [],
        "recent_texts": [],
    }
    data["users"].append(new_user)
    save_data(data)
    return new_user


def delete_user(name: str) -> bool:
    """Delete a user and all associated history."""
    data = load_data()
    original_count = len(data["users"])
    cleaned_name = normalize_user_name(name).lower()

    data["users"] = [user for user in data["users"] if user["name"].lower() != cleaned_name]

    if len(data["users"]) == original_count:
        return False

    save_data(data)
    return True


def get_user_profile(name: str) -> dict[str, Any] | None:
    """Return a complete user profile record."""
    data = load_data()
    user = find_user(data, name)

    if user is None:
        return None

    return user


def add_analysis(name: str, reference_text: str, result: dict[str, Any]) -> dict[str, Any]:
    """Append a pronunciation analysis result to a user's history."""
    data = load_data()
    user = find_user(data, name)

    if user is None:
        user = create_user(name)
        data = load_data()
        user = find_user(data, name)

    analysis_entry = {
        "reference_text": reference_text,
        "transcript": result["transcript"],
        "score": result["score"],
        "errors": result["errors"],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    user["analyses"].append(analysis_entry)

    cleaned_text = " ".join(reference_text.strip().split())
    if cleaned_text:
        recent_texts = [text for text in user["recent_texts"] if text != cleaned_text]
        recent_texts.insert(0, cleaned_text)
        user["recent_texts"] = recent_texts[:5]

    save_data(data)
    return analysis_entry
