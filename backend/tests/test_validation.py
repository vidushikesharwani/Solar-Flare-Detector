"""
backend/tests/test_validation.py
Unit tests for the GOES cross-check matching logic.

Tests cover:
  - Exact match within window
  - Just-outside window (no match, not treated as FP)
  - Closest match when multiple GOES entries exist
  - Unmatched events returning correct contract fields
  - Signed time_diff_minutes direction
  - Empty catalog / empty events edge cases
  - Boundary condition: event exactly at ±10 min

Note: possible_goes_miss is an internal concept (logged but NOT in the API response).
Tests verify that unmatched events return goes_match=False with goes_class=None
and time_diff_minutes=None — the correct spec-compliant response.
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
        # possible_goes_miss is internal — must not be in the returned dict
        assert "possible_goes_miss" not in results[0]

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
        # Unmatched events must not be automatically labelled as false positives.
        # possible_goes_miss is internal (logged) — not returned in the dict.
        assert "possible_goes_miss" not in results[0]
        assert results[0]["goes_class"] is None
        assert results[0]["time_diff_minutes"] is None


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



class TestUnmatchedNotFP:
    """Verify unmatched events are NOT auto-labelled as false positives."""

    def test_no_catalog_entry_returns_goes_match_false(self):
        """Empty catalog → goes_match=False with null fields (not a false positive label)."""
        events = [make_event("E1", "2024-03-15T06:00:00Z")]
        results = match_events_to_goes(events, goes_catalog=[], match_window_minutes=10.0)
        assert results[0]["goes_match"] is False
        assert results[0]["goes_class"] is None
        assert results[0]["time_diff_minutes"] is None
        # Internal field must not leak into the returned dict
        assert "possible_goes_miss" not in results[0]

    def test_outside_window_returns_goes_match_false(self):
        events = [make_event("E1", "2024-03-15T06:00:00Z")]
        catalog = [make_goes("G1", "2024-03-15T08:00:00Z")]  # 2 hours away
        results = match_events_to_goes(events, catalog, match_window_minutes=10.0)
        assert results[0]["goes_match"] is False
        assert "possible_goes_miss" not in results[0]


class TestEdgeCases:
    def test_empty_events_returns_empty_list(self):
        catalog = [make_goes("G1", "2024-03-15T06:00:00Z")]
        results = match_events_to_goes([], catalog)
        assert results == []

    def test_empty_catalog_all_unmatched(self):
        events = [make_event("E1", "2024-03-15T06:00:00Z"),
                  make_event("E2", "2024-03-15T10:00:00Z")]
        results = match_events_to_goes(events, goes_catalog=[])
        assert len(results) == 2
        # All unmatched — but not auto-labelled as false positives
        assert all(r["goes_match"] is False for r in results)
        assert all("possible_goes_miss" not in r for r in results)

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
        # summarise_validation only receives the contract dict keys
        results = [
            {"goes_match": True},
            {"goes_match": True},
            {"goes_match": False},
            {"goes_match": False},
        ]
        summary = summarise_validation(results)
        assert summary["total_events"] == 4
        assert summary["matched"] == 2
        assert summary["unmatched"] == 2
        # possible_goes_misses not in the summary dict — it's internal
        assert "possible_goes_misses" not in summary

    def test_summarise_empty(self):
        summary = summarise_validation([])
        assert summary["total_events"] == 0
        assert summary["matched"] == 0
