"""
Solar flare inference / prediction pipeline.

Loads the trained XGBoost model and converts sensor data
into backend-ready prediction records.

Fixed output schema:

{
    timestamp,
    flare_probability,
    predicted_class,
    confidence,
    top_features
}
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap

from pipeline.features import build_feature_dataframe


# ============================================================
# PATHS
# ============================================================

MODEL_FILE = Path(
    "models/solar_flare_xgboost.joblib"
)

ENCODER_FILE = Path(
    "models/label_encoder.joblib"
)


# ============================================================
# MODEL LOADING
# ============================================================

def load_model():
    """
    Load trained XGBoost model and label encoder.
    """

    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            f"Model not found: {MODEL_FILE}"
        )

    if not ENCODER_FILE.exists():
        raise FileNotFoundError(
            f"Label encoder not found: {ENCODER_FILE}"
        )

    model = joblib.load(
        MODEL_FILE
    )

    encoder = joblib.load(
        ENCODER_FILE
    )

    return model, encoder


# ============================================================
# FEATURE PREPARATION
# ============================================================

def prepare_prediction_features(
    feature_df: pd.DataFrame,
):
    """
    Prepare engineered features for XGBoost inference.

    Keeps only numeric model features and preserves NaN values
    because XGBoost can handle missing values natively.
    """

    X = feature_df.copy()

    # Timestamp is used separately for output.
    # It must not be given to the model.
    if "timestamp" in X.columns:
        X = X.drop(
            columns=["timestamp"]
        )

    # Quality flag is metadata, not a model feature.
    if "quality_flag" in X.columns:
        X = X.drop(
            columns=["quality_flag"]
        )

    # Keep only numeric columns.
    X = X.select_dtypes(
        include=[np.number]
    )

    # Replace infinities with NaN.
    # Do NOT forward-fill/back-fill because that can
    # introduce temporal leakage.
    X = X.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    # Remove columns that contain no usable values.
    X = X.dropna(
        axis=1,
        how="all",
    )

    return X


# ============================================================
# SHAP TOP FEATURES
# ============================================================

def get_top_features(
    explainer,
    X: pd.DataFrame,
    row_index: int,
    predicted_class_id: int,
    top_n: int = 5,
):
    """
    Return the features with the strongest SHAP
    contribution for a specific prediction.

    For multiclass XGBoost, SHAP values are selected
    for the class that was actually predicted.
    """

    row = X.iloc[[row_index]]

    shap_output = explainer.shap_values(
        row
    )

    # --------------------------------------------------------
    # Convert SHAP output into numpy array
    # --------------------------------------------------------

    if hasattr(
        shap_output,
        "values",
    ):
        shap_array = np.asarray(
            shap_output.values
        )
    else:
        shap_array = np.asarray(
            shap_output
        )

    # --------------------------------------------------------
    # Older SHAP versions:
    #
    # list[class] -> array(samples, features)
    # --------------------------------------------------------

    if isinstance(
        shap_output,
        list,
    ):

        if predicted_class_id >= len(
            shap_output
        ):
            predicted_class_id = 0

        feature_values = np.asarray(
            shap_output[
                predicted_class_id
            ]
        )[0]

    # --------------------------------------------------------
    # Newer SHAP versions:
    #
    # samples × features × classes
    # --------------------------------------------------------

    elif shap_array.ndim == 3:

        feature_values = shap_array[
            0,
            :,
            predicted_class_id,
        ]

    # --------------------------------------------------------
    # Single-output / binary fallback
    # --------------------------------------------------------

    elif shap_array.ndim == 2:

        feature_values = shap_array[
            0
        ]

    # --------------------------------------------------------
    # Unexpected shape fallback
    # --------------------------------------------------------

    else:

        feature_values = (
            shap_array.reshape(-1)
        )

    # --------------------------------------------------------
    # Validate SHAP output
    # --------------------------------------------------------

    if len(feature_values) != len(
        X.columns
    ):
        raise ValueError(
            "SHAP output does not match "
            "the number of input features."
        )

    # --------------------------------------------------------
    # Absolute SHAP contribution
    # --------------------------------------------------------

    absolute_values = np.abs(
        feature_values
    )

    # Strongest features first.
    top_indices = np.argsort(
        absolute_values
    )[::-1][:top_n]

    # --------------------------------------------------------
    # Fixed top_features format
    # --------------------------------------------------------

    results = []

    for index in top_indices:

        results.append(
            {
                "feature": X.columns[index],
                "importance": float(
                    absolute_values[index]
                ),
            }
        )

    return results


# ============================================================
# PREDICTION
# ============================================================

def predict(
    sensor_df: pd.DataFrame,
):
    """
    Generate predictions for sensor data.

    Returns a list of dictionaries using the fixed
    backend output schema.
    """

    # --------------------------------------------------------
    # Load model
    # --------------------------------------------------------

    model, encoder = load_model()

    # SHAP explainer for individual predictions.
    explainer = shap.TreeExplainer(
        model
    )

    # --------------------------------------------------------
    # Build engineered features
    # --------------------------------------------------------

    feature_df = build_feature_dataframe(
        sensor_df
    )

    # --------------------------------------------------------
    # Prepare model input
    # --------------------------------------------------------

    X = prepare_prediction_features(
        feature_df
    )

    # --------------------------------------------------------
    # Predict probabilities
    # --------------------------------------------------------

    probabilities = (
        model.predict_proba(X)
    )

    # Class with highest probability.
    predicted_ids = np.argmax(
        probabilities,
        axis=1,
    )

    # Convert encoded IDs back to:
    # C / M / X / NO_FLARE
    predicted_classes = (
        encoder.inverse_transform(
            predicted_ids
        )
    )

    # --------------------------------------------------------
    # Timestamps
    # --------------------------------------------------------

    timestamps = pd.to_datetime(
        feature_df.index,
        utc=True,
        errors="coerce",
    )

    # --------------------------------------------------------
    # Build backend-ready results
    # --------------------------------------------------------

    results = []

    for i in range(
        len(X)
    ):

        probability_vector = (
            probabilities[i]
        )

        predicted_id = int(
            predicted_ids[i]
        )

        predicted_class = (
            predicted_classes[i]
        )

        # Probability of the predicted class.
        confidence = float(
            probability_vector[
                predicted_id
            ]
        )

        # ----------------------------------------------------
        # Probability of ANY flare
        #
        # Sum probability of C + M + X.
        # ----------------------------------------------------

        flare_probability = float(
            sum(
                probability_vector[
                    class_id
                ]
                for class_id, class_name
                in enumerate(
                    encoder.classes_
                )
                if class_name != "NO_FLARE"
            )
        )

        # ----------------------------------------------------
        # SHAP top features
        # ----------------------------------------------------

        top_features = get_top_features(
            explainer,
            X,
            i,
            predicted_class_id=predicted_id,
        )

        # ----------------------------------------------------
        # Fixed output schema
        # ----------------------------------------------------

        results.append(
            {
                "timestamp": (
                    timestamps[i].isoformat()
                    if not pd.isna(
                        timestamps[i]
                    )
                    else None
                ),

                "flare_probability": (
                    flare_probability
                ),

                "predicted_class": (
                    str(predicted_class)
                ),

                "confidence": (
                    confidence
                ),

                "top_features": (
                    top_features
                ),
            }
        )

    return results


# ============================================================
# STANDALONE TEST
# ============================================================

def main():

    print(
        "=" * 70
    )

    print(
        "SOLAR FLARE MODEL INFERENCE TEST"
    )

    print(
        "=" * 70
    )

    # --------------------------------------------------------
    # Mock sensor data
    # --------------------------------------------------------

    sensor_file = Path(
        "data/mock/synthetic_sensor_data.csv"
    )

    print(
        "\nLoading sensor data..."
    )

    sensor_df = pd.read_csv(
        sensor_file
    )

    print(
        f"Rows loaded: {len(sensor_df)}"
    )

    # --------------------------------------------------------
    # Generate predictions
    # --------------------------------------------------------

    print(
        "\nGenerating predictions..."
    )

    results = predict(
        sensor_df
    )

    print(
        f"Predictions generated: "
        f"{len(results)}"
    )

    # --------------------------------------------------------
    # Show first 5 predictions
    # --------------------------------------------------------

    print(
        "\nFirst 5 predictions:"
    )

    for result in results[:5]:

        print(
            "\n" + "-" * 60
        )

        print(
            f"Timestamp: "
            f"{result['timestamp']}"
        )

        print(
            f"Flare probability: "
            f"{result['flare_probability']:.4f}"
        )

        print(
            f"Predicted class: "
            f"{result['predicted_class']}"
        )

        print(
            f"Confidence: "
            f"{result['confidence']:.4f}"
        )

        print(
            "Top features:"
        )

        for feature in result[
            "top_features"
        ]:

            print(
                f"  {feature['feature']}: "
                f"{feature['importance']:.4f}"
            )

    print(
        "\n" + "=" * 70
    )

    print(
        "INFERENCE TEST COMPLETE"
    )

    print(
        "=" * 70
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()