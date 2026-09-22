from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data import make_group_ids  # noqa: E402
from scripts.run_transfer_comparison import (  # noqa: E402
    COMMON_FEATURES,
    GENERAL_PATH,
    MODEL_NAMES,
    TARGET,
    _make_preprocessor,
    _make_random_forest,
    _make_xgboost,
    file_sha256,
    load_general_dataset,
)


RESULTS_DIR = ROOT / "results" / "general_benchmark"
MODELS_DIR = ROOT / "models" / "general_benchmark"


def _group_bootstrap_ci(oof: pd.DataFrame, repetitions: int = 5000, seed: int = 42) -> tuple[float, float, float, float]:
    grouped = oof.assign(
        absolute_error=(oof["observed"] - oof["prediction"]).abs(),
        squared_error=(oof["observed"] - oof["prediction"]) ** 2,
    ).groupby("group_id")[["absolute_error", "squared_error"]].mean()
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(grouped), size=(repetitions, len(grouped)))
    mae_draws = grouped["absolute_error"].to_numpy()[indices].mean(axis=1)
    rmse_draws = np.sqrt(grouped["squared_error"].to_numpy()[indices].mean(axis=1))
    return (
        float(np.quantile(mae_draws, 0.025)),
        float(np.quantile(mae_draws, 0.975)),
        float(np.quantile(rmse_draws, 0.025)),
        float(np.quantile(rmse_draws, 0.975)),
    )


def _fit_general_model(
    train_frame: pd.DataFrame,
    feature_columns: list[str],
    target: str,
    model_name: str,
    total_trees: int,
    seed: int,
) -> tuple[object, object, dict[str, object]]:
    if model_name not in MODEL_NAMES:
        raise ValueError(f"未知模型: {model_name}")
    if total_trees < 1:
        raise ValueError("total_trees 必须为正数")
    preprocessor, observed_features = _make_preprocessor(train_frame, feature_columns)
    preprocessor.fit(train_frame[observed_features])
    transformed = preprocessor.transform(train_frame[observed_features])
    if model_name == "random_forest":
        model = _make_random_forest(total_trees, seed)
    else:
        model = _make_xgboost(total_trees, seed)
    model.fit(transformed, train_frame[target].to_numpy(dtype=float))
    metadata = {
        "model": model_name,
        "features": observed_features,
        "total_trees": total_trees,
        "validation": "publication_grouped_outer_cv",
    }
    return preprocessor, model, metadata


def _evaluate_general_frame(
    frame: pd.DataFrame,
    target: str,
    group_column: str,
    feature_columns: list[str],
    outer_splits: int,
    total_trees: int,
    seed: int,
) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame, list[dict[str, object]]]:
    frame = frame.reset_index(drop=True).copy()
    groups = frame[group_column].astype(str).reset_index(drop=True)
    if groups.nunique() < outer_splits:
        raise ValueError("outer_splits 不能超过 publication groups 数量")
    splitter = GroupKFold(n_splits=outer_splits)
    oof_rows: list[dict[str, object]] = []
    fold_rows: list[dict[str, object]] = []
    metadata_rows: list[dict[str, object]] = []
    for fold, (train_idx, test_idx) in enumerate(splitter.split(frame, frame[target], groups)):
        train_frame = frame.iloc[train_idx].reset_index(drop=True)
        test_frame = frame.iloc[test_idx].reset_index(drop=True)
        for model_name in MODEL_NAMES:
            preprocessor, model, metadata = _fit_general_model(
                train_frame,
                feature_columns,
                target,
                model_name,
                total_trees,
                seed + fold,
            )
            prediction = np.asarray(model.predict(preprocessor.transform(test_frame[metadata["features"]])), dtype=float)
            observed = test_frame[target].to_numpy(dtype=float)
            fold_rows.append(
                {
                    "model": model_name,
                    "outer_fold": fold,
                    "n_train": len(train_frame),
                    "n_test": len(test_frame),
                    "n_test_groups": int(test_frame[group_column].nunique()),
                    "mae": mean_absolute_error(observed, prediction),
                    "rmse": mean_squared_error(observed, prediction) ** 0.5,
                    "r2": r2_score(observed, prediction),
                    "total_trees": total_trees,
                    "features": " | ".join(metadata["features"]),
                }
            )
            metadata_rows.append({"outer_fold": fold, **metadata})
            for row_index, group_id, observed_value, predicted_value in zip(
                test_idx, test_frame[group_column], observed, prediction
            ):
                oof_rows.append(
                    {
                        "row_index": int(row_index),
                        "group_id": str(group_id),
                        "outer_fold": fold,
                        "model": model_name,
                        "observed": float(observed_value),
                        "prediction": float(predicted_value),
                    }
                )

    oof = pd.DataFrame(oof_rows)
    folds = pd.DataFrame(fold_rows)
    metric_rows: list[dict[str, object]] = []
    for model_name, subset in oof.groupby("model", sort=True):
        observed = subset["observed"].to_numpy(dtype=float)
        prediction = subset["prediction"].to_numpy(dtype=float)
        mae_ci_low, mae_ci_high, rmse_ci_low, rmse_ci_high = _group_bootstrap_ci(subset, seed=seed + 1)
        fold_subset = folds[folds["model"].eq(model_name)]
        metric_rows.append(
            {
                "validation": "publication_grouped_outer_cv",
                "model": model_name,
                "n_oof": len(subset),
                "publication_groups": int(subset["group_id"].nunique()),
                "mae": mean_absolute_error(observed, prediction),
                "rmse": mean_squared_error(observed, prediction) ** 0.5,
                "r2": r2_score(observed, prediction),
                "mae_ci_low": mae_ci_low,
                "mae_ci_high": mae_ci_high,
                "rmse_ci_low": rmse_ci_low,
                "rmse_ci_high": rmse_ci_high,
                "fold_mae_sd": float(fold_subset["mae"].std(ddof=0)),
                "fold_rmse_sd": float(fold_subset["rmse"].std(ddof=0)),
                "fold_r2_sd": float(fold_subset["r2"].std(ddof=0)),
                "selected_features": " | ".join(sorted(fold_subset["features"].unique())),
            }
        )
    payload = {
        "validation": "publication_grouped_outer_cv",
        "design": {
            "outer_splits": outer_splits,
            "total_trees": total_trees,
            "features": feature_columns,
            "models": list(MODEL_NAMES),
        },
        "data": {
            "rows": len(frame),
            "publication_groups": int(groups.nunique()),
            "largest_group_rows": int(groups.value_counts().max()),
        },
        "metrics": metric_rows,
        "artifacts": {},
    }
    return payload, oof, folds, metadata_rows


def evaluate_general_frame(
    frame: pd.DataFrame,
    target: str = TARGET,
    group_column: str = "group_id",
    outer_splits: int = 5,
    total_trees: int = 500,
    seed: int = 42,
) -> dict[str, object]:
    """Evaluate a prepared General frame without writing repository artifacts."""

    return _evaluate_general_frame(
        frame,
        target=target,
        group_column=group_column,
        feature_columns=COMMON_FEATURES,
        outer_splits=outer_splits,
        total_trees=total_trees,
        seed=seed,
    )[0]


def run_general_benchmark(
    input_path: Path = GENERAL_PATH,
    output_dir: Path = RESULTS_DIR,
    models_dir: Path = MODELS_DIR,
    outer_splits: int = 5,
    total_trees: int = 500,
    seed: int = 42,
) -> dict[str, object]:
    general = load_general_dataset(input_path)
    general["group_id"] = make_group_ids(general)
    payload, oof, folds, metadata_rows = _evaluate_general_frame(
        general,
        target=TARGET,
        group_column="group_id",
        feature_columns=COMMON_FEATURES,
        outer_splits=outer_splits,
        total_trees=total_trees,
        seed=seed,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)
    folds.to_csv(output_dir / "fold_metrics.csv", index=False)
    oof.to_csv(output_dir / "oof_predictions.csv", index=False)
    general[["group_id"]].assign(row_index=np.arange(len(general))).to_csv(output_dir / "group_assignments.csv", index=False)
    pd.DataFrame(metadata_rows).to_json(output_dir / "fit_metadata.json", orient="records", force_ascii=False, indent=2)

    model_metadata: dict[str, object] = {}
    for model_name in MODEL_NAMES:
        preprocessor, model, metadata = _fit_general_model(
            general,
            COMMON_FEATURES,
            TARGET,
            model_name,
            total_trees,
            seed,
        )
        final_metadata = {
            **metadata,
            "fit_mode": "full_data",
            "validation": "full_data_fit_after_publication_grouped_outer_cv",
        }
        model_path = models_dir / f"{model_name}.joblib"
        joblib.dump({"preprocessor": preprocessor, "model": model, "metadata": final_metadata}, model_path)
        model_metadata[model_name] = {"path": model_path.relative_to(ROOT).as_posix(), **final_metadata}
    (models_dir / "metadata.json").write_text(json.dumps(model_metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    payload["data"]["input_sha256"] = file_sha256(input_path)
    payload["artifacts"] = {
        "metrics": "results/general_benchmark/metrics.csv",
        "fold_metrics": "results/general_benchmark/fold_metrics.csv",
        "oof_predictions": "results/general_benchmark/oof_predictions.csv",
        "group_assignments": "results/general_benchmark/group_assignments.csv",
        "fit_metadata": "results/general_benchmark/fit_metadata.json",
        "model_metadata": "models/general_benchmark/metadata.json",
    }
    pd.DataFrame(payload["metrics"]).to_csv(output_dir / "metrics.csv", index=False)
    (output_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the independent General nanotoxicity backbone benchmark.")
    parser.add_argument("--outer-splits", type=int, default=5)
    parser.add_argument("--total-trees", type=int, default=500)
    args = parser.parse_args(list(argv) if argv is not None else None)
    payload = run_general_benchmark(outer_splits=args.outer_splits, total_trees=args.total_trees)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
