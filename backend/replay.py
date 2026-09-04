"""
backend/replay.py
Replay-mode helpers for the exhibition demo.

The /api/flux?replay=true&speed=N endpoint calls `stream_flux_replay()` which
yields JSON-encoded rows at (original_cadence / N) seconds per row, simulating
a live data feed at N× speed.

Frontend polls this Server-Sent Events (SSE) stream and animates accordingly.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# Default replay speed multiplier if not provided by caller
DEFAULT_SPEED: float = 10.0

# Assumed original data cadence (seconds between samples).
# Real cadence from Prakriti's preprocessing should match this.
DEFAULT_CADENCE_SECONDS: float = 4.0


async def stream_flux_replay(
    flux_records: list[dict],
    speed: float = DEFAULT_SPEED,
    cadence_seconds: float = DEFAULT_CADENCE_SECONDS,
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields flux records as SSE-formatted strings,
    pausing between each record to simulate real-time data flow.

    Each yielded string is a valid SSE line:
        data: {json}\n\n

    Parameters
    ----------
    flux_records : list[dict]
        All flux data points (from data_loader.load_flux()).
    speed : float
        Replay speed multiplier (10 = 10× faster than real time).
    cadence_seconds : float
        Original time between samples in real data.

    Yields
    ------
    str
        SSE-formatted event string.
    """
    if not flux_records:
        yield "data: {}\n\n"
        return

    if speed <= 0:
        raise ValueError("speed must be > 0")

    delay = cadence_seconds / speed
    total = len(flux_records)
    logger.info("Starting replay: %d points at %.1f× speed (%.3fs delay)", total, speed, delay)

    for i, record in enumerate(flux_records):
        payload = json.dumps(record, default=str)
        yield f"data: {payload}\n\n"
        if i < total - 1:
            await asyncio.sleep(delay)

    # Signal end of stream
    yield "data: {\"__replay_done\": true}\n\n"
    logger.info("Replay stream complete")
