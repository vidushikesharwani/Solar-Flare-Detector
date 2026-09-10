"""
Feature engineering for the Solar Flare Detector ML pipeline.

Input contract:
    timestamp
    solexs_flux
    hel1os_flux
    quality_flag

Compatible with Prakriti's preprocessing output:
    quality_flag = "good", "gap", or "saturated"

Feature groups:
    1. SoLEXS rolling statistics
    2. SoLEXS rate-of-change features
    3. SoLEXS rolling slope / acceleration features
    4. HEL1OS impulsive/spike features
    5. Quality indicators

Important:
    All features are causal. No future observations are used.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ROLLING_WINDOW = "90min"

ROC_LAG_MINUTES = (
    1,
    3,
    5,
    10,
    15,
    30,
    60,
)

ROC_SLOPE_WINDOWS = (
    "5min",
    "15min",
    "30min",
)

IMPULSE_SHORT_LAG_MINUTES = (
    1,
    3,
    5,
)

HEL1OS_BASELINE_WINDOW = "30min"

EPS = 1e-12


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _prepare_index(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse timestamp as UTC, set it as the index, sort chronologically,
    and remove duplicate timestamps.
    """

    df = df.copy()

    if "timestamp" not in df.columns:
        raise ValueError("Input dataframe must contain 'timestamp'.")

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
        errors="coerce",
    )

    df = df.dropna(subset=["timestamp"])

    df = df.set_index("timestamp")

    df = df.sort_index()

    df = df[~df.index.duplicated(keep="first")]

    return df


def _infer_cadence_minutes(index: pd.DatetimeIndex) -> float:
    """
    Infer sampling cadence from the median timestamp difference.
    """

    if len(index) < 2:
        return 1.0

    deltas = index.to_series().diff().dropna()

    median_seconds = deltas.dt.total_seconds().median()

    if not np.isfinite(median_seconds) or median_seconds <= 0:
        return 1.0

    return median_seconds / 60.0


def _lag_to_periods(
    lag_minutes: int,
    cadence_minutes: float,
) -> int:
    """
    Convert a time lag in minutes to an integer number of samples.
    """

    periods = int(round(lag_minutes / cadence_minutes))

    return max(1, periods)


def _window_to_periods(
    window: str,
    cadence_minutes: float,
) -> int:
    """
    Convert a window such as '5min' into number of samples.

    At least two samples are required for slope calculation.
    """

    window_minutes = pd.Timedelta(window).total_seconds() / 60.0

    periods = int(round(window_minutes / cadence_minutes))

    return max(2, periods)


def _rolling_slope(
    series: pd.Series,
    window: str,
) -> pd.Series:
    """
    Causal rolling linear-regression slope.

    Only the current observation and previous observations are used.

    This avoids:
        - centered windows
        - future leakage
        - scipy peak functions that inspect future data
    """

    cadence_minutes = _infer_cadence_minutes(series.index)

    periods = _window_to_periods(
        window,
        cadence_minutes,
    )

    def slope(values: np.ndarray) -> float:

        values = np.asarray(values, dtype=float)

        valid = np.isfinite(values)

        if valid.sum() < 2:
            return np.nan

        y = values[valid]

        x = np.arange(len(values), dtype=float)[valid]

        x_mean = x.mean()
        y_mean = y.mean()

        denominator = np.sum(
            (x - x_mean) ** 2
        )

        if denominator <= 0:
            return 0.0

        return np.sum(
            (x - x_mean) * (y - y_mean)
        ) / denominator

    return (
        series
        .rolling(
            window=periods,
            min_periods=2,
        )
        .apply(
            slope,
            raw=True,
        )
    )


# ---------------------------------------------------------------------------
# SoLEXS rolling features
# ---------------------------------------------------------------------------

def compute_rolling_features(
    df: pd.DataFrame,
    flux_col: str = "solexs_flux",
    window: str = ROLLING_WINDOW,
) -> pd.DataFrame:
    """
    Compute causal rolling statistics for SoLEXS.

    Features:
        - rolling mean
        - rolling standard deviation
        - rolling z-score
    """

    series = pd.to_numeric(
        df[flux_col],
        errors="coerce",
    )

    rolling_mean = series.rolling(
        window=window,
        min_periods=2,
    ).mean()

    rolling_std = series.rolling(
        window=window,
        min_periods=2,
    ).std()

    zscore = (
        series - rolling_mean
    ) / (
        rolling_std + EPS
    )

    return pd.DataFrame(
        {
            "solexs_flux_roll_mean_90m": rolling_mean,
            "solexs_flux_roll_std_90m": rolling_std,
            "solexs_flux_roll_zscore_90m": zscore,
        },
        index=df.index,
    )


# ---------------------------------------------------------------------------
# SoLEXS rate-of-change features
# ---------------------------------------------------------------------------

def compute_rate_of_change_features(
    df: pd.DataFrame,
    flux_col: str = "solexs_flux",
) -> pd.DataFrame:
    """
    Compute causal rate-of-change features for SoLEXS.

    SoLEXS is the dominant signal, so this feature family is deliberately
    richer than the HEL1OS feature family.
    """

    series = pd.to_numeric(
        df[flux_col],
        errors="coerce",
    )

    cadence_minutes = _infer_cadence_minutes(
        series.index
    )

    features = {}

    for lag_minutes in ROC_LAG_MINUTES:

        periods = _lag_to_periods(
            lag_minutes,
            cadence_minutes,
        )

        previous = series.shift(periods)

        absolute_change = (
            series - previous
        )

        relative_change = (
            absolute_change
            / (previous.abs() + EPS)
        )

        log_return = np.log(
            (series.clip(lower=0) + EPS)
            / (previous.clip(lower=0) + EPS)
        )

        rate_per_minute = (
            absolute_change
            / max(lag_minutes, EPS)
        )

        features[
            f"solexs_flux_roc_abs_{lag_minutes}min"
        ] = absolute_change

        features[
            f"solexs_flux_roc_rel_{lag_minutes}min"
        ] = relative_change

        features[
            f"solexs_flux_roc_logret_{lag_minutes}min"
        ] = log_return

        features[
            f"solexs_flux_roc_permin_{lag_minutes}min"
        ] = rate_per_minute

    result = pd.DataFrame(
        features,
        index=df.index,
    )

    # Acceleration:
    # difference between short-term and slightly longer-term rate.
    short_periods = _lag_to_periods(
        5,
        cadence_minutes,
    )

    long_periods = _lag_to_periods(
        15,
        cadence_minutes,
    )

    short_rate = (
        series - series.shift(short_periods)
    ) / 5.0

    long_rate = (
        series - series.shift(long_periods)
    ) / 15.0

    result["solexs_flux_acceleration"] = (
        short_rate - long_rate
    )

    # Causal rolling slopes.
    for window in ROC_SLOPE_WINDOWS:

        result[
            f"solexs_flux_slope_{window}"
        ] = _rolling_slope(
            series,
            window,
        )

    # Maximum absolute long-term rate over the recent 90 minutes.
    long_rate_column = (
        "solexs_flux_roc_permin_60min"
    )

    result[
        "solexs_flux_roc_permin_60min_rollmax_90m"
    ] = (
        result[long_rate_column]
        .abs()
        .rolling(
            window=ROLLING_WINDOW,
            min_periods=2,
        )
        .max()
    )

    return result


# ---------------------------------------------------------------------------
# HEL1OS impulsive / spike features
# ---------------------------------------------------------------------------

def compute_impulsive_spike_features(
    df: pd.DataFrame,
    flux_col: str = "hel1os_flux",
) -> pd.DataFrame:
    """
    Compute causal impulsive/spike features from HEL1OS.

    No centered windows or future-looking peak detection are used.
    """

    series = pd.to_numeric(
        df[flux_col],
        errors="coerce",
    )

    cadence_minutes = _infer_cadence_minutes(
        series.index
    )

    features = {}

    # -----------------------------------------------------------------------
    # Short-term impulsive changes
    # -----------------------------------------------------------------------

    for lag_minutes in IMPULSE_SHORT_LAG_MINUTES:

        periods = _lag_to_periods(
            lag_minutes,
            cadence_minutes,
        )

        previous = series.shift(periods)

        absolute_change = (
            series - previous
        )

        percentage_change = (
            absolute_change
            / (previous.abs() + EPS)
        )

        rate_per_minute = (
            absolute_change
            / max(lag_minutes, EPS)
        )

        features[
            f"hel1os_flux_impulse_roc_abs_{lag_minutes}min"
        ] = absolute_change

        features[
            f"hel1os_flux_impulse_pct_change_{lag_minutes}min"
        ] = percentage_change

        features[
            f"hel1os_flux_impulse_roc_permin_{lag_minutes}min"
        ] = rate_per_minute

    result = pd.DataFrame(
        features,
        index=df.index,
    )

    # -----------------------------------------------------------------------
    # Causal baseline
    # -----------------------------------------------------------------------

    baseline_mean = series.rolling(
        window=HEL1OS_BASELINE_WINDOW,
        min_periods=2,
    ).mean()

    baseline_std = series.rolling(
        window=HEL1OS_BASELINE_WINDOW,
        min_periods=2,
    ).std()

    deviation = (
        series - baseline_mean
    )

    spike_score = (
        deviation
        / (baseline_std + EPS)
    )

    result[
        "hel1os_flux_baseline_mean_30m"
    ] = baseline_mean

    result[
        "hel1os_flux_baseline_std_30m"
    ] = baseline_std

    result[
        "hel1os_flux_deviation_from_baseline"
    ] = deviation

    result[
        "hel1os_flux_spike_score"
    ] = spike_score

    # -----------------------------------------------------------------------
    # Causal peak detection
    # -----------------------------------------------------------------------

    previous_max = (
        series
        .shift(1)
        .rolling(
            window="15min",
            min_periods=1,
        )
        .max()
    )

    is_peak = (
        series > previous_max
    ) & (
        spike_score > 1.5
    )

    result[
        "hel1os_flux_peak_prominence"
    ] = (
        series - previous_max
    ).where(is_peak)

    # Time since previous detected peak.
    peak_times = pd.Series(
        np.nan,
        index=df.index,
        dtype=float,
    )

    last_peak_time = None

    for timestamp, peak in is_peak.items():

        if bool(peak):

            last_peak_time = timestamp

            peak_times.loc[
                timestamp
            ] = 0.0

        elif last_peak_time is not None:

            peak_times.loc[
                timestamp
            ] = (
                timestamp - last_peak_time
            ).total_seconds() / 60.0

    result[
        "time_since_last_peak_min"
    ] = peak_times

    # Number of detected peaks in previous 60 minutes.
    peak_numeric = is_peak.astype(float)

    result[
        "hel1os_flux_peak_count_60min"
    ] = peak_numeric.rolling(
        window="60min",
        min_periods=1,
    ).sum()

    return result


# ---------------------------------------------------------------------------
# Main feature builder
# ---------------------------------------------------------------------------

def build_feature_dataframe(
    sensor_df: pd.DataFrame,
    timestamp_col: str = "timestamp",
    solexs_col: str = "solexs_flux",
    hel1os_col: str = "hel1os_flux",
    quality_col: str = "quality_flag",
) -> pd.DataFrame:
    """
    Build the complete ML feature dataframe.

    Input:
        timestamp
        solexs_flux
        hel1os_flux
        quality_flag

    Returns:
        A dataframe indexed by UTC timestamp containing raw sensor values,
        quality information, and engineered numeric features.
    """

    required_columns = {
        timestamp_col,
        solexs_col,
        hel1os_col,
        quality_col,
    }

    missing = required_columns - set(
        sensor_df.columns
    )

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    df = sensor_df.copy()

    # Rename to internal standard names.
    df = df.rename(
        columns={
            timestamp_col: "timestamp",
            solexs_col: "solexs_flux",
            hel1os_col: "hel1os_flux",
            quality_col: "quality_flag",
        }
    )

    df = _prepare_index(df)

    # Convert fluxes to numeric.
    df["solexs_flux"] = pd.to_numeric(
        df["solexs_flux"],
        errors="coerce",
    )

    df["hel1os_flux"] = pd.to_numeric(
        df["hel1os_flux"],
        errors="coerce",
    )

    # -----------------------------------------------------------------------
    # Quality handling
    # -----------------------------------------------------------------------

    # Prakriti's preprocessing contract:
    #
    #   good       -> valid
    #   gap        -> invalid
    #   saturated  -> invalid
    #
    # Also support the current synthetic dataset if it uses 1/0 flags.

    quality = (
        df["quality_flag"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    good_quality = quality.isin(
        [
            "good",
            "1",
            "true",
        ]
    )

    # Keep the original quality flag unchanged.
    df["flux_is_flagged"] = (
        ~good_quality
    ).astype(int)

    # Create clean copies for feature calculations.
    solexs_clean = df[
        "solexs_flux"
    ].where(
        good_quality
    )

    hel1os_clean = df[
        "hel1os_flux"
    ].where(
        good_quality
    )

    feature_input = pd.DataFrame(
        {
            "solexs_flux": solexs_clean,
            "hel1os_flux": hel1os_clean,
        },
        index=df.index,
    )

    # -----------------------------------------------------------------------
    # Feature families
    # -----------------------------------------------------------------------

    rolling_features = compute_rolling_features(
        feature_input,
        flux_col="solexs_flux",
        window=ROLLING_WINDOW,
    )

    roc_features = compute_rate_of_change_features(
        feature_input,
        flux_col="solexs_flux",
    )

    hel1os_features = compute_impulsive_spike_features(
        feature_input,
        flux_col="hel1os_flux",
    )

    # -----------------------------------------------------------------------
    # Combine everything
    # -----------------------------------------------------------------------

    output = pd.concat(
        [
            df[
                [
                    "solexs_flux",
                    "hel1os_flux",
                    "quality_flag",
                    "flux_is_flagged",
                ]
            ],
            rolling_features,
            roc_features,
            hel1os_features,
        ],
        axis=1,
    )

    # Replace infinities generated by divisions.
    output = output.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    # Safety check.
    if output.columns.duplicated().any():

        duplicate_columns = (
            output.columns[
                output.columns.duplicated()
            ].tolist()
        )

        raise ValueError(
            f"Duplicate feature columns: {duplicate_columns}"
        )

    return output


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    sensor_file = (
        "data/mock/synthetic_sensor_data.csv"
    )

    sensor_df = pd.read_csv(
        sensor_file
    )

    features = build_feature_dataframe(
        sensor_df
    )

    print("\nFeature dataframe shape:")
    print(features.shape)

    print("\nFeature columns:")
    for column in features.columns:
        print(" -", column)

    print("\nFirst 5 rows:")
    print(features.head())

    print("\nMissing values:")
    print(
        features.isna()
        .sum()
        .sort_values(
            ascending=False
        )
        .head(20)
    )

    print("\nCompletely NaN columns:")
    print(
        features.columns[
            features.isna().all()
        ].tolist()
    )

    print("\nData types:")
    print(features.dtypes)