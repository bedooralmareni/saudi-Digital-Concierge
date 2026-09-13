"""Run every dataset cleaner: raw -> clean -> validate -> data/processed/.

Usage (from repo root):
    python -m src.cleaning.run_all

Events requires the live Enjoy.sa API; if it is unreachable the step is skipped with a
note rather than failing the whole run.
"""
from __future__ import annotations

from src.cleaning import (clean_places, clean_reviews, clean_hotels, clean_entertainment,
                          clean_tourism_statistics, clean_datasaudi, clean_events)
from src.cleaning.common import save_processed

FILE_CLEANERS = [
    ("places", clean_places),
    ("reviews", clean_reviews),
    ("hotels", clean_hotels),
    ("entertainment", clean_entertainment),
    ("tourism_statistics", clean_tourism_statistics),
    ("tourism_indicators", clean_datasaudi)
]


def main():
    for entity, mod in FILE_CLEANERS:
        df = mod.clean()
        path = save_processed(df, entity)
        print(f"  saved -> {path}")

    # Events last: needs the live API.
    try:
        df = clean_events.clean()
        path = save_processed(df, "events")
        print(f"  saved -> {path}")
    except Exception as exc:  # noqa: BLE001
        print("\n=== events ===")
        print(f"  SKIPPED — live Enjoy.sa API not reachable here ({type(exc).__name__}). "
              f"Run `python -m src.cleaning.clean_events` where enjoy.sa is reachable.")


if __name__ == "__main__":
    main()
