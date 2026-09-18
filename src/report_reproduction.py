from __future__ import annotations

import hashlib
import re
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder, StandardScaler
from xgboost import XGBRegressor


SEED = 42
REPORT_TARGETS = {
    ("random_forest", "baseline"): {"mae": 11.044676, "r2": 0.700973},
    ("random_forest", "enhanced"): {"mae": 7.627901, "r2": 0.914680},
    ("xgboost", "baseline"): {"mae": 9.868701, "r2": 0.750721},
    ("xgboost", "enhanced"): {"mae": 7.196281, "r2": 0.956696},
    ("tabtransformer", "baseline"): {"mae": 24.130409, "r2": 0.002994},
    ("tabtransformer", "enhanced"): {"mae": 25.495027, "r2": 0.056558},
}

REQUIRED_COLUMNS = ["Cell_Viability (%)", "Time (hr)", "Concentration (ug/ml)"]
EXCLUDED_TEST_PATTERN = r"Characterization|Western|Cellular Uptake|DNA|LDH"
CANDIDATE_FEATURES = [
    "IC50_uM",
    "Elemental_Se_wt",
    "Stability_weeks",
    "Binding_Energy_Se3d",
    "Crystal_Code",
]
BASE_NUMERIC = ["Log_Concentration", "Time_Log", "Diameter_nm", "Zeta_mV", "Size_Ratio"]
BASE_CATEGORICAL = ["Charge_Code", "Cell_Code", "Coat_Code", "Test_Code"]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_report_frame(source: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the filtering rules visible in the historical report script."""

    frame = source.copy()
    frame["source_row"] = np.arange(len(frame)) + 2
    for column in REQUIRED_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    material = frame["Material"].astype("string")
    is_selenium = material.str.contains("Se", case=False, regex=False, na=False)
    valid_material = is_selenium
    valid_test = ~frame["Test"].astype("string").str.contains(EXCLUDED_TEST_PATTERN, case=False, regex=True, na=False)
    complete = frame[REQUIRED_COLUMNS].notna().all(axis=1)

    reasons = np.select(
        [~valid_material, ~valid_test, ~complete],
        ["非纳米硒材料", "非细胞存活率检测", "缺少建模必需字段"],
        default="",
    )
    included = frame.loc[valid_material & valid_test & complete].copy()
    excluded = frame.loc[~(valid_material & valid_test & complete)].copy()
    excluded["exclusion_reason"] = pd.Series(reasons, index=frame.index).loc[excluded.index]

    included["Concentration_uM"] = included["Concentration (ug/ml)"] / 78.96
    included["sample_id"] = included["source_row"].map(lambda value: f"xlsx-row-{value}")
    return included.reset_index(drop=True), excluded.reset_index(drop=True)


def load_report_source(path: Path, sheet_name: str = "工作表1") -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    source = pd.read_excel(path, sheet_name=sheet_name)
    included, excluded = prepare_report_frame(source)
    metadata = {
        "input_path": path.as_posix(),
        "input_sha256": file_sha256(path),
        "sheet_name": sheet_name,
        "source_rows": int(len(source)),
        "included_rows": int(len(included)),
        "excluded_rows": int(len(excluded)),
    }
    return included, excluded, metadata


def _numeric_column(frame: pd.DataFrame, name: str, default: float = np.nan) -> pd.Series:
    if name not in frame:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[name], errors="coerce")


def _text_column(frame: pd.DataFrame, name: str) -> pd.Series:
    if name not in frame:
        return pd.Series("Unknown", index=frame.index, dtype="string")
    return frame[name].fillna("Unknown").astype(str)


def _extract_se_wt(value: object) -> float:
    if pd.isna(value):
        return np.nan
    match = re.search(r"Se\s+([0-9.]+)%", str(value))
    return float(match.group(1)) if match else np.nan


def engineer_historical_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Reproduce transformations visible in the archived 31-combination script."""

    out = frame.copy()
    out["Cell_Viability"] = _numeric_column(out, "Cell_Viability (%)")
    out["Time_hr"] = _numeric_column(out, "Time (hr)")
    out["Diameter_nm"] = _numeric_column(out, "Diameter (nm)")
    size = _numeric_column(out, "Size_in_Water (nm)")
    out["Size_in_Water_nm"] = size.fillna(out["Diameter_nm"] * 1.5)
    out["Zeta_mV"] = _numeric_column(out, "Zeta_in_Water (mV)").fillna(-15.0)
    out["IC50_uM"] = _numeric_column(out, "IC50 (µM)")
    if out["IC50_uM"].notna().any():
        out["IC50_uM"] = out["IC50_uM"].fillna(out["IC50_uM"].median())
    elemental = out.get("Elemental Composition (wt%)", pd.Series(np.nan, index=out.index)).map(_extract_se_wt)
    out["Elemental_Se_wt"] = elemental.fillna(elemental.median() if elemental.notna().any() else 0.0)
    out["Stability_weeks"] = _numeric_column(out, "Long-term Stability (weeks)").fillna(13.0)
    out["Binding_Energy_Se3d"] = _numeric_column(out, "Binding Energy Se3d (eV)").fillna(55.0)
    crystal = _text_column(out, "Crystallinity / Fringe Spacing (Å)")

    categorical = {
        "Charge_Code": _text_column(out, "Surface_Charge"),
        "Cell_Code": _text_column(out, "Cell_Type"),
        "Coat_Code": _text_column(out, "Coat/Functional Group"),
        "Test_Code": _text_column(out, "Test"),
        "Crystal_Code": crystal,
    }
    for output_name, values in categorical.items():
        out[output_name] = LabelEncoder().fit_transform(values)

    out["Log_Concentration"] = np.log1p(out["Concentration_uM"])
    out["Time_Log"] = np.log1p(out["Time_hr"])
    out["Size_Ratio"] = (out["Size_in_Water_nm"] / out["Diameter_nm"].replace(0, np.nan)).fillna(1.5)
    return out


def assign_folds(frame: pd.DataFrame, seed: int = SEED) -> pd.Series:
    folds = np.empty(len(frame), dtype=int)
    splitter = KFold(n_splits=3, shuffle=True, random_state=seed)
    for fold, (_, valid_index) in enumerate(splitter.split(frame)):
        folds[valid_index] = fold
    return pd.Series(folds, index=frame.index, name="fold")


def evaluate_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    required = {"model", "feature_set", "fold", "observed", "prediction"}
    if predictions.empty or not required.issubset(predictions.columns):
        raise ValueError("必须提供逐样本预测才能计算指标")
    rows: list[dict[str, object]] = []
    for (model, feature_set), group in predictions.groupby(["model", "feature_set"], sort=True):
        fold_mae = group.groupby("fold").apply(
            lambda part: mean_absolute_error(part["observed"], part["prediction"]),
            include_groups=False,
        )
        rows.append(
            {
                "model": model,
                "feature_set": feature_set,
                "n_predictions": int(len(group)),
                "mae": float(mean_absolute_error(group["observed"], group["prediction"])),
                "cv_mae_mean": float(fold_mae.mean()),
                "cv_mae_sd": float(fold_mae.std(ddof=0)),
                "r2": float(r2_score(group["observed"], group["prediction"])),
                "metric_source": "逐样本预测重新计算",
            }
        )
    return pd.DataFrame(rows)


def build_historical_matrix(frame: pd.DataFrame, added_features: list[str]) -> tuple[np.ndarray, list[str], dict[str, object]]:
    numeric = BASE_NUMERIC + [name for name in added_features if name != "Crystal_Code"]
    categorical = BASE_CATEGORICAL + (["Crystal_Code"] if "Crystal_Code" in added_features else [])
    numeric = [name for name in numeric if name in frame and frame[name].notna().any()]
    categorical = [name for name in categorical if name in frame]
    numeric_values = frame[numeric].to_numpy(dtype=float)
    keep = np.var(numeric_values, axis=0) > 1e-10
    numeric_values = numeric_values[:, keep]
    kept_numeric = [name for name, include in zip(numeric, keep) if include]
    scaler = StandardScaler().fit(numeric_values)
    scaled = scaler.transform(numeric_values)
    matrix = np.hstack([scaled, frame[categorical].to_numpy(dtype=float)])
    return matrix, kept_numeric + categorical, {
        "numeric_features": kept_numeric,
        "categorical_features": categorical,
        "scaler": scaler,
    }


def _make_regressor(model_name: str, seed: int):
    if model_name == "random_forest":
        return RandomForestRegressor(
            n_estimators=100,
            max_depth=8,
            min_samples_split=5,
            random_state=seed,
        )
    if model_name == "xgboost":
        return XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=seed,
            n_jobs=1,
        )
    raise ValueError(f"未知模型: {model_name}")


def run_tree_model(
    frame: pd.DataFrame,
    model_name: str,
    feature_set: str,
    added_features: list[str],
    seed: int = SEED,
) -> tuple[pd.DataFrame, dict[str, object], object]:
    matrix, columns, preprocessing = build_historical_matrix(frame, added_features)
    target = frame["Cell_Viability"].to_numpy(dtype=float)
    folds = assign_folds(frame, seed).to_numpy()
    rows: list[dict[str, object]] = []
    fold_mae: list[float] = []
    for fold in range(3):
        train_index = folds != fold
        valid_index = folds == fold
        model = _make_regressor(model_name, seed)
        model.fit(matrix[train_index], target[train_index])
        prediction = model.predict(matrix[valid_index])
        fold_mae.append(float(mean_absolute_error(target[valid_index], prediction)))
        for row_index, observed, predicted in zip(np.flatnonzero(valid_index), target[valid_index], prediction):
            rows.append(
                {
                    "row_index": int(row_index),
                    "sample_id": frame.iloc[row_index]["sample_id"],
                    "model": model_name,
                    "feature_set": feature_set,
                    "fold": fold,
                    "observed": float(observed),
                    "prediction": float(predicted),
                }
            )
    final_model = _make_regressor(model_name, seed)
    final_model.fit(matrix, target)
    fitted = final_model.predict(matrix)
    summary = {
        "model": model_name,
        "feature_set": feature_set,
        "n_rows": int(len(frame)),
        "features": columns,
        "cv_mae_mean": float(np.mean(fold_mae)),
        "cv_mae_sd": float(np.std(fold_mae, ddof=0)),
        "full_mae": float(mean_absolute_error(target, fitted)),
        "full_r2": float(r2_score(target, fitted)),
        "validation": "3-fold KFold; preprocessing fitted before folds as in historical script",
    }
    bundle = {"model": final_model, "preprocessing": preprocessing, "summary": summary}
    return pd.DataFrame(rows), summary, bundle


def search_feature_combinations(frame: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for selected in candidate_feature_combinations():
        _, summary, _ = run_tree_model(frame, "random_forest", "combination", selected, seed)
        rows.append(
            {
                "features": "+".join(selected),
                "feature_count": len(selected),
                "cv_mae_mean": summary["cv_mae_mean"],
                "cv_mae_sd": summary["cv_mae_sd"],
                "full_r2": summary["full_r2"],
            }
        )
    return pd.DataFrame(rows).sort_values(["cv_mae_mean", "features"], kind="stable").reset_index(drop=True)


def compare_with_report(computed: pd.DataFrame) -> dict[str, object]:
    keyed = {
        (str(row.model), str(row.feature_set)): row
        for row in computed.itertuples(index=False)
    }
    models: list[dict[str, object]] = []
    for (model, feature_set), target in REPORT_TARGETS.items():
        row = keyed.get((model, feature_set))
        computed_mae = None if row is None else float(getattr(row, "cv_mae_mean", getattr(row, "mae", np.nan)))
        computed_r2 = None if row is None else float(getattr(row, "full_r2", getattr(row, "r2", np.nan)))
        exact = (
            row is not None
            and round(computed_mae, 2) == round(target["mae"], 2)
            and round(computed_r2, 3) == round(target["r2"], 3)
        )
        models.append(
            {
                "model": model,
                "feature_set": feature_set,
                "target_mae": target["mae"],
                "target_r2": target["r2"],
                "computed_mae": computed_mae,
                "computed_r2": computed_r2,
                "mae_delta": None if row is None else computed_mae - target["mae"],
                "r2_delta": None if row is None else computed_r2 - target["r2"],
                "status": "exact" if exact else "missing" if row is None else "different",
            }
        )
    return {
        "status": "exact" if all(item["status"] == "exact" for item in models) else "partial",
        "models": models,
    }


def candidate_feature_combinations() -> list[list[str]]:
    return [
        list(group)
        for size in range(1, len(CANDIDATE_FEATURES) + 1)
        for group in combinations(CANDIDATE_FEATURES, size)
    ]


def make_dashboard_payload(audit: dict[str, object], comparison: dict[str, object]) -> dict[str, object]:
    return {
        "report_reproduction": {
            "status": comparison["status"],
            "values_are_computed": True,
            "report_values_are_targets_only": True,
            "audit": audit,
            "models": comparison["models"],
        }
    }
