"""
Trains a machine learning model to predict risk scores based on metadata features.
Serializes the trained model to backend/ml/risk_model.joblib.

How to rerun training:
    python backend/ml/train_risk_model.py
or
    py -m backend.ml.train_risk_model
"""

from pathlib import Path
from typing import Optional
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split

# Context mapping
CONTEXT_MAP = {
    "public": 0,
    "team": 1,
    "anonymous": 2,
}

FEATURE_COLUMNS = [
    "has_gps",
    "has_author_pii",
    "has_timestamp",
    "has_hidden_content",
    "has_device_info",
    "has_revision_history",
    "context",
]


def train_risk_model(
    data_path: Optional[str] = None,
    model_output_path: Optional[str] = None,
    random_state: int = 42,
) -> float:
    """
    Train a risk classification model using synthetic metadata features
    and serialize to risk_model.joblib.
    """
    ml_dir = Path(__file__).resolve().parent

    if not data_path:
        data_path = str(ml_dir / "synthetic_risk_data.csv")

    if not model_output_path:
        model_output_path = str(ml_dir / "risk_model.joblib")

    # If dataset doesn't exist, generate it first
    csv_file = Path(data_path)
    if not csv_file.exists():
        from backend.ml.generate_synthetic_data import generate_synthetic_data

        print(f"Dataset not found at {csv_file}. Generating synthetic dataset...")
        generate_synthetic_data(num_samples=800, output_csv=str(csv_file))

    df = pd.read_csv(csv_file)

    # Encode context if it was stored as string
    if df["context"].dtype == object:
        df["context"] = df["context"].str.lower().map(CONTEXT_MAP).fillna(0).astype(int)

    X = df[FEATURE_COLUMNS]
    y = df["risk_level"]

    # 80/20 train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=random_state, stratify=y
    )

    # Simple Random Forest classifier (default-ish parameters)
    model = RandomForestClassifier(
        n_estimators=50,
        max_depth=6,
        random_state=random_state,
    )
    model.fit(X_train, y_train)

    # Evaluate on test set
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    print(f"--- IntentGuard ML Model Training ---")
    print(f"Dataset samples: {len(df)} (Train: {len(X_train)}, Test: {len(X_test)})")
    print(f"Test Accuracy:   {accuracy * 100:.2f}%")
    print("\nClassification Report:\n", classification_report(y_test, y_pred))

    # Save trained model to disk
    out_file = Path(model_output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out_file)
    print(f"Model successfully saved to: {out_file}\n")

    return accuracy


if __name__ == "__main__":
    train_risk_model()
