"""
Scores file risk based on extracted metadata and model predictions.
Uses a serialized scikit-learn model (risk_model.joblib) with an automatic
rule-based fallback when the model file is absent or fails to load.
"""

from pathlib import Path
from typing import Any, Dict, List, Union
import numpy as np
import joblib

# Feature definitions aligned with model training
FEATURE_COLUMNS = [
    "has_gps",
    "has_author_pii",
    "has_timestamp",
    "has_hidden_content",
    "has_device_info",
    "has_revision_history",
    "context",
]

CONTEXT_MAP = {
    "public": 0,
    "team": 1,
    "anonymous": 2,
}

MODEL_PATH = Path(__file__).resolve().parent / "risk_model.joblib"


def _load_model():
    """Load model once at module initialization."""
    if MODEL_PATH.is_file():
        try:
            return joblib.load(MODEL_PATH)
        except Exception as e:
            print(f"[Warning] Failed to load risk_model.joblib: {e}. Falling back to rule-based.")
            return None
    return None


# Module-level model instance
_MODEL = _load_model()


def _rule_based_fallback(features: Dict[str, int], context_name: str) -> Dict[str, Any]:
    """
    Rule-based fallback if ML model is unavailable.
    Mirrors rule-of-thumb:
      - has_gps=1 OR (has_author_pii=1 AND context=public) -> high
      - has_hidden_content=1 OR has_revision_history=1 -> medium (unless already high)
      - has_timestamp=1 OR has_device_info=1 -> medium
      - else -> safe
    """
    ctx_clean = str(context_name).lower().strip()
    if features["has_gps"] == 1 or (features["has_author_pii"] == 1 and ctx_clean == "public"):
        risk_level = "high"
    elif features["has_hidden_content"] == 1 or features["has_revision_history"] == 1:
        risk_level = "medium"
    elif features["has_timestamp"] == 1 or features["has_device_info"] == 1:
        risk_level = "medium"
    else:
        risk_level = "safe"

    return {
        "risk_level": risk_level,
        "confidence": 1.0,
        "source": "rule-based",
    }


def extract_features(
    metadata_input: Union[List[Dict[str, Any]], Dict[str, Any]],
    context: str = "public",
) -> Dict[str, int]:
    """
    Convert normalized metadata records or raw metadata dictionary into binary feature flags.
    """
    ctx_num = CONTEXT_MAP.get(str(context).lower().strip(), 0)

    # 1. If already provided as a feature dict
    if isinstance(metadata_input, dict) and "has_gps" in metadata_input:
        return {
            "has_gps": int(bool(metadata_input.get("has_gps"))),
            "has_author_pii": int(bool(metadata_input.get("has_author_pii"))),
            "has_timestamp": int(bool(metadata_input.get("has_timestamp"))),
            "has_hidden_content": int(bool(metadata_input.get("has_hidden_content"))),
            "has_device_info": int(bool(metadata_input.get("has_device_info"))),
            "has_revision_history": int(bool(metadata_input.get("has_revision_history"))),
            "context": ctx_num,
        }

    # 2. Extract keys from normalized record list or raw dictionary
    raw_keys = set()
    categories = set()

    if isinstance(metadata_input, list):
        for item in metadata_input:
            if isinstance(item, dict):
                k = str(item.get("raw_key", "")).lower()
                c = str(item.get("category", "")).lower()
                if k:
                    raw_keys.add(k)
                if c:
                    categories.add(c)
    elif isinstance(metadata_input, dict):
        for k, v in metadata_input.items():
            if v is not None and v is not False and v != "" and v != []:
                raw_keys.add(str(k).lower())

    # Map raw keys / categories to training features
    has_gps = 1 if any("gps" in k for k in raw_keys) else 0
    has_author_pii = (
        1
        if any(
            k in ("author", "creator", "last_modified_by") or "author" in k or "creator" in k
            for k in raw_keys
        )
        else 0
    )
    has_timestamp = (
        1
        if any(
            k in ("created", "modified", "datetime", "creation_date", "mod_date")
            or "date" in k
            or "time" in k
            for k in raw_keys
        )
        else 0
    )
    has_hidden_content = (
        1
        if any(
            k in ("hidden_sheets", "has_tracked_changes") or "hidden" in k
            for k in raw_keys
        )
        else 0
    )
    has_device_info = (
        1
        if any(
            k in ("device", "software", "producer") or "device" in k or "software" in k
            for k in raw_keys
        )
        else 0
    )
    has_revision_history = (
        1
        if any(
            k in ("revision", "has_tracked_changes") or "revision" in k
            for k in raw_keys
        )
        else 0
    )

    return {
        "has_gps": has_gps,
        "has_author_pii": has_author_pii,
        "has_timestamp": has_timestamp,
        "has_hidden_content": has_hidden_content,
        "has_device_info": has_device_info,
        "has_revision_history": has_revision_history,
        "context": ctx_num,
    }


def score_risk(
    metadata_features: Union[List[Dict[str, Any]], Dict[str, Any]],
    context: str = "public",
) -> Dict[str, Any]:
    """
    Score the risk level of file metadata using ML model with rule-based fallback.

    Parameters:
      - metadata_features: Output from normalizer.normalize() or raw metadata dict.
      - context: Sharing context ('public', 'team', 'anonymous').

    Returns:
      Dict with:
        - risk_level: 'high' | 'medium' | 'safe'
        - confidence: float (0.0 - 1.0)
        - source: 'ml' | 'rule-based'
    """
    global _MODEL

    features_dict = extract_features(metadata_features, context=context)

    # Attempt to reload model if not previously loaded
    if _MODEL is None and MODEL_PATH.is_file():
        _MODEL = _load_model()

    if _MODEL is None:
        return _rule_based_fallback(features_dict, context)

    try:
        import pandas as pd
        feature_df = pd.DataFrame(
            [[features_dict[col] for col in FEATURE_COLUMNS]],
            columns=FEATURE_COLUMNS,
        )

        pred = _MODEL.predict(feature_df)[0]
        probs = _MODEL.predict_proba(feature_df)[0]
        confidence = round(float(np.max(probs)), 2)

        return {
            "risk_level": str(pred),
            "confidence": confidence,
            "source": "ml",
        }
    except Exception as e:
        print(f"[Warning] ML prediction failed ({e}). Using rule-based fallback.")
        return _rule_based_fallback(features_dict, context)
