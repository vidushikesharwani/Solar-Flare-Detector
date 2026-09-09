"""
Train XGBoost model for solar flare classification.

Classes:
    NO_FLARE
    C
    M
    X

Input contract:
    timestamp
    solexs_flux
    hel1os_flux
    quality_flag

Output artifacts:
    models/solar_flare_xgboost.joblib
    models/label_encoder.joblib
"""

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    accuracy_score,
)
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

from pipeline.features import build_feature_dataframe


# ============================================================
# PATHS
# ============================================================

SENSOR_FILE = Path("data/mock/synthetic_sensor_data.csv")
EVENT_FILE = Path("data/mock/synthetic_flare_events.csv")

MODEL_DIR = Path("models")

MODEL_FILE = MODEL_DIR / "solar_flare_xgboost.joblib"
ENCODER_FILE = MODEL_DIR / "label_encoder.joblib"


# ============================================================
# LABELING
# ============================================================

CLASS_ORDER = ["NO_FLARE", "C", "M", "X"]


def create_labels(feature_df: pd.DataFrame, event_df: pd.DataFrame) -> pd.Series:
    """
    Create flare labels from event intervals and precursor-gated
    sensor activity.

    Main flare interval:
        start_time -> end_time

    Precursor window:
        max(15 min, 2 * peak_sigma) before start_time

    A timestamp inside the precursor window is labeled only when
    there is evidence of increasing/impulsive sensor activity.

    This prevents calm pre-flare periods from automatically becoming
    false-negative examples.
    """

    timestamps = pd.to_datetime(
    feature_df.index,
    utc=True,
    errors="coerce",
)

    labels = pd.Series(
        "NO_FLARE",
        index=feature_df.index,
        dtype="object",
    )

    for _, event in event_df.iterrows():

        start_time = pd.to_datetime(
            event["start_time"],
            utc=True,
            errors="coerce",
        )

        end_time = pd.to_datetime(
            event["end_time"],
            utc=True,
            errors="coerce",
        )

        if pd.isna(start_time) or pd.isna(end_time):
            continue

        flare_class = str(event["flare_class"]).strip().upper()

        if flare_class not in {"C", "M", "X"}:
            continue

        # ----------------------------------------------------
        # Main flare interval
        # ----------------------------------------------------

        main_mask = (
            (timestamps >= start_time)
            & (timestamps <= end_time)
        )

        labels.loc[main_mask] = flare_class

        # ----------------------------------------------------
        # Precursor window
        # ----------------------------------------------------

        sigma_value = pd.to_numeric(
            event.get("peak_sigma", np.nan),
            errors="coerce",
        )

        if pd.isna(sigma_value):
            precursor_minutes = 30.0
        else:
            precursor_minutes = max(
                15.0,
                2.0 * float(sigma_value),
            )

        precursor_start = (
            start_time
            - pd.Timedelta(minutes=precursor_minutes)
        )

        precursor_mask = (
            (timestamps >= precursor_start)
            & (timestamps < start_time)
        )

        # ----------------------------------------------------
        # Sensor-based precursor gate
        # ----------------------------------------------------
        #
        # We require evidence of increasing activity.
        #
        # SoLEXS:
        #   - positive 5-min rate of change
        #   - OR elevated 90-min z-score
        #
        # HEL1OS:
        #   - impulsive spike score
        #
        # Missing values naturally evaluate as False.
        # ----------------------------------------------------

        precursor_signal = pd.Series(
            False,
            index=feature_df.index,
        )

        if "solexs_flux_roc_5min_per_min" in feature_df.columns:
            precursor_signal |= (
                feature_df["solexs_flux_roc_5min_per_min"] > 0
            )

        if "solexs_flux_zscore_90min" in feature_df.columns:
            precursor_signal |= (
                feature_df["solexs_flux_zscore_90min"] >= 1.0
            )

        if "hel1os_flux_spike_score_30min" in feature_df.columns:
            precursor_signal |= (
                feature_df["hel1os_flux_spike_score_30min"] >= 1.5
            )

        gated_precursor_mask = (
            precursor_mask
            & precursor_signal
        )

        labels.loc[gated_precursor_mask] = flare_class

    return labels


# ============================================================
# DATA QUALITY
# ============================================================

def prepare_training_data(
    feature_df: pd.DataFrame,
    labels: pd.Series,
):
    """
    Prepare X and y without future-data leakage.

    - Keep only good-quality sensor rows.
    - Remove timestamp because it is not a model feature.
    - Remove raw string quality_flag.
    - Keep numeric engineered features.
    - Let XGBoost handle remaining NaN values natively.
    """

    working = feature_df.copy()

    # --------------------------------------------------------
    # Ensure labels align with feature rows
    # --------------------------------------------------------

    labels = labels.reindex(working.index)

    # --------------------------------------------------------
    # Good quality rows
    # --------------------------------------------------------

    if "flux_is_flagged" in working.columns:
        quality_mask = (
            working["flux_is_flagged"] == 0
        )
    else:
        quality = (
            working["quality_flag"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        quality_mask = quality.isin(
            ["good", "1", "true"]
        )

    # --------------------------------------------------------
    # Sensor values must be finite
    # --------------------------------------------------------

    sensor_mask = (
        pd.to_numeric(
            working["solexs_flux"],
            errors="coerce",
        ).notna()
        &
        pd.to_numeric(
            working["hel1os_flux"],
            errors="coerce",
        ).notna()
    )

    valid_mask = quality_mask & sensor_mask

    working = working.loc[valid_mask].copy()
    labels = labels.loc[valid_mask].copy()

    # --------------------------------------------------------
    # Build numeric feature matrix
    # --------------------------------------------------------

    X = working.drop(
        columns=[
            "timestamp",
            "quality_flag",
        ],
        errors="ignore",
    )

    # Keep only numeric columns
    X = X.select_dtypes(
        include=[np.number]
    ).copy()

    # Replace infinities with NaN.
    # XGBoost handles NaN natively.
    X = X.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    # Remove completely NaN columns
    all_nan_columns = [
        column
        for column in X.columns
        if X[column].isna().all()
    ]

    if all_nan_columns:
        X = X.drop(
            columns=all_nan_columns
        )

    return X, labels


# ============================================================
# CLASS WEIGHTS
# ============================================================

def calculate_class_weights(y_encoded: np.ndarray):
    """
    Balanced class weights.

    Rare classes such as X receive higher weight.
    """

    counts = np.bincount(y_encoded)

    total = len(y_encoded)
    n_classes = len(counts)

    weights = {}

    for class_id, count in enumerate(counts):

        if count == 0:
            weights[class_id] = 1.0
        else:
            weights[class_id] = (
                total
                / (n_classes * count)
            )

    return weights


# ============================================================
# MODEL
# ============================================================

def create_model(n_classes: int):
    """
    Create XGBoost multiclass classifier.
    """

    return XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="multi:softprob",
        num_class=n_classes,
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=-1,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("SOLAR FLARE XGBOOST TRAINING")
    print("=" * 70)

    # --------------------------------------------------------
    # 1. Load sensor data
    # --------------------------------------------------------

    print("\n[1/8] Loading sensor data...")

    sensor_df = pd.read_csv(
        SENSOR_FILE
    )

    event_df = pd.read_csv(
        EVENT_FILE
    )

    print(
        f"Sensor rows: {len(sensor_df)}"
    )

    print(
        f"Flare events: {len(event_df)}"
    )

    # --------------------------------------------------------
    # 2. Build features
    # --------------------------------------------------------

    print("\n[2/8] Building features...")

    feature_df = build_feature_dataframe(
        sensor_df
    )

    print(
        f"Feature dataframe shape: "
        f"{feature_df.shape}"
    )

    # --------------------------------------------------------
    # 3. Create labels
    # --------------------------------------------------------

    print("\n[3/8] Creating flare labels...")

    labels = create_labels(
        feature_df,
        event_df,
    )

    print("\nLabel distribution:")

    print(
        labels.value_counts()
        .reindex(CLASS_ORDER, fill_value=0)
    )

    # --------------------------------------------------------
    # 4. Prepare X and y
    # --------------------------------------------------------

    print("\n[4/8] Preparing training data...")

    X, y_text = prepare_training_data(
        feature_df,
        labels,
    )

    print(
        f"Training matrix shape: "
        f"{X.shape}"
    )

    print(
        f"Number of features: "
        f"{X.shape[1]}"
    )

    print(
        f"Valid labelled rows: "
        f"{len(y_text)}"
    )

    # --------------------------------------------------------
    # 5. Encode labels
    # --------------------------------------------------------

    print("\n[5/8] Encoding classes...")

    encoder = LabelEncoder()

    encoder.fit(CLASS_ORDER)

    y = encoder.transform(
        y_text
    )

    print(
        "Classes:"
    )

    print(
        list(encoder.classes_)
    )

    # --------------------------------------------------------
    # 6. Chronological validation split
    # --------------------------------------------------------

    print(
        "\n[6/8] Creating chronological "
        "train/validation split..."
    )

    split_index = int(
        len(X) * 0.80
    )

    X_train = X.iloc[
        :split_index
    ].copy()

    X_valid = X.iloc[
        split_index:
    ].copy()

    y_train = y[
        :split_index
    ]

    y_valid = y[
        split_index:
    ]

    print(
        f"Training rows: "
        f"{len(X_train)}"
    )

    print(
        f"Validation rows: "
        f"{len(X_valid)}"
    )

    # --------------------------------------------------------
    # Check whether every class exists in training data
    # --------------------------------------------------------

    train_classes = set(
        np.unique(y_train)
    )

    all_classes = set(
        range(len(encoder.classes_))
    )

    missing_train_classes = (
        all_classes - train_classes
    )

    if missing_train_classes:

        missing_names = [
            encoder.classes_[i]
            for i in sorted(
                missing_train_classes
            )
        ]

        print(
            "\nWARNING:"
        )

        print(
            "These classes are absent "
            "from the chronological training "
            f"split: {missing_names}"
        )

        print(
            "This is expected with the tiny "
            "synthetic dataset if the latest "
            "flare occurs near the end."
        )

        print(
            "The validation result for those "
            "classes will not be meaningful."
        )

    # --------------------------------------------------------
    # 7. Train validation model
    # --------------------------------------------------------

    print(
        "\n[7/8] Training XGBoost..."
    )

    train_class_weights = (
        calculate_class_weights(
            y_train
        )
    )

    sample_weights = np.array(
        [
            train_class_weights[
                class_id
            ]
            for class_id in y_train
        ]
    )

    print(
        "\nClass weights:"
    )

    for class_id, weight in (
        train_class_weights.items()
    ):
        print(
            f"  {encoder.classes_[class_id]}: "
            f"{weight:.4f}"
        )

    validation_model = create_model(
        n_classes=len(
            encoder.classes_
        )
    )

    validation_model.fit(
        X_train,
        y_train,
        sample_weight=sample_weights,
        eval_set=[
            (X_train, y_train),
        ],
        verbose=False,
    )
        # --------------------------------------------------------
    # Save training curve history
    # --------------------------------------------------------

    training_history = (
        validation_model.evals_result()
    )

    history_dir = Path(
        "data/processed"
    )

    history_file = (
        history_dir / "training_history.json"
    )

    history_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    import json

    with open(
        history_file,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            training_history,
            file,
            indent=2,
        )

    print(
        f"\nTraining history saved to:"
    )

    print(
        f"  {history_file}"
    )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if len(X_valid) > 0:

        y_pred = (
            validation_model
            .predict(X_valid)
        )

        print(
            "\nValidation accuracy:"
        )

        print(
            f"{accuracy_score(y_valid, y_pred):.4f}"
        )

        print(
            "\nClassification report:"
        )

        print(
            classification_report(
                y_valid,
                y_pred,
                labels=np.arange(
                    len(encoder.classes_)
                ),
                target_names=encoder.classes_,
                zero_division=0,
            )
        )

        print(
            "Confusion matrix:"
        )

        print(
            confusion_matrix(
                y_valid,
                y_pred,
                labels=np.arange(
                    len(encoder.classes_)
                ),
            )
        )

    # --------------------------------------------------------
    # Final model: train on ALL valid data
    # --------------------------------------------------------

    print(
        "\nTraining final model on "
        "all valid data..."
    )

    final_class_weights = (
        calculate_class_weights(y)
    )

    final_sample_weights = np.array(
        [
            final_class_weights[
                class_id
            ]
            for class_id in y
        ]
    )

    final_model = create_model(
        n_classes=len(
            encoder.classes_
        )
    )

    final_model.fit(
        X,
        y,
        sample_weight=final_sample_weights,
        verbose=False,
    )

    # --------------------------------------------------------
    # 8. Save artifacts
    # --------------------------------------------------------

    print(
        "\n[8/8] Saving model artifacts..."
    )

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(
        final_model,
        MODEL_FILE,
    )

    joblib.dump(
        encoder,
        ENCODER_FILE,
    )

    print(
        f"\nModel saved to:"
    )

    print(
        f"  {MODEL_FILE}"
    )

    print(
        f"Label encoder saved to:"
    )

    print(
        f"  {ENCODER_FILE}"
    )

    print("\n" + "=" * 70)
    print("TRAINING COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()