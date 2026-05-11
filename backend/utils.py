"""
This file contains helper functions.

We keep helper logic here so that main.py stays clean and beginner-friendly.
"""

from difflib import SequenceMatcher
from pathlib import Path
import re
import tempfile

import librosa
import numpy as np
import soundfile as sf


_SMALL_NUMBER_WORDS = {
    0: "zero",
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
    17: "seventeen",
    18: "eighteen",
    19: "nineteen",
}

_SMALL_WORD_TO_NUMBER = {word: number for number, word in _SMALL_NUMBER_WORDS.items()}
_TENS_WORDS = {
    20: "twenty",
    30: "thirty",
    40: "forty",
    50: "fifty",
    60: "sixty",
    70: "seventy",
    80: "eighty",
    90: "ninety",
}
_TENS_WORD_TO_NUMBER = {word: number for number, word in _TENS_WORDS.items()}
_DIGIT_WORDS = {word: number for number, word in _SMALL_NUMBER_WORDS.items() if number < 10}



def replace_time_tokens(text: str) -> str:
    """
    Replace HH:MM time patterns with space-separated numbers.

    Example:
    - 13:22 -> 13 22

    This lets the next normalization step compare the time against spoken words
    like "thirteen twenty two".
    """
    def convert_match(match: re.Match[str]) -> str:
        return f"{int(match.group(1))} {int(match.group(2))}"

    return re.sub(r"\b(\d{1,2}):(\d{2})\b", convert_match, text)



def parse_digit_word_sequence(tokens: list[str], start_index: int):
    """
    Parse sequences like "one zero four" into "104".
    """
    index = start_index
    digits = []

    while index < len(tokens) and tokens[index] in _DIGIT_WORDS:
        digits.append(str(_DIGIT_WORDS[tokens[index]]))
        index += 1

    if len(digits) >= 2:
        return "".join(digits), index - start_index

    return None, 0



def parse_standard_number_phrase(tokens: list[str], start_index: int):
    """
    Parse phrases like:
    - thirteen
    - twenty two
    - one hundred four
    """
    index = start_index
    total = 0
    current = 0
    consumed = 0

    while index < len(tokens):
        token = tokens[index]

        if token in _SMALL_WORD_TO_NUMBER:
            current += _SMALL_WORD_TO_NUMBER[token]
        elif token in _TENS_WORD_TO_NUMBER:
            current += _TENS_WORD_TO_NUMBER[token]
        elif token == "hundred" and current > 0:
            current *= 100
        elif token == "thousand" and current > 0:
            total += current * 1000
            current = 0
        else:
            break

        consumed += 1
        index += 1

    if consumed == 0:
        return None, 0

    return str(total + current), consumed



def canonicalize_number_tokens(text: str) -> str:
    """
    Convert spoken number words into digit strings.

    This helps treat the following as equal during comparison:
    - 56
    - fifty six
    - 104
    - one zero four
    - 13 22
    - thirteen twenty two
    """
    tokens = text.split()
    normalized_tokens = []
    index = 0

    while index < len(tokens):
        token = tokens[index]

        if token.isdigit():
            normalized_tokens.append(token)
            index += 1
            continue

        digit_sequence_value, digit_sequence_length = parse_digit_word_sequence(tokens, index)
        if digit_sequence_length > 0:
            normalized_tokens.append(digit_sequence_value)
            index += digit_sequence_length
            continue

        standard_number_value, standard_number_length = parse_standard_number_phrase(tokens, index)
        if standard_number_length > 0:
            normalized_tokens.append(standard_number_value)
            index += standard_number_length
            continue

        normalized_tokens.append(token)
        index += 1

    return " ".join(normalized_tokens)



def normalize_text(text: str) -> str:
    """
    Make text easier to compare.

    What we do:
    - convert to lowercase
    - normalize time tokens like 13:22 into 13 22
    - remove punctuation
    - convert spoken number phrases into digit strings
    - remove extra spaces
    """
    lowered_text = text.lower().strip()
    expanded_time_tokens = replace_time_tokens(lowered_text)
    expanded_symbols = expanded_time_tokens.replace("&", " and ").replace("/", " ")
    cleaned_text = re.sub(r"[^\w\s']", " ", expanded_symbols)
    compact_text = " ".join(cleaned_text.split())

    return canonicalize_number_tokens(compact_text)



def convert_audio_to_wav(input_path: str) -> str:
    """
    Convert any supported audio file into a clean WAV file at 16 kHz.

    We trim quiet leading and trailing silence and lightly normalize volume so the
    speech recognizer handles different speaking speeds a bit more reliably.
    """
    waveform, sample_rate = librosa.load(input_path, sr=16000, mono=True)
    trimmed_waveform, _ = librosa.effects.trim(waveform, top_db=25)

    if len(trimmed_waveform) > 1600:
        waveform = trimmed_waveform

    peak = float(np.max(np.abs(waveform))) if len(waveform) else 0.0
    if peak > 0:
        waveform = waveform / peak * 0.95

    temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_wav_path = temp_wav.name
    temp_wav.close()

    sf.write(temp_wav_path, waveform, sample_rate)

    return temp_wav_path



AUDIO_SAMPLE_RATE = 16000
MAX_TRANSCRIPTION_CHUNK_SECONDS = 12
CHUNK_OVERLAP_SECONDS = 1



def build_chunk_ranges(waveform: np.ndarray, sample_rate: int):
    """
    Split long audio into smaller ranges for transcription.

    Why this helps:
    - long recordings can get truncated by the speech model
    - smaller chunks are easier for the model to handle
    - light overlap helps preserve words near chunk boundaries
    """
    max_chunk_samples = sample_rate * MAX_TRANSCRIPTION_CHUNK_SECONDS
    overlap_samples = sample_rate * CHUNK_OVERLAP_SECONDS

    non_silent_ranges = librosa.effects.split(waveform, top_db=25)
    if len(non_silent_ranges) == 0:
        non_silent_ranges = np.array([[0, len(waveform)]])

    merged_ranges = []
    current_start, current_end = non_silent_ranges[0]

    for next_start, next_end in non_silent_ranges[1:]:
        if next_end - current_start <= max_chunk_samples:
            current_end = next_end
        else:
            merged_ranges.append((current_start, current_end))
            current_start, current_end = next_start, next_end

    merged_ranges.append((current_start, current_end))

    final_ranges = []
    for range_start, range_end in merged_ranges:
        chunk_start = range_start

        while chunk_start < range_end:
            chunk_end = min(chunk_start + max_chunk_samples, range_end)
            final_ranges.append((chunk_start, chunk_end))

            if chunk_end >= range_end:
                break

            chunk_start = max(chunk_end - overlap_samples, chunk_start + 1)

    return final_ranges



def merge_transcript_text(existing_text: str, new_text: str) -> str:
    """
    Merge chunk transcripts and remove simple duplicated overlap words.
    """
    existing_words = existing_text.split()
    new_words = new_text.split()

    if not existing_words:
        return new_text.strip()

    max_overlap_words = min(6, len(existing_words), len(new_words))
    for overlap_size in range(max_overlap_words, 0, -1):
        if existing_words[-overlap_size:] == new_words[:overlap_size]:
            return " ".join(existing_words + new_words[overlap_size:]).strip()

    return " ".join(existing_words + new_words).strip()



def transcribe_audio_in_chunks(model, wav_path: str) -> str:
    """
    Transcribe long audio in smaller chunks and combine the chunk transcripts.

    This is the main fix for recordings where transcription stops too early.
    """
    waveform, sample_rate = librosa.load(wav_path, sr=AUDIO_SAMPLE_RATE, mono=True)

    if len(waveform) <= sample_rate * MAX_TRANSCRIPTION_CHUNK_SECONDS:
        return model.transcribe_file(wav_path).strip()

    chunk_ranges = build_chunk_ranges(waveform, sample_rate)
    combined_transcript = ""

    for chunk_start, chunk_end in chunk_ranges:
        chunk_waveform = waveform[chunk_start:chunk_end]

        # Skip tiny fragments that are too short to be useful.
        if len(chunk_waveform) < sample_rate:
            continue

        temp_chunk_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_chunk_path = temp_chunk_file.name
        temp_chunk_file.close()

        try:
            sf.write(temp_chunk_path, chunk_waveform, sample_rate)
            chunk_transcript = model.transcribe_file(temp_chunk_path).strip()
            if chunk_transcript:
                combined_transcript = merge_transcript_text(combined_transcript, chunk_transcript)
        finally:
            safe_delete_file(temp_chunk_path)

    return combined_transcript.strip()



def token_similarity(expected_word: str, spoken_word: str) -> float:
    """
    Return a similarity score between two words.
    """
    return SequenceMatcher(None, expected_word, spoken_word).ratio()



def build_word_alignment(reference_words: list[str], transcript_words: list[str]):
    """
    Align reference words and transcript words using dynamic programming.
    """
    ref_count = len(reference_words)
    hyp_count = len(transcript_words)

    dp = [[0.0] * (hyp_count + 1) for _ in range(ref_count + 1)]
    backtrack = [[None] * (hyp_count + 1) for _ in range(ref_count + 1)]

    for ref_index in range(1, ref_count + 1):
        dp[ref_index][0] = float(ref_index)
        backtrack[ref_index][0] = "delete"

    for hyp_index in range(1, hyp_count + 1):
        dp[0][hyp_index] = float(hyp_index)
        backtrack[0][hyp_index] = "insert"

    for ref_index in range(1, ref_count + 1):
        for hyp_index in range(1, hyp_count + 1):
            expected_word = reference_words[ref_index - 1]
            spoken_word = transcript_words[hyp_index - 1]
            similarity = token_similarity(expected_word, spoken_word)

            if expected_word == spoken_word:
                substitution_cost = 0.0
                substitution_label = "match"
            elif similarity >= 0.88:
                substitution_cost = 0.15
                substitution_label = "near_match"
            elif similarity >= 0.72:
                substitution_cost = 0.55
                substitution_label = "replace"
            else:
                substitution_cost = 1.0
                substitution_label = "replace"

            substitution_total = dp[ref_index - 1][hyp_index - 1] + substitution_cost
            deletion_total = dp[ref_index - 1][hyp_index] + 1.0
            insertion_total = dp[ref_index][hyp_index - 1] + 1.0

            best_total = min(substitution_total, deletion_total, insertion_total)
            dp[ref_index][hyp_index] = best_total

            if best_total == substitution_total:
                backtrack[ref_index][hyp_index] = substitution_label
            elif best_total == deletion_total:
                backtrack[ref_index][hyp_index] = "delete"
            else:
                backtrack[ref_index][hyp_index] = "insert"

    alignment = []
    ref_index = ref_count
    hyp_index = hyp_count

    while ref_index > 0 or hyp_index > 0:
        step = backtrack[ref_index][hyp_index]

        if step in {"match", "near_match", "replace"}:
            alignment.append(
                {
                    "type": step,
                    "expected": reference_words[ref_index - 1],
                    "spoken": transcript_words[hyp_index - 1],
                    "similarity": token_similarity(reference_words[ref_index - 1], transcript_words[hyp_index - 1]),
                }
            )
            ref_index -= 1
            hyp_index -= 1
        elif step == "delete":
            alignment.append(
                {
                    "type": "delete",
                    "expected": reference_words[ref_index - 1],
                    "spoken": "(missing)",
                    "similarity": 0.0,
                }
            )
            ref_index -= 1
        elif step == "insert":
            alignment.append(
                {
                    "type": "insert",
                    "expected": "(extra)",
                    "spoken": transcript_words[hyp_index - 1],
                    "similarity": 0.0,
                }
            )
            hyp_index -= 1
        else:
            break

    alignment.reverse()
    return alignment, dp[ref_count][hyp_count]



def build_suggestion(error_type: str, expected_word: str, spoken_word: str) -> str:
    """
    Create a more natural, human-sounding suggestion for each highlighted error.
    """
    if error_type == "delete":
        return f'Give "{expected_word}" a little more space when you say it. A brief pause before or after it may help.'

    if error_type == "insert":
        return f'"{spoken_word}" may have slipped in because the pace got quick here. Try this part a bit more steadily.'

    if spoken_word == "(missing)":
        return f'Try that part again and lean a little more clearly into "{expected_word}".'

    return f'That sounded close, but "{spoken_word}" came out a bit differently from "{expected_word}". Try that word once more.'



def compress_error_items(alignment: list[dict[str, str]]):
    """
    Group long runs of missing or extra words into one readable card.

    Important improvement:
    - if later words are matched again, we do not claim the transcript "stopped early"
    - we only say that when the long missing run is truly near the end
    """
    if not alignment:
        return []

    compressed_errors = []
    index = 0

    while index < len(alignment):
        current_item = alignment[index]
        item_type = current_item["type"]

        if item_type in {"match", "near_match"}:
            index += 1
            continue

        if item_type == "delete":
            start_index = index
            missing_words = []

            while index < len(alignment) and alignment[index]["type"] == "delete":
                missing_words.append(alignment[index]["expected"])
                index += 1

            has_later_match = any(item["type"] in {"match", "near_match"} for item in alignment[index:])

            if len(missing_words) >= 4:
                expected_phrase = " ".join(missing_words)
                if has_later_match:
                    suggestion = "This part may have been blended or skipped in the middle. Try this phrase again with a slightly steadier rhythm."
                else:
                    suggestion = "The transcript seems to fade out here. Try ending this paragraph with a tiny pause and a touch more volume."

                compressed_errors.append(
                    {
                        "expected": expected_phrase,
                        "spoken": "(missing phrase)",
                        "suggestion": suggestion,
                    }
                )
            else:
                for missing_word in missing_words:
                    compressed_errors.append(
                        {
                            "expected": missing_word,
                            "spoken": "(missing)",
                            "suggestion": build_suggestion("delete", missing_word, "(missing)"),
                        }
                    )
            continue

        if item_type == "insert":
            extra_words = []
            while index < len(alignment) and alignment[index]["type"] == "insert":
                extra_words.append(alignment[index]["spoken"])
                index += 1

            if len(extra_words) >= 2:
                spoken_phrase = " ".join(extra_words)
                compressed_errors.append(
                    {
                        "expected": "(extra phrase)",
                        "spoken": spoken_phrase,
                        "suggestion": "A few extra words seem to have slipped in here. Try this part once more at a calmer pace.",
                    }
                )
            else:
                compressed_errors.append(
                    {
                        "expected": "(extra)",
                        "spoken": extra_words[0],
                        "suggestion": build_suggestion("insert", "(extra)", extra_words[0]),
                    }
                )
            continue

        compressed_errors.append(
            {
                "expected": current_item["expected"],
                "spoken": current_item["spoken"],
                "suggestion": build_suggestion("replace", current_item["expected"], current_item["spoken"]),
            }
        )
        index += 1

    return compressed_errors



def build_word_errors(reference_text: str, transcript_text: str):
    """
    Build a word-by-word mistake list with suggestions.
    """
    normalized_reference = normalize_text(reference_text)
    normalized_transcript = normalize_text(transcript_text)

    reference_words = normalized_reference.split()
    transcript_words = normalized_transcript.split()

    alignment, _ = build_word_alignment(reference_words, transcript_words)
    return compress_error_items(alignment)



def analyze_pronunciation(reference_text: str, transcript_text: str):
    """
    Compare the spoken text with the reference text and compute a score.

    The score uses a forgiving word alignment so that:
    - 56 can match fifty six
    - 104 can match one zero four or one hundred four
    - 13:22 can match thirteen twenty two
    - tiny transcription variations are penalized less
    - long false chains of missing words are reduced
    """
    normalized_reference = normalize_text(reference_text)
    normalized_transcript = normalize_text(transcript_text)

    reference_words = normalized_reference.split()
    transcript_words = normalized_transcript.split()
    _, weighted_error_count = build_word_alignment(reference_words, transcript_words)

    reference_word_count = max(1, len(reference_words))
    adjusted_error_rate = min(1.0, weighted_error_count / reference_word_count)
    score = max(0, round((1 - adjusted_error_rate) * 100))

    errors = build_word_errors(normalized_reference, normalized_transcript)

    return {
        "transcript": transcript_text.strip(),
        "score": score,
        "errors": errors,
    }



def safe_delete_file(file_path: str):
    """
    Delete a file if it exists.
    """
    path = Path(file_path)
    if path.exists():
        path.unlink()
