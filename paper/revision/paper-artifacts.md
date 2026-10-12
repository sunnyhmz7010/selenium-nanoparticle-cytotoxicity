# 论文材料与复现入口

仓库根目录分为 `paper/`（论文）和 `research/`（研究材料）。本文下列 `data/`、`models/`、`results/`、`scripts/`、`src/` 路径均相对于 `research/`；其他研究文档及结果元数据中的同类路径也采用这一基准。论文目录仍位于仓库根目录的 `paper/`。

目录区别：`src/` 是处理数据、训练和评价模型的代码；`scripts/` 是调用这些代码的运行入口；`models/` 是训练后保存的模型，可加载用于预测；`results/` 是已计算的预测值、评价指标和日志；`data/` 是输入数据。研究说明和论文修改指导统一放在仓库根目录下的 `paper/revision/`，不再设置 `research/docs/`。

本目录清理以提交 `10f2039` 为基线。旧文件保留在 Git 历史中，当前目录只保留论文相关材料及其计算依赖。

## 论文与数据

- 根目录 `paper/v1/`：保留的初稿；`paper/v2/`：独立工作版本，2026-10-12 已完成基于新增实验数据的中文全文修订，英文仍为初稿；`paper/revision/`：原始意见、修改记录与核验报告。中文入口为 `paper/v2/manuscript_zh.tex`，详细记录见 [中文 V2 全文修订记录](v2-zh-revision-2026-10-12.md)。中文入口采用独立参考文献库，原中英文入口及初稿保持可追溯。
- `data/benchmark/d0en01240h1.xlsx`：通用数据原始工作簿。原中文命名副本与其 SHA256 相同，已去重。
- `data/senp/纳米硒毒性预测验证集数据集.xlsx`：434条严格分析所用原始工作簿。
- `data/reproduction/`：历史复现中的纳入、排除记录及审计信息。

## 结果、模型和脚本对应关系

| 论文证据 | 结果目录 | 模型目录 | 复现入口 |
|---|---|---|---|
| 434条SeNP严格分组验证 | `results/improved_434/` | `models/improved_434/` | `scripts/run_improved_434.py` |
| 通用纳米材料独立基准 | `results/general_benchmark/` | `models/general_benchmark/` | `scripts/run_general_benchmark.py` |
| General→SeNP迁移对照 | `results/transfer_comparison/` | 无单独归档的最终迁移模型 | `scripts/run_transfer_comparison.py` |
| 剂量-时间交互消融 | `results/dose_time_interaction/` | 无单独归档的最终交互模型 | `scripts/run_dose_time_interaction.py` |
| 历史报告复现与差异核对 | `results/report_reproduction/` | `models/report_reproduction/` | `scripts/reproduce_report.py` |

各目录的 OOF 预测、逐折结果、选择日志和分组信息保留，用于核验表中汇总指标。历史报告复现与严格分组验证属于不同评价口径，不可混用；含 IC50 的模型仅作辅助分析。

## 复现

在仓库根目录、Python 3.11 或更高版本环境中执行（先进入研究材料目录）：

```sh
cd research
python -m pip install -r requirements.txt
python scripts/reproduce_report.py
python scripts/run_improved_434.py
python scripts/run_general_benchmark.py
python scripts/run_transfer_comparison.py
python scripts/run_dose_time_interaction.py
```

`src/` 是这些入口及保存模型的代码依赖，必须保留。`requirements.txt` 保留运行依赖，移除已删除测试使用的 pytest，并补列读取 XLSX 所需的 openpyxl。版本范围不是原模型训练环境的精确锁定，跨版本加载 joblib 模型需要核验兼容性。

## 新增351条实验数据归档

已从用户重新提供的 `C:\Users\Sunny\下载\实验数据.xlsx` 归档：

- `data/prospective/experimental_huvec_original.xlsx`：原始文件逐字节副本。
- `data/prospective/experimental_huvec_dose_time.csv`：Sheet1的351条记录，原始数值文本保留，不插补、不换算、不裁剪存活率。
- `data/prospective/audit.json`：原始表头、字段映射、原始文件与CSV的SHA256、覆盖和完整性检查。
- `scripts/archive_huvec_data.py`：标准库转换入口，运行 `python scripts/archive_huvec_data.py` 可重新生成CSV和审计文件。

核验结果：9种材料、HUVEC、24/48/72 h、13个浓度，27组材料-时间组合均完整；无空值和重复条件，Sheet2、Sheet3为空。

浓度原表头为“药物浓度（μm）”，不是已确认的μg/mL。CSV采用中性字段 `concentration_reported`，待确认单位含义及其是否按元素硒计量后再作换算。既有浓度和表观IC50数值应按原始浓度尺度解读。

每条件只有一个报告值，未提供重复孔或汇总方式；不能据此断言实验未做重复，也不能计算重复实验误差条。此前两份指导/状态文档中的“无重复”应按“未提供重复数据”理解。

原始数据归档后，2026-10-12 中文修订已新增 `results/huvec_exploratory/`，包含材料比较、时间汇总、27条曲线的表观IC50与描述符相关性，入口为 `scripts/summarize_huvec_for_paper.py`。重新计算得到19条可插值曲线、8条未达到50%存活率，替代早期指导中的20/7口径。论文曲线及生成脚本位于 `paper/v2/figures/`，表格位于 `paper/v2/tables/`。这些是实验观测分析，仍没有新增材料的配对模型预测结果。

## 清理范围

按用户确认，移除根目录 README、LICENSE、tests、网页及相关工作流、开发计划、旧版脚本、重复数据、旧205条分析及顶层旧模型/结果、旧版本清单。复现入口中的网页同步调用已一并移除。

2026-10-12 按用户要求恢复 PDF 构建工作流 `.github/workflows/main.yml`，构建入口调整为中文 V2：`paper/v2/manuscript_zh.tex`。在 GitHub Actions 中选择 **Build and Auto-Push to Output → Run workflow → main** 即可构建。流程采用 XeLaTeX 与 Biber，成功后将带北京时间戳的 PDF、递归合并的 `main.tex`、`references_zh.bib` 及引用图片发布到 `output` 分支。该分支保留已有 PDF 和提交历史；根目录 `main.tex` 更新为最新中文稿，旧稿源可从历史提交恢复。下载配套稿源时需一并保留参考文献和 `figures/` 目录，Overleaf 的编译器选择 XeLaTeX。流程延续原来的手动触发方式，网页部署流程未恢复。

V1 与 V2 英文仍保留历史383条数据及未完整复现的深度模型描述，不能因目录清理就认定这些旧段落得到新验证。V2 中文主分析已改为434条归档数据，并删除旧深度模型与分类指标的主文比较，详细取舍保留在中文修订记录中。
