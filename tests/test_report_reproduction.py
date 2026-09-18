from __future__ import annotations

import pandas as pd
import pytest

from src.report_reproduction import (
    REPORT_TARGETS,
    assign_folds,
    candidate_feature_combinations,
    compare_with_report,
    evaluate_predictions,
    make_dashboard_payload,
    prepare_report_frame,
)


def _source_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "No": [1, 2, 3, 4],
            "Material": ["SeNPs", "Na2SeO3", "SeNPs", "SeNPs"],
            "Test": ["MTT", "MTT", "Western Blot", "MTT"],
            "Cell_Viability (%)": [50, 60, 70, None],
            "Time (hr)": [24, 24, 24, 24],
            "Concentration (ug/ml)": [78.96, 78.96, 78.96, 78.96],
        }
    )


def test_prepare_report_frame_records_inclusion_and_exclusion_reasons():
    included, excluded = prepare_report_frame(_source_frame())

    assert included["source_row"].tolist() == [2]
    assert included["Concentration_uM"].tolist() == [1.0]
    assert set(excluded["exclusion_reason"]) == {
        "非纳米硒材料",
        "非细胞存活率检测",
        "缺少建模必需字段",
    }


def test_assign_folds_is_stable_and_contains_three_folds():
    frame = pd.DataFrame({"sample_id": [f"sample-{i}" for i in range(12)]})

    first = assign_folds(frame, seed=42)
    second = assign_folds(frame, seed=42)

    assert first.tolist() == second.tolist()
    assert set(first) == {0, 1, 2}


def test_metrics_are_recomputed_from_predictions():
    predictions = pd.DataFrame(
        {
            "model": ["random_forest"] * 4,
            "feature_set": ["baseline"] * 4,
            "fold": [0, 1, 1, 2],
            "observed": [0.0, 1.0, 2.0, 3.0],
            "prediction": [0.0, 1.0, 1.0, 2.0],
        }
    )

    metrics = evaluate_predictions(predictions).iloc[0]

    assert metrics["mae"] == pytest.approx(0.5)
    assert metrics["r2"] == pytest.approx(0.6)
    assert metrics["metric_source"] == "逐样本预测重新计算"


def test_missing_predictions_cannot_be_replaced_by_report_targets():
    with pytest.raises(ValueError, match="逐样本预测"):
        evaluate_predictions(pd.DataFrame())


def test_report_comparison_keeps_target_and_computed_values_separate():
    computed = pd.DataFrame(
        [
            {
                "model": "xgboost",
                "feature_set": "enhanced",
                "mae": REPORT_TARGETS[("xgboost", "enhanced")]["mae"],
                "r2": REPORT_TARGETS[("xgboost", "enhanced")]["r2"],
            }
        ]
    )

    comparison = compare_with_report(computed)

    assert comparison["status"] == "partial"
    row = next(item for item in comparison["models"] if item["model"] == "xgboost" and item["feature_set"] == "enhanced")
    assert row["computed_mae"] == 7.196281
    assert row["target_mae"] == 7.196281
    assert row["status"] == "exact"


def test_five_candidates_produce_all_31_non_empty_combinations():
    combinations = candidate_feature_combinations()

    assert len(combinations) == 31
    assert len({tuple(item) for item in combinations}) == 31
    assert all(item for item in combinations)


def test_dashboard_payload_labels_report_values_as_targets():
    comparison = compare_with_report(pd.DataFrame())

    payload = make_dashboard_payload(
        audit={"included_rows": 434, "report_target_rows": 310},
        comparison=comparison,
    )

    assert payload["report_reproduction"]["status"] == "partial"
    assert payload["report_reproduction"]["values_are_computed"] is True
    assert payload["report_reproduction"]["report_values_are_targets_only"] is True
