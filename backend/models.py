"""
backend/models.py
Pydantic response schemas — fixed data contract with all teammates.
DO NOT change these schemas without raising a GitHub issue first.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


# ─── /api/flux ────────────────────────────────────────────────────────────────

class FluxPoint(BaseModel):
    """Single aligned flux sample (Prakriti's preprocessing output)."""
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp")
    solexs_flux: Optional[float] = Field(None, description="SoLEXS 1–15 keV flux (W/m²)")
    hel1os_flux: Optional[float] = Field(None, description="HEL1OS 12–200 keV flux (counts/s)")
    quality_flag: int = Field(0, description="0=good, 1=gap/dropout, 2=saturated, 3=noisy")


class FluxResponse(BaseModel):
    data: list[FluxPoint]
    total_points: int
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None
    replay_mode: bool = False


# ─── /api/events ──────────────────────────────────────────────────────────────

class FlareEvent(BaseModel):
    """Detected flare event (Aditi's detection engine output)."""
    event_id: str
    start_time: str
    peak_time: str
    end_time: str
    peak_sigma: float = Field(..., description="Peak flux above baseline in σ units")
    flare_class: str = Field(..., description="A / B / C / M / X")
    instrument: str = Field(..., description="SoLEXS | HEL1OS")


class EventsResponse(BaseModel):
    events: list[FlareEvent]
    total_events: int


# ─── /api/predictions ─────────────────────────────────────────────────────────

class Prediction(BaseModel):
    """XGBoost ML prediction (Vidushi's ML pipeline output)."""
    timestamp: str
    flare_probability: float = Field(..., ge=0.0, le=1.0)
    predicted_class: str = Field(..., description="A / B / C / M / X")
    confidence: float = Field(..., ge=0.0, le=1.0)
    top_features: dict[str, float] = Field(
        default_factory=dict,
        description="SHAP values keyed by feature name"
    )


class PredictionsResponse(BaseModel):
    predictions: list[Prediction]
    total_predictions: int
    model_version: Optional[str] = None


# ─── /api/validation ──────────────────────────────────────────────────────────

class ValidationResult(BaseModel):
    """GOES cross-check result for a detected event."""
    event_id: str
    goes_match: bool
    goes_class: Optional[str] = Field(None, description="GOES assigned class, None if no match")
    time_diff_minutes: Optional[float] = Field(
        None,
        description="Signed offset: our peak_time minus GOES peak_time (minutes)"
    )
    possible_goes_miss: bool = Field(
        False,
        description="True when our detector fired but no GOES entry exists within window"
    )


class ValidationResponse(BaseModel):
    results: list[ValidationResult]
    total_events: int
    matched: int
    unmatched: int
    possible_goes_misses: int


# ─── /api/metrics ─────────────────────────────────────────────────────────────

class ClassMetrics(BaseModel):
    flare_class: str
    precision: float
    recall: float
    f1: float
    support: int


class TrainingPoint(BaseModel):
    epoch: int
    train_loss: float
    val_loss: Optional[float] = None
    train_accuracy: Optional[float] = None
    val_accuracy: Optional[float] = None


class FeatureImportance(BaseModel):
    feature: str
    importance: float
    instrument: str = Field(..., description="SoLEXS | HEL1OS | combined")


class MetricsResponse(BaseModel):
    per_class_metrics: list[ClassMetrics]
    training_curve: list[TrainingPoint]
    feature_importance: list[FeatureImportance]
    overall_accuracy: float
    model_version: Optional[str] = None
    trained_at: Optional[str] = None
