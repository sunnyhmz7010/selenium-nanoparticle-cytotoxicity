import numpy as np
import pandas as pd

from scripts.run_general_benchmark import COMMON_FEATURES, _evaluate_general_frame, evaluate_general_frame


def _synthetic_general_frame() -> pd.DataFrame:
    rows = []
    for group in range(4):
        for row in range(3):
            rows.append(
                {
                    "group_id": f"doi:g{group}",
                    "target": float(group * 10 + row),
                    "numeric": float(row),
                    "category": f"c{row % 2}",
                }
            )
    frame = pd.DataFrame(rows)
    for column in COMMON_FEATURES:
        if column not in frame:
            frame[column] = np.nan
    frame["Year"] = np.arange(len(frame), dtype=float)
    frame["Concentration (ug/ml)"] = frame["numeric"] + 1.0
    frame["Time (hr)"] = 24.0
    frame["log_concentration"] = np.log1p(frame["Concentration (ug/ml)"])
    frame["log_time"] = np.log1p(frame["Time (hr)"])
    frame["category"] = frame["category"].astype("string")
    return frame


def test_general_benchmark_reports_grouped_oof_metrics_for_each_model():
    payload = evaluate_general_frame(
        _synthetic_general_frame(),
        target="target",
        group_column="group_id",
        outer_splits=2,
        total_trees=4,
        seed=42,
    )

    assert payload["validation"] == "publication_grouped_outer_cv"
    assert payload["data"]["rows"] == 12
    assert payload["data"]["publication_groups"] == 4
    assert {row["model"] for row in payload["metrics"]} == {"random_forest", "xgboost"}
    assert all(row["n_oof"] == 12 for row in payload["metrics"])
    assert payload["artifacts"] == {}


def test_general_benchmark_oof_covers_each_row_once_without_cross_fold_groups():
    frame = _synthetic_general_frame()
    _, oof, _, _ = _evaluate_general_frame(
        frame,
        target="target",
        group_column="group_id",
        feature_columns=COMMON_FEATURES,
        outer_splits=2,
        total_trees=4,
        seed=42,
    )

    assert len(oof) == len(frame) * 2
    assert oof.groupby(["model", "row_index"]).size().eq(1).all()
    assert oof.groupby(["model", "group_id"])["outer_fold"].nunique().max() == 1
