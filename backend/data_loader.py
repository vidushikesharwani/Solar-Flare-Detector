"""
backend/data_loader.py
Reads processed pipeline outputs and the GOES catalog from disk.

Expected file locations (produced by teammates' pipeline modules):
  data/processed/aligned_flux*.parquet  ← Prakriti's preprocessing output
  data/processed/events*.json           ← Aditi's detection engine output
  data/processed/predictions*.json      ← Vidushi's ML pipeline output
  data/processed/metrics*.json          ← Vidushi's evaluation output
  data/goes_catalog/goes_events.json    ← Real GOES/DONKI catalog (2024, offline)

If a file is missing the endpoint raises HTTP 503 — no fake fallback data.
Swapping to a live data source only requires replacing the _find_latest() call
in the relevant function; the rest of the stack stays unchanged.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_REPO_ROOT    = Path(__file__).resolve().parent.parent
DATA_PROCESSED = _REPO_ROOT / "data" / "processed"
GOES_CATALOG   = _REPO_ROOT / "data" / "goes_catalog" / "goes_events.json"
MODELS_DIR     = _REPO_ROOT / "models"


# ── Internal helpers ───────────────────────────────────────────────────────────

def _find_latest(pattern: str) -> Path | None:
    """Return the most recently modified file matching a glob in DATA_PROCESSED."""
    candidates = sorted(
        DATA_PROCESSED.glob(pattern),
        key=lambda p: p.stat().st_mtime,
    )
    return candidates[-1] if candidates else None


def _load_json(path: Path) -> Any:
    """Load JSON; return None if file does not exist (caller raises 503)."""
    if not path or not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_parquet(path: Path | None) -> pd.DataFrame | None:
    """Load parquet; return None if file does not exist (caller raises 503)."""
    if not path or not path.exists():
        return None
    return pd.read_parquet(path)


# ── Public loaders ─────────────────────────────────────────────────────────────

def load_flux(limit: int | None = None) -> list[dict] | None:
    """
    Load aligned flux time series from Prakriti's preprocessing output.
    Returns None if no file is available yet (endpoint should raise 503).
    Contract columns: timestamp, solexs_flux, hel1os_flux, quality_flag
    API response exposes: timestamp, solexs_flux, hel1os_flux  (no quality_flag)
    """
    path = _find_latest("aligned_flux*.parquet")
    df = _load_parquet(path)
    if df is None:
        logger.warning("No aligned flux parquet found in %s", DATA_PROCESSED)
        return None

    df.columns = [c.lower().strip() for c in df.columns]
    if "timestamp" not in df.columns:
        logger.error("Flux parquet missing required 'timestamp' column: %s", path)
        return None

    for col in ("solexs_flux", "hel1os_flux"):
        if col not in df.columns:
            df[col] = None

    if pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    df = df.where(pd.notna(df), other=None)
    # Return only the API contract columns (quality_flag stays internal)
    records = df[["timestamp", "solexs_flux", "hel1os_flux"]].to_dict(orient="records")
    return records if limit is None else records[:limit]


def load_events() -> list[dict] | None:
    """
    Load detected flare events from Aditi's detection engine output.
    Returns None if no file is available yet.
    Contract: {event_id, start_time, peak_time, end_time, peak_sigma, flare_class, instrument}
    """
    path = _find_latest("events*.json")
    data = _load_json(path)
    if data is None:
        logger.warning("No events JSON found in %s", DATA_PROCESSED)
        return None
    if not isinstance(data, list):
        logger.error("Events JSON is not a list: %s", path)
        return None
    return data


def load_predictions() -> list[dict] | None:
    """
    Load ML predictions from Vidushi's XGBoost pipeline output.
    Returns None if no file is available yet.
    Contract: {timestamp, flare_probability, predicted_class, confidence, top_features}
    """
    path = _find_latest("predictions*.json")
    data = _load_json(path)
    if data is None:
        logger.warning("No predictions JSON found in %s", DATA_PROCESSED)
        return None
    if not isinstance(data, list):
        logger.error("Predictions JSON is not a list: %s", path)
        return None
    return data


def load_metrics() -> dict | None:
    """
    Load model evaluation metrics from Vidushi's pipeline.
    Returns None if no file is available yet.
    """
    path = _find_latest("metrics*.json")
    data = _load_json(path)
    if data is None:
        logger.warning("No metrics JSON found in %s", DATA_PROCESSED)
        return None
    return data if isinstance(data, dict) else None


def load_goes_catalog() -> list[dict]:
    """
    Load the real offline GOES flare catalog (2024, sourced from NASA DONKI).
    Always returns a list — empty if the file is somehow missing.
    """
    data = _load_json(GOES_CATALOG)
    if data is None:
        logger.error("GOES catalog not found at %s", GOES_CATALOG)
        return []
    if not isinstance(data, list):
        logger.error("GOES catalog at %s is not a list", GOES_CATALOG)
        return []
    return data


def get_model_version() -> str | None:
    """Return the latest model version tag from models/versions/ if available."""
    version_files = sorted(
        MODELS_DIR.glob("versions/*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    if not version_files:
        return None
    try:
        with version_files[-1].open() as fh:
            return json.load(fh).get("version")
    except Exception:
        return None
