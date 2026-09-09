import numpy as np
import pandas as pd

from pipeline.features import build_feature_dataframe
from pipeline.predict import prepare_prediction_features, predict


def load_mock_data():
    return pd.read_csv(
        "data/mock/synthetic_sensor_data.csv"
    )


def test_feature_dataframe_has_required_columns():
    sensor_df = load_mock_data()

    feature_df = build_feature_dataframe(
        sensor_df
    )

    required_columns = {
        "solexs_flux",
        "hel1os_flux",
        "quality_flag",
        "flux_is_flagged",
    }

    assert required_columns.issubset(
        set(feature_df.columns)
    )

    # Timestamp is used as the DataFrame index
    assert isinstance(
        feature_df.index,
        pd.DatetimeIndex
    )


def test_feature_dataframe_has_engineered_features():
    sensor_df = load_mock_data()

    feature_df = build_feature_dataframe(
        sensor_df
    )

    expected_features = [
        "solexs_flux_roll_mean_90m",
        "solexs_flux_roll_std_90m",
        "solexs_flux_roc_permin_1min",
        "hel1os_flux_deviation_from_baseline",
    ]

    for feature in expected_features:
        assert feature in feature_df.columns


def test_prediction_features_are_numeric():
    sensor_df = load_mock_data()

    feature_df = build_feature_dataframe(
        sensor_df
    )

    X = prepare_prediction_features(
        feature_df
    )

    # Same number of rows as the input data
    assert len(X) == len(sensor_df)

    # Every prediction feature must be numeric
    assert all(
        np.issubdtype(dtype, np.number)
        for dtype in X.dtypes
    )


def test_prediction_output_schema():
    sensor_df = load_mock_data()

    results = predict(sensor_df)

    # One prediction per sensor row
    assert len(results) == len(sensor_df)

    required_keys = {
        "timestamp",
        "flare_probability",
        "predicted_class",
        "confidence",
        "top_features",
    }

    assert required_keys.issubset(
        results[0].keys()
    )


def test_synthetic_flare_peaks_are_detected():
    sensor_df = load_mock_data()

    results = predict(sensor_df)

    expected_events = {
        "2026-01-01T10:30:00+00:00": "C",
        "2026-01-02T18:45:00+00:00": "M",
        "2026-01-03T07:20:00+00:00": "M",
        "2026-01-04T15:10:00+00:00": "X",
    }

    predictions = {
        result["timestamp"]: result["predicted_class"]
        for result in results
    }

    for timestamp, expected_class in expected_events.items():
        assert timestamp in predictions
        assert predictions[timestamp] == expected_class


def test_top_features_are_present():
    sensor_df = load_mock_data()

    results = predict(sensor_df)

    for result in results[:10]:
        assert isinstance(
            result["top_features"],
            list
        )

        assert len(
            result["top_features"]
        ) == 5

        for feature in result["top_features"]:
            assert "feature" in feature
            assert "importance" in feature

            assert feature["importance"] >= 0