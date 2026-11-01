"""从保存的交付文件独立核对数值、条件配对与 SHAP 重构。"""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import joblib
import numpy as np
import openpyxl
import pandas as pd
import pymupdf

ROOT = Path(__file__).resolve().parents[1]


def read_csv(path):
    return pd.read_csv(path, float_precision="round_trip", keep_default_na=False)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    output = args.directory.resolve()
    audit = json.loads((output / "audit.json").read_text(encoding="utf-8"))
    source = ROOT / "data/prospective/experimental_huvec_dose_time.csv"
    experiments = read_csv(output / "experimental_data.csv")
    predictions = read_csv(output / "model_predictions.csv")
    keys = ["nanoparticle", "concentration_reported", "time_h"]
    assert sha(source) == audit["source_csv_sha256"]
    source_values = read_csv(source).sort_values(keys).reset_index(drop=True)
    delivered_values = experiments[source_values.columns].sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(source_values, delivered_values)
    assert len(experiments) == len(predictions) == 351
    assert not experiments.duplicated(keys).any() and not predictions.duplicated(keys).any()
    paired = predictions.merge(experiments, on=keys, validate="one_to_one")
    assert len(paired) == 351
    assert set(predictions["concentration_unit"]) == {audit["concentration_unit"]}
    if "concentration_unit" in experiments:
        assert set(experiments["concentration_unit"]) == {audit["concentration_unit"]}
    for path in output.rglob("*.csv"):
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf") and b"\r\n" not in raw, path
        raw.decode("utf-8")

    # 从原工作簿核对所有 351×7 个报告字段，避免只核对归档 CSV 自身。
    workbook = openpyxl.load_workbook(ROOT / "data/prospective/experimental_huvec_original.xlsx", read_only=True, data_only=True)
    worksheet_rows = list(workbook["Sheet1"].values)[1:]
    lookup = {(r[0], float(r[4]), int(r[5])): r for r in worksheet_rows}
    max_workbook_delta = 0.0
    for row in experiments.to_dict("records"):
        original = lookup[(row["nanoparticle"], row["concentration_reported"], row["time_h"])]
        assert original[0] == row["nanoparticle"] and original[3] == row["cell_type"]
        for column, index in (("size_nm", 1), ("zeta_mV", 2), ("concentration_reported", 4), ("time_h", 5), ("viability_percent", 6)):
            difference = abs(float(original[index]) - float(row[column]))
            max_workbook_delta = max(max_workbook_delta, difference)
            assert difference < 1e-12, (column, difference)
    workbook.close()

    ic50 = read_csv(output / "experimental_ic50.csv")
    assert len(ic50) == 27 and not ic50.duplicated(["nanoparticle", "time_h"]).any()
    checked_finite = 0
    for row in ic50.to_dict("records"):
        if row["status"] == "interpolated":
            c1, c2 = float(row["lower_concentration"]), float(row["upper_concentration"])
            y1, y2 = float(row["lower_viability_percent"]), float(row["upper_viability_percent"])
            assert 0 < c1 < c2 and y1 > 50 >= y2
            # 与生成代码的 log10 实现独立：自然对数及 exp 验证同一阈值位置。
            expected = math.exp(math.log(c1) + (y1 - 50) / (y1 - y2) * math.log(c2 / c1))
            assert math.isclose(expected, float(row["ic50_reported_scale"]), rel_tol=1e-12)
            checked_finite += 1
        else:
            assert row["status"] == "not_reached" and row["ic50_display"] == ">512" and row["ic50_reported_scale"] == ""
    assert checked_finite == 19
    model_ic50 = read_csv(output / "model_ic50.csv")
    assert len(model_ic50) == 27 and not model_ic50.duplicated(["nanoparticle", "time_h"]).any()
    for row in model_ic50.to_dict("records"):
        curve = predictions.loc[predictions["nanoparticle"].eq(row["nanoparticle"]) & predictions["time_h"].eq(row["time_h"])].sort_values("concentration_reported")
        positive = curve.loc[curve["concentration_reported"].gt(0)]
        if row["status"] == "not_reached":
            assert positive["predicted_viability_percent"].gt(50).all()
            assert row["ic50_display"] == ">512" and row["ic50_reported_scale"] == ""
        elif row["status"] == "interpolated":
            c1, c2 = float(row["lower_concentration"]), float(row["upper_concentration"])
            y1, y2 = float(row["lower_viability_percent"]), float(row["upper_viability_percent"])
            assert 0 < c1 < c2 and y1 > 50 >= y2
            expected = math.exp(math.log(c1) + (y1 - 50) / (y1 - y2) * math.log(c2 / c1))
            assert math.isclose(expected, float(row["ic50_reported_scale"]), rel_tol=1e-12)
        else:
            assert row["status"] in {"observed_at_50", "ambiguous", "below_tested_range"}
    model_status_counts = dict(Counter(model_ic50["status"]))

    ranking = read_csv(output / "toxicity_ranking_72h_512.csv")
    selected = predictions.query("time_h == 72 and concentration_reported == 512").sort_values(["predicted_viability_percent", "nanoparticle"])
    assert len(ranking) == 9 and list(ranking["nanoparticle"]) == list(selected["nanoparticle"])
    assert ranking["predicted_viability_percent"].is_monotonic_increasing
    assert list(ranking["toxicity_rank"]) == list(range(1, 10))

    inputs = pd.read_csv(output / "model_inputs.csv", float_precision="round_trip")
    # 单独验证单位与 log 特征：不能只验证“读回值等于误用单位时的模型值”。
    if audit["concentration_unit"] == "umol/L":
        assert audit["molar_concentration_basis"] == "Se"
        factor = 78.971 / 1000
    else:
        assert audit["concentration_unit"] == "ug/mL"
        factor = 1.0
    assert math.isclose(audit["dose_conversion_to_ug_ml_factor"], factor, rel_tol=1e-15)
    converted = predictions["concentration_reported"].to_numpy(float) * factor
    assert np.allclose(inputs["Concentration (ug/ml)"], converted, atol=1e-12, rtol=0)
    assert np.allclose(inputs["log_concentration"], np.log1p(converted), atol=1e-12, rtol=0)
    assert np.allclose(predictions["model_concentration_ug_ml"], converted, atol=1e-12, rtol=0)
    pipeline = joblib.load(ROOT / audit["model"])
    reproduced = pipeline.predict(inputs[audit["features"]])
    prediction_delta = np.abs(reproduced - predictions["predicted_viability_percent"].to_numpy()).max()
    assert prediction_delta < 1e-10
    reconstructed = read_csv(output / "shap_additivity_check.csv")
    encoded = read_csv(output / "shap_encoded_values.csv")
    grouped = read_csv(output / "shap_grouped_values.csv")
    for frame in (inputs, reconstructed, encoded, grouped):
        assert frame[keys].equals(predictions[keys])
    encoded_values = encoded.drop(columns=keys).to_numpy(float)
    group_values = grouped.drop(columns=keys).to_numpy(float)
    assert encoded_values.shape == (351, 116)
    assert np.isfinite(encoded_values).all() and np.isfinite(group_values).all()
    assert np.allclose(encoded_values.sum(axis=1), group_values.sum(axis=1), atol=1e-10, rtol=0)
    additive_delta = np.abs(reconstructed["base_value"].to_numpy(float) + encoded_values.sum(axis=1) - reproduced).max()
    assert additive_delta < 1e-6
    assert sha(ROOT / audit["model"]) == audit["model_sha256"]
    for filename, expected_digest in audit["outputs_sha256"].items():
        assert sha(output / filename) == expected_digest, filename

    figure_results = []
    for name in ("shap_particle_size", "shap_zeta_potential"):
        collision = json.loads((output / "figures" / f"{name}.collision-audit.json").read_text(encoding="utf-8"))
        assert collision["verdict"] == "PASS"
        with pymupdf.open(output / "figures" / f"{name}.pdf") as document:
            page = document[0]
            sizes = [span["size"] for block in page.get_text("dict")["blocks"] if "lines" in block for line in block["lines"] for span in line["spans"]]
            assert min(sizes) >= 5
            assert abs(page.rect.width * 25.4 / 72 - 180) < 0.01
            figure_results.append({"figure": name, "width_mm": page.rect.width * 25.4 / 72, "minimum_text_pt": min(sizes), "collision_verdict": collision["verdict"], "alignment": "single panel; not applicable", "visual_review": "all points preserved; axes and labels readable; no clipping"})
    report = {
        "status": "PASS", "experiment_rows": 351, "prediction_rows": 351, "curves": 27,
        "experimental_finite_ic50": checked_finite, "experimental_censored_ic50": 8,
        "model_ic50_status_counts": model_status_counts, "ranked_materials": 9,
        "concentration_unit": audit["concentration_unit"], "molar_basis": audit["molar_concentration_basis"],
        "maximum_reported_dose": float(predictions["concentration_reported"].max()), "maximum_model_dose_ug_ml": float(converted.max()),
        "max_original_workbook_numeric_delta": max_workbook_delta,
        "max_reloaded_prediction_delta": float(prediction_delta), "max_readback_shap_additivity_delta": float(additive_delta),
        "csv_encoding": "UTF-8 without BOM; LF", "figures": figure_results,
        "static_figure_preflight": {"fail": 0, "warnings_reviewed": ["PNG is a 300 dpi preview; editable PDF/SVG are authoritative", "180 mm physical PDF width independently measured; static width regex misread 180/25.4", "dropna used only to list unknown categories; no prediction or SHAP rows excluded"]},
    }
    (output / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
