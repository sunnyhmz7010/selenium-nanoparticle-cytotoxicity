"""完成 25、27、30：冻结模型推理、曲线阈值、排序和可复核的 Tree SHAP。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import platform
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from summarize_huvec_for_paper import CONCENTRATIONS, MATERIALS, TIMES, apparent_ic50

SOURCE = ROOT / "data/prospective/experimental_huvec_dose_time.csv"
MODEL = ROOT / "models/improved_434/baseline_random_forest.joblib"
METADATA = ROOT / "models/improved_434/metadata.json"
COAT_LABELS = {"CS": "Chitosan (CS)"}
SHAP_DOC = "https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html"
SE_MOLAR_MASS_G_MOL = 78.971
SE_MOLAR_MASS_SOURCE = "https://ciaaw.org/selenium.htm"


def concentration_scale(unit: str, molar_basis: str | None = None) -> float:
    """将明确计量基准的报告浓度换算为模型使用的 μg/mL。"""
    if unit == "ug_ml" and molar_basis is None:
        return 1.0
    if unit == "umol_l" and molar_basis == "Se":
        # μmol/L × g/mol = μg/L，再除以 1000 换成 μg/mL。
        return SE_MOLAR_MASS_G_MOL / 1000
    raise ValueError("μmol/L 的模型推理必须确认按元素 Se 计；其他基准需要另行核实")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def write_csv(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def read_experiments() -> tuple[list[dict], dict]:
    audit = json.loads((SOURCE.parent / "audit.json").read_text(encoding="utf-8"))
    if digest(SOURCE) != audit["csv_sha256"]:
        raise ValueError("实验 CSV 哈希与归档不符")
    if digest(SOURCE.parent / audit["source"]) != audit["source_sha256"]:
        raise ValueError("实验工作簿哈希与归档不符")
    with SOURCE.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    expected = {(m, t, c) for m in MATERIALS for t in TIMES for c in CONCENTRATIONS}
    keys = [(r["nanoparticle"], int(r["time_h"]), float(r["concentration_reported"])) for r in rows]
    if len(rows) != 351 or len(set(keys)) != 351 or set(keys) != expected:
        raise ValueError("实验条件必须完整且唯一：9×3×13=351")
    for row in rows:
        if row["cell_type"] != "HUVEC" or any(v == "" for v in row.values()):
            raise ValueError("实验字段缺失或细胞类型不符")
        if not all(math.isfinite(float(row[k])) for k in ("size_nm", "zeta_mV", "time_h", "concentration_reported", "viability_percent")):
            raise ValueError("实验字段存在非有限值")
    rows.sort(key=lambda r: (r["nanoparticle"], int(r["time_h"]), float(r["concentration_reported"])))
    return rows, audit


def curve_records(rows: list[dict], response: str) -> list[dict]:
    results = []
    for material in MATERIALS:
        for time in TIMES:
            points = [
                {"nanoparticle": material, "time_h": time,
                 "concentration_reported": float(r["concentration_reported"]),
                 "viability_percent": float(r[response])}
                for r in rows if r["nanoparticle"] == material and int(r["time_h"]) == time
            ]
            points.sort(key=lambda r: r["concentration_reported"])
            if len(points) != 13:
                raise ValueError("每条曲线必须保留 13 个报告浓度点")
            record = apparent_ic50(points)
            positive = [p for p in points if p["concentration_reported"] > 0]
            # 最低正浓度已经低于阈值时，不能在 log(0) 上插值或给出虚假精确值。
            if all(p["viability_percent"] < 50 for p in positive):
                record.update(status="below_tested_range", apparent_ic50_reported_scale="<0.25")
            value = record.pop("apparent_ic50_reported_scale")
            record["ic50_reported_scale"] = value if isinstance(value, (float, int)) else ""
            record["ic50_display"] = value
            record["control_viability_percent"] = points[0]["viability_percent"]
            record["local_viability_increases"] = sum(b["viability_percent"] > a["viability_percent"] for a, b in zip(points, points[1:]))
            record["method"] = "adjacent_positive_log10_interpolation_absolute_50_percent"
            results.append(record)
    return results


def build_inputs(rows: list[dict], scale: float, features: list[str]):
    import numpy as np
    import pandas as pd
    if any("ic50" in f.lower() or "viability" in f.lower() for f in features):
        raise ValueError("主预测输入禁止包含实测响应或 IC50")
    records = []
    for row in rows:
        size, zeta = float(row["size_nm"]), float(row["zeta_mV"])
        concentration, time = float(row["concentration_reported"]) * scale, int(row["time_h"])
        coat = row["nanoparticle"].removesuffix("-SeNPs")
        # 未提供的合成路线、年份和接种数量保持缺失，由已冻结预处理器处理。
        records.append({
            "Coat/Functional Group": COAT_LABELS.get(coat, coat),
            "Synthesis_Method": np.nan,
            "Surface_Charge": "Positive" if zeta > 0 else "Negative" if zeta < 0 else "Neutral",
            "Cell_Type": row["cell_type"], "Cell_Tissue": "Vascular endothelium",
            "Year": np.nan, "size_final": size, "zeta_final": zeta, "abs_zeta": abs(zeta),
            "Time (hr)": time, "Concentration (ug/ml)": concentration,
            "log_size": np.log1p(size), "log_time": np.log1p(time), "log_concentration": np.log1p(concentration),
            "No_of_Cells (cells/well)": np.nan, "zeta_missing": 0, "cell_count_missing": 1,
            "coat_missing": 0, "surface_charge_missing": 0,
        })
    frame = pd.DataFrame(records)[features]
    return frame


def shap_groups(names: list[str]) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = {}
    for index, name in enumerate(names):
        raw = name.split("__", 1)[1]
        if name.startswith("categorical__"):
            raw = next(f for f in ("Coat/Functional Group", "Synthesis_Method", "Surface_Charge", "Cell_Type", "Cell_Tissue") if raw.startswith(f + "_"))
        family = {
            "size_final": "Particle size", "log_size": "Particle size",
            "zeta_final": "Zeta potential", "abs_zeta": "Zeta potential", "zeta_missing": "Zeta potential",
            "Concentration (ug/ml)": "Concentration", "log_concentration": "Concentration",
            "Time (hr)": "Time", "log_time": "Time",
            "No_of_Cells (cells/well)": "Cell count", "cell_count_missing": "Cell count",
            "Coat/Functional Group": "Coating label", "coat_missing": "Coating label",
            "Surface_Charge": "Surface charge", "surface_charge_missing": "Surface charge",
            "Synthesis_Method": "Synthesis method", "Cell_Type": "Cell type", "Cell_Tissue": "Cell tissue",
            "Year": "Year",
        }[raw]
        groups.setdefault(family, []).append(index)
    if sorted(i for indices in groups.values() for i in indices) != list(range(len(names))):
        raise ValueError("SHAP 分组没有完整覆盖编码后的特征")
    return groups


def plot_shap(rows: list[dict], grouped, figures: Path, qa_scripts: Path) -> None:
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sys.path.insert(0, str(qa_scripts))
    from audit_panel_alignment import require_matplotlib_panel_alignment
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"], "font.size": 8,
        "axes.labelsize": 8, "axes.titlesize": 9, "xtick.labelsize": 7, "ytick.labelsize": 7,
        "pdf.fonttype": 42, "svg.fonttype": "none", "axes.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
    })
    figures.mkdir(parents=True, exist_ok=True)
    for family, column, label, filename in (
        ("Particle size", "size_nm", "Reported particle size (nm)", "shap_particle_size"),
        ("Zeta potential", "zeta_mV", "Reported zeta potential (mV)", "shap_zeta_potential"),
    ):
        fig, ax = plt.subplots(figsize=(180 / 25.4, 110 / 25.4))
        fig.subplots_adjust(left=0.16, right=0.96, bottom=0.24, top=0.85)
        x = np.array([float(r[column]) for r in rows])
        ax.scatter(x, grouped[family], color="#0072B2", s=10, alpha=0.45, edgecolors="none")
        ax.axhline(0, color="#888888", linewidth=0.6, linestyle=":", zorder=0)
        ax.set_xlabel(label)
        ax.set_ylabel("Grouped SHAP contribution\n(viability percentage points)")
        ax.set_title(f"Frozen Random Forest: {family.lower()}", pad=12)
        fig.text(0.16, 0.07, "351 conditions; 9 materials. Signed sum of derived-feature SHAP values.", fontsize=7)
        path = figures / filename
        require_matplotlib_panel_alignment(fig, json_out=str(path) + ".alignment.json", strict=True)
        fig.savefig(str(path) + ".pdf")
        fig.savefig(str(path) + ".svg")
        fig.savefig(str(path) + ".png", dpi=300)
        plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concentration-unit", choices=("ug_ml", "umol_l"))
    parser.add_argument("--molar-basis", choices=("Se",))
    parser.add_argument("--experiments-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qa-scripts", type=Path)
    args = parser.parse_args()
    if not args.experiments_only and (not args.concentration_unit or not args.qa_scripts):
        parser.error("正式推理必须明确浓度单位及 SHAP 图审计脚本目录")
    scale = None if args.experiments_only else concentration_scale(args.concentration_unit, args.molar_basis)
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("输出目录非空；请用新目录，避免覆盖已交付结果")
    output.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone(timedelta(hours=8))).isoformat()
    rows, source_audit = read_experiments()
    unit = {"ug_ml": "ug/mL", "umol_l": "umol/L"}.get(args.concentration_unit, "unconfirmed")
    experimental_ic50 = curve_records(rows, "viability_percent")
    for record in experimental_ic50:
        record["concentration_unit"] = unit
    write_csv(output / "experimental_ic50.csv", experimental_ic50)
    # 保留所有原始数值文本，另增明确的单位列，不改动原始归档。
    write_csv(output / "experimental_data.csv", [{**row, "concentration_unit": unit} for row in rows])
    audit = {
        "run_started_at": started, "timezone": "Asia/Shanghai", "source_csv_sha256": digest(SOURCE),
        "source_xlsx_sha256": source_audit["source_sha256"], "rows": len(rows), "curves": 27,
        "concentration_unit": unit, "original_header": source_audit["source_headers"][4],
        "unit_confirmation_basis": "user_confirmation_in_chat" if args.concentration_unit else "not_confirmed",
        "molar_concentration_basis": args.molar_basis,
        "experimental_ic50_status_counts": dict(Counter(r["status"] for r in experimental_ic50)),
        "replicate_status": source_audit["replicate_status"],
        "validation_design": "retrospective_external_inference; experimental_outcomes_already_available",
    }
    if args.experiments_only:
        write_json(output / "audit.json", audit)
        print(json.dumps(audit, ensure_ascii=False, indent=2))
        return 0

    import joblib
    import numpy as np
    import pandas as pd
    import shap
    import sklearn
    if sklearn.__version__ != "1.9.1":
        raise RuntimeError("模型归档使用 scikit-learn 1.9.1，请保持相同版本")
    model_hash = digest(MODEL)
    pipeline = joblib.load(MODEL)
    meta = json.loads(METADATA.read_text(encoding="utf-8"))["baseline_random_forest"]
    features = meta["selected_features"]
    frame = build_inputs(rows, scale, features)
    prediction = pipeline.predict(frame)
    if prediction.shape != (351,) or not np.isfinite(prediction).all():
        raise ValueError("预测必须为 351 个有限值")
    predicted_rows = [
        {"nanoparticle": r["nanoparticle"], "concentration_reported": r["concentration_reported"],
         "time_h": r["time_h"], "predicted_viability_percent": float(y), "concentration_unit": unit,
         "model_concentration_ug_ml": float(r["concentration_reported"]) * scale}
        for r, y in zip(rows, prediction)
    ]
    write_csv(output / "model_predictions.csv", predicted_rows)
    model_ic50 = curve_records(predicted_rows, "predicted_viability_percent")
    for record in model_ic50:
        value = record["ic50_reported_scale"]
        record["concentration_unit"] = unit
        record["ic50_ug_ml"] = value * scale if value != "" else ""
    write_csv(output / "model_ic50.csv", model_ic50)
    ranking = pd.DataFrame([r for r in predicted_rows if int(r["time_h"]) == 72 and float(r["concentration_reported"]) == 512])
    ranking["toxicity_rank"] = ranking["predicted_viability_percent"].rank(method="min", ascending=True).astype(int)
    ranking.sort_values(["predicted_viability_percent", "nanoparticle"]).to_csv(output / "toxicity_ranking_72h_512.csv", index=False, lineterminator="\n")
    keys = pd.DataFrame([{k: r[k] for k in ("nanoparticle", "concentration_reported", "time_h")} for r in rows])
    pd.concat([keys, frame], axis=1).to_csv(output / "model_inputs.csv", index=False, lineterminator="\n")

    preprocess, forest = pipeline.named_steps["preprocess"], pipeline.named_steps["model"]
    transformed = preprocess.transform(frame)
    names = list(preprocess.get_feature_names_out())
    if not np.isfinite(transformed).all() or not np.allclose(forest.predict(transformed), prediction, atol=1e-10, rtol=0):
        raise ValueError("编码输入不合法或与 Pipeline 预测不一致")
    # 使用模型内记录的训练路径样本数作为背景，不以新增实验响应构造背景。
    explainer = shap.TreeExplainer(forest, feature_perturbation="tree_path_dependent", model_output="raw", feature_names=names)
    values = np.asarray(explainer.shap_values(transformed, approximate=False, check_additivity=True))
    base = float(np.asarray(explainer.expected_value).reshape(-1)[0])
    if values.shape != transformed.shape or not np.isfinite(values).all():
        raise ValueError("SHAP 维度或有限性检查失败")
    reconstruction = base + values.sum(axis=1)
    residual = reconstruction - prediction
    if not np.allclose(reconstruction, prediction, atol=1e-6, rtol=0):
        raise ValueError("SHAP 加和无法重构正式预测")
    groups = shap_groups(names)
    grouped = pd.DataFrame({group: values[:, indices].sum(axis=1) for group, indices in groups.items()})
    if not np.allclose(grouped.sum(axis=1), values.sum(axis=1), atol=1e-10, rtol=0):
        raise ValueError("SHAP 分组聚合加和不一致")
    pd.concat([keys, pd.DataFrame(transformed, columns=names)], axis=1).to_csv(output / "transformed_inputs.csv", index=False, lineterminator="\n")
    pd.concat([keys, pd.DataFrame(values, columns=names)], axis=1).to_csv(output / "shap_encoded_values.csv", index=False, lineterminator="\n")
    pd.concat([keys, grouped], axis=1).to_csv(output / "shap_grouped_values.csv", index=False, lineterminator="\n")
    write_csv(output / "shap_additivity_check.csv", [
        {**key, "base_value": base, "prediction": float(y), "shap_reconstructed_prediction": float(s), "residual": float(e)}
        for key, y, s, e in zip(keys.to_dict("records"), prediction, reconstruction, residual)
    ])
    write_json(output / "shap_feature_groups.json", {group: [names[i] for i in indices] for group, indices in groups.items()})
    categorical = preprocess.named_transformers_["categorical"]
    columns = list(categorical.feature_names_in_)
    modes = categorical.named_steps["imputer"].statistics_
    categories = categorical.named_steps["onehot"].categories_
    unknown = {column: sorted({str(v) for v in frame[column].dropna() if v not in category}) for column, category in zip(columns, categories)}
    numeric = preprocess.named_transformers_["numeric"]
    imputations = {column: float(value) for column, value in zip(numeric.feature_names_in_, numeric.named_steps["imputer"].statistics_) if frame[column].isna().any()}
    imputations.update({column: str(value) for column, value in zip(columns, modes) if frame[column].isna().any()})
    audit.update({
        "model": meta["path"], "model_sha256": model_hash, "training_rows": meta["n_rows"], "training_groups": meta["n_groups"],
        "model_selection_basis": "baseline Random Forest selected from historical validation, without new experimental targets",
        "features": features, "transformed_feature_count": len(names), "training": "none; existing model and preprocessor reused",
        "dose_conversion_to_ug_ml_factor": scale,
        "dose_conversion_formula": "identity" if args.concentration_unit == "ug_ml" else "umol_Se_per_L * 78.971 / 1000",
        "molar_mass_g_mol": SE_MOLAR_MASS_G_MOL if args.molar_basis == "Se" else None,
        "molar_mass_source": SE_MOLAR_MASS_SOURCE if args.molar_basis == "Se" else None,
        "missing_input_imputations_from_frozen_model": imputations,
        "unknown_categories_encoded_as_all_zero": unknown,
        "feature_mapping": {"coating_label": "material name without -SeNPs; CS -> Chitosan (CS); LET kept unexpanded",
                            "cell_tissue": "HUVEC -> Vascular endothelium, matching historical HUVEC labels",
                            "surface_charge": "sign of reported zeta potential; Positive/Negative/Neutral",
                            "particle_size": "reported size used as size_final; measurement method/medium not supplied",
                            "zeta": "reported zeta used as zeta_final; measurement medium not supplied"},
        "modifier_category": "absent; coating labels are not Modifier Category",
        "molecular_weight": "absent; not imputed, fabricated or attributed",
        "model_ic50_status_counts": dict(Counter(r["status"] for r in model_ic50)),
        "predictions_min_max": [float(prediction.min()), float(prediction.max())],
        "prediction_clipping_or_monotonic_adjustment": "none; zero-concentration predictions not forced to 100",
        "shap": {"explainer": "TreeExplainer", "feature_perturbation": "tree_path_dependent", "model_output": "raw",
                 "background": "training path counts saved inside frozen trees", "approximate": False,
                 "base_value": base, "additivity_max_abs_residual": float(np.abs(residual).max()), "additivity_tolerance": 1e-6,
                 "aggregation": "signed sum across derived features and one-hot levels; all encoded columns retained", "documentation": SHAP_DOC},
        "software": {"python": platform.python_version(), **{p: importlib.metadata.version(p) for p in ("numpy", "pandas", "scikit-learn", "joblib", "shap", "matplotlib")}},
    })
    plot_shap(rows, grouped, output / "figures", args.qa_scripts)
    if digest(MODEL) != model_hash or digest(SOURCE) != source_audit["csv_sha256"]:
        raise ValueError("推理过程中模型或源实验文件发生变化")
    audit["run_finished_at"] = datetime.now(timezone(timedelta(hours=8))).isoformat()
    audit["outputs_sha256"] = {path.relative_to(output).as_posix(): digest(path) for path in sorted(output.rglob("*")) if path.is_file()}
    write_json(output / "audit.json", audit)
    print(json.dumps({key: audit[key] for key in ("rows", "curves", "concentration_unit", "model_sha256", "experimental_ic50_status_counts", "model_ic50_status_counts", "predictions_min_max", "shap")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
