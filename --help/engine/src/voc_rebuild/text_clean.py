"""Deterministic text cleaning owned by the Phase 1 rebuild engine.

The cleaner normalizes noisy YouTube comment text before the LLM sees it. It is
intentionally conservative: it preserves meaning-bearing words, numbers, model
names, prices, and negation while normalizing control characters, whitespace,
emoji runs, and non-semantic repeated marks.
"""

from __future__ import annotations

import re
import unicodedata


_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")
_EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "]+",
    flags=re.UNICODE,
)


def safe_clean_source_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if value != value:  # NaN without importing pandas.
            return ""
    except Exception:
        pass
    return str(value)


def clean_text(original_voc: object) -> str:
    """Normalize, rather than semantically rewrite, a raw VoC comment.

    Rules:
    - remove control characters while keeping ordinary text;
    - collapse duplicate whitespace;
    - preserve emoji and repeated laughter/punctuation as written.
    """

    text = safe_clean_source_text(original_voc)
    text = unicodedata.normalize("NFC", text)
    text = _CONTROL_CHARS_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def cleaning_length_ratio(original_voc: object, cleaned_voc: object | None = None) -> float:
    """Return cleaned/original non-space length ratio for over-cleaning checks."""

    original_compact = re.sub(r"\s+", "", safe_clean_source_text(original_voc))
    if not original_compact:
        return 1.0
    cleaned = clean_text(original_voc) if cleaned_voc is None else safe_clean_source_text(cleaned_voc)
    cleaned_compact = re.sub(r"\s+", "", cleaned)
    return round(len(cleaned_compact) / len(original_compact), 3)
