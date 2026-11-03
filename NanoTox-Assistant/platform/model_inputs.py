"""复用 research/scripts/run_huvec_external.py 的冻结模型输入与解释分组。"""


COAT_LABELS = {"CS": "Chitosan (CS)"}


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
        # 本工作台对应HUVEC实验，最终源表接种密度为2300/孔。
        cells = float(row.get("cells_per_well", 2300))
        records.append({
            "Coat/Functional Group": COAT_LABELS.get(coat, coat),
            "Synthesis_Method": np.nan,
            "Surface_Charge": "Positive" if zeta > 0 else "Negative" if zeta < 0 else "Neutral",
            "Cell_Type": row["cell_type"], "Cell_Tissue": "Vascular endothelium",
            "Year": np.nan, "size_final": size, "zeta_final": zeta, "abs_zeta": abs(zeta),
            "Time (hr)": time, "Concentration (ug/ml)": concentration,
            "log_size": np.log1p(size), "log_time": np.log1p(time), "log_concentration": np.log1p(concentration),
            "No_of_Cells (cells/well)": cells, "zeta_missing": 0, "cell_count_missing": int(np.isnan(cells)),
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
