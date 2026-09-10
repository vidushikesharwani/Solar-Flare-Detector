"""
backend/main.py
FastAPI application — Solar Flare Detector backend.

Endpoints
---------
GET /api/flux               Aligned X-ray flux time series
GET /api/flux?replay=true   SSE replay stream at ?speed=N (default 10×)
GET /api/events             Detected flare events
GET /api/predictions        XGBoost ML predictions
GET /api/validation         GOES cross-check results
GET /api/metrics            Per-class P/R/F1, training curve, feature importance
GET /health                 Quick liveness probe

All endpoints read local files produced by the pipeline — no live internet
required. This makes it fully exhibition-demo safe.

Run with:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend import data_loader, validation as goes_validator
from backend.models import (
    FluxResponse,
    FluxPoint,
    EventsResponse,
    FlareEvent,
    PredictionsResponse,
    Prediction,
    ValidationResponse,
    ValidationResult,
    MetricsResponse,
    ClassMetrics,
    TrainingPoint,
    FeatureImportance,
)
from backend.replay import stream_flux_replay

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Solar Flare Detector API",
    description=(
        "Backend API for the Aditya-L1 Solar Flare Detector. "
        "Serves flux data, detected events, ML predictions, GOES validation, "
        "and model metrics to the React dashboard."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS — allow React dev server (Gauri/Kasak's frontend) ───────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:3000",   # fallback CRA port
    ],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════════
# Health check
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Quick liveness probe — returns OK when the server is up."""
    return {"status": "ok", "version": app.version}


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/flux
# ═══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/api/flux",
    response_model=FluxResponse,
    responses={
        200: {
            "content": {
                "application/json": {},
                "text/event-stream": {
                    "schema": {"type": "string"},
                    "description": "Server-Sent Events (SSE) replay stream when replay=true",
                },
            },
            "description": "Aligned flux time series data (JSON) or replay stream (SSE)",
        }
    },
    tags=["Data"],
    summary="Aligned X-ray flux time series",
    description=(
        "Returns the preprocessed, aligned SoLEXS + HEL1OS flux time series. "
        "Add `?replay=true&speed=N` to receive a Server-Sent Events stream that "
        "replays historical data at N× speed for the exhibition live demo."
    ),
)
async def get_flux(
    replay: Annotated[bool, Query(description="Enable replay mode SSE stream")] = False,
    speed: Annotated[float, Query(ge=0.1, le=1000, description="Replay speed multiplier")] = 10.0,
    limit: Annotated[Optional[int], Query(ge=1, description="Max number of points to return")] = None,
):
    records = data_loader.load_flux(limit=limit)

    if records is None:
        raise HTTPException(
            status_code=503,
            detail="Flux data not available yet — run preprocessing pipeline first (pipeline/preprocessing.py).",
        )

    # ── Replay mode: stream as SSE ────────────────────────────────────────────
    if replay:
        logger.info("Replay mode activated at %.1f×", speed)
        return StreamingResponse(
            stream_flux_replay(records, speed=speed),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ── Normal mode: return full dataset ─────────────────────────────────────
    points = [FluxPoint(**r) for r in records]
    time_start = points[0].timestamp if points else None
    time_end = points[-1].timestamp if points else None

    return FluxResponse(
        data=points,
        total_points=len(points),
        time_range_start=time_start,
        time_range_end=time_end,
        replay_mode=False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/events
# ═══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/api/events",
    response_model=EventsResponse,
    tags=["Detection"],
    summary="Detected solar flare events",
    description=(
        "Returns the list of flare events detected by the statistical "
        "rolling-baseline + k-sigma engine (Aditi's module)."
    ),
)
async def get_events(
    flare_class: Annotated[
        Optional[str],
        Query(description="Filter by flare class: A, B, C, M, or X"),
    ] = None,
    instrument: Annotated[
        Optional[str],
        Query(description="Filter by instrument: SoLEXS or HEL1OS"),
    ] = None,
):
    events = data_loader.load_events()

    if events is None:
        raise HTTPException(
            status_code=503,
            detail="Event data not available yet — run detection pipeline first (pipeline/detection.py).",
        )

    # Optional server-side filtering
    if flare_class:
        events = [e for e in events if e.get("flare_class", "").upper() == flare_class.upper()]
    if instrument:
        events = [e for e in events if e.get("instrument", "").upper() == instrument.upper()]

    validated = [FlareEvent(**e) for e in events]
    return EventsResponse(events=validated, total_events=len(validated))


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/predictions
# ═══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/api/predictions",
    response_model=PredictionsResponse,
    tags=["ML"],
    summary="XGBoost flare probability predictions",
    description=(
        "Returns ML model predictions including per-timestamp flare probability, "
        "predicted class, confidence, and SHAP-based top feature attributions "
        "(Vidushi's pipeline output)."
    ),
)
async def get_predictions(
    limit: Annotated[Optional[int], Query(ge=1, description="Limit number of predictions")] = None,
):
    preds = data_loader.load_predictions()

    if preds is None:
        raise HTTPException(
            status_code=503,
            detail="Prediction data not available yet — run ML pipeline first (pipeline/predict.py).",
        )

    if limit:
        preds = preds[:limit]

    model_version = data_loader.get_model_version()
    validated = [Prediction(**p) for p in preds]
    return PredictionsResponse(
        predictions=validated,
        total_predictions=len(validated),
        model_version=model_version,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/validation
# ═══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/api/validation",
    response_model=ValidationResponse,
    tags=["Validation"],
    summary="GOES catalog cross-check results",
    description=(
        "Cross-matches our detected events against the NOAA GOES flare catalog "
        "(local offline copy). Returns match status, GOES class, and time offset "
        "for each event. Unmatched events are not automatically treated as false "
        "positives — GOES coverage is incomplete, so misses are logged separately."
    ),
)
async def get_validation(
    match_window_minutes: Annotated[
        float,
        Query(ge=1.0, le=60.0, description="±window in minutes for GOES matching"),
    ] = 10.0,
):
    detected = data_loader.load_events()
    if detected is None:
        raise HTTPException(
            status_code=503,
            detail="Event data not available yet — run detection pipeline first (pipeline/detection.py).",
        )
    goes_catalog = data_loader.load_goes_catalog()

    raw_results = goes_validator.match_events_to_goes(
        detected, goes_catalog, match_window_minutes=match_window_minutes
    )
    summary = goes_validator.summarise_validation(raw_results)

    validated = [ValidationResult(**r) for r in raw_results]
    return ValidationResponse(results=validated, **summary)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/metrics
# ═══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/api/metrics",
    response_model=MetricsResponse,
    tags=["ML"],
    summary="Model evaluation metrics",
    description=(
        "Returns per-class precision/recall/F1, XGBoost training loss/accuracy "
        "curves, and feature importance rankings (Vidushi's evaluation output)."
    ),
)
async def get_metrics():
    metrics = data_loader.load_metrics()

    if not metrics:
        raise HTTPException(
            status_code=503,
            detail="No metrics available yet — run the training pipeline first.",
        )

    per_class_raw = metrics.get("per_class_metrics")
    if per_class_raw is None and isinstance(metrics.get("per_class"), dict):
        per_class_raw = []
        for cls, v in metrics["per_class"].items():
            if isinstance(v, dict):
                per_class_raw.append({
                    "flare_class": cls,
                    "precision": v.get("precision", 0.0),
                    "recall": v.get("recall", 0.0),
                    "f1": v.get("f1", v.get("f1_score", 0.0)),
                    "support": v.get("support", 0),
                })

    per_class = [ClassMetrics(**m) for m in (per_class_raw or [])]
    training_curve = [TrainingPoint(**t) for t in metrics.get("training_curve", [])]
    feature_importance = [FeatureImportance(**f) for f in metrics.get("feature_importance", [])]

    return MetricsResponse(
        per_class_metrics=per_class,
        training_curve=training_curve,
        feature_importance=feature_importance,
        overall_accuracy=metrics.get("overall_accuracy", metrics.get("accuracy", 0.0)),
        model_version=metrics.get("model_version"),
        trained_at=metrics.get("trained_at"),
    )
