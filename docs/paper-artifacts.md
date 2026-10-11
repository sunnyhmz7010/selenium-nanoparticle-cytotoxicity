# 论文材料与复现入口

本目录清理以提交 `10f2039` 为基线。旧文件保留在 Git 历史中，当前目录只保留论文相关材料及其计算依赖。

## 论文与数据

- `paper/`：中英文 LaTeX 正文、参考文献和样式包。正文仍需按照 `paper-revision-guidance.md` 修改；清理目录不等于已完成论文修改。
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

在仓库根目录、Python 3.11 或更高版本环境中执行：

```sh
python -m pip install -r requirements.txt
python scripts/reproduce_report.py
python scripts/run_improved_434.py
python scripts/run_general_benchmark.py
python scripts/run_transfer_comparison.py
python scripts/run_dose_time_interaction.py
```

`src/` 是这些入口及保存模型的代码依赖，必须保留。`requirements.txt` 保留运行依赖，移除已删除测试使用的 pytest，并补列读取 XLSX 所需的 openpyxl。版本范围不是原模型训练环境的精确锁定，跨版本加载 joblib 模型需要核验兼容性。

## 新增351条实验数据的归档缺口

本次整理时，先前提供的 `实验数据.xlsx` 已无法从原路径读取，也未在百度同步目录中找到同名工作簿。因此本次没有创建或上传其 CSV，不能用之前的汇总结果反向拼造原始记录。

`improvement-recommendations-status.md` 和 `paper-revision-guidance.md` 中的新实验结论仍属于先前分析记录，不代表仓库已有对应原始表、绘图文件或可复现的分析脚本。需重新提供原始文件后才能完成这一部分归档。浓度单位也需核对原始表头，不能未经核实标记为 µg/mL。

## 清理范围

按用户确认，移除根目录 README、LICENSE、tests、网页及相关工作流、开发计划、旧版脚本、重复数据、旧205条分析及顶层旧模型/结果、旧版本清单。复现入口中的网页同步调用已一并移除。

当前论文仍有历史383条数据和未完整复现的深度模型描述，不能因清理后只保留434条主分析材料就认为这些旧段落得到新验证。应按修改指导调整或标注历史口径，必要时从清理前提交追溯旧材料。
