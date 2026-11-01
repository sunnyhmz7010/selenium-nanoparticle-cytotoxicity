# HUVEC 数据交付：任务 25、27、30

本次使用已有的基础 Random Forest 模型，对 9 种新材料 × 13 个浓度 × 24/48/72 h，共 351 个条件进行推理。模型在历史 434 条记录、24 个文献组上建立；按历史验证选择模型，未使用新增实验存活率选择模型、训练、校准或调参，输入不含实测 IC50。

## 给合作同学的三个文件

| 文件 | 记录数 | 内容 |
|---|---:|---|
| `model_predictions.csv` | 351 | 材料、原报告浓度、时间、预测存活率及确认后的浓度单位 |
| `experimental_data.csv` | 351 | 完整实验报告值，含粒径、Zeta、细胞、浓度、时间和存活率；保留原 CSV 数值文本 |
| `experimental_ic50.csv` | 27 | 实验侧表观 IC50、删失状态、插值括区和方法 |

三个文件都用 `nanoparticle` 标识材料；351 条预测与实验通过 `nanoparticle + concentration_reported + time_h` 配对，IC50 通过 `nanoparticle + time_h` 配对。存活率单位为百分数，例如 70 表示 70%，误差单位为百分点。CSV 为 UTF-8 无 BOM、LF；读取时显式指定 UTF-8。

**浓度单位已于 2026-10-13 在本次对话中由用户确认为 μg/mL，原工作簿 E1 的“μm”为表头误写。** 原始工作簿及归档 CSV 未修改；交付的 `concentration_reported` 数值可直接作为 μg/mL 使用，与模型字段 `Concentration (ug/ml)` 一致。512 的排序条件应写成 **72 h、512 μg/mL**。

## 25：从预测曲线估计 IC50

`model_ic50.csv` 包含全部 27 条预测曲线的结果。本模型的 351 个预测值范围为 53.7387%–99.8083%，所有正浓度预测点均高于 50%，因此 **27 条曲线全部为 `not_reached`，显示 `>512` μg/mL，数值列留空**。这表示在所评估浓度网格内未达到阈值，没有给出区间外的精确 IC50，也没有外推拟合。

实验侧沿用当前归档的计算口径：**19 条可插值，8 条 >512**，不是早期截图中的 20/7。方法是在相邻正浓度点之间，按 log10 浓度对存活率等于 50% 的位置做线性插值；多次穿越或缺少有效括区时标记 `NA`，最低正浓度已经低于阈值时仅标记 `<0.25`。不在 log(0) 上插值，不强行平滑、归一化、限制存活率至 0–100% 或生成置信区间。

合作同学处理第 26 项时，当前模型侧没有有限 IC50 可与实验侧组成数值对，不能将 `>512` 替换成 512 后计算普通 log 误差或 R²。应先报告删失情况，再决定是否需要单独的删失分析。

## 27：预测毒性排序

`toxicity_ranking_72h_512.csv` 保存 HUVEC、72 h、512 μg/mL 下的 9 种材料预测排序，预测存活率越低，毒性排名越靠前；并列值使用相同的最小秩。

| 毒性排名 | 材料 | 预测存活率（%） |
|---:|---|---:|
| 1 | PAH-SeNPs | 66.0527 |
| 2 | CS-SeNPs | 68.0011 |
| 3 | PEG-SeNPs | 69.9530 |
| 4 | PEI-SeNPs | 70.6724 |
| 5 | PVP-SeNPs | 71.2143 |
| 6 | Sucrose-SeNPs | 71.4318 |
| 7 | LET-SeNPs | 71.9304 |
| 8 | Glucose-SeNPs | 73.3531 |
| 9 | TW80-SeNPs | 73.8074 |

排序只适用于上述条件。第 28 项与实验排序的一致性由合作同学另行计算。

## 30：可审计的 SHAP 流程

`figures/` 包含粒径和 Zeta 的 SHAP 散点图，各提供 PDF、SVG 和 PNG。图中全部 351 个条件均保留，只有 9 个独立材料描述符组合；这些点不能视为 351 次独立材料实验。图展示模型贡献，不作为粒径或电位的因果证据，不绘制重复实验误差条。

采用精确 Tree SHAP，显式指定 `TreeExplainer(feature_perturbation="tree_path_dependent", model_output="raw")`，背景使用冻结树中保存的历史训练路径样本计数；没有采用新增实验响应作为背景。方法和加和定义参见 [SHAP 官方文档](https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html)。所有 351 条记录均检查 `base_value + sum(SHAP) = prediction`，最大绝对残差为 1.4211×10⁻¹³ 个百分点，允许阈值为 10⁻⁶。

粒径图为 `size_final + log_size` 的有符号 SHAP 加和；Zeta 图为 `zeta_final + abs_zeta + zeta_missing` 的有符号加和。根据 Zeta 正负映射的 `Surface_Charge` 类别单列保留，不并入 Zeta 数值图。对分类特征，将全部 one-hot 列的有符号贡献加和；这种后处理汇总不等同于重新定义一组特征联合进入 Shapley 博弈。

可复核文件包括：

- `model_inputs.csv`：映射后、插补前的 19 个输入特征。
- `transformed_inputs.csv`：冻结插补和 one-hot 编码后的 116 列输入。
- `shap_encoded_values.csv`：全部 116 列的逐条件 SHAP 值。
- `shap_grouped_values.csv`、`shap_feature_groups.json`：全部特征组贡献及精确分组映射。
- `shap_additivity_check.csv`：逐条件基准值、预测、重构值及残差。
- `audit.json`：模型/数据哈希、时间戳、软件版本、缺失处理、映射、删失状态及 SHAP 配置。
- 图形审计 JSON 与 `verification.json`：数据回读、公式与图形检查。

**Modifier Category 和修饰物 Molecular Weight 均未提供，不能生成它们的 SHAP 图。** 模型包含的是已有 `Coat/Functional Group` 名称字段，两者不能混称。CS 名称映射到历史标签 `Chitosan (CS)`，PEG、PVP 原样匹配；Glucose、LET、PAH、PEI、Sucrose、TW80 在冻结编码器中为未知类别，按原有 `handle_unknown="ignore"` 编成全零，未强配到另一种修饰物。LET 未展开成未经确认的化学名称。

新增数据未提供年份、接种细胞数和合成路线。已冻结插补器分别填入历史中位数 2016、10000 cells/well 和历史众数 `Chemical reduction`，这些是模型默认输入，不是实验已知条件。年份在该模型中贡献较大，需要结合此缺失情况解读。粒径和 Zeta 使用原报告值，测量方法及介质未提供；HUVEC 组织标签映射为历史使用的 `Vascular endothelium`，电荷类别依据 Zeta 符号映射。

## 验证边界与复现

这些预测生成于实验数据已经归档之后，属于事后独立推理。本次时间戳只证明当前生成时间，不能补成“实验开展前已封存”的盲法前瞻验证；合作同学处理第 21 项时需要保留这一事实。原始重复孔数量与汇总方式未提供，IC50 仅为报告曲线的表观阈值估计。

完整压缩包的 `reproduction/` 目录包含本次冻结模型、输入数据、运行与验证脚本、测试、依赖版本和图形审计工具。解压后在该目录运行下述命令，将 `<图形审计脚本目录>` 替换为 `qa`。模型 SHA256 为 `d0268e0831da09faf8f86a59300415410610195f1905aac9afc063095215ce50`。顶层 `manifest.json` 列出交付文件及复现材料的哈希。

在项目根目录按已授权的环境运行：

```powershell
.\.venv\Scripts\python.exe research\scripts\run_huvec_external.py --concentration-unit ug_ml --output research\results\huvec_external_new_run --qa-scripts <图形审计脚本目录>
.\.venv\Scripts\python.exe -m unittest discover -s research\tests -p test_huvec_external.py
```

新运行目录的 PDF 需先通过碰撞审计和文字尺寸审计，再运行 `research/scripts/verify_huvec_external.py <新运行目录>`。本次提供的 `verification.json` 和两张图的审计 JSON 已完成这些检查。

输入模型和预处理器全程不重新拟合；脚本拒绝覆盖已有非空输出目录。直接依赖版本记录在 `research/requirements-huvec-external.txt`。第 22、24、26、28 项的评价指标及论文改写不在本次计算范围内。
