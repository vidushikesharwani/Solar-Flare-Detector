"""
backend/tests/test_validation.py
Unit tests for the GOES cross-check matching logic.

Tests cover:
  - Exact match within window
  - Just-outside window (no match)
  - Closest match when multiple GOES entries exist
  - possible_goes_miss flagging
  - Signed time_diff_minutes direction
  - Empty catalog / empty events edge cases
  - Boundary condition: event exactly at ±10 min

Run with:
    pytest backend/tests/test_validation.py -v
"""

from __future__ import annotations

import pytest
from backend.validation import match_events_to_goes, summarise_validation


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_event(event_id: str, peak_time: str, flare_class: str = "M") -> dict:
    return {
        "event_id": event_id,
        "start_time": peak_time,
        "peak_time": peak_time,
        "end_time": peak_time,
        "peak_sigma": 7.0,
        "flare_class": flare_class,
        "instrument": "SoLEXS",
    }


def make_goes(goes_id: str, peak_time: str, goes_class: str = "M3.0") -> dict:
    return {
        "goes_id": goes_id,
        "start_time": peak_time,
        "peak_time": peak_time,
        "end_time": peak_time,
        "goes_class": goes_class,
    }


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestExactMatch:
    def test_identical_peak_times_match(self):
        events = [make_event("E1", "2024-03-15T06:00:00Z")]
        catalog = [make_goes("G1", "2024-03-15T06:00:00Z")]
        results = match_events_to_goes(events, catalog)
        assert results[0]["goes_match"] is True
        assert results[0]["time_diff_minutes"] == 0.0
        assert results[0]["goes_class"] == "M3.0"
        assert results[0]["possible_goes_miss"] is False

    def test_match_within_window(self):
        """Event 5 minutes after GOES peak — should match."""
        events = [make_event("E1", "2024-03-15T06:05:00Z")]
        catalog = [make_goes("G1", "2024-03-15T06:00:00Z")]
        results = match_events_to_goes(events, catalog, match_window_minutes=10.0)
        assert results[0]["goes_match"] is True
        assert results[0]["time_diff_minutes"] == pytest.approx(5.0)

    def test_time_diff_is_signed(self):
        """Our event BEFORE goes peak → negative diff."""
        events = [make_event("E1", "2024-03-15T05:55:00Z")]
        catalog = [make_goes("G1", "2024-03-15T06:00:00Z")]
        results = match_events_to_goes(events, catalog, match_window_minutes=10.0)
        assert results[0]["goes_match"] is True
        assert results[0]["time_diff_minutes"] == pytest.approx(-5.0)


class TestWindowBoundary:
    def test_exactly_at_boundary_matches(self):
        """Exactly ±10 min is within window (≤, not <)."""
        events = [make_event("E1", "2024-03-15T06:10:00Z")]
        catalog = [make_goes("G1", "2024-03-15T06:00:00Z")]
        results = match_events_to_goes(events, catalog, match_window_minutes=10.0)
        assert results[0]["goes_match"] is True

    def test_just_outside_boundary_no_match(self):
        """10 min 1 second outside window → no match."""
        events = [make_event("E1", "2024-03-15T06:10:01Z")]
        catalog = [make_goes("G1", "2024-03-15T06:00:00Z")]
        results = match_events_to_goes(events, catalog, match_window_minutes=10.0)
        assert results[0]["goes_match"] is False
        assert results[0]["possible_goes_miss"] is True


class TestMultipleGoesEntries:
    def test_picks_closest_goes_entry(self):
        """With two GOES entries in window, pick the nearer one."""
        events = [make_event("E1", "2024-03-15T06:07:00Z")]
        catalog = [
            make_goes("G1", "2024-03-15T06:00:00Z", "M1.0"),  # 7 min away
            make_goes("G2", "2024-03-15T06:05:00Z", "M5.0"),  # 2 min away ← closest
        ]
        results = match_events_to_goes(events, catalog, match_window_minutes=10.0)
        assert results[0]["goes_match"] is True
        assert results[0]["goes_class"] == "M5.0"
        assert results[0]["time_diff_minutes"] == pytest.approx(2.0)


class TestPossibleGoesMiss:
    def test_no_catalog_entry_flags_possible_miss(self):
        events = [make_event("E1", "2024-03-15T06:00:00Z")]
        results = match_events_to_goes(events, goes_catalog=[], match_window_minutes=10.0)
        assert results[0]["goes_match"] is False
        assert results[0]["possible_goes_miss"] is True
        assert results[0]["goes_class"] is None
        assert results[0]["time_diff_minutes"] is None

    def test_outside_window_also_flags_miss(self):
        events = [make_event("E1", "2024-03-15T06:00:00Z")]
        catalog = [make_goes("G1", "2024-03-15T08:00:00Z")]  # 2 hours away
        results = match_events_to_goes(events, catalog, match_window_minutes=10.0)
        assert results[0]["goes_match"] is False
        assert results[0]["possible_goes_miss"] is True


class TestEdgeCases:
    def test_empty_events_returns_empty_list(self):
        catalog = [make_goes("G1", "2024-03-15T06:00:00Z")]
        results = match_events_to_goes([], catalog)
        assert results == []

    def test_empty_catalog_all_flagged_as_misses(self):
        events = [make_event("E1", "2024-03-15T06:00:00Z"),
                  make_event("E2", "2024-03-15T10:00:00Z")]
        results = match_events_to_goes(events, goes_catalog=[])
        assert len(results) == 2
        assert all(r["possible_goes_miss"] for r in results)

    def test_multiple_events_independently_matched(self):
        events = [
            make_event("E1", "2024-03-15T06:00:00Z"),
            make_event("E2", "2024-03-15T10:00:00Z"),
        ]
        catalog = [
            make_goes("G1", "2024-03-15T06:02:00Z", "X1.0"),
            make_goes("G2", "2024-03-15T20:00:00Z", "M2.0"),  # far from E2
        ]
        results = match_events_to_goes(events, catalog, match_window_minutes=10.0)
        assert results[0]["goes_match"] is True
        assert results[0]["goes_class"] == "X1.0"
        assert results[1]["goes_match"] is False


class TestSummarise:
    def test_summarise_counts(self):
        results = [
            {"goes_match": True,  "possible_goes_miss": False},
            {"goes_match": True,  "possible_goes_miss": False},
            {"goes_match": False, "possible_goes_miss": True},
            {"goes_match": False, "possible_goes_miss": False},
        ]
        summary = summarise_validation(results)
        assert summary["total_events"] == 4
        assert summary["matched"] == 2
        assert summary["unmatched"] == 2
        assert summary["possible_goes_misses"] == 1

    def test_summarise_empty(self):
        summary = summarise_validation([])
        assert summary["total_events"] == 0
        assert summary["matched"] == 0
