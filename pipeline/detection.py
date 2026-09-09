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


def flag_triggers(df: pd.DataFrame, flux_col: str, k: float = 3.0) -> pd.DataFrame:
    """
    STEP 2: Flag each sample as a candidate flare trigger when
        F >= B + k*sigma

    Requires df to already have f"{flux_col}_baseline" and f"{flux_col}_sigma"
    columns (i.e. run compute_baseline_sigma() first).

    Adds one new column: f"{flux_col}_trigger" (bool) and
    f"{flux_col}_n_sigma" (how many sigma above baseline the sample is,
    useful later for classification).
    """
    baseline_col = f"{flux_col}_baseline"
    sigma_col = f"{flux_col}_sigma"
    for col in (baseline_col, sigma_col):
        if col not in df.columns:
            raise ValueError(f"df must have '{col}' — run compute_baseline_sigma() first")

    df = df.copy()

    # guard against sigma == 0 (e.g. first sample, or a perfectly flat window)
    # to avoid divide-by-zero / infinite n_sigma
    safe_sigma = df[sigma_col].replace(0, np.nan)

    df[f"{flux_col}_n_sigma"] = (df[flux_col] - df[baseline_col]) / safe_sigma
    df[f"{flux_col}_trigger"] = df[flux_col] >= (df[baseline_col] + k * df[sigma_col])

    # where sigma is 0/NaN we can't meaningfully trigger — treat as no trigger
    df[f"{flux_col}_trigger"] = df[f"{flux_col}_trigger"].fillna(False)

    return df


def group_events(df: pd.DataFrame, flux_col: str, instrument: str,
                  min_consecutive: int = 3, decay_k: float = 1.5) -> list:
    """
    STEP 3: Turn per-sample trigger flags into actual flare EVENTS.

    Two rules from the spec:
    - Noise rejection: only confirm an event once flux has been above the
      k-sigma trigger threshold for `min_consecutive` consecutive samples.
    - Decay tracking: once confirmed, the event stays "active" (keeps
      extending its end_time / tracking peak) until flux decays back
      below B + decay_k*sigma. decay_k (1.5) is looser than trigger k (3.0)
      on purpose — that's what lets an event's "tail" extend past the
      point it stopped being a fresh k-sigma trigger.

    Also respects quality_flag: any sample with quality_flag != 1 (bad/gap)
    can't start or extend an event. A bad sample inside an already-active
    event is just skipped (doesn't kill the event, doesn't count toward
    decay either) — avoids false event-splitting from one dropped sample.

    Returns a list of event dicts:
        {event_id, start_time, peak_time, end_time, peak_sigma,
         flare_class (None here — filled in Step 4), instrument}
    """
    trigger_col = f"{flux_col}_trigger"
    n_sigma_col = f"{flux_col}_n_sigma"
    baseline_col = f"{flux_col}_baseline"
    sigma_col = f"{flux_col}_sigma"
    for col in (trigger_col, n_sigma_col, baseline_col, sigma_col):
        if col not in df.columns:
            raise ValueError(f"df must have '{col}' — run compute_baseline_sigma() and flag_triggers() first")

    has_quality = "quality_flag" in df.columns

    # FIX (review from Mayank): quality_flag can arrive as a string
    # ("1", "1.0") instead of an int/float, depending on how it was
    # serialized upstream (e.g. parquet round-tripped through object dtype,
    # or read from CSV). A plain `== 1` comparison silently fails on
    # strings — "1" == 1 is False in Python — which would make every
    # sample look "bad" (or every sample look "good", depending on which
    # way the bug leans) with NO error raised. Coerce to numeric up front
    # so the comparison is type-safe regardless of how it arrived.
    # Anything that fails to coerce (NaN, garbage) is treated as bad data.
    quality_numeric = pd.to_numeric(df["quality_flag"], errors="coerce") if has_quality else None

    events = []
    event_id_counter = 0

    # a candidate run of consecutive triggers, not yet confirmed as an event
    candidate_start_idx = None
    candidate_len = 0

    # the currently CONFIRMED, active event (or None)
    active_event = None

    def is_good(i):
        if not has_quality:
            return True
        val = quality_numeric.iloc[i]
        return pd.notna(val) and val == 1

    for i in range(len(df)):
        row = df.iloc[i]
        good = is_good(i)
        triggered = bool(row[trigger_col]) and good

        if active_event is None:
            if triggered:
                if candidate_start_idx is None:
                    candidate_start_idx = i
                    candidate_len = 1
                else:
                    candidate_len += 1

                if candidate_len >= min_consecutive:
                    # CONFIRMED: promote the candidate run into an active event
                    event_id_counter += 1
                    start_idx = candidate_start_idx
                    window = df[n_sigma_col].iloc[start_idx:i + 1]
                    peak_offset = int(window.values.argmax())
                    active_event = {
                        "event_id": f"{instrument}_{event_id_counter:04d}",
                        "start_time": df["timestamp"].iloc[start_idx],
                        "peak_time": df["timestamp"].iloc[start_idx + peak_offset],
                        "end_time": df["timestamp"].iloc[i],
                        "peak_sigma": float(window.max()),
                        "instrument": instrument,
                    }
                    candidate_start_idx = None
                    candidate_len = 0
            else:
                # broken run of triggers — this IS the noise rejection
                candidate_start_idx = None
                candidate_len = 0
        else:
            if not good:
                continue  # bad sample: skip, don't extend or kill the event

            still_above_decay = row[flux_col] >= (row[baseline_col] + decay_k * row[sigma_col])

            if still_above_decay:
                active_event["end_time"] = row["timestamp"]
                if row[n_sigma_col] > active_event["peak_sigma"]:
                    active_event["peak_sigma"] = float(row[n_sigma_col])
                    active_event["peak_time"] = row["timestamp"]
            else:
                events.append(active_event)
                active_event = None
                candidate_start_idx = None
                candidate_len = 0

    if active_event is not None:
        # data ended while still active — close it out anyway
        events.append(active_event)

    return events


def classify_flare(peak_sigma: float) -> str:
    """
    STEP 4: Classify a flare event by its peak sigma above baseline.

        X-Class: peak >= 10.0
        M-Class: peak >= 7.0
        C-Class: peak >= 4.0
        B-Class: peak >= 2.0
        A-Class: peak < 2.0
    """
    if peak_sigma >= 10.0:
        return "X"
    elif peak_sigma >= 7.0:
        return "M"
    elif peak_sigma >= 4.0:
        return "C"
    elif peak_sigma >= 2.0:
        return "B"
    else:
        return "A"


def detect_flares(df: pd.DataFrame, window: int = 90, k: float = 3.0,
                   min_consecutive: int = 3, decay_k: float = 1.5) -> list:
    """
    MAIN ENTRY POINT. Runs the full pipeline (steps 1-4) for BOTH instruments
    independently (solexs_flux and hel1os_flux), since the ML teammate fuses
    them later and each needs its own detections.

    Returns a combined list of event dicts matching the shared schema:
        {event_id, start_time, peak_time, end_time, peak_sigma,
         flare_class, instrument}
    """
    all_events = []

    for flux_col, instrument in [("solexs_flux", "solexs"), ("hel1os_flux", "hel1os")]:
        if flux_col not in df.columns:
            continue  # that instrument's data isn't present in this df, skip it

        out = compute_baseline_sigma(df, flux_col, window_minutes=window)
        out = flag_triggers(out, flux_col, k=k)
        events = group_events(out, flux_col, instrument=instrument,
                               min_consecutive=min_consecutive, decay_k=decay_k)

        for e in events:
            e["flare_class"] = classify_flare(e["peak_sigma"])

        all_events.extend(events)

    return all_events


def events_to_json(events: list) -> str:
    """
    STEP 5 (part 1): Serialize the event list to JSON, matching the schema
    the backend (Mayank) and ML pipeline (Vidushi) expect.
    Timestamps are converted to ISO 8601 strings.
    """
    import json

    serializable = []
    for e in events:
        e2 = dict(e)
        for time_key in ("start_time", "peak_time", "end_time"):
            e2[time_key] = pd.Timestamp(e2[time_key]).isoformat()
        serializable.append(e2)

    return json.dumps(serializable, indent=2)


def run_pipeline(input_path: str = "data/processed/aligned_flux.parquet",
                  output_path: str = "data/processed/events.json",
                  window: int = 90, k: float = 3.0,
                  min_consecutive: int = 3, decay_k: float = 1.5) -> list:
    """
    STEP 5 (part 2): CLI entry point. Reads Prakriti's aligned parquet output,
    runs detect_flares(), and writes the result to output_path as JSON so the
    backend's /api/events can serve it directly.
    """
    import os

    df = pd.read_parquet(input_path)
    events = detect_flares(df, window=window, k=k,
                            min_consecutive=min_consecutive, decay_k=decay_k)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(events_to_json(events))

    print(f"Wrote {len(events)} event(s) to {output_path}")
    return events


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the statistical flare detection pipeline.")
    parser.add_argument("--input", default="data/processed/aligned_flux.parquet",
                         help="Path to Prakriti's aligned parquet file")
    parser.add_argument("--output", default="data/processed/events.json",
                         help="Path to write detected events JSON")
    parser.add_argument("--window", type=int, default=90, help="Rolling window in minutes")
    parser.add_argument("--k", type=float, default=3.0, help="Trigger threshold (k * sigma)")
    parser.add_argument("--min-consecutive", type=int, default=3,
                         help="Min consecutive samples above threshold to confirm an event")
    parser.add_argument("--decay-k", type=float, default=1.5, help="Decay threshold (decay_k * sigma)")
    parser.add_argument("--demo", action="store_true",
                         help="Run on synthetic demo data instead of reading a real file "
                              "(useful before Prakriti's parquet file exists)")
    args = parser.parse_args()

    if args.demo:
        rng = pd.date_range("2026-01-01", periods=300, freq="1min")
        np.random.seed(42)
        solexs = np.random.normal(loc=100, scale=2, size=300)
        solexs[150:160] += 40
        hel1os = np.random.normal(loc=50, scale=1, size=300)
        hel1os[200:205] += 15
        df = pd.DataFrame({"timestamp": rng, "solexs_flux": solexs, "hel1os_flux": hel1os})

        events = detect_flares(df, window=args.window, k=args.k,
                                min_consecutive=args.min_consecutive, decay_k=args.decay_k)
        print(f"Found {len(events)} event(s) total:\n")
        for e in events:
            print(e)
        print("\n--- JSON output ---")
        print(events_to_json(events))
    else:
        run_pipeline(input_path=args.input, output_path=args.output,
                     window=args.window, k=args.k,
                     min_consecutive=args.min_consecutive, decay_k=args.decay_k)
