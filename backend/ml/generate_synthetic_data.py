"""
Generates synthetic metadata datasets with risk labels for training the ML model.
Dataset simulates various combinations of metadata flags and sharing contexts.
"""

import random
from pathlib import Path
from typing import Optional
import pandas as pd


CONTEXT_MAP = {
    "public": 0,
    "team": 1,
    "anonymous": 2,
}


def _determine_ground_truth(
    has_gps: int,
    has_author_pii: int,
    has_timestamp: int,
    has_hidden_content: int,
    has_device_info: int,
    has_revision_history: int,
    context: int,
) -> str:
    """
    Rule-of-thumb baseline labeling:
      - has_gps=1 OR (has_author_pii=1 AND context=public/0) -> high
      - has_hidden_content=1 OR has_revision_history=1 -> medium (unless already high)
      - has_timestamp=1 OR has_device_info=1 alone -> medium
      - none of the above -> safe
    """
    if has_gps == 1 or (has_author_pii == 1 and context == 0):
        return "high"
    elif has_hidden_content == 1 or has_revision_history == 1:
        return "medium"
    elif has_timestamp == 1 or has_device_info == 1:
        return "medium"
    else:
        return "safe"


def generate_synthetic_data(
    num_samples: int = 800,
    output_csv: Optional[str] = None,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic metadata feature combinations and risk labels.

    Columns:
      - has_gps (0/1)
      - has_author_pii (0/1)
      - has_timestamp (0/1)
      - has_hidden_content (0/1)
      - has_device_info (0/1)
      - has_revision_history (0/1)
      - context (0: public, 1: team, 2: anonymous)
      - risk_level (high, medium, safe)
    """
    random.seed(seed)
    rows = []
    labels_pool = ["high", "medium", "safe"]

    for _ in range(num_samples):
        # Generate realistic distribution of metadata flags
        has_gps = 1 if random.random() < 0.25 else 0
        has_author_pii = 1 if random.random() < 0.45 else 0
        has_timestamp = 1 if random.random() < 0.70 else 0
        has_hidden_content = 1 if random.random() < 0.20 else 0
        has_device_info = 1 if random.random() < 0.40 else 0
        has_revision_history = 1 if random.random() < 0.25 else 0
        context = random.choice([0, 1, 2])

        label = _determine_ground_truth(
            has_gps=has_gps,
            has_author_pii=has_author_pii,
            has_timestamp=has_timestamp,
            has_hidden_content=has_hidden_content,
            has_device_info=has_device_info,
            has_revision_history=has_revision_history,
            context=context,
        )

        # Inject ~5% random noise/flips to keep accuracy realistic for a demo
        if random.random() < 0.05:
            other_labels = [l for l in labels_pool if l != label]
            label = random.choice(other_labels)

        rows.append(
            {
                "has_gps": has_gps,
                "has_author_pii": has_author_pii,
                "has_timestamp": has_timestamp,
                "has_hidden_content": has_hidden_content,
                "has_device_info": has_device_info,
                "has_revision_history": has_revision_history,
                "context": context,
                "risk_level": label,
            }
        )

    df = pd.DataFrame(rows)

    if output_csv:
        output_path = Path(output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"Generated {len(df)} synthetic samples saved to: {output_path}")

    return df


if __name__ == "__main__":
    default_csv = Path(__file__).resolve().parent / "synthetic_risk_data.csv"
    generate_synthetic_data(num_samples=800, output_csv=str(default_csv))
