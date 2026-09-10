"""
Unit tests for pipeline/detection.py
Owner: Aditi

Run from repo root with: pytest tests/test_detection.py -v
(or just `pytest` from the repo root, which auto-discovers this file)
"""

import numpy as np
import pandas as pd
import pytest

from pipeline.detection import (
    compute_baseline_sigma,
    flag_triggers,
    group_events,
    classify_flare,
    detect_flares,
)


# ---------- helpers ----------

def make_flat_noise_df(n=300, mean=100.0, std=2.0, seed=42, freq="1min"):
    """Flat baseline + gaussian noise, no injected flare."""
    rng = np.random.default_rng(seed)
    flux = rng.normal(loc=mean, scale=std, size=n)
    timestamps = pd.date_range("2026-01-01", periods=n, freq=freq)
    return pd.DataFrame({"timestamp": timestamps, "solexs_flux": flux})


def inject_spike(df, flux_col, start_idx, length, amplitude):
    df = df.copy()
    df.loc[start_idx:start_idx + length - 1, flux_col] += amplitude
    return df


# ---------- Step 1+2: baseline/sigma/trigger sanity ----------

def test_baseline_tracks_flat_signal():
    """On a flat noisy signal, baseline should sit close to the true mean."""
    df = make_flat_noise_df(mean=100.0, std=2.0)
    out = compute_baseline_sigma(df, "solexs_flux", window_minutes=90)
    assert abs(out["solexs_flux_baseline"].iloc[-1] - 100.0) < 2.0


# ---------- Step 3+4: the actual required test cases ----------

def test_injected_spike_is_detected():
    """A clear injected spike on a flat baseline must produce exactly one event."""
    df = make_flat_noise_df(mean=100.0, std=2.0)
    df = inject_spike(df, "solexs_flux", start_idx=150, length=10, amplitude=40)  # ~15-20 sigma

    events = detect_flares(df, window=90, k=3.0, min_consecutive=3, decay_k=1.5)
    solexs_events = [e for e in events if e["instrument"] == "solexs"]

    assert len(solexs_events) == 1
    assert solexs_events[0]["peak_sigma"] >= 3.0
    assert solexs_events[0]["flare_class"] in ("B", "C", "M", "X")


def test_pure_noise_triggers_no_false_positive():
    """Pure gaussian noise with no injected flare should produce zero events
    across many random seeds (statistically, k=3 sigma should almost never
    sustain min_consecutive=3 samples in a row on pure noise)."""
    false_positive_count = 0
    n_trials = 20

    for seed in range(n_trials):
        df = make_flat_noise_df(mean=100.0, std=2.0, seed=seed)
        events = detect_flares(df, window=90, k=3.0, min_consecutive=3, decay_k=1.5)
        if len(events) > 0:
            false_positive_count += 1

    assert false_positive_count <= 1, (
        f"{false_positive_count}/{n_trials} pure-noise trials produced a false event"
    )


def test_boundary_exactly_at_k_sigma():
    """A sample sitting exactly at B + k*sigma must count as a trigger
    (the spec says '>=', not '>')."""
    df = make_flat_noise_df(mean=100.0, std=2.0)
    out = compute_baseline_sigma(df, "solexs_flux", window_minutes=90)

    idx = 200
    baseline = out["solexs_flux_baseline"].iloc[idx]
    sigma = out["solexs_flux_sigma"].iloc[idx]
    out.loc[idx, "solexs_flux"] = baseline + 3.0 * sigma  # exactly 3.0 sigma

    out = flag_triggers(out, "solexs_flux", k=3.0)
    assert out["solexs_flux_trigger"].iloc[idx] == True  # noqa: E712


def test_just_below_k_sigma_does_not_trigger():
    """A sample just under B + k*sigma should NOT trigger."""
    df = make_flat_noise_df(mean=100.0, std=2.0)
    out = compute_baseline_sigma(df, "solexs_flux", window_minutes=90)

    idx = 200
    baseline = out["solexs_flux_baseline"].iloc[idx]
    sigma = out["solexs_flux_sigma"].iloc[idx]
    out.loc[idx, "solexs_flux"] = baseline + 2.999 * sigma

    out = flag_triggers(out, "solexs_flux", k=3.0)
    assert out["solexs_flux_trigger"].iloc[idx] == False  # noqa: E712


def test_short_spike_rejected_as_noise():
    """A spike shorter than min_consecutive samples must NOT become an event."""
    df = make_flat_noise_df(mean=100.0, std=2.0)
    df = inject_spike(df, "solexs_flux", start_idx=150, length=2, amplitude=40)

    events = detect_flares(df, window=90, k=3.0, min_consecutive=3, decay_k=1.5)
    solexs_events = [e for e in events if e["instrument"] == "solexs"]
    assert len(solexs_events) == 0


# ---------- Classification thresholds ----------

@pytest.mark.parametrize("peak_sigma,expected_class", [
    (15.0, "X"),
    (10.0, "X"),
    (9.99, "M"),
    (7.0, "M"),
    (6.99, "C"),
    (4.0, "C"),
    (3.99, "B"),
    (2.0, "B"),
    (1.99, "A"),
    (0.5, "A"),
])
def test_classify_flare_boundaries(peak_sigma, expected_class):
    assert classify_flare(peak_sigma) == expected_class


# ---------- quality_flag handling ----------

def test_bad_quality_samples_do_not_trigger_events():
    """A spike that occurs entirely in quality_flag=0 (bad) samples must
    not produce an event."""
    df = make_flat_noise_df(mean=100.0, std=2.0)
    df["quality_flag"] = 1
    df = inject_spike(df, "solexs_flux", start_idx=150, length=10, amplitude=40)
    df.loc[150:159, "quality_flag"] = 0

    events = detect_flares(df, window=90, k=3.0, min_consecutive=3, decay_k=1.5)
    solexs_events = [e for e in events if e["instrument"] == "solexs"]
    assert len(solexs_events) == 0


def test_string_quality_flag_does_not_break_detection():
    """Regression test for review comment: quality_flag arriving as the
    real mission pipeline's categorical string ('good') must not silently
    break the check and drop every event."""
    df = make_flat_noise_df(mean=100.0, std=2.0)
    df = inject_spike(df, "solexs_flux", start_idx=150, length=10, amplitude=40)
    df["quality_flag"] = "good"  # real pipeline's actual value, not "1"

    events = detect_flares(df, window=90, k=3.0, min_consecutive=3, decay_k=1.5)
    solexs_events = [e for e in events if e["instrument"] == "solexs"]
    assert len(solexs_events) == 1  # must still detect the spike, not silently drop it


def test_bad_categorical_quality_flags_reject_samples():
    """'gap' and 'saturated' (Prakriti's other real quality_flag values)
    must be treated as bad, same as the old numeric 0 convention."""
    df = make_flat_noise_df(mean=100.0, std=2.0)
    df = inject_spike(df, "solexs_flux", start_idx=150, length=10, amplitude=40)
    df["quality_flag"] = "good"
    df.loc[150:159, "quality_flag"] = "saturated"  # mark the spike itself as bad

    events = detect_flares(df, window=90, k=3.0, min_consecutive=3, decay_k=1.5)
    solexs_events = [e for e in events if e["instrument"] == "solexs"]
    assert len(solexs_events) == 0


def test_event_includes_baseline_peak_flux_and_duration():
    """New fields requested for ML/GOES cross-calibration: baseline_flux
    at onset, peak_flux (raw units), and duration_minutes must be present
    and sane."""
    df = make_flat_noise_df(mean=100.0, std=2.0)
    df = inject_spike(df, "solexs_flux", start_idx=150, length=10, amplitude=40)

    events = detect_flares(df, window=90, k=3.0, min_consecutive=3, decay_k=1.5)
    solexs_events = [e for e in events if e["instrument"] == "solexs"]
    assert len(solexs_events) == 1

    e = solexs_events[0]
    assert "baseline_flux" in e
    assert "peak_flux" in e
    assert "duration_minutes" in e
    # baseline should be close to the true flat background (~100), not the spike
    assert 95 < e["baseline_flux"] < 105
    # peak flux should reflect the injected spike (~140), well above baseline
    assert e["peak_flux"] > e["baseline_flux"] + 20
    # duration should be positive and roughly match the ~10-15 min spike+decay window
    assert 0 < e["duration_minutes"] < 60


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
