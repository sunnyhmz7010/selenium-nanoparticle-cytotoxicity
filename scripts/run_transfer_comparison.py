from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data import BASELINE_FEATURES  # noqa: E402
from src.report_reproduction import load_report_source, prepare_improved_analysis  # noqa: E402


SENP_PATH = ROOT / "data" / "senp" / "纳米硒毒性预测验证集数据集.xlsx"
GENERAL_PATH = ROOT / "data" / "benchmark" / "d0en01240h1.xlsx"
RESULTS_DIR = ROOT / "results" / "transfer_comparison"
TARGET = "Cell_Viability (%)"
COMMON_FEATURES = BASELINE_FEATURES.copy()
MODEL_NAMES = ("random_forest", "xgboost")
STRATEGIES = ("senp_only", "general_zero_shot", "general_to_senp")
MISSING_MARKERS = ["NA", "N/A", "--", "-", "", "None", "nan"]
NUMERIC_COLUMNS = [
    "Year",
    "Diameter (nm)",
    "Size_in_Water (nm)",
    "Size_in_Medium (nm)",
    "Zeta_in_Water (mV)",
    "Zeta_in_Medium (mV)",
    "No_of_Cells (cells/well)",
    "Time (hr)",
    "Concentration (ug/ml)",
    TARGET,
]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_common_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Create the shared baseline features without fitting any data-dependent transform."""

    out = frame.copy()
    out = out.replace(MISSING_MARKERS, np.nan)
    for column in NUMERIC_COLUMNS:
        if column in out:
            out[column] = pd.to_numeric(out[column], errors="coerce")
        else:
            out[column] = np.nan
    for column in COMMON_FEATURES:
        if column not in out:
            out[column] = np.nan

    out["size_final"] = out["Diameter (nm)"].fillna(out["Size_in_Water (nm)"]).fillna(out["Size_in_Medium (nm)"])
    out["zeta_final"] = out["Zeta_in_Water (mV)"].fillna(out["Zeta_in_Medium (mV)"])
    out["abs_zeta"] = out["zeta_final"].abs()
    out["log_size"] = np.log1p(out["size_final"])
    out["log_time"] = np.log1p(out["Time (hr)"])
    out["log_concentration"] = np.log1p(out["Concentration (ug/ml)"])
    out["zeta_missing"] = out["zeta_final"].isna().astype(int)
    out["cell_count_missing"] = out["No_of_Cells (cells/well)"].isna().astype(int)
    out["coat_missing"] = out["Coat/Functional Group"].isna().astype(int)
    out["surface_charge_missing"] = out["Surface_Charge"].isna().astype(int)
    return out


def load_general_dataset(path: Path = GENERAL_PATH) -> pd.DataFrame:
    source = pd.read_excel(path, sheet_name="Viability")
    frame = prepare_common_frame(source)
    material = frame["Material"].astype("string") if "Material" in frame else pd.Series("", index=frame.index, dtype="string")
    selenium_rows = material.str.contains("selenium|\bse(?:np)?\b", case=False, regex=True, na=False)
    if selenium_rows.any():
        raise ValueError("通用数据集包含Se材料，无法作为独立预训练集")
    valid = frame[TARGET].notna() & frame["Time (hr)"].notna() & frame["Concentration (ug/ml)"].notna()
    return frame.loc[valid].reset_index(drop=True)


def _observed_features(frame: pd.DataFrame, feature_columns: list[str]) -> list[str]:
    return [column for column in feature_columns if frame[column].notna().any()]


def _make_preprocessor(frame: pd.DataFrame, feature_columns: list[str]) -> tuple[ColumnTransformer, list[str]]:
    observed = _observed_features(frame, feature_columns)
    numeric = [column for column in observed if pd.api.types.is_numeric_dtype(frame[column])]
    categorical = [column for column in observed if column not in numeric]
    transformers = []
    if numeric:
        transformers.append(("numeric", Pipeline([("imputer", SimpleImputer(strategy="median"))]), numeric))
    if categorical:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                categorical,
            )
        )
    if not transformers:
        raise ValueError("迁移实验没有可用特征")
    return ColumnTransformer(transformers=transformers, remainder="drop"), observed


def _make_random_forest(n_estimators: int, seed: int, warm_start: bool = False) -> RandomForestRegressor:
    return RandomForestRegressor(
        n_estimators=n_estimators,
        min_samples_leaf=2,
        random_state=seed,
        n_jobs=1,
        warm_start=warm_start,
    )


def _make_xgboost(n_estimators: int, seed: int) -> XGBRegressor:
    return XGBRegressor(
        n_estimators=n_estimators,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        objective="reg:squarederror",
        eval_metric="mae",
        tree_method="hist",
        random_state=seed,
        n_jobs=1,
    )


def fit_strategy(
    general_frame: pd.DataFrame,
    senp_frame: pd.DataFrame,
    feature_columns: list[str],
    target: str,
    model_name: str,
    strategy: str,
    total_trees: int = 500,
    seed: int = 42,
) -> tuple[ColumnTransformer, object, dict[str, object]]:
    """Fit one fixed-budget strategy and return its preprocessing and model."""

    if strategy not in STRATEGIES:
        raise ValueError(f"未知迁移策略: {strategy}")
    if model_name not in MODEL_NAMES:
        raise ValueError(f"未知模型: {model_name}")
    if total_trees < 2:
        raise ValueError("total_trees 必须至少为2")

    if strategy == "senp_only":
        fit_frame = senp_frame
    elif strategy == "general_zero_shot":
        fit_frame = general_frame
    else:
        fit_frame = pd.concat([general_frame, senp_frame], ignore_index=True)
    preprocessor, observed_features = _make_preprocessor(fit_frame, feature_columns)
    preprocessor.fit(fit_frame[observed_features])
    x_general = preprocessor.transform(general_frame[observed_features])
    x_senp = preprocessor.transform(senp_frame[observed_features])
    y_general = general_frame[target].to_numpy(dtype=float)
    y_senp = senp_frame[target].to_numpy(dtype=float)
    half = total_trees // 2
    metadata: dict[str, object] = {
        "strategy": strategy,
        "model": model_name,
        "features": observed_features,
        "total_trees": total_trees,
        "pretrained_trees": 0,
        "finetune_trees": 0,
    }

    if model_name == "random_forest":
        if strategy == "senp_only":
            model = _make_random_forest(total_trees, seed)
            model.fit(x_senp, y_senp)
        elif strategy == "general_zero_shot":
            model = _make_random_forest(total_trees, seed)
            model.fit(x_general, y_general)
        else:
            model = _make_random_forest(half, seed, warm_start=True)
            model.fit(x_general, y_general)
            model.set_params(n_estimators=total_trees)
            model.fit(x_senp, y_senp)
            metadata["pretrained_trees"] = half
            metadata["finetune_trees"] = total_trees - half
    else:
        if strategy == "senp_only":
            model = _make_xgboost(total_trees, seed)
            model.fit(x_senp, y_senp)
        elif strategy == "general_zero_shot":
            model = _make_xgboost(total_trees, seed)
            model.fit(x_general, y_general)
        else:
            pretrained = _make_xgboost(half, seed)
            pretrained.fit(x_general, y_general)
            model = _make_xgboost(total_trees - half, seed)
            model.fit(x_senp, y_senp, xgb_model=pretrained.get_booster())
            metadata["pretrained_trees"] = half
            metadata["finetune_trees"] = total_trees - half
    if model_name == "random_forest":
        metadata["fitted_trees"] = len(model.estimators_)
    else:
        metadata["fitted_trees"] = int(model.get_booster().num_boosted_rounds())
    return preprocessor, model, metadata


def _predict(preprocessor: ColumnTransformer, model: object, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    return np.asarray(model.predict(preprocessor.transform(frame[features])), dtype=float)


def group_bootstrap_deltas(oof: pd.DataFrame, repetitions: int = 5000, seed: int = 42) -> pd.DataFrame:
    baseline = oof[oof["strategy"].eq("senp_only")][["row_index", "model", "group_id", "observed", "prediction"]].copy()
    baseline["baseline_abs_error"] = (baseline["observed"] - baseline["prediction"]).abs()
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for strategy in ("general_zero_shot", "general_to_senp"):
        variant = oof[oof["strategy"].eq(strategy)][["row_index", "model", "prediction"]].rename(columns={"prediction": "variant_prediction"})
        paired = baseline.merge(variant, on=["row_index", "model"], validate="one_to_one")
        paired["variant_abs_error"] = (paired["observed"] - paired["variant_prediction"]).abs()
        paired["delta"] = paired["variant_abs_error"] - paired["baseline_abs_error"]
        for model_name, model_rows in paired.groupby("model", sort=True):
            group_delta = model_rows.groupby("group_id")["delta"].mean().to_numpy()
            draws = rng.choice(group_delta, size=(repetitions, len(group_delta)), replace=True).mean(axis=1)
            rows.append(
                {
                    "model": model_name,
                    "strategy": strategy,
                    "paired_rows": int(len(model_rows)),
                    "publication_groups": int(len(group_delta)),
                    "pooled_mae_delta": float(model_rows["delta"].mean()),
                    "group_bootstrap_ci_low": float(np.quantile(draws, 0.025)),
                    "group_bootstrap_ci_high": float(np.quantile(draws, 0.975)),
                    "improved": bool(np.quantile(draws, 0.975) < 0),
                }
            )
    return pd.DataFrame(rows)


def _load_senp(path: Path = SENP_PATH) -> tuple[pd.DataFrame, dict[str, object]]:
    included, _, audit = load_report_source(path)
    prepared = prepare_improved_analysis(included)
    frame = prepare_common_frame(prepared)
    frame["group_id"] = prepared["group_id"].astype(str).to_numpy()
    return frame, audit


def run_transfer_comparison(
    senp_path: Path = SENP_PATH,
    general_path: Path = GENERAL_PATH,
    outer_splits: int = 5,
    total_trees: int = 500,
    seed: int = 42,
) -> dict[str, object]:
    senp, senp_audit = _load_senp(senp_path)
    general = load_general_dataset(general_path)
    if len(senp) != 434 or senp["group_id"].nunique() != 24:
        raise ValueError(f"SeNP 数据契约不匹配: rows={len(senp)}, groups={senp['group_id'].nunique()}")
    if len(general) == 0:
        raise ValueError("通用预训练数据为空")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    splitter = GroupKFold(n_splits=outer_splits)
    oof_rows: list[dict[str, object]] = []
    fold_rows: list[dict[str, object]] = []
    metadata_rows: list[dict[str, object]] = []
    groups = senp["group_id"].astype(str)
    for fold, (train_idx, test_idx) in enumerate(splitter.split(senp, senp[TARGET], groups)):
        train_senp = senp.iloc[train_idx].reset_index(drop=True)
        test_senp = senp.iloc[test_idx].reset_index(drop=True)
        for model_name in MODEL_NAMES:
            for strategy in STRATEGIES:
                preprocessor, model, metadata = fit_strategy(
                    general,
                    train_senp,
                    COMMON_FEATURES,
                    TARGET,
                    model_name,
                    strategy,
                    total_trees=total_trees,
                    seed=seed + fold,
                )
                prediction = _predict(preprocessor, model, test_senp, metadata["features"])
                observed = test_senp[TARGET].to_numpy(dtype=float)
                fold_rows.append(
                    {
                        "model": model_name,
                        "strategy": strategy,
                        "outer_fold": fold,
                        "n_train_senp": len(train_senp),
                        "n_test": len(test_senp),
                        "n_test_groups": int(test_senp["group_id"].nunique()),
                        "mae": mean_absolute_error(observed, prediction),
                        "rmse": mean_squared_error(observed, prediction) ** 0.5,
                        "r2": r2_score(observed, prediction),
                        "pretrained_trees": metadata["pretrained_trees"],
                        "finetune_trees": metadata["finetune_trees"],
                        "total_trees": metadata["total_trees"],
                        "features": " | ".join(metadata["features"]),
                    }
                )
                metadata_rows.append({"outer_fold": fold, **metadata})
                for row_index, group_id, observed_value, predicted_value in zip(test_idx, test_senp["group_id"], observed, prediction):
                    oof_rows.append(
                        {
                            "row_index": int(row_index),
                            "group_id": group_id,
                            "outer_fold": fold,
                            "model": model_name,
                            "strategy": strategy,
                            "observed": float(observed_value),
                            "prediction": float(predicted_value),
                        }
                    )

    oof = pd.DataFrame(oof_rows)
    folds = pd.DataFrame(fold_rows)
    metric_rows: list[dict[str, object]] = []
    for (model_name, strategy), subset in oof.groupby(["model", "strategy"], sort=True):
        observed = subset["observed"].to_numpy()
        prediction = subset["prediction"].to_numpy()
        fold_subset = folds[(folds["model"] == model_name) & (folds["strategy"] == strategy)]
        metric_rows.append(
            {
                "validation": "publication_grouped_outer_cv",
                "model": model_name,
                "strategy": strategy,
                "n_oof": len(subset),
                "publication_groups": int(subset["group_id"].nunique()),
                "mae": mean_absolute_error(observed, prediction),
                "rmse": mean_squared_error(observed, prediction) ** 0.5,
                "r2": r2_score(observed, prediction),
                "fold_mae_sd": float(fold_subset["mae"].std(ddof=0)),
                "fold_rmse_sd": float(fold_subset["rmse"].std(ddof=0)),
                "fold_r2_sd": float(fold_subset["r2"].std(ddof=0)),
            }
        )
    metrics = pd.DataFrame(metric_rows)
    improvements = group_bootstrap_deltas(oof, seed=seed)
    folds.to_csv(RESULTS_DIR / "fold_metrics.csv", index=False)
    metrics.to_csv(RESULTS_DIR / "metrics.csv", index=False)
    oof.to_csv(RESULTS_DIR / "oof_predictions.csv", index=False)
    improvements.to_csv(RESULTS_DIR / "improvement_analysis.csv", index=False)
    pd.DataFrame(metadata_rows).to_json(RESULTS_DIR / "fit_metadata.json", orient="records", force_ascii=False, indent=2)
    (RESULTS_DIR / "group_assignments.csv").write_text(senp[["sample_id", "group_id"]].to_csv(index=False), encoding="utf-8")
    payload = {
        "design": {
            "validation": "publication_grouped_outer_cv",
            "outer_splits": outer_splits,
            "total_trees": total_trees,
            "pretrained_trees": total_trees // 2,
            "finetune_trees": total_trees - total_trees // 2,
            "features": COMMON_FEATURES,
            "strategies": STRATEGIES,
        },
        "data": {
            "senp_rows": len(senp),
            "senp_publication_groups": int(senp["group_id"].nunique()),
            "general_rows": len(general),
            "senp_input_sha256": senp_audit["input_sha256"],
            "general_input_sha256": file_sha256(general_path),
        },
        "metrics": metrics.to_dict(orient="records"),
        "improvements": improvements.to_dict(orient="records"),
    }
    (RESULTS_DIR / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare SeNP-only, General zero-shot and General-to-SeNP transfer under publication-grouped CV.")
    parser.add_argument("--outer-splits", type=int, default=5)
    parser.add_argument("--total-trees", type=int, default=500)
    args = parser.parse_args(list(argv) if argv is not None else None)
    payload = run_transfer_comparison(outer_splits=args.outer_splits, total_trees=args.total_trees)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
