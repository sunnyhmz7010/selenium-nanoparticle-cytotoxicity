"""用修正版逐条件 SHAP 值生成粒径和 Zeta 的两行 Summary Plot。"""

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
import shap

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/huvec_external_20261013_umol_se"
OUTPUT = ROOT / "results/task30_shap_20261013_umol_se"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qa-scripts", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.qa_scripts))
    from audit_panel_alignment import require_matplotlib_panel_alignment

    # 运行交付的代码片段，核对它确实能复现既有全部 SHAP 值。
    snippet = OUTPUT / "shap_code_snippet.py"
    spec = importlib.util.spec_from_file_location("task30_shap_snippet", snippet)
    calculated = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(calculated)
    keys = ["nanoparticle", "concentration_reported", "time_h"]
    stored = pd.read_csv(SOURCE / "shap_encoded_values.csv", float_precision="round_trip")
    source = pd.read_csv(SOURCE / "experimental_data.csv", float_precision="round_trip")
    grouped = pd.read_csv(SOURCE / "shap_grouped_values.csv", float_precision="round_trip")
    assert len(source) == len(stored) == len(grouped) == 351
    assert source[keys].equals(stored[keys]) and source[keys].equals(grouped[keys])
    assert list(stored.drop(columns=keys).columns) == list(calculated.feature_names)
    np.testing.assert_allclose(calculated.phi, stored.drop(columns=keys), atol=1e-10, rtol=0)
    np.testing.assert_allclose(calculated.grouped_phi, grouped[["Particle size", "Zeta potential"]], atol=1e-10, rtol=0)

    # 单位不同的描述符只按各自行内取值高低着色，不比较跨行的原始数值。
    values = source[["size_nm", "zeta_mV"]].to_numpy(float)
    explanation = shap.Explanation(values=calculated.grouped_phi, data=values,
                                   feature_names=["Particle size (nm)", "Zeta potential (mV)"])
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 9,
        "xtick.labelsize": 7, "ytick.labelsize": 8,
        "pdf.fonttype": 42, "svg.fonttype": "none", "axes.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
    })
    cmap = LinearSegmentedColormap.from_list("low_high", ["#2166AC", "#8C6BB1", "#B2182B"])
    fig, ax = plt.subplots(figsize=(180 / 25.4, 90 / 25.4))
    fig.subplots_adjust(left=0.26, right=0.84, bottom=0.28, top=0.79)
    np.random.seed(42)  # 仅固定蜂群图在特征行内的垂直排布，不改变 SHAP 值。
    shap.plots.beeswarm(explanation, max_display=2, ax=ax, plot_size=None,
                       color=cmap, color_bar=False, group_remaining_features=False,
                       s=9, alpha=0.8, show=False)
    ax.set_xlabel("SHAP contribution to predicted viability (percentage points)", fontsize=8, labelpad=9)
    ax.tick_params(axis="x", labelsize=7)
    ax.tick_params(axis="y", labelsize=8, pad=5)
    fig.text(0.26, 0.91, "SHAP summary: particle size and zeta potential", fontsize=10)
    cax = fig.add_axes([0.90, 0.33, 0.022, 0.40])
    colorbar = fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(0, 1), cmap=cmap), cax=cax)
    colorbar.set_ticks([0, 1], labels=["Low", "High"])
    colorbar.set_label("Feature value", fontsize=8, labelpad=7)
    colorbar.ax.tick_params(labelsize=7, length=0)
    colorbar.outline.set_visible(False)
    fig.text(0.26, 0.09, "351 exposure conditions from 9 materials; each point is one condition.", fontsize=7)
    fig.text(0.26, 0.045, "Signed sums of derived-feature SHAP values; two descriptor groups shown.", fontsize=7)
    prefix = OUTPUT / "shap_summary_beeswarm"
    require_matplotlib_panel_alignment(fig, json_out=str(prefix) + ".alignment.json", exclude_axes=[cax], strict=True)
    fig.savefig(str(prefix) + ".pdf")
    fig.savefig(str(prefix) + ".svg")
    fig.savefig(str(prefix) + ".png", dpi=300)
    plt.close(fig)

    audit = {
        "conditions": 351, "materials": 9, "plotted_feature_groups": list(calculated.group_columns),
        "plotted_groups_of_total": "2 of 11 groups; specifically requested material descriptors",
        "group_columns": calculated.group_columns, "all_encoded_features_for_additivity": 116,
        "model_sha256": calculated.audit["model_sha256"], "source_grouped_shap_sha256": sha(SOURCE / "shap_grouped_values.csv"),
        "source_experiment_sha256": sha(SOURCE / "experimental_data.csv"), "snippet_sha256": sha(snippet),
        "max_recomputed_shap_difference": float(np.abs(calculated.phi - stored.drop(columns=keys).to_numpy(float)).max()),
        "max_additivity_error": float(np.abs(calculated.reconstructed - calculated.prediction).max()),
        "bee_layout_seed": 42, "horizontal_values": "unchanged signed SHAP contributions",
        "color": "row-specific descriptor values, blue low and red high",
        "uncertainty": "none; deterministic model explanation, not independent experimental replicates",
        "all_rows_used": True, "concentration_basis": "umol/L Se; model input uses converted ug/mL",
        "plot_api": "shap.plots.beeswarm; shap 0.53.0",
        "documentation": "https://shap.readthedocs.io/en/latest/generated/shap.plots.beeswarm.html",
    }
    (OUTPUT / "beeswarm_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
