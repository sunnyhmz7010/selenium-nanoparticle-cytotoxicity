from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data import feature_groups  # noqa: E402
from src.evaluation import fit_final_pipeline, run_nested_grouped_cv, write_evaluation_bundle  # noqa: E402
from src.report_reproduction import load_report_source, prepare_improved_analysis  # noqa: E402


INPUT_PATH = ROOT / "data" / "senp" / "纳米硒毒性预测验证集数据集.xlsx"
RESULTS_DIR = ROOT / "results" / "improved_434"
MODELS_DIR = ROOT / "models" / "improved_434"
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
    raise ValueError(f"未知特征组: {name}")


def group_bootstrap_improvements(oof: pd.DataFrame, repetitions: int = 5000, seed: int = 42) -> pd.DataFrame:
    baseline = oof[oof["feature_set"].eq("baseline")][["row_index", "model", "group_id", "observed", "prediction"]].copy()
    baseline["baseline_abs_error"] = (baseline["observed"] - baseline["prediction"]).abs()
    rows: list[dict[str, object]] = []
    rng = np.random.default_rng(seed)
    for feature_set in ("chemistry_no_ic50", "ic50_assisted"):
        variant = oof[oof["feature_set"].eq(feature_set)][["row_index", "model", "prediction"]].rename(columns={"prediction": "variant_prediction"})
        paired = baseline.merge(variant, on=["row_index", "model"], validate="one_to_one")
        paired["variant_abs_error"] = (paired["observed"] - paired["variant_prediction"]).abs()
        paired["delta"] = paired["variant_abs_error"] - paired["baseline_abs_error"]
        for model, model_rows in paired.groupby("model", sort=True):
            group_delta = model_rows.groupby("group_id")["delta"].mean().to_numpy()
            draws = rng.choice(group_delta, size=(repetitions, len(group_delta)), replace=True).mean(axis=1)
            rows.append(
                {
                    "model": model,
                    "feature_set": feature_set,
                    "paired_rows": int(len(model_rows)),
                    "publication_groups": int(len(group_delta)),
                    "pooled_mae_delta": float(model_rows["delta"].mean()),
                    "group_mean_mae_delta": float(group_delta.mean()),
                    "group_bootstrap_ci_low": float(np.quantile(draws, 0.025)),
                    "group_bootstrap_ci_high": float(np.quantile(draws, 0.975)),
                    "improved": bool(np.quantile(draws, 0.975) < 0),
                }
            )
    return pd.DataFrame(rows)


def records(frame: pd.DataFrame) -> list[dict[str, object]]:
    return json.loads(frame.to_json(orient="records"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run leakage-safe grouped nested-CV improvements on the 434-row report dataset.")
    parser.add_argument("--outer-splits", type=int, default=5)
    parser.add_argument("--inner-splits", type=int, default=3)
    args = parser.parse_args(argv)

    included, _, audit = load_report_source(INPUT_PATH)
    analysis = prepare_improved_analysis(included)
    if len(analysis) != 434:
        raise ValueError(f"改进实验数据应为434条，实际为{len(analysis)}条")
    groups = feature_groups()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    metric_frames: list[pd.DataFrame] = []
    fold_frames: list[pd.DataFrame] = []
    oof_frames: list[pd.DataFrame] = []
    selection_frames: list[pd.DataFrame] = []
    metadata: dict[str, object] = {}

    for feature_set, columns in groups.items():
        candidates = candidate_feature_sets(feature_set, groups)
        bundle = run_nested_grouped_cv(
            frame=analysis,
            feature_columns=columns,
            target=TARGET,
            groups=analysis["group_id"],
            model_names=MODEL_NAMES,
            outer_splits=args.outer_splits,
            inner_splits=args.inner_splits,
            seed=42,
            candidate_feature_sets=candidates,
            feature_set_name=feature_set,
        )
        write_evaluation_bundle(bundle, RESULTS_DIR, feature_set)
        metric_frames.append(bundle.metrics)
        fold_frames.append(bundle.fold_metrics)
        oof_frames.append(bundle.oof_predictions)
        selection_frames.append(bundle.selection_log)

        for model_name in MODEL_NAMES:
            pipeline, model_meta = fit_final_pipeline(
                frame=analysis,
                feature_columns=columns,
                target=TARGET,
                model_name=model_name,
                groups=analysis["group_id"],
                candidate_feature_sets=candidates,
                inner_splits=args.inner_splits,
                seed=42,
            )
            key = f"{feature_set}_{model_name}"
            path = MODELS_DIR / f"{key}.joblib"
            joblib.dump(pipeline, path)
            metadata[key] = {
                "path": path.relative_to(ROOT).as_posix(),
                "n_rows": len(analysis),
                "n_groups": int(analysis["group_id"].nunique()),
                "validation": "publication_grouped_nested_cv",
                **model_meta,
            }

    metrics = pd.concat(metric_frames, ignore_index=True)
    folds = pd.concat(fold_frames, ignore_index=True)
    oof = pd.concat(oof_frames, ignore_index=True)
    selection = pd.concat(selection_frames, ignore_index=True)
    improvements = group_bootstrap_improvements(oof)
    metrics.to_csv(RESULTS_DIR / "metrics.csv", index=False)
    folds.to_csv(RESULTS_DIR / "fold_metrics.csv", index=False)
    oof.to_csv(RESULTS_DIR / "oof_predictions.csv", index=False)
    selection.to_csv(RESULTS_DIR / "selection_log.csv", index=False)
    improvements.to_csv(RESULTS_DIR / "improvement_analysis.csv", index=False)
    analysis[["sample_id", "source_row", "group_id"]].to_csv(RESULTS_DIR / "group_assignments.csv", index=False)
    (MODELS_DIR / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = {
        "validation": "publication_grouped_nested_cv",
        "data": {
            "rows": len(analysis),
            "publication_groups": int(analysis["group_id"].nunique()),
            "largest_group_rows": int(analysis["group_id"].value_counts().max()),
            "input_sha256": audit["input_sha256"],
        },
        "metrics": records(metrics),
        "improvements": records(improvements),
        "artifacts": {
            "metrics": "results/improved_434/metrics.csv",
            "oof_predictions": "results/improved_434/oof_predictions.csv",
            "improvement_analysis": "results/improved_434/improvement_analysis.csv",
            "model_metadata": "models/improved_434/metadata.json",
        },
    }
    (RESULTS_DIR / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"rows": len(analysis), "groups": int(analysis["group_id"].nunique()), "metrics": records(metrics), "improvements": records(improvements)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
