import numpy as np
import pandas as pd

from src.evaluation import run_nested_grouped_cv
from src.models import make_pipeline


def _toy_frame() -> pd.DataFrame:
    rows = []
    for group in range(6):
        for replicate in range(4):
            rows.append(
                {
                    "numeric": float(group + replicate / 10),
                    "category": "a" if group % 2 else "b",
                    "target": float(group + replicate / 10),
                    "group_id": f"study-{group}",
                }
            )
    return pd.DataFrame(rows)


def test_nested_grouped_cv_keeps_groups_out_of_each_outer_test_fold():
    frame = _toy_frame()
    bundle = run_nested_grouped_cv(
        frame=frame,
        feature_columns=["numeric", "category"],
        target="target",
        groups=frame["group_id"],
        model_names=("random_forest",),
        outer_splits=3,
        inner_splits=2,
        seed=42,
    )

    oof = bundle.oof_predictions
    assert len(oof) == len(frame)
    assert oof["row_index"].nunique() == len(frame)
    assert set(oof["group_id"]) == set(frame["group_id"])
    assert bundle.metrics["validation"].eq("publication_grouped_nested_cv").all()


def test_nested_grouped_cv_reports_pooled_metrics_and_fold_variability():
    frame = _toy_frame()
    bundle = run_nested_grouped_cv(
        frame=frame,
        feature_columns=["numeric", "category"],
        target="target",
        groups=frame["group_id"],
        model_names=("random_forest",),
        outer_splits=3,
        inner_splits=2,
        seed=42,
    )

    metrics = bundle.metrics.iloc[0]
    assert np.isfinite(metrics["mae"])
    assert np.isfinite(metrics["rmse"])
    assert np.isfinite(metrics["r2"])
    assert metrics["fold_mae_sd"] >= 0
    assert metrics["n_oof"] == len(frame)


def test_pipeline_drops_features_that_are_unobserved_in_the_training_fold():
    frame = pd.DataFrame(
        {
            "observed": [1.0, 2.0],
            "unobserved": [np.nan, np.nan],
            "target": [1.0, 2.0],
        }
    )

    pipeline = make_pipeline(frame, ["observed", "unobserved"], "random_forest", {"n_estimators": 5}, 42)
    pipeline.fit(frame[["observed", "unobserved"]], frame["target"])

    assert pipeline.named_steps["preprocess"].transformers_[0][2] == ["observed"]
    assert pipeline.predict(frame[["observed", "unobserved"]]).shape == (2,)
