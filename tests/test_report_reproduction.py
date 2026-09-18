from __future__ import annotations

import pandas as pd
import pytest

from scripts.run_improved_434 import group_bootstrap_improvements
from src.report_reproduction import (
    REPORT_TARGETS,
    assign_folds,
    candidate_feature_combinations,
    compare_with_report,
    engineer_historical_features,
    evaluate_predictions,
    make_dashboard_payload,
    prepare_improved_analysis,
    prepare_report_frame,
)


def _source_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "No": [1, 2, 3, 4],
            "Material": ["SeNPs", "Gold", "SeNPs", "SeNPs"],
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


def test_historical_material_filter_keeps_selenite_because_script_only_checks_se_text():
    source = _source_frame().iloc[[0]].copy()
    source["Material"] = "Na2SeO3"

    included, excluded = prepare_report_frame(source)

    assert len(included) == 1
    assert excluded.empty


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


def test_historical_feature_engineering_uses_documented_defaults():
    included, _ = prepare_report_frame(_source_frame())
    included["Diameter (nm)"] = 20.0
    included["Size_in_Water (nm)"] = None
    included["Zeta_in_Water (mV)"] = None
    included["IC50 (µM)"] = 5.0
    included["Elemental Composition (wt%)"] = "Se 82.5%"
    included["Long-term Stability (weeks)"] = None
    included["Binding Energy Se3d (eV)"] = None
    included["Crystallinity / Fringe Spacing (Å)"] = None
    included["Surface_Charge"] = None
    included["Cell_Type"] = "A549"
    included["Coat/Functional Group"] = None

    engineered = engineer_historical_features(included)

    assert engineered.loc[0, "Size_in_Water_nm"] == 30.0
    assert engineered.loc[0, "Zeta_mV"] == -15.0
    assert engineered.loc[0, "Elemental_Se_wt"] == 82.5
    assert engineered.loc[0, "Stability_weeks"] == 13.0
    assert engineered.loc[0, "Binding_Energy_Se3d"] == 55.0


def test_improved_analysis_coerces_raw_numeric_fields_and_builds_publication_groups():
    included, _ = prepare_report_frame(_source_frame())
    included["Article_ID"] = "article-1"
    included["DOI"] = "10.1000/example"
    included["Diameter (nm)"] = "20.5"
    included["Size_in_Water (nm)"] = None
    included["Size_in_Medium (nm)"] = None
    included["Zeta_in_Water (mV)"] = "-18.2"
    included["Zeta_in_Medium (mV)"] = None
    included["No_of_Cells (cells/well)"] = "10000"
    included["IC50 (µM)"] = "5.5"
    included["Binding Energy Se3d (eV)"] = "55.1"
    included["Long-term Stability (weeks)"] = "13"
    included["Crystallinity / Fringe Spacing (Å)"] = None
    included["Size Ratio"] = None
    included["Elemental Composition (wt%)"] = "Se 80%"
    included["Coat/Functional Group"] = "PVP"
    included["Synthesis_Method"] = "Chemical"
    included["Surface_Charge"] = "Negative"
    included["Cell_Type"] = "A549"
    included["Cell_Tissue"] = "Lung"
    included["Year"] = "2020"

    analysis = prepare_improved_analysis(included)

    assert analysis.loc[0, "zeta_final"] == -18.2
    assert analysis.loc[0, "IC50_uM"] == 5.5
    assert analysis.loc[0, "group_id"] == "doi:10.1000/example"


def test_improved_analysis_rejects_abstract_text_in_doi_column():
    included, _ = prepare_report_frame(_source_frame())
    included["Article_ID"] = "article-1"
    included["DOI"] = "This study investigates selenium nanoparticles."
    for column in [
        "Diameter (nm)", "Size_in_Water (nm)", "Size_in_Medium (nm)",
        "Zeta_in_Water (mV)", "Zeta_in_Medium (mV)", "No_of_Cells (cells/well)",
        "IC50 (µM)", "Binding Energy Se3d (eV)", "Long-term Stability (weeks)",
        "Crystallinity / Fringe Spacing (Å)", "Size Ratio", "Elemental Composition (wt%)",
    ]:
        included[column] = None
    for column in ["Coat/Functional Group", "Surface_Charge"]:
        included[column] = None

    analysis = prepare_improved_analysis(included)

    assert analysis.loc[0, "group_id"] == "article:article-1"


def test_improved_analysis_normalizes_mixed_categorical_values_to_strings():
    included, _ = prepare_report_frame(_source_frame())
    included["Surface_Charge"] = 12.5
    included["Article_ID"] = "article-1"
    included["DOI"] = None
    for column in [
        "Diameter (nm)", "Size_in_Water (nm)", "Size_in_Medium (nm)",
        "Zeta_in_Water (mV)", "Zeta_in_Medium (mV)", "No_of_Cells (cells/well)",
        "IC50 (µM)", "Binding Energy Se3d (eV)", "Long-term Stability (weeks)",
        "Crystallinity / Fringe Spacing (Å)", "Size Ratio", "Elemental Composition (wt%)",
    ]:
        included[column] = None
    included["Coat/Functional Group"] = None

    analysis = prepare_improved_analysis(included)

    assert analysis.loc[0, "Surface_Charge"] == "12.5"


def test_group_bootstrap_marks_only_consistent_error_reduction_as_improved():
    rows = []
    for feature_set, predictions in (
        ("baseline", [4.0, 5.0, 6.0, 7.0]),
        ("chemistry_no_ic50", [2.0, 3.0, 4.0, 5.0]),
        ("ic50_assisted", [4.0, 5.0, 6.0, 7.0]),
    ):
        for index, prediction in enumerate(predictions):
            rows.append(
                {
                    "row_index": index,
                    "model": "random_forest",
                    "feature_set": feature_set,
                    "group_id": f"paper-{index // 2}",
                    "observed": 0.0,
                    "prediction": prediction,
                }
            )
    oof = pd.DataFrame(rows)

    result = group_bootstrap_improvements(oof, repetitions=200, seed=42)
    chemistry = result[result["feature_set"].eq("chemistry_no_ic50")].iloc[0]

    assert chemistry["pooled_mae_delta"] == -2.0
    assert chemistry["group_bootstrap_ci_high"] < 0
    assert bool(chemistry["improved"]) is True
