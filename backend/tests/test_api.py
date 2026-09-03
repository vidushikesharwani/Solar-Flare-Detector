"""
backend/tests/test_api.py
API integration tests using pytest + httpx.

Each test:
  - Spins up the FastAPI app with TestClient (synchronous)
  - Confirms HTTP status, response schema shape, and required fields

Run with:
    pytest backend/tests/test_api.py -v
"""

from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app, raise_server_exceptions=True)


# ─── /health ──────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_schema(self):
        data = client.get("/health").json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "version" in data


# ─── /api/flux ────────────────────────────────────────────────────────────────

class TestFlux:
    def test_flux_returns_200(self):
        resp = client.get("/api/flux")
        assert resp.status_code == 200

    def test_flux_top_level_schema(self):
        data = client.get("/api/flux").json()
        assert "data" in data
        assert "total_points" in data
        assert isinstance(data["data"], list)
        assert isinstance(data["total_points"], int)

    def test_flux_point_schema(self):
        data = client.get("/api/flux").json()
        if data["data"]:
            point = data["data"][0]
            # Fixed API contract: timestamp, solexs_flux, hel1os_flux only
            assert "timestamp" in point
            assert "solexs_flux" in point
            assert "hel1os_flux" in point
            # quality_flag is a pipeline-internal field — must NOT appear in the API response
            assert "quality_flag" not in point, (
                "quality_flag is an internal preprocessing field and must not be in the API response"
            )

    def test_flux_limit_param(self):
        data = client.get("/api/flux?limit=5").json()
        assert len(data["data"]) <= 5

    def test_flux_limit_reduces_response(self):
        all_data = client.get("/api/flux").json()
        limited = client.get("/api/flux?limit=3").json()
        if all_data["total_points"] > 3:
            assert limited["total_points"] == 3

    def test_flux_replay_mode_streams(self):
        """Replay mode should return a streaming response (content-type check)."""
        # Use a very high speed so it returns quickly
        with client.stream("GET", "/api/flux?replay=true&speed=1000") as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            # Read just the first chunk
            for chunk in resp.iter_lines():
                if chunk:
                    assert chunk.startswith("data:")
                    break


# ─── /api/events ──────────────────────────────────────────────────────────────

class TestEvents:
    def test_events_returns_200(self):
        resp = client.get("/api/events")
        assert resp.status_code == 200

    def test_events_top_level_schema(self):
        data = client.get("/api/events").json()
        assert "events" in data
        assert "total_events" in data
        assert isinstance(data["events"], list)

    def test_event_schema(self):
        data = client.get("/api/events").json()
        if data["events"]:
            evt = data["events"][0]
            for key in ("event_id", "start_time", "peak_time", "end_time",
                         "peak_sigma", "flare_class", "instrument"):
                assert key in evt, f"Missing key: {key}"

    def test_events_filter_by_class(self):
        resp = client.get("/api/events?flare_class=X")
        assert resp.status_code == 200
        data = resp.json()
        for evt in data["events"]:
            assert evt["flare_class"].upper() == "X"

    def test_events_filter_by_instrument(self):
        resp = client.get("/api/events?instrument=SoLEXS")
        assert resp.status_code == 200
        data = resp.json()
        for evt in data["events"]:
            assert evt["instrument"].upper() == "SOLEXS"


# ─── /api/predictions ─────────────────────────────────────────────────────────

class TestPredictions:
    def test_predictions_returns_200(self):
        resp = client.get("/api/predictions")
        assert resp.status_code == 200

    def test_predictions_top_level_schema(self):
        data = client.get("/api/predictions").json()
        assert "predictions" in data
        assert "total_predictions" in data

    def test_prediction_schema(self):
        data = client.get("/api/predictions").json()
        if data["predictions"]:
            pred = data["predictions"][0]
            for key in ("timestamp", "flare_probability", "predicted_class",
                         "confidence", "top_features"):
                assert key in pred, f"Missing key: {key}"

    def test_prediction_probability_range(self):
        data = client.get("/api/predictions").json()
        for pred in data["predictions"]:
            assert 0.0 <= pred["flare_probability"] <= 1.0
            assert 0.0 <= pred["confidence"] <= 1.0

    def test_predictions_limit_param(self):
        data = client.get("/api/predictions?limit=2").json()
        assert len(data["predictions"]) <= 2


# ─── /api/validation ──────────────────────────────────────────────────────────

class TestValidation:
    def test_validation_returns_200(self):
        resp = client.get("/api/validation")
        assert resp.status_code == 200

    def test_validation_top_level_schema(self):
        data = client.get("/api/validation").json()
        # Fixed contract: results, total_events, matched, unmatched
        for key in ("results", "total_events", "matched", "unmatched"):
            assert key in data, f"Missing key: {key}"

    def test_validation_result_schema(self):
        data = client.get("/api/validation").json()
        if data["results"]:
            result = data["results"][0]
            # Fixed contract: event_id, goes_match, goes_class, time_diff_minutes
            for key in ("event_id", "goes_match", "goes_class", "time_diff_minutes"):
                assert key in result, f"Missing key: {key}"
            # possible_goes_miss is internal — must NOT appear in the API response
            assert "possible_goes_miss" not in result, (
                "possible_goes_miss is an internal field and must not be in the API response"
            )

    def test_validation_counts_are_consistent(self):
        data = client.get("/api/validation").json()
        assert data["matched"] + data["unmatched"] == data["total_events"]

    def test_validation_custom_window(self):
        """A very tight window should produce fewer or equal matches."""
        tight = client.get("/api/validation?match_window_minutes=1").json()
        normal = client.get("/api/validation?match_window_minutes=10").json()
        assert tight["matched"] <= normal["matched"]


# ─── /api/metrics ─────────────────────────────────────────────────────────────

class TestMetrics:
    def test_metrics_returns_200(self):
        resp = client.get("/api/metrics")
        # 200 if sample data exists, 503 if no data at all
        assert resp.status_code in (200, 503)

    def test_metrics_schema_when_available(self):
        resp = client.get("/api/metrics")
        if resp.status_code == 200:
            data = resp.json()
            assert "per_class_metrics" in data
            assert "training_curve" in data
            assert "feature_importance" in data
            assert "overall_accuracy" in data

    def test_per_class_metrics_schema(self):
        resp = client.get("/api/metrics")
        if resp.status_code == 200:
            for cls_metric in resp.json()["per_class_metrics"]:
                for key in ("flare_class", "precision", "recall", "f1", "support"):
                    assert key in cls_metric, f"Missing key: {key}"

    def test_training_curve_schema(self):
        resp = client.get("/api/metrics")
        if resp.status_code == 200:
            for point in resp.json()["training_curve"]:
                assert "epoch" in point
                assert "train_loss" in point
