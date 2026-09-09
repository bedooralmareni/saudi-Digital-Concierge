"""Text cleaning and normalisation helpers.

These functions are deliberately dependency-free so they can run early in the
pipeline before heavier libraries are loaded.
"""

from __future__ import annotations

import re
import unicodedata

# Arabic diacritics (tashkeel) that are usually safe to strip for retrieval.
_ARABIC_DIACRITICS = re.compile(r"[ؗ-ًؚ-ْٰـ]")
_WHITESPACE = re.compile(r"\s+")


def normalise_whitespace(text: str) -> str:
    """Collapse runs of whitespace and trim the ends."""
    return _WHITESPACE.sub(" ", text).strip()


def strip_arabic_diacritics(text: str) -> str:
    """Remove Arabic diacritics and the tatweel elongation character."""
    return _ARABIC_DIACRITICS.sub("", text)


def clean_text(text: str) -> str:
    """Apply the standard cleaning chain to a single string.

    Steps: Unicode NFKC normalisation, diacritic removal, whitespace collapse.
    """
    text = unicodedata.normalize("NFKC", text)
    text = strip_arabic_diacritics(text)
    text = normalise_whitespace(text)
    return text
