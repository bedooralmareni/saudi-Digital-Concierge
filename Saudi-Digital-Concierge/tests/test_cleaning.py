"""Tests for the text cleaning helpers.

Run with ``pytest`` from the project root.
"""

from src.cleaning.cleaner import (
    clean_text,
    normalise_whitespace,
    strip_arabic_diacritics,
)


def test_normalise_whitespace_collapses_and_trims():
    assert normalise_whitespace("  hello   world \n") == "hello world"


def test_strip_arabic_diacritics_removes_tashkeel():
    # "مَرْحَبًا" (with diacritics) -> "مرحبا" (without)
    assert strip_arabic_diacritics("مَرْحَبًا") == "مرحبا"


def test_clean_text_runs_full_chain():
    assert clean_text("  Riyadh   Season  ") == "Riyadh Season"
