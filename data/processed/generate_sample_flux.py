"""
Script to generate sample_flux.parquet for testing.
Run once: python data/processed/generate_sample_flux.py
"""
import numpy as np
import pandas as pd
from pathlib import Path

def generate_flux(n: int = 1440, seed: int = 42) -> pd.DataFrame:
    """
    Generate 1440 samples (~24 hours at 1-minute cadence).
    Injects two synthetic flare spikes to simulate real data.
    """
    rng = np.random.default_rng(seed)
    timestamps = pd.date_range("2024-03-15T00:00:00Z", periods=n, freq="1min")

    # Quiet-sun background
    solexs_bg = 1e-7
    hel1os_bg = 500.0
    solexs_flux = solexs_bg + rng.normal(0, solexs_bg * 0.05, n)
    hel1os_flux = hel1os_bg + rng.normal(0, hel1os_bg * 0.05, n)

    # Inject X-class flare at index 370 (~06:10)
    for i, t in enumerate(timestamps):
        offset_370 = (i - 370)
        if abs(offset_370) < 25:
            spike = 5e-5 * np.exp(-0.5 * (offset_370 / 8) ** 2)
            solexs_flux[i] += spike
            hel1os_flux[i] += spike * 80000

    # Inject M-class flare at index 618 (~10:18)
    for i, t in enumerate(timestamps):
        offset_618 = (i - 618)
        if abs(offset_618) < 15:
            spike = 8e-6 * np.exp(-0.5 * (offset_618 / 5) ** 2)
            solexs_flux[i] += spike
            hel1os_flux[i] += spike * 60000

    quality_flag = np.zeros(n, dtype=int)
    # Simulate a 10-minute data gap at index 900–910
    quality_flag[900:910] = 1
    solexs_flux[900:910] = np.nan
    hel1os_flux[900:910] = np.nan

    df = pd.DataFrame({
        "timestamp": timestamps,
        "solexs_flux": solexs_flux,
        "hel1os_flux": hel1os_flux,
        "quality_flag": quality_flag,
    })
    return df


if __name__ == "__main__":
    out = Path(__file__).parent / "sample_flux.parquet"
    df = generate_flux()
    df.to_parquet(out, index=False)
    print(f"Saved {len(df)} rows to {out}")
