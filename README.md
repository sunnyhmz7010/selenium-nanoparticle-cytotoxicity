<div align="center">
  <h1>selenium-nanoparticle-cytotoxicity</h1>
  <p>基于可核验 SeNP 数据重建毒性预测模型并展示分组验证结果。</p>
</div>

<p align="center">
  <a href="https://github.com/sunnyhmz7010/selenium-nanoparticle-cytotoxicity/releases"><img src="https://img.shields.io/github/v/release/sunnyhmz7010/selenium-nanoparticle-cytotoxicity?label=Release&color=3b82f6" alt="Release" /></a>
  <a href="https://github.com/sunnyhmz7010/selenium-nanoparticle-cytotoxicity/blob/main/LICENSE"><img src="https://img.shields.io/github/license/sunnyhmz7010/selenium-nanoparticle-cytotoxicity?color=10b981" alt="License" /></a>
  <a href="https://github.com/sunnyhmz7010/selenium-nanoparticle-cytotoxicity/actions"><img src="https://img.shields.io/github/actions/workflow/status/sunnyhmz7010/selenium-nanoparticle-cytotoxicity/main.yml?branch=main&label=CI" alt="CI" /></a>
</p>

---

## ✨ 为什么做这个项目

论文仓库、建模数据和输出结果需要在同一份可追溯材料中管理。本项目保留论文源文件，同时用公开归档数据重建无 IC50 主模型、IC50 辅助模型和按论文分组的嵌套交叉验证。

## 🚀 核心能力

- 按 SeNP、MTT、目标值、时间和浓度筛选分析数据。
- 以 DOI 为主、Article_ID 为回退执行 publication-grouped nested CV。
- 将插补、类别编码、候选特征选择和参数选择限制在训练折内。
- 保存 OOF 预测、逐折指标、模型 pipeline、特征覆盖率和 SHA256 清单。
- 用静态网页查看历史报告复现对照和 434 条数据的严格分组验证结果。

## ⚡ 快速开始

### 📋 前置要求

- Python 3.11 或更高版本。
- 可读取仓库中归档 CSV 的本地环境。

### 📦 安装与运行

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python scripts/run_experiments.py
python scripts/reproduce_report.py
python scripts/run_improved_434.py
python scripts/run_dose_time_interaction.py
python scripts/build_manifest.py
python -m http.server 8000 --directory web
```

打开 <http://localhost:8000> 查看网页。网页需要通过 HTTP 服务访问，不能直接依赖 `file://` 加载 JSON。

## 📖 使用说明

主实验入口是 `scripts/run_experiments.py`，默认读取 `data/senp/senp_validation_dataset_final.csv`，生成 `results/` 中的 CSV/JSON 和 `models/` 中的 joblib pipeline。该入口产生的 205 条 MTT 结果保留为历史归档。网页只使用 434 条严格验证口径；`scripts/build_manifest.py` 从 `results/report_reproduction/acceptance.json`、`data/reproduction/audit.json` 和 `results/improved_434/summary.json` 重新生成 `web/data/dashboard.json`。

`baseline` 和 `chemistry_no_ic50` 是可用于主分析的配置。`ic50_assisted` 明确标记为 response-correlated 辅助基准，不应被解释为前瞻性预测模型。

## 🧠 功能细节

历史主实验包含 205 条 MTT 回归记录，相关结果仅保存在 `results/` 供追溯，不进入网页。当前网页与改进实验统一采用 434 条记录、24 个文献组；publication group 由 DOI/Article_ID 回退规则确定。模型结果采用外层 5 折、内层 3 折的分组嵌套交叉验证，指标由外层 pooled OOF 预测计算。

论文中出现的 `R²=0.957` 等报告值属于论文原文语境，不能直接当作本仓库当前重建结果。本仓库不虚构分子量、修饰物分类、新合成材料或不存在的前瞻实验结果。

### 历史报告复现

`scripts/reproduce_report.py` 按历史日志可确认的清洗、单位换算、三折 KFold 和树模型参数重新计算报告指标。当前归档 Excel 的 SHA-256 为 `6e0c832f335993cdf3f08809dd311050a6ca82be35327a3ed364a1b663272e5d`，历史规则得到 434 条记录；报告记录的是 310 条，且目标值分布也不同，因此验收状态为 `partial`。

实际计算结果保存在 `results/report_reproduction/`，模型保存在 `models/report_reproduction/`，纳入和排除记录保存在 `data/reproduction/`。`acceptance.json` 分开记录计算值、报告目标值和差值。报告对应的 TabTransformer 训练代码及依赖版本未归档，因此不使用其他神经网络替代。

`scripts/run_improved_434.py` 在同一434条数据上执行按文献分组的5×3嵌套交叉验证。预处理、特征选择和参数选择均限制在训练折内；结果保存在 `results/improved_434/`，六个最终模型保存在 `models/improved_434/`。当前最佳严格验证结果为IC50辅助XGBoost（OOF MAE 18.87，R² 0.142），但相对基础XGBoost的按文献组bootstrap MAE差值95%区间跨过0，因此不能认定为稳定改进。化学增强且不含IC50的配置没有降低MAE。

`scripts/run_dose_time_interaction.py` 在相同的434条数据和publication-grouped nested CV设置下，比较基础特征与显式 `log_concentration × log_time` 交互项。该消融结果单独保存到 `results/dose_time_interaction/`，不并入网页主结果；当前交互项未显示稳定改善。

全部36项论文修改建议的完成状态、实验结果、预期判断和未完成原因见 [`docs/improvement-recommendations-status.md`](docs/improvement-recommendations-status.md)。

## 🧱 技术栈

- Python：pandas、scikit-learn、XGBoost、joblib
- 网页：原生 HTML、CSS、JavaScript 和 SVG
- 论文：LaTeX/XeLaTeX
- 目标平台：Windows、Linux、macOS

## 🗂️ 项目结构

```
selenium-nanoparticle-cytotoxicity/
├── paper/                  # 论文 LaTeX 源文件和历史快照
├── data/                   # 归档数据与数据副本
├── src/                    # 数据契约、模型和评估实现
├── scripts/                # 实验入口与 manifest 生成
├── models/                 # 验证后保存的 pipeline
├── results/                # 指标、OOF 预测和覆盖率
├── web/                    # 静态结果网页
├── tests/                  # 数据与评估测试
├── historical_modeling/    # 旧建模材料归档
└── manifest/               # 基线和 SHA256 清单
```

## 👨‍💻 本地开发

### 🧰 环境

使用隔离的 Python 虚拟环境，并确保 `requirements.txt` 中的科学计算依赖可安装。

### ⚙️ 命令

```bash
pytest -q tests
python -m compileall -q src scripts
python scripts/run_experiments.py
python scripts/build_manifest.py
```

完整实验需要进行多轮分组交叉验证，运行时间取决于本机 CPU。模型和结果文件生成后再运行网页检查或提交。

## 🔐 安全报告

如果发现安全问题，请不要公开披露细节。请优先参考仓库中的 [SECURITY.md](./SECURITY.md) 提交安全报告。

## 📄 许可证

本项目基于 [GPL-3.0](./LICENSE) 开源。

<div align="center">
  <sub>Built with ❤️ by Sunny</sub>
</div>
