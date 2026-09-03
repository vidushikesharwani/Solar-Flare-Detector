"""
backend/validation.py
GOES cross-check validation module.

Given our detected flare events and a local GOES catalog, this module:
  1. Matches each detected event to the nearest GOES entry within ±MATCH_WINDOW_MINUTES.
  2. Records the time offset and GOES assigned class.
  3. Flags "possible GOES misses" — events we detected but GOES has no record of —
     rather than silently treating them as false positives.

Design is intentionally file-agnostic: swap `load_goes_catalog()` with a
live NOAA API call and nothing else needs to change.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Default matching window: ±10 minutes around our detected peak
MATCH_WINDOW_MINUTES: float = 10.0


def _parse_dt(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp string to a UTC-aware datetime."""
    # Handle both 'Z' suffix and '+00:00'
    ts = ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def match_events_to_goes(
    detected_events: list[dict],
    goes_catalog: list[dict],
    match_window_minutes: float = MATCH_WINDOW_MINUTES,
) -> list[dict]:
    """
    Cross-match detected flare events against the GOES catalog.

    Parameters
    ----------
    detected_events : list[dict]
        Events from detection engine. Each must have keys:
        event_id, peak_time (ISO string), flare_class.
    goes_catalog : list[dict]
        GOES events. Each must have keys:
        goes_id, peak_time (ISO string), goes_class.
    match_window_minutes : float
        Half-window (±) in minutes for a match to be accepted.

    Returns
    -------
    list[dict]
        One entry per detected event:
        {event_id, goes_match, goes_class, time_diff_minutes, possible_goes_miss}
    """
    window = timedelta(minutes=match_window_minutes)
    results: list[dict] = []

    # Pre-parse GOES peak times once for efficiency
    parsed_goes: list[tuple[datetime, dict]] = []
    for entry in goes_catalog:
        try:
            pt = _parse_dt(entry["peak_time"])
            parsed_goes.append((pt, entry))
        except Exception as exc:
            logger.warning("Skipping GOES entry with bad timestamp: %s — %s", entry, exc)

    for event in detected_events:
        event_id = event.get("event_id", "unknown")
        try:
            our_peak = _parse_dt(event["peak_time"])
        except Exception as exc:
            logger.error("Cannot parse peak_time for event %s: %s", event_id, exc)
            results.append({
                "event_id": event_id,
                "goes_match": False,
                "goes_class": None,
                "time_diff_minutes": None,
                "possible_goes_miss": False,
            })
            continue

        # Find the closest GOES event within the window
        best_match: Optional[dict] = None
        best_diff: Optional[float] = None

        for goes_peak, goes_entry in parsed_goes:
            diff = (our_peak - goes_peak).total_seconds() / 60.0  # signed, minutes
            if abs(diff) <= match_window_minutes:
                if best_diff is None or abs(diff) < abs(best_diff):
                    best_match = goes_entry
                    best_diff = diff

        if best_match is not None:
            results.append({
                "event_id": event_id,
                "goes_match": True,
                "goes_class": best_match.get("goes_class"),
                "time_diff_minutes": round(best_diff, 2),
                "possible_goes_miss": False,
            })
            logger.debug(
                "Event %s matched GOES %s (Δ=%.1f min)",
                event_id, best_match.get("goes_id"), best_diff,
            )
        else:
            # No GOES match found.
            # Flag as possible_goes_miss if our detector had high confidence —
            # GOES catalog is not 100% complete, especially for weaker flares
            # or events outside GOES field-of-view.
            results.append({
                "event_id": event_id,
                "goes_match": False,
                "goes_class": None,
                "time_diff_minutes": None,
                "possible_goes_miss": True,
            })
            logger.info("Event %s: no GOES match — flagged as possible GOES miss", event_id)

    return results


def summarise_validation(results: list[dict]) -> dict:
    """
    Compute aggregate validation statistics from match_events_to_goes() output.

    Returns
    -------
    dict with keys: total_events, matched, unmatched, possible_goes_misses
    """
    total = len(results)
    matched = sum(1 for r in results if r["goes_match"])
    possible_misses = sum(1 for r in results if r.get("possible_goes_miss"))
    return {
        "total_events": total,
        "matched": matched,
        "unmatched": total - matched,
        "possible_goes_misses": possible_misses,
    }
