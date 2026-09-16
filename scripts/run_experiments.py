from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data import add_derived_features, build_analysis_subset, feature_coverage, feature_groups, load_senp_dataset
from src.evaluation import fit_final_pipeline, run_nested_grouped_cv, write_evaluation_bundle


DATA_PATH = ROOT / "data" / "senp" / "senp_validation_dataset_final.csv"
RESULTS_DIR = ROOT / "results"
MODELS_DIR = ROOT / "models"
TARGET = "Cell_Viability (%)"
MODEL_NAMES = ("random_forest", "xgboost")


def candidate_feature_sets(name: str, groups: dict[str, list[str]]) -> list[list[str]]:
    baseline = groups["baseline"]
    chemistry = groups["chemistry_no_ic50"]
    extras = [column for column in chemistry if column not in baseline]
    if name == "baseline":
        return [baseline]
    if name == "chemistry_no_ic50":
        return [baseline] + [baseline + [column] for column in extras] + [chemistry]
    if name == "ic50_assisted":
        ic50 = groups["ic50_assisted"][-1]
        return [baseline, baseline + [ic50]] + [baseline + [column] for column in extras] + [chemistry, chemistry + [ic50]]
    raise ValueError(f"Unknown feature set: {name}")


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    return json.loads(frame.to_json(orient="records"))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the reproducible SeNP nested grouped-CV experiments.")
    parser.parse_args(argv)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    curated = load_senp_dataset(DATA_PATH)
    analysis = build_analysis_subset(curated)
    groups = feature_groups()
    all_metrics: list[pd.DataFrame] = []
    all_folds: list[pd.DataFrame] = []
    all_oof: list[pd.DataFrame] = []
    all_selection: list[pd.DataFrame] = []
    model_metadata: dict[str, object] = {}

    for feature_set_name, columns in groups.items():
        candidates = candidate_feature_sets(feature_set_name, groups)
        bundle = run_nested_grouped_cv(
            frame=analysis,
            feature_columns=columns,
            target=TARGET,
            groups=analysis["group_id"],
            model_names=MODEL_NAMES,
            outer_splits=5,
            inner_splits=3,
            seed=42,
            candidate_feature_sets=candidates,
            feature_set_name=feature_set_name,
        )
        write_evaluation_bundle(bundle, RESULTS_DIR, feature_set_name)
        all_metrics.append(bundle.metrics)
        all_folds.append(bundle.fold_metrics)
        all_oof.append(bundle.oof_predictions)
        all_selection.append(bundle.selection_log)

        for model_name in MODEL_NAMES:
            pipeline, metadata = fit_final_pipeline(
                frame=analysis,
                feature_columns=columns,
                target=TARGET,
                model_name=model_name,
                groups=analysis["group_id"],
                candidate_feature_sets=candidates,
                inner_splits=3,
                seed=42,
            )
            model_key = f"nested_{feature_set_name}_{model_name}"
            model_path = MODELS_DIR / f"{model_key}.joblib"
            joblib.dump(pipeline, model_path)
            model_metadata[model_key] = {
                "path": str(model_path.relative_to(ROOT)),
                "feature_set": feature_set_name,
                "target": TARGET,
                "validation": "publication_grouped_nested_cv",
                "n_rows": len(analysis),
                "n_groups": int(analysis["group_id"].nunique()),
                **metadata,
            }

    metrics = pd.concat(all_metrics, ignore_index=True)
    folds = pd.concat(all_folds, ignore_index=True)
    oof = pd.concat(all_oof, ignore_index=True)
    selection = pd.concat(all_selection, ignore_index=True)
    metrics.to_csv(RESULTS_DIR / "metrics.csv", index=False)
    folds.to_csv(RESULTS_DIR / "fold_metrics.csv", index=False)
    oof.to_csv(RESULTS_DIR / "oof_predictions.csv", index=False)
    selection.to_csv(RESULTS_DIR / "selection_log.csv", index=False)

    coverage = feature_coverage(analysis, groups)
    coverage.insert(0, "dataset", "mtt_analysis")
    curated_coverage = feature_coverage(add_derived_features(curated), groups)
    curated_coverage.insert(0, "dataset", "curated_senp")
    coverage = pd.concat([coverage, curated_coverage], ignore_index=True)
    coverage.to_csv(RESULTS_DIR / "feature_coverage.csv", index=False)

    model_metadata_path = MODELS_DIR / "nested_model_metadata.json"
    model_metadata_path.write_text(json.dumps(model_metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    dashboard = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "validation": "publication_grouped_nested_cv",
        "data": {
            "curated_senp_rows": len(curated),
            "analysis_mtt_rows": len(analysis),
            "publication_groups": int(analysis["group_id"].nunique()),
        },
        "metrics": _records(metrics),
        "coverage": _records(coverage),
        "oof": _records(oof),
        "artifacts": {
            "metrics": "results/metrics.csv",
            "fold_metrics": "results/fold_metrics.csv",
            "oof_predictions": "results/oof_predictions.csv",
            "feature_coverage": "results/feature_coverage.csv",
            "model_metadata": "models/nested_model_metadata.json",
        },
        "notes": [
            "主模型不使用 IC50。",
            "IC50-assisted 仅作为 response-correlated 辅助基准。",
            "当前数据不包含分子量、修饰物分类和新合成材料的前瞻性结果。",
        ],
    }
    (RESULTS_DIR / "dashboard.json").write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"rows": len(analysis), "groups": int(analysis["group_id"].nunique()), "metrics": len(metrics)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
