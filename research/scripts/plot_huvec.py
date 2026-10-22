"""绘制完整 HUVEC 报告值；不插补、不平滑、不推定重复实验误差。"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "research/data/prospective/experimental_huvec_dose_time.csv"
MATERIALS = ("CS-SeNPs", "Glucose-SeNPs", "LET-SeNPs", "PAH-SeNPs", "PEG-SeNPs", "PEI-SeNPs", "PVP-SeNPs", "Sucrose-SeNPs", "TW80-SeNPs")
STYLES = {24: ("#0072B2", "o", "-"), 48: ("#D55E00", "s", "--"), 72: ("#009E73", "^", "-.")}


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 9 种材料的完整剂量—时间报告曲线")
    parser.add_argument("--qa-scripts", type=Path, required=True, help="nature-figure 的审计脚本目录")
    args = parser.parse_args()
    sys.path.insert(0, str(args.qa_scripts))
    from audit_panel_alignment import require_matplotlib_panel_alignment

    with SOURCE.open(encoding="utf-8", newline="") as stream:
        records = list(csv.DictReader(stream))
    if len(records) != 351:
        raise ValueError("曲线图必须使用完整的 351 条报告值")
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 8,
        "pdf.fonttype": 42, "svg.fonttype": "none", "axes.linewidth": 0.6,
        "axes.spines.right": False, "axes.spines.top": False, "legend.frameon": False,
    })
    fig, axes = plt.subplots(3, 3, figsize=(180 / 25.4, 145 / 25.4), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.105, right=0.975, bottom=0.11, top=0.885, wspace=0.28, hspace=0.49)
    for index, (material, ax) in enumerate(zip(MATERIALS, axes.flat)):
        for time, (color, marker, linestyle) in STYLES.items():
            subset = sorted(
                (record for record in records if record["nanoparticle"] == material and int(record["time_h"]) == time),
                key=lambda record: float(record["concentration_reported"]),
            )
            if len(subset) != 13:
                raise ValueError(f"材料—时间曲线缺少数据: {material}, {time}")
            concentrations = [float(record["concentration_reported"]) for record in subset]
            viability = [float(record["viability_percent"]) for record in subset]
            # symlog 保留零浓度，正浓度区间采用 log2；连线只连接原始报告点。
            ax.plot(concentrations, viability, color=color, marker=marker, linestyle=linestyle,
                    linewidth=0.9, markersize=2.8, markeredgewidth=0.4, label=f"{time} h")
        ax.set_xscale("symlog", base=2, linthresh=0.25, linscale=0.6)
        ax.set_xlim(-0.02, 650)
        ax.set_ylim(0, 130)
        ax.set_xticks([0, 0.25, 1, 4, 16, 64, 512])
        ax.set_xticklabels(["0", "0.25", "1", "4", "16", "64", "512"])
        ax.set_yticks([0, 50, 100])
        ax.axhline(50, color="#8C8C8C", linewidth=0.5, linestyle=":", zorder=0)
        ax.set_title(material, pad=8)
        ax.annotate(chr(ord("a") + index), xy=(0, 1), xycoords="axes fraction",
                    xytext=(-10, 7), textcoords="offset points", fontsize=9, fontweight="bold",
                    ha="left", va="bottom", annotation_clip=False)
        ax.tick_params(length=2.5, width=0.6)
        if index % 3 == 0:
            ax.set_ylabel("Cell viability (%)", labelpad=5)
        if index >= 6:
            ax.set_xlabel("Reported concentration", labelpad=5)
    handles = [Line2D([0], [0], color=color, marker=marker, linestyle=linestyle,
                      linewidth=0.9, markersize=3, label=f"{time} h")
               for time, (color, marker, linestyle) in STYLES.items()]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.54, 0.985), ncol=3,
               columnspacing=2.4, handlelength=2.2)
    fig.canvas.draw()
    out = REPO / "research/results/huvec_exploratory/figures/huvec-dose-time"
    qa = out.parent
    qa.mkdir(parents=True, exist_ok=True)
    require_matplotlib_panel_alignment(fig, json_out=qa / "huvec-alignment.json",
                                       require_panel_labels=True, strict=True)
    fig.savefig(out.with_suffix(".pdf"), metadata={"Title": "HUVEC dose-time observations", "Creator": "plot_huvec.py"})
    fig.savefig(out.with_suffix(".svg"))
    # Matplotlib 的多行路径属性会留下行尾空格；仅规范空白，不改变图形数据。
    svg_path = out.with_suffix(".svg")
    svg_text = svg_path.read_text(encoding="utf-8")
    svg_path.write_text("\n".join(line.rstrip() for line in svg_text.splitlines()) + "\n",
                        encoding="utf-8", newline="\n")
    fig.savefig(out.with_suffix(".png"), dpi=600)
    plt.close(fig)
    print("Exported all 351 values in 27 curves; 9 panels aligned; no error bars or smoothing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
