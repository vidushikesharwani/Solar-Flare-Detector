"""
backend/validation.py
GOES cross-check validation module.

Given our detected flare events and a local GOES catalog, this module:
  1. Matches each detected event to the nearest GOES entry within ±MATCH_WINDOW_MINUTES.
  2. Records the time offset and GOES assigned class.
  3. Internally identifies "possible GOES misses" (events we detected but GOES has no
     record of) to avoid treating them as false positives. This determination is
     used for logging only — it is NOT exposed in the API response schema.

Fixed API output per event: {event_id, goes_match, goes_class, time_diff_minutes}

Design note: the GOES data source is abstracted through the `goes_catalog` parameter
so that a LocalGOESProvider or a future LiveGOESProvider can be swapped in without
rewriting any matching logic here.
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
            })
            logger.debug(
                "Event %s matched GOES %s (Δ=%.1f min)",
                event_id, best_match.get("goes_id"), best_diff,
            )
        else:
            # No GOES match found.
            # Internally we consider this a "possible GOES miss" — GOES catalog is
            # not 100% complete (coverage gaps, weak flares below GOES threshold,
            # or events outside GOES field-of-view). We log it but do NOT
            # automatically label it a false positive in the API response.
            results.append({
                "event_id": event_id,
                "goes_match": False,
                "goes_class": None,
                "time_diff_minutes": None,
            })
            logger.info(
                "Event %s: no GOES match within ±%.1f min — possible GOES miss (not auto-labelled FP)",
                event_id, match_window_minutes,
            )

    return results


def summarise_validation(results: list[dict]) -> dict:
    """
    Compute aggregate validation statistics from match_events_to_goes() output.

    Returns
    -------
    dict with keys: total_events, matched, unmatched
    (possible_goes_misses is tracked internally via logs, not exposed in API)
    """
    total = len(results)
    matched = sum(1 for r in results if r["goes_match"])
    return {
        "total_events": total,
        "matched": matched,
        "unmatched": total - matched,
    }
