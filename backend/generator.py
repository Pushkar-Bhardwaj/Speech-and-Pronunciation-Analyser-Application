from __future__ import annotations

import json
import urllib.error
import urllib.request

from config import OLLAMA_BASE_URL, OLLAMA_MODEL


class IntroductionGenerationError(Exception):
    """Raised when the introduction generator cannot return valid output."""


def build_introduction_prompt(details: dict[str, str]) -> str:
    """Build the prompt used for the local introduction model."""
    return f"""
Convert the following structured details into a natural, fluent, and confident self-introduction suitable for an interview.

Important writing rule:
- write in first person
- use words like I, my, and me
- do not refer to the candidate as he, she, they, or by name in the final paragraph
- make it sound like the candidate is speaking directly in the interview

Make it:
- grammatically perfect
- human-like (not robotic)
- well structured
- concise but impactful

Details:
Name: {details['name']}
Age: {details['age']}
Education: {details['education']}
City: {details['city']}
Strengths: {details['strengths']}
Weaknesses: {details['weaknesses']}
Hobbies: {details['hobbies']}
Achievements: {details['achievements']}
Work Experience: {details['experience']}
Motivation: {details['motivation']}

Output:
A single smooth paragraph in first person.
The paragraph should sound like something the candidate would say aloud in an interview.
Return only the paragraph and nothing else.
""".strip()


def normalize_generated_text(text: str) -> str:
    """Normalize generator output to a single paragraph."""
    return " ".join(text.strip().split())


def generate_introduction(details: dict[str, str]) -> str:
    """Generate a first-person interview introduction using the local Ollama API."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": build_introduction_prompt(details),
        "stream": False,
        "options": {
            "temperature": 0.6,
        },
    }

    request = urllib.request.Request(
        url=f"{OLLAMA_BASE_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as error:
        raise IntroductionGenerationError(
            "The local introduction model could not be reached. "
            "Verify that Ollama is running on the server and that the configured model is installed. "
            f"Original error: {error}"
        ) from error

    generated_text = response_payload.get("response", "")
    cleaned_text = normalize_generated_text(generated_text)

    if not cleaned_text:
        raise IntroductionGenerationError("The local introduction model returned an empty response.")

    return cleaned_text
