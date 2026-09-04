"""
backend/tests/test_api.py
API integration tests using pytest + httpx TestClient.

Strategy:
  - /api/flux, /api/events, /api/predictions: mock data_loader so tests run
    without needing real pipeline output on disk.
  - /api/validation: uses the real GOES catalog (data/goes_catalog/goes_events.json)
    with mocked events to verify matching logic end-to-end.
  - /api/metrics: mocked since training hasn't run yet.
  - When pipeline data exists on disk the mocks are bypassed by the actual loaders.

Run with:
    pytest backend/tests/test_api.py -v
"""

from __future__ import annotations

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app, raise_server_exceptions=True)

# ── Minimal valid payloads matching exact API contracts ────────────────────────

MOCK_FLUX = [
    {"timestamp": "2024-03-15T06:00:00Z", "solexs_flux": 1.2e-7, "hel1os_flux": 500.0},
    {"timestamp": "2024-03-15T06:01:00Z", "solexs_flux": 1.5e-7, "hel1os_flux": 510.0},
]

MOCK_EVENTS = [
    {
        "event_id": "EVT-001", "start_time": "2024-03-15T06:10:00Z",
        "peak_time": "2024-03-15T06:23:00Z", "end_time": "2024-03-15T06:47:00Z",
        "peak_sigma": 12.4, "flare_class": "X", "instrument": "SoLEXS",
    },
    {
        "event_id": "EVT-002", "start_time": "2024-03-15T10:03:00Z",
        "peak_time": "2024-03-15T10:20:00Z", "end_time": "2024-03-15T10:42:00Z",
        "peak_sigma": 7.8, "flare_class": "M", "instrument": "HEL1OS",
    },
]

MOCK_PREDICTIONS = [
    {
        "timestamp": "2024-03-15T06:20:00Z", "flare_probability": 0.91,
        "predicted_class": "X", "confidence": 0.88,
        "top_features": {"solexs_roc_60s": 0.42, "hel1os_peak_amplitude": 0.15},
    },
]

MOCK_METRICS = {
    "overall_accuracy": 0.84,
    "model_version": "xgb-v0.1",
    "trained_at": "2024-03-15T00:00:00Z",
    "per_class_metrics": [
        {"flare_class": "X", "precision": 0.92, "recall": 0.88, "f1": 0.90, "support": 12},
    ],
    "training_curve": [
        {"epoch": 1, "train_loss": 1.42, "val_loss": 1.51, "train_accuracy": 0.41, "val_accuracy": 0.38},
    ],
    "feature_importance": [
        {"feature": "solexs_roc_60s", "importance": 0.38, "instrument": "SoLEXS"},
    ],
}


# ─── /health ──────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self):
        assert client.get("/health").status_code == 200

    def test_health_schema(self):
        data = client.get("/health").json()
        assert data["status"] == "ok"
        assert "version" in data


# ─── /api/flux ────────────────────────────────────────────────────────────────

class TestFlux:
    def test_flux_503_without_data(self):
        """Without pipeline data on disk, endpoint must return 503."""
        with patch("backend.data_loader.load_flux", return_value=None):
            assert client.get("/api/flux").status_code == 503

    def test_flux_returns_200_with_data(self):
        with patch("backend.data_loader.load_flux", return_value=MOCK_FLUX):
            assert client.get("/api/flux").status_code == 200

    def test_flux_top_level_schema(self):
        with patch("backend.data_loader.load_flux", return_value=MOCK_FLUX):
            data = client.get("/api/flux").json()
            assert "data" in data
            assert "total_points" in data
            assert isinstance(data["data"], list)

    def test_flux_point_schema(self):
        """API contract: timestamp, solexs_flux, hel1os_flux — no quality_flag."""
        with patch("backend.data_loader.load_flux", return_value=MOCK_FLUX):
            point = client.get("/api/flux").json()["data"][0]
            assert "timestamp" in point
            assert "solexs_flux" in point
            assert "hel1os_flux" in point
            assert "quality_flag" not in point, (
                "quality_flag is internal — must not appear in the API response"
            )

    def test_flux_limit_param(self):
        with patch("backend.data_loader.load_flux", return_value=MOCK_FLUX[:1]):
            data = client.get("/api/flux?limit=1").json()
            assert len(data["data"]) <= 1

    def test_flux_replay_mode_streams(self):
        with patch("backend.data_loader.load_flux", return_value=MOCK_FLUX):
            with client.stream("GET", "/api/flux?replay=true&speed=1000") as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers.get("content-type", "")
                for chunk in resp.iter_lines():
                    if chunk:
                        assert chunk.startswith("data:")
                        break


# ─── /api/events ──────────────────────────────────────────────────────────────

class TestEvents:
    def test_events_503_without_data(self):
        with patch("backend.data_loader.load_events", return_value=None):
            assert client.get("/api/events").status_code == 503

    def test_events_returns_200_with_data(self):
        with patch("backend.data_loader.load_events", return_value=MOCK_EVENTS):
            assert client.get("/api/events").status_code == 200

    def test_events_schema(self):
        with patch("backend.data_loader.load_events", return_value=MOCK_EVENTS):
            evt = client.get("/api/events").json()["events"][0]
            for key in ("event_id", "start_time", "peak_time", "end_time",
                        "peak_sigma", "flare_class", "instrument"):
                assert key in evt, f"Missing key: {key}"

    def test_events_filter_by_class(self):
        with patch("backend.data_loader.load_events", return_value=MOCK_EVENTS):
            data = client.get("/api/events?flare_class=X").json()
            assert all(e["flare_class"].upper() == "X" for e in data["events"])

    def test_events_filter_by_instrument(self):
        with patch("backend.data_loader.load_events", return_value=MOCK_EVENTS):
            data = client.get("/api/events?instrument=SoLEXS").json()
            assert all(e["instrument"].upper() == "SOLEXS" for e in data["events"])


# ─── /api/predictions ─────────────────────────────────────────────────────────

class TestPredictions:
    def test_predictions_503_without_data(self):
        with patch("backend.data_loader.load_predictions", return_value=None):
            assert client.get("/api/predictions").status_code == 503

    def test_predictions_returns_200_with_data(self):
        with patch("backend.data_loader.load_predictions", return_value=MOCK_PREDICTIONS):
            assert client.get("/api/predictions").status_code == 200

    def test_prediction_schema(self):
        with patch("backend.data_loader.load_predictions", return_value=MOCK_PREDICTIONS):
            pred = client.get("/api/predictions").json()["predictions"][0]
            for key in ("timestamp", "flare_probability", "predicted_class",
                        "confidence", "top_features"):
                assert key in pred, f"Missing key: {key}"

    def test_prediction_probability_range(self):
        with patch("backend.data_loader.load_predictions", return_value=MOCK_PREDICTIONS):
            for pred in client.get("/api/predictions").json()["predictions"]:
                assert 0.0 <= pred["flare_probability"] <= 1.0
                assert 0.0 <= pred["confidence"] <= 1.0

    def test_predictions_limit_param(self):
        with patch("backend.data_loader.load_predictions", return_value=MOCK_PREDICTIONS):
            data = client.get("/api/predictions?limit=1").json()
            assert len(data["predictions"]) <= 1


# ─── /api/validation ──────────────────────────────────────────────────────────
# Uses real GOES catalog + mocked events so matching logic is tested end-to-end.

class TestValidation:
    def test_validation_returns_200(self):
        """Real GOES catalog + mock events — no patch needed for catalog."""
        with patch("backend.data_loader.load_events", return_value=MOCK_EVENTS):
            assert client.get("/api/validation").status_code == 200

    def test_validation_top_level_schema(self):
        with patch("backend.data_loader.load_events", return_value=MOCK_EVENTS):
            data = client.get("/api/validation").json()
            # Fixed contract: results, total_events, matched, unmatched
            for key in ("results", "total_events", "matched", "unmatched"):
                assert key in data, f"Missing key: {key}"
            assert "possible_goes_misses" not in data

    def test_validation_result_schema(self):
        with patch("backend.data_loader.load_events", return_value=MOCK_EVENTS):
            data = client.get("/api/validation").json()
            if data["results"]:
                result = data["results"][0]
                # Fixed contract: event_id, goes_match, goes_class, time_diff_minutes
                for key in ("event_id", "goes_match", "goes_class", "time_diff_minutes"):
                    assert key in result, f"Missing key: {key}"
                assert "possible_goes_miss" not in result

    def test_validation_counts_consistent(self):
        with patch("backend.data_loader.load_events", return_value=MOCK_EVENTS):
            data = client.get("/api/validation").json()
            assert data["matched"] + data["unmatched"] == data["total_events"]

    def test_validation_custom_window(self):
        """Tight window should produce fewer or equal matches than wide window."""
        with patch("backend.data_loader.load_events", return_value=MOCK_EVENTS):
            tight  = client.get("/api/validation?match_window_minutes=1").json()
            normal = client.get("/api/validation?match_window_minutes=10").json()
            assert tight["matched"] <= normal["matched"]

    def test_validation_503_without_events(self):
        with patch("backend.data_loader.load_events", return_value=None):
            assert client.get("/api/validation").status_code == 503


# ─── /api/metrics ─────────────────────────────────────────────────────────────

class TestMetrics:
    def test_metrics_503_without_data(self):
        with patch("backend.data_loader.load_metrics", return_value=None):
            assert client.get("/api/metrics").status_code == 503

    def test_metrics_returns_200_with_data(self):
        with patch("backend.data_loader.load_metrics", return_value=MOCK_METRICS):
            assert client.get("/api/metrics").status_code == 200

    def test_metrics_schema(self):
        with patch("backend.data_loader.load_metrics", return_value=MOCK_METRICS):
            data = client.get("/api/metrics").json()
            assert "per_class_metrics" in data
            assert "training_curve" in data
            assert "feature_importance" in data
            assert "overall_accuracy" in data

    def test_per_class_metrics_schema(self):
        with patch("backend.data_loader.load_metrics", return_value=MOCK_METRICS):
            for cls_m in client.get("/api/metrics").json()["per_class_metrics"]:
                for key in ("flare_class", "precision", "recall", "f1", "support"):
                    assert key in cls_m, f"Missing key: {key}"

    def test_training_curve_schema(self):
        with patch("backend.data_loader.load_metrics", return_value=MOCK_METRICS):
            for point in client.get("/api/metrics").json()["training_curve"]:
                assert "epoch" in point
                assert "train_loss" in point


# ─── Edge cases & defensive checks ───────────────────────────────────────────

def test_load_flux_missing_timestamp_returns_none():
    import pandas as pd
    from backend.data_loader import load_flux

    bad_df = pd.DataFrame({"solexs_flux": [1.0, 2.0], "hel1os_flux": [10.0, 20.0]})
    with patch("backend.data_loader._find_latest", return_value="fake_aligned.parquet"):
        with patch("backend.data_loader._load_parquet", return_value=bad_df):
            assert load_flux() is None


@pytest.mark.asyncio
async def test_replay_speed_zero_or_negative_raises_value_error():
    from backend.replay import stream_flux_replay

    records = [{"timestamp": "2024-03-15T06:00:00Z", "solexs_flux": 1e-7, "hel1os_flux": 500.0}]
    with pytest.raises(ValueError, match="speed must be > 0"):
        async for _ in stream_flux_replay(records, speed=0):
            pass

    with pytest.raises(ValueError, match="speed must be > 0"):
        async for _ in stream_flux_replay(records, speed=-5.0):
            pass


def test_load_events_non_list_returns_none():
    from backend.data_loader import load_events

    with patch("backend.data_loader._find_latest", return_value="fake_events.json"):
        with patch("backend.data_loader._load_json", return_value={"events": []}):
            assert load_events() is None


def test_load_predictions_non_list_returns_none():
    from backend.data_loader import load_predictions

    with patch("backend.data_loader._find_latest", return_value="fake_predictions.json"):
        with patch("backend.data_loader._load_json", return_value={"predictions": []}):
            assert load_predictions() is None


def test_load_goes_catalog_non_list_returns_empty_list():
    from backend.data_loader import load_goes_catalog

    with patch("backend.data_loader._load_json", return_value={"goes_events": {}}):
        assert load_goes_catalog() == []


