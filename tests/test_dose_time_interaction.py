import subprocess
import sys

import pandas as pd

from scripts.run_dose_time_interaction import group_bootstrap_mae_delta

def test_dose_time_interaction_entrypoint_is_available():
    result = subprocess.run(
        [sys.executable, "scripts/run_dose_time_interaction.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "dose-time" in result.stdout


def test_group_bootstrap_mae_delta_pairs_rows_and_publication_groups():
    oof = pd.DataFrame(
        [
            {"row_index": 0, "model": "random_forest", "group_id": "g1", "observed": 1.0, "prediction": 1.0, "feature_set": "baseline"},
            {"row_index": 1, "model": "random_forest", "group_id": "g1", "observed": 2.0, "prediction": 2.0, "feature_set": "baseline"},
            {"row_index": 2, "model": "random_forest", "group_id": "g2", "observed": 3.0, "prediction": 3.0, "feature_set": "baseline"},
            {"row_index": 3, "model": "random_forest", "group_id": "g2", "observed": 4.0, "prediction": 4.0, "feature_set": "baseline"},
            {"row_index": 0, "model": "random_forest", "group_id": "g1", "observed": 1.0, "prediction": 2.0, "feature_set": "dose_time_interaction"},
            {"row_index": 1, "model": "random_forest", "group_id": "g1", "observed": 2.0, "prediction": 2.0, "feature_set": "dose_time_interaction"},
            {"row_index": 2, "model": "random_forest", "group_id": "g2", "observed": 3.0, "prediction": 2.0, "feature_set": "dose_time_interaction"},
            {"row_index": 3, "model": "random_forest", "group_id": "g2", "observed": 4.0, "prediction": 4.0, "feature_set": "dose_time_interaction"},
        ]
    )

    result = group_bootstrap_mae_delta(oof, "baseline", "dose_time_interaction", repetitions=100, seed=42)

    row = result.iloc[0]
    assert row["paired_rows"] == 4
    assert row["publication_groups"] == 2
    assert row["pooled_mae_delta"] == 0.5
