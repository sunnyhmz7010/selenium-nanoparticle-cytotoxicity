from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data import feature_groups  # noqa: E402
from src.evaluation import run_nested_grouped_cv, write_evaluation_bundle  # noqa: E402
from src.report_reproduction import load_report_source, prepare_improved_analysis  # noqa: E402


INPUT_PATH = ROOT / "data" / "senp" / "纳米硒毒性预测验证集数据集.xlsx"
RESULTS_DIR = ROOT / "results" / "dose_time_interaction"
TARGET = "Cell_Viability (%)"
MODEL_NAMES = ("random_forest", "xgboost")


def _records(frame: pd.DataFrame) -> list[dict[str, object]]:
    return json.loads(frame.to_json(orient="records"))


def group_bootstrap_mae_delta(
    oof: pd.DataFrame,
    baseline_feature_set: str,
    variant_feature_set: str,
    repetitions: int = 5000,
    seed: int = 42,
) -> pd.DataFrame:
    """Compare paired absolute errors by publication group."""

    baseline = oof[oof["feature_set"].eq(baseline_feature_set)][
        ["row_index", "model", "group_id", "observed", "prediction"]
    ].copy()
    baseline["baseline_abs_error"] = (baseline["observed"] - baseline["prediction"]).abs()
    variant = oof[oof["feature_set"].eq(variant_feature_set)][
        ["row_index", "model", "prediction"]
    ].rename(columns={"prediction": "variant_prediction"})
    paired = baseline.merge(variant, on=["row_index", "model"], validate="one_to_one")
    paired["variant_abs_error"] = (paired["observed"] - paired["variant_prediction"]).abs()
    paired["delta"] = paired["variant_abs_error"] - paired["baseline_abs_error"]

    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for model, model_rows in paired.groupby("model", sort=True):
        group_delta = model_rows.groupby("group_id")["delta"].mean().to_numpy()
        draws = rng.choice(group_delta, size=(repetitions, len(group_delta)), replace=True).mean(axis=1)
        rows.append(
            {
                "model": model,
                "baseline_feature_set": baseline_feature_set,
                "variant_feature_set": variant_feature_set,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare SeNP baseline and explicit dose-time interaction under grouped nested CV."
    )
    parser.add_argument("--outer-splits", type=int, default=5)
    parser.add_argument("--inner-splits", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args(argv)

    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    included, _, audit = load_report_source(INPUT_PATH)
    analysis = prepare_improved_analysis(included)
    if len(analysis) != 434:
        raise ValueError(f"改进实验数据应为434条，实际为{len(analysis)}条")

    groups = feature_groups()
    feature_sets = {
        "baseline": groups["baseline"],
        "dose_time_interaction": groups["baseline"] + ["dose_time_interaction"],
    }
    output_dir.mkdir(parents=True, exist_ok=True)

    metric_frames: list[pd.DataFrame] = []
    fold_frames: list[pd.DataFrame] = []
    oof_frames: list[pd.DataFrame] = []
    selection_frames: list[pd.DataFrame] = []
    for feature_set_name, columns in feature_sets.items():
        bundle = run_nested_grouped_cv(
            frame=analysis,
            feature_columns=columns,
            target=TARGET,
            groups=analysis["group_id"],
            model_names=MODEL_NAMES,
            outer_splits=args.outer_splits,
            inner_splits=args.inner_splits,
            seed=42,
            candidate_feature_sets=[columns],
            feature_set_name=feature_set_name,
        )
        write_evaluation_bundle(bundle, output_dir, feature_set_name)
        metric_frames.append(bundle.metrics)
        fold_frames.append(bundle.fold_metrics)
        oof_frames.append(bundle.oof_predictions)
        selection_frames.append(bundle.selection_log)

    metrics = pd.concat(metric_frames, ignore_index=True)
    folds = pd.concat(fold_frames, ignore_index=True)
    oof = pd.concat(oof_frames, ignore_index=True)
    selection = pd.concat(selection_frames, ignore_index=True)
    improvements = group_bootstrap_mae_delta(oof, "baseline", "dose_time_interaction")
    metrics.to_csv(output_dir / "metrics.csv", index=False)
    folds.to_csv(output_dir / "fold_metrics.csv", index=False)
    oof.to_csv(output_dir / "oof_predictions.csv", index=False)
    selection.to_csv(output_dir / "selection_log.csv", index=False)
    improvements.to_csv(output_dir / "improvement_analysis.csv", index=False)
    analysis[["sample_id", "source_row", "group_id"]].to_csv(output_dir / "group_assignments.csv", index=False)

    artifact_prefix = output_dir.relative_to(ROOT).as_posix()
    payload = {
        "validation": "publication_grouped_nested_cv",
        "comparison": "baseline_vs_explicit_log_dose_time_interaction",
        "data": {
            "rows": len(analysis),
            "publication_groups": int(analysis["group_id"].nunique()),
            "input_sha256": audit["input_sha256"],
        },
        "metrics": _records(metrics),
        "improvements": _records(improvements),
        "artifacts": {
            "metrics": f"{artifact_prefix}/metrics.csv",
            "oof_predictions": f"{artifact_prefix}/oof_predictions.csv",
            "improvement_analysis": f"{artifact_prefix}/improvement_analysis.csv",
        },
    }
    (output_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
