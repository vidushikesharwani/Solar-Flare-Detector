"""
Evaluate the trained Solar Flare XGBoost model.

Outputs:
    data/processed/metrics.json

The metrics file contains:
    - overall accuracy
    - per-class precision
    - per-class recall
    - per-class F1-score
    - support
    - confusion matrix
    - training curve data when available
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
import joblib

from pipeline.features import build_feature_dataframe
from pipeline.train_model import (
    create_labels,
    prepare_training_data,
    SENSOR_FILE,
    EVENT_FILE,
    MODEL_FILE,
    ENCODER_FILE,
)


# ============================================================
# PATHS
# ============================================================

OUTPUT_DIR = Path("data/processed")
METRICS_FILE = OUTPUT_DIR / "metrics.json"


# ============================================================
# EVALUATION
# ============================================================

def evaluate_model():
    """Evaluate the saved model and return metrics."""

    print("=" * 70)
    print("SOLAR FLARE MODEL EVALUATION")
    print("=" * 70)

    # --------------------------------------------------------
    # 1. Check model artifacts
    # --------------------------------------------------------

    if not MODEL_FILE.exists():
        raise FileNotFoundError(
            f"Model file not found: {MODEL_FILE}\n"
            "Run: python pipeline/train_model.py"
        )

    if not ENCODER_FILE.exists():
        raise FileNotFoundError(
            f"Label encoder not found: {ENCODER_FILE}\n"
            "Run: python pipeline/train_model.py"
        )

    # --------------------------------------------------------
    # 2. Load data
    # --------------------------------------------------------

    print("\n[1/5] Loading data...")

    sensor_df = pd.read_csv(SENSOR_FILE)
    event_df = pd.read_csv(EVENT_FILE)

    feature_df = build_feature_dataframe(
        sensor_df
    )

    labels = create_labels(
        feature_df,
        event_df,
    )

    X, y_text = prepare_training_data(
        feature_df,
        labels,
    )

    # --------------------------------------------------------
    # 3. Load model + encoder
    # --------------------------------------------------------

    print("[2/5] Loading trained model...")

    model = joblib.load(
        MODEL_FILE
    )

    encoder = joblib.load(
        ENCODER_FILE
    )

    y = encoder.transform(
        y_text
    )

    # --------------------------------------------------------
    # 4. Generate predictions
    # --------------------------------------------------------

    print("[3/5] Generating predictions...")

    y_pred = model.predict(X)

    y_pred = np.asarray(
        y_pred,
        dtype=int,
    )

    class_ids = np.arange(
        len(encoder.classes_)
    )

    # --------------------------------------------------------
    # Overall accuracy
    # --------------------------------------------------------

    accuracy = accuracy_score(
        y,
        y_pred,
    )

    # --------------------------------------------------------
    # Per-class metrics
    # --------------------------------------------------------

    report = classification_report(
        y,
        y_pred,
        labels=class_ids,
        target_names=encoder.classes_,
        output_dict=True,
        zero_division=0,
    )

    per_class = {}

    for class_name in encoder.classes_:
        class_metrics = report.get(
            class_name,
            {},
        )

        per_class[class_name] = {
            "precision": float(
                class_metrics.get(
                    "precision",
                    0.0,
                )
            ),
            "recall": float(
                class_metrics.get(
                    "recall",
                    0.0,
                )
            ),
            "f1_score": float(
                class_metrics.get(
                    "f1-score",
                    0.0,
                )
            ),
            "support": int(
                class_metrics.get(
                    "support",
                    0,
                )
            ),
        }

    # --------------------------------------------------------
    # Confusion matrix
    # --------------------------------------------------------

    cm = confusion_matrix(
        y,
        y_pred,
        labels=class_ids,
    )

    confusion = cm.tolist()

    # --------------------------------------------------------
    # Training curve
    # --------------------------------------------------------
    #
    # Current train_model.py does not yet save evals_result.
    # Therefore this remains empty until training history
    # is added to the training pipeline.
    #

        # --------------------------------------------------------
    # Training curve
    # --------------------------------------------------------

    history_file = (
        OUTPUT_DIR / "training_history.json"
    )

    training_curve = {
        "epochs": [],
        "training_mlogloss": [],
        "validation_mlogloss": [],
    }

    if history_file.exists():

        with open(
            history_file,
            "r",
            encoding="utf-8",
        ) as file:
            history = json.load(file)

        training_values = (
            history
            .get("validation_0", {})
            .get("mlogloss", [])
        )

        validation_values = (
            history
            .get("validation_1", {})
            .get("mlogloss", [])
        )

        training_curve["epochs"] = list(
            range(
                1,
                len(training_values) + 1,
            )
        )

        training_curve["training_mlogloss"] = [
            float(value)
            for value in training_values
        ]

        training_curve["validation_mlogloss"] = [
            float(value)
            for value in validation_values
        ]

    # --------------------------------------------------------
    # Build output
    # --------------------------------------------------------

    metrics = {
        "accuracy": float(
            accuracy
        ),
        "classes": list(
            encoder.classes_
        ),
        "per_class": per_class,
        "confusion_matrix": {
            "labels": list(
                encoder.classes_
            ),
            "values": confusion,
        },
        "training_curve": training_curve,
        "dataset": {
            "sensor_rows": int(
                len(sensor_df)
            ),
            "evaluation_rows": int(
                len(X)
            ),
            "flare_events": int(
                len(event_df)
            ),
            "feature_count": int(
                X.shape[1]
            ),
        },
    }

    # --------------------------------------------------------
    # Save JSON
    # --------------------------------------------------------

    print("[4/5] Saving metrics...")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        METRICS_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metrics,
            file,
            indent=2,
        )

    print(
        f"\nMetrics saved to:"
    )

    print(
        f"  {METRICS_FILE}"
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("[5/5] Evaluation complete.")

    print(
        f"\nAccuracy: {accuracy:.4f}"
    )

    print("\nPer-class metrics:")

    for class_name, values in per_class.items():
        print(
            f"  {class_name}: "
            f"precision={values['precision']:.4f}, "
            f"recall={values['recall']:.4f}, "
            f"F1={values['f1_score']:.4f}"
        )

    print("\n" + "=" * 70)

    return metrics


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    evaluate_model()