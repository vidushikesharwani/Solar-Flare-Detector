"""
Feature engineering for the Solar Flare Detector ML pipeline.

Input schema:
    timestamp, solexs_flux, hel1os_flux, quality_flag

Output:
    A single XGBoost-ready DataFrame indexed by timestamp.

Feature families:
    1. SoLEXS 90-minute rolling statistics
    2. Multi-scale SoLEXS rate-of-change features
    3. HEL1OS short-window impulsive/spike features

All engineered features are causal:
features at time t use only information available at or before t.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

ROLLING_WINDOW = "90min"

# SoLEXS is the primary flare-onset signal.
ROC_LAG_MINUTES = (1, 3, 5, 10, 15, 30, 60)
ROC_SLOPE_WINDOWS = ("5min", "15min", "30min")

# HEL1OS is used as a secondary/confirmation signal.
IMPULSE_SHORT_LAG_MINUTES = (1, 3, 5)

# Short baseline for detecting impulsive activity.
HEL1OS_BASELINE_WINDOW = "30min"

EPS = 1e-12


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _infer_cadence_minutes(index: pd.DatetimeIndex) -> float:
    """Infer the median sampling cadence in minutes."""

    if len(index) < 2:
        raise ValueError("Need at least 2 timestamps to infer cadence.")

    deltas = (
        index.to_series()
        .diff()
        .dropna()
        .dt.total_seconds()
        / 60.0
    )

    cadence = float(deltas.median())

    if cadence <= 0:
        raise ValueError(
            "Non-positive median cadence. Check timestamps."
        )

    return cadence


def _lag_to_periods(
    lag_minutes: float,
    cadence_minutes: float
) -> int:
    """Convert minutes into number of rows based on sampling cadence."""

    return max(1, round(lag_minutes / cadence_minutes))


def _rolling_slope(
    series: pd.Series,
    window: str
) -> pd.Series:
    """
    Calculate a causal rolling linear-regression slope.

    The window only contains the current and previous observations.
    """

    def slope(values: np.ndarray) -> float:

        if len(values) < 2:
            return np.nan

        if np.all(np.isnan(values)):
            return np.nan

        valid = ~np.isnan(values)

        if valid.sum() < 2:
            return np.nan

        y = values[valid]
        x = np.arange(len(values), dtype=float)[valid]

        if np.all(y == y[0]):
            return 0.0

        coefficient = np.polyfit(x, y, 1)

        return float(coefficient[0])

    return series.rolling(
        window,
        min_periods=2
    ).apply(slope, raw=True)


# --------------------------------------------------------------------------
# 1. SoLEXS rolling features
# --------------------------------------------------------------------------

def compute_rolling_features(
    df: pd.DataFrame,
    flux_col: str = "solexs_flux",
    window: str = ROLLING_WINDOW
) -> pd.DataFrame:
    """
    Compute 90-minute rolling mean, standard deviation and z-score
    for SoLEXS flux.
    """

    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError(
            "compute_rolling_features expects a DatetimeIndex."
        )

    rolling = df[flux_col].rolling(
        window,
        min_periods=3
    )

    mean = rolling.mean()
    std = rolling.std()

    output = pd.DataFrame(index=df.index)

    output[f"{flux_col}_roll_mean_90m"] = mean

    output[f"{flux_col}_roll_std_90m"] = std

    output[f"{flux_col}_roll_zscore_90m"] = (
        (df[flux_col] - mean)
        / (std + EPS)
    )

    return output


# --------------------------------------------------------------------------
# 2. SoLEXS rate-of-change features
# --------------------------------------------------------------------------

def compute_rate_of_change_features(
    df: pd.DataFrame,
    flux_col: str = "solexs_flux",
    lag_minutes: tuple[int, ...] = ROC_LAG_MINUTES,
    slope_windows: tuple[str, ...] = ROC_SLOPE_WINDOWS
) -> pd.DataFrame:
    """
    Compute multi-scale rate-of-change features for SoLEXS.

    Includes:
        - absolute difference
        - relative difference
        - log return
        - rate per minute
        - acceleration
        - rolling slopes

    These features are intentionally rich because SoLEXS
    gradients are expected to be the dominant flare signal.
    """

    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError(
            "compute_rate_of_change_features expects a DatetimeIndex."
        )

    cadence = _infer_cadence_minutes(df.index)

    flux = df[flux_col]

    output = pd.DataFrame(index=df.index)

    shortest_roc_column = None

    for lag_min in lag_minutes:

        periods = _lag_to_periods(
            lag_min,
            cadence
        )

        previous = flux.shift(periods)

        absolute_difference = flux - previous

        relative_difference = (
            absolute_difference
            / (previous.abs() + EPS)
        )

        log_return = (
            np.log(flux + EPS)
            - np.log(previous + EPS)
        )

        rate_per_minute = (
            absolute_difference
            / lag_min
        )

        tag = f"{lag_min}min"

        output[
            f"{flux_col}_roc_abs_{tag}"
        ] = absolute_difference

        output[
            f"{flux_col}_roc_rel_{tag}"
        ] = relative_difference

        output[
            f"{flux_col}_roc_logret_{tag}"
        ] = log_return

        output[
            f"{flux_col}_roc_permin_{tag}"
        ] = rate_per_minute

        if shortest_roc_column is None:
            shortest_roc_column = (
                f"{flux_col}_roc_abs_{tag}"
            )

    # Acceleration = change in shortest-term ROC
    output[
        f"{flux_col}_acceleration"
    ] = output[shortest_roc_column].diff()

    # Causal rolling slopes
    for window in slope_windows:

        output[
            f"{flux_col}_slope_{window}"
        ] = _rolling_slope(
            flux,
            window
        )

    # Running maximum of the absolute long-term ROC.
    longest_lag = max(lag_minutes)

    longest_column = (
        f"{flux_col}_roc_permin_{longest_lag}min"
    )

    output[
        f"{longest_column}_rollmax_90m"
    ] = (
        output[longest_column]
        .abs()
        .rolling(
            ROLLING_WINDOW,
            min_periods=1
        )
        .max()
    )

    return output


# --------------------------------------------------------------------------
# 3. HEL1OS impulsive-spike features
# --------------------------------------------------------------------------

def compute_impulsive_spike_features(
    df: pd.DataFrame,
    flux_col: str = "hel1os_flux",
    short_lag_minutes: tuple[int, ...] = (
        IMPULSE_SHORT_LAG_MINUTES
    )
) -> pd.DataFrame:
    """
    Compute causal impulsive-spike features for HEL1OS.

    Features include:
        - short-term absolute ROC
        - short-term ROC per minute
        - short-term percentage change
        - deviation from rolling baseline
        - spike score
        - causal peak indicator
        - recent peak count

    No future observations are used.
    """

    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError(
            "compute_impulsive_spike_features expects a DatetimeIndex."
        )

    cadence = _infer_cadence_minutes(df.index)

    flux = df[flux_col]

    output = pd.DataFrame(index=df.index)

    # --------------------------------------------------------------
    # Short-window rate of change
    # --------------------------------------------------------------

    for lag_min in short_lag_minutes:

        periods = _lag_to_periods(
            lag_min,
            cadence
        )

        previous = flux.shift(periods)

        absolute_difference = flux - previous

        percentage_change = (
            absolute_difference
            / (previous.abs() + EPS)
            * 100
        )

        tag = f"{lag_min}min"

        output[
            f"{flux_col}_impulse_roc_abs_{tag}"
        ] = absolute_difference

        output[
            f"{flux_col}_impulse_roc_permin_{tag}"
        ] = (
            absolute_difference
            / lag_min
        )

        output[
            f"{flux_col}_impulse_pct_change_{tag}"
        ] = percentage_change

    # --------------------------------------------------------------
    # Causal baseline
    # --------------------------------------------------------------

    baseline = flux.rolling(
        HEL1OS_BASELINE_WINDOW,
        min_periods=3
    )

    baseline_mean = baseline.mean()
    baseline_std = baseline.std()

    output[
        f"{flux_col}_baseline_mean_30m"
    ] = baseline_mean

    output[
        f"{flux_col}_baseline_std_30m"
    ] = baseline_std

    # Difference from recent baseline
    output[
        f"{flux_col}_deviation_from_baseline"
    ] = (
        flux - baseline_mean
    )

    # Spike score / normalized deviation
    output[
        f"{flux_col}_spike_score"
    ] = (
        (flux - baseline_mean)
        / (baseline_std + EPS)
    )

    # --------------------------------------------------------------
    # Causal peak detection
    # --------------------------------------------------------------
    #
    # IMPORTANT:
    # We do NOT use scipy.find_peaks() or center=True.
    #
    # A real-time system cannot know whether the current point
    # is a peak until future values arrive.
    #
    # Instead, we define an "impulsive spike" as:
    #
    # current value > previous rolling maximum
    #
    # This uses only historical/current information.
    # --------------------------------------------------------------

    previous_max = flux.shift(1).rolling(
        "15min",
        min_periods=2
    ).max()

    is_impulsive_peak = (
        flux > previous_max
    )

    # Require the spike to be meaningfully above baseline.
    spike_score = output[
        f"{flux_col}_spike_score"
    ]

    output["is_local_peak"] = (
        is_impulsive_peak
        & (spike_score > 1.5)
    ).astype(np.int8)

    # --------------------------------------------------------------
    # Peak strength
    # --------------------------------------------------------------

    output["peak_prominence"] = (
        flux - previous_max
    ).where(
        output["is_local_peak"] == 1,
        0.0
    )

    # --------------------------------------------------------------
    # Time since previous detected peak
    # --------------------------------------------------------------

    peak_times = df.index.to_series().where(
        output["is_local_peak"] == 1
    )

    last_peak_time = peak_times.ffill()

    output["time_since_last_peak_min"] = (
        (
            df.index.to_series()
            - last_peak_time
        )
        .dt.total_seconds()
        / 60.0
    )

    # --------------------------------------------------------------
    # Number of recent impulsive peaks
    # --------------------------------------------------------------

    peak_series = pd.Series(
        output["is_local_peak"].values,
        index=df.index
    )

    output["peak_count_60min"] = (
        peak_series
        .rolling(
            "60min",
            min_periods=1
        )
        .sum()
    )

    return output


# --------------------------------------------------------------------------
# Data preparation
# --------------------------------------------------------------------------

def _prepare_index(
    df: pd.DataFrame,
    timestamp_col: str = "timestamp"
) -> pd.DataFrame:
    """Prepare timestamp index and sort the data."""

    output = df.copy()

    if timestamp_col in output.columns:

        output[timestamp_col] = pd.to_datetime(
            output[timestamp_col],
            utc=True
        )

        output = output.set_index(
            timestamp_col
        )

    elif not isinstance(
        output.index,
        pd.DatetimeIndex
    ):

        raise ValueError(
            f"Expected '{timestamp_col}' column "
            "or a DatetimeIndex."
        )

    output = output.sort_index()

    # Remove duplicate timestamps.
    if output.index.duplicated().any():

        duplicate_count = int(
            output.index.duplicated().sum()
        )

        output = output[
            ~output.index.duplicated(
                keep="first"
            )
        ]

        print(
            f"[features] Warning: removed "
            f"{duplicate_count} duplicate timestamps."
        )

    return output


# --------------------------------------------------------------------------
# Main feature-building function
# --------------------------------------------------------------------------

def build_feature_dataframe(
    sensor_df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    solexs_col: str = "solexs_flux",
    hel1os_col: str = "hel1os_flux",
    quality_col: str = "quality_flag"
) -> pd.DataFrame:
    """
    Build the complete XGBoost-ready feature DataFrame.

    Input:
        timestamp
        solexs_flux
        hel1os_flux
        quality_flag

    Output:
        DataFrame indexed by timestamp.
    """

    required = {
        timestamp_col,
        solexs_col,
        hel1os_col,
        quality_col
    }

    missing = required - set(sensor_df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    # --------------------------------------------------------------
    # Prepare data
    # --------------------------------------------------------------

    df = _prepare_index(
        sensor_df,
        timestamp_col
    )

    # Convert sensor columns to numeric.
    df[solexs_col] = pd.to_numeric(
        df[solexs_col],
        errors="coerce"
    )

    df[hel1os_col] = pd.to_numeric(
        df[hel1os_col],
        errors="coerce"
    )

    df[quality_col] = pd.to_numeric(
        df[quality_col],
        errors="coerce"
    )

    # --------------------------------------------------------------
    # Quality masking
    # --------------------------------------------------------------

    # quality_flag == 1 → good
    # quality_flag == 0 → flagged/bad
    good_quality = (
        df[quality_col] == 1
    )

    # Bad observations become NaN for feature calculations.
    # The original quality flag is still preserved in output.
    solexs_clean = df[solexs_col].where(
        good_quality
    )

    hel1os_clean = df[hel1os_col].where(
        good_quality
    )

    clean_df = pd.DataFrame(
        {
            solexs_col: solexs_clean,
            hel1os_col: hel1os_clean
        },
        index=df.index
    )

    # --------------------------------------------------------------
    # Calculate feature families
    # --------------------------------------------------------------

    rolling_features = compute_rolling_features(
        clean_df,
        flux_col=solexs_col
    )

    roc_features = compute_rate_of_change_features(
        clean_df,
        flux_col=solexs_col
    )

    impulse_features = compute_impulsive_spike_features(
        clean_df,
        flux_col=hel1os_col
    )

    # --------------------------------------------------------------
    # Assemble final DataFrame
    # --------------------------------------------------------------

    features = pd.DataFrame(
        index=df.index
    )

    # Raw sensor values
    features[solexs_col] = df[solexs_col]
    features[hel1os_col] = df[hel1os_col]

    # Quality information
    features[quality_col] = df[quality_col]

    features["flux_is_flagged"] = (
        df[quality_col] == 0
    ).astype(np.int8)

    # Engineered features
    features = pd.concat(
        [
            features,
            rolling_features,
            roc_features,
            impulse_features
        ],
        axis=1
    )

    # --------------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------------

    # Replace infinite values.
    features = features.replace(
        [np.inf, -np.inf],
        np.nan
    )

    # Check duplicate columns.
    assert not features.columns.duplicated().any(), (
        "Duplicate feature columns produced."
    )

    return features


# --------------------------------------------------------------------------
# Manual smoke test
# --------------------------------------------------------------------------

if __name__ == "__main__":

    sensor_path = (
        "data/mock/synthetic_sensor_data.csv"
    )

    sensor = pd.read_csv(
        sensor_path
    )

    features = build_feature_dataframe(
        sensor
    )

    print("\n" + "=" * 60)
    print("SOLAR FLARE FEATURE ENGINEERING TEST")
    print("=" * 60)

    print("\nFeature DataFrame shape:")
    print(features.shape)

    print("\nFeature columns:")
    for column in features.columns:
        print(f"  - {column}")

    print("\nFirst 5 rows:")
    print(features.head())

    print("\nData types:")
    print(features.dtypes)

    print("\nMissing values:")
    print(features.isna().sum())

    print("\nIndex:")
    print(features.index)

    print("\n" + "=" * 60)
    print("FEATURE ENGINEERING TEST COMPLETE")
    print("=" * 60)