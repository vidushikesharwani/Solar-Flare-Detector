"""
Solar Flare Detector — Statistical Detection Engine
Owner: Aditi

STEP 1: rolling baseline (median) + rolling sigma (std) computation.
"""

import pandas as pd
import numpy as np


def compute_baseline_sigma(df: pd.DataFrame, flux_col: str, window_minutes: int = 90) -> pd.DataFrame:
    """
    Compute rolling median baseline (B) and rolling std (sigma) for a flux column.

    Assumes df has a 'timestamp' column (datetime64) and is sorted ascending by time.
    Uses a TIME-based rolling window (not sample-count based) so it stays correct
    even when the cadence is irregular or there are data gaps.

    Returns a copy of df with two new columns added:
        f"{flux_col}_baseline"  -> rolling median
        f"{flux_col}_sigma"     -> rolling std
    """
    if "timestamp" not in df.columns:
        raise ValueError("df must have a 'timestamp' column")
    if flux_col not in df.columns:
        raise ValueError(f"df must have a '{flux_col}' column")

    df = df.copy()

    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    # rolling() with a time offset REQUIRES the time column to be the index
    df = df.sort_values("timestamp").set_index("timestamp")

    window_str = f"{window_minutes}min"
    roll = df[flux_col].rolling(window_str, min_periods=1)

    df[f"{flux_col}_baseline"] = roll.median()
    df[f"{flux_col}_sigma"] = roll.std()

    df = df.reset_index()
    return df


if __name__ == "__main__":
    # --- quick sanity test with synthetic data (not the real unit tests yet) ---
    rng = pd.date_range("2026-01-01", periods=300, freq="1min")
    np.random.seed(42)
    flux = np.random.normal(loc=100, scale=2, size=300)  # flat baseline + noise
    flux[150:155] += 40  # injected spike

    df = pd.DataFrame({"timestamp": rng, "solexs_flux": flux})
    out = compute_baseline_sigma(df, "solexs_flux", window_minutes=90)

    print(out[["timestamp", "solexs_flux", "solexs_flux_baseline", "solexs_flux_sigma"]].iloc[145:158])
