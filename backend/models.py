"""
backend/models.py
Pydantic response schemas — fixed data contract with all teammates.
DO NOT change these schemas without raising a GitHub issue first.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict


# ─── /api/flux ────────────────────────────────────────────────────────────────

class FluxPoint(BaseModel):
    """Single aligned flux sample — API contract: timestamp, solexs_flux, hel1os_flux."""
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp")
    solexs_flux: Optional[float] = Field(None, description="SoLEXS 1–15 keV flux (W/m²)")
    hel1os_flux: Optional[float] = Field(None, description="HEL1OS 12–200 keV flux (counts/s)")


class FluxResponse(BaseModel):
    data: list[FluxPoint]
    total_points: int
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None
    replay_mode: bool = False


# ─── /api/events ──────────────────────────────────────────────────────────────

class FlareEvent(BaseModel):
    """Detected flare event (Aditi's detection engine output)."""
    model_config = ConfigDict(extra="ignore")

    event_id: str
    start_time: str
    peak_time: str
    end_time: str
    peak_sigma: float = Field(..., description="Peak flux above baseline in σ units")
    flare_class: str = Field(..., description="A / B / C / M / X")
    instrument: str = Field(..., description="SoLEXS | HEL1OS")
    background_flux: Optional[float] = Field(None, description="Baseline flux at event onset")
    peak_flux: Optional[float] = Field(None, description="Maximum flux reached during event")
    duration_minutes: Optional[float] = Field(None, description="Event duration in minutes")


class EventsResponse(BaseModel):
    events: list[FlareEvent]
    total_events: int


# ─── /api/predictions ─────────────────────────────────────────────────────────

class Prediction(BaseModel):
    """XGBoost ML prediction (Vidushi's ML pipeline output)."""
    model_config = ConfigDict(extra="ignore")

    timestamp: str
    flare_probability: float = Field(..., ge=0.0, le=1.0)
    predicted_class: str = Field(..., description="A / B / C / M / X / NO_FLARE / quiet")
    confidence: float = Field(..., ge=0.0, le=1.0)
    top_features: Any = Field(
        default_factory=dict,
        description="SHAP values keyed by feature name or list of feature objects"
    )


class PredictionsResponse(BaseModel):
    predictions: list[Prediction]
    total_predictions: int
    model_version: Optional[str] = None


# ─── /api/validation ──────────────────────────────────────────────────────────

class ValidationResult(BaseModel):
    """GOES cross-check result — fixed contract: event_id, goes_match, goes_class, time_diff_minutes."""
    event_id: str
    goes_match: bool
    goes_class: Optional[str] = Field(None, description="GOES assigned class, None if no match")
    time_diff_minutes: Optional[float] = Field(
        None,
        description="Signed offset: our peak_time minus GOES peak_time (minutes)"
    )
    # NOTE: possible_goes_miss is tracked internally in validation.py but is NOT
    # part of the fixed API contract — do not expose it here.


class ValidationResponse(BaseModel):
    results: list[ValidationResult]
    total_events: int
    matched: int
    unmatched: int


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
