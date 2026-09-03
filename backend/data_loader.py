"""
backend/data_loader.py
Reads processed pipeline outputs from data/processed/ and data/goes_catalog/.
All functions return plain Python dicts/lists ready for Pydantic validation.

Structure is designed so that swapping local files for a live API is a
one-function change — just replace the `_load_*_file()` helpers.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ── Resolved paths ─────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PROCESSED = _REPO_ROOT / "data" / "processed"
GOES_CATALOG = _REPO_ROOT / "data" / "goes_catalog" / "goes_events.json"
MODELS_DIR = _REPO_ROOT / "models"


# ── Internal helpers ───────────────────────────────────────────────────────────

def _load_json(path: Path) -> Any:
    """Load a JSON file; return empty list/dict on missing file."""
    if not path.exists():
        logger.warning("File not found: %s — returning empty payload", path)
        return []
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_parquet(path: Path) -> pd.DataFrame:
    """Load a parquet file; return empty DataFrame on missing file."""
    if not path.exists():
        logger.warning("Parquet not found: %s — returning empty DataFrame", path)
        return pd.DataFrame()
    return pd.read_parquet(path)


def _find_latest(pattern: str) -> Path | None:
    """Return the most recently modified file matching a glob in DATA_PROCESSED."""
    candidates = sorted(DATA_PROCESSED.glob(pattern), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


# ── Public data-loading functions ─────────────────────────────────────────────

def load_flux(limit: int | None = None) -> list[dict]:
    """
    Load the aligned flux time series produced by Prakriti's preprocessing module.
    Falls back to sample_flux.parquet if no real output exists yet.

    Returns list of dicts: {timestamp, solexs_flux, hel1os_flux, quality_flag}
    """
    path = _find_latest("aligned_flux*.parquet") or DATA_PROCESSED / "sample_flux.parquet"
    df = _load_parquet(path)

    if df.empty:
        logger.warning("No flux data found — endpoints will return empty payload")
        return []

    # Normalise column names (defensive)
    df.columns = [c.lower().strip() for c in df.columns]

    # Ensure required columns exist
    for col in ("timestamp", "solexs_flux", "hel1os_flux", "quality_flag"):
        if col not in df.columns:
            df[col] = None

    # Convert timestamp to ISO string if it's a datetime
    if pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # NaN → None so JSON serialiser doesn't choke
    df = df.where(pd.notna(df), other=None)

    records = df[["timestamp", "solexs_flux", "hel1os_flux", "quality_flag"]].to_dict(orient="records")
    return records if limit is None else records[:limit]


def load_events() -> list[dict]:
    """
    Load detected flare events from Aditi's detection engine output.
    Schema: {event_id, start_time, peak_time, end_time, peak_sigma, flare_class, instrument}
    """
    path = _find_latest("events*.json") or DATA_PROCESSED / "sample_events.json"
    return _load_json(path)


def load_predictions() -> list[dict]:
    """
    Load ML predictions from Vidushi's XGBoost pipeline output.
    Schema: {timestamp, flare_probability, predicted_class, confidence, top_features}
    """
    path = _find_latest("predictions*.json") or DATA_PROCESSED / "sample_predictions.json"
    return _load_json(path)


def load_metrics() -> dict:
    """
    Load model evaluation metrics (per-class P/R/F1, training curve, feature importance).
    """
    path = _find_latest("metrics*.json") or DATA_PROCESSED / "sample_metrics.json"
    data = _load_json(path)
    if isinstance(data, list):
        # Shouldn't happen, but guard it
        return {}
    return data


def load_goes_catalog() -> list[dict]:
    """
    Load the offline GOES flare catalog.
    Each entry: {goes_id, start_time, peak_time, end_time, goes_class}
    """
    return _load_json(GOES_CATALOG)


def get_model_version() -> str | None:
    """Return the latest model version tag from models/versions/ if available."""
    version_files = sorted(MODELS_DIR.glob("versions/*.json"), key=lambda p: p.stat().st_mtime)
    if not version_files:
        return None
    try:
        with version_files[-1].open() as fh:
            meta = json.load(fh)
            return meta.get("version")
    except Exception:
        return None
