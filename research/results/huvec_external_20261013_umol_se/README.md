# HUVEC 交付修正版：浓度为 μmol/L Se

**本版本取代上一版按 μg/mL 直接输入的结果。** 用户于 2026-10-13 更正：原表浓度为微摩尔每升（μmol/L，等同于 μM），并确认按元素硒（Se）计。原始实验工作簿及归档 CSV 保留不变。本次重新生成 351 条模型预测、27 条模型侧 IC50、72 h/512 μmol/L 的毒性排序和全部 SHAP 值及图形。

## 三个交付文件

| 文件 | 记录数 | 内容 |
|---|---:|---|
| `model_predictions.csv` | 351 | 材料、报告浓度、时间、预测存活率、报告浓度单位及模型输入质量浓度 |
| `experimental_data.csv` | 351 | 原实验的全部七个字段，保留原数值文本，另增明确的浓度单位列 |
| `experimental_ic50.csv` | 27 | 实验侧表观 IC50、删失状态和插值括区，浓度单位为 μmol/L |

预测与实验通过 `nanoparticle + concentration_reported + time_h` 配对，IC50 通过 `nanoparticle + time_h` 配对。`concentration_reported` 始终为实验原始微摩尔浓度，例如 512 表示 512 μmol/L Se；CSV 的 `concentration_unit` 用 ASCII 文本 `umol/L` 表示。存活率为百分数，例如 70 表示 70%，误差为百分点。所有 CSV 使用 UTF-8 无 BOM、LF。

## 单位换算与模型

硒采用摩尔质量 78.971 g/mol，来源为 [CIAAW 的硒原子量记录](https://ciaaw.org/selenium.htm)。换算公式为：

```text
模型输入（μg/mL） = 实验报告值（μmol/L Se） × 78.971 / 1000
1 μmol/L Se = 0.078971 μg/mL
512 μmol/L Se = 40.433152 μg/mL
```

仅模型输入的 `Concentration (ug/ml)` 使用换算后的值，`log_concentration` 也从该质量浓度计算。预测 CSV 额外提供 `model_concentration_ug_ml`，避免把报告值 512 误当成模型输入 512 μg/mL。

模型和预处理器继续使用已有的基础 Random Forest，没有重训、校准、调参或根据新增实验响应更换模型；输入不含实测 IC50。模型 SHA256 保持为 `d0268e0831da09faf8f86a59300415410610195f1905aac9afc063095215ce50`。模型来自历史 434 条记录、24 个文献组的建模和分组验证。

## 25：模型侧与实验侧 IC50

`model_ic50.csv` 含全部 27 条材料—时间预测曲线。351 个预测值范围为 **53.3250%–99.8083%**，所有正浓度预测点均高于 50%，所以 **27 条模型侧 IC50 均为 `not_reached`，显示 `>512` μmol/L Se，数值列留空**。等价质量浓度下，测试上限为 40.433152 μg/mL；未给出上限之外的精确 IC50。

实验侧仍为 **19 条可插值、8 条 >512 μmol/L**；更正单位不改变其原报告尺度的插值数值。插值是在相邻正浓度点之间，按 log10 浓度求存活率等于 50% 的位置。多次穿越或无有效括区时显示 `NA`；最低正浓度已经低于阈值时仅显示 `<0.25`。不对 log(0) 插值，不强行平滑、截断存活率或拟合区间外 IC50。

合作同学计算第 26 项时，不能将模型侧 `>512` 当作数值 512。当前模型没有有限 IC50 可组成普通数值配对，需报告删失情况；不能据此直接计算普通 log 误差或 R²。原始重复孔数量与汇总方式未提供，IC50 仅为报告曲线的表观阈值，不提供伪造的置信区间。

## 27：72 h、512 μmol/L Se 下的预测毒性排序

`toxicity_ranking_72h_512.csv` 按预测存活率升序排列，存活率越低，毒性排名越靠前。以下排序取代上一版：

| 排名 | 材料 | 预测存活率（%） |
|---:|---|---:|
| 1 | PAH-SeNPs | 53.5446 |
| 2 | CS-SeNPs | 54.0929 |
| 3 | PEG-SeNPs | 54.4938 |
| 4 | Glucose-SeNPs | 55.3654 |
| 5 | PEI-SeNPs | 55.4047 |
| 6 | PVP-SeNPs | 55.5874 |
| 7 | LET-SeNPs | 56.0747 |
| 8 | Sucrose-SeNPs | 56.6462 |
| 9 | TW80-SeNPs | 57.2365 |

排序条件为 HUVEC、72 h、512 μmol/L Se，模型对应输入为 40.433152 μg/mL。第 28 项与实验排序的一致性由合作同学另行评价。

## 30：SHAP 与审计

`figures/` 提供本次重新计算的粒径、Zeta SHAP 图，分别有 PDF、SVG 和 PNG。全部 351 个条件均保留，但只有 9 种材料；不得把这些点当成 351 次独立材料实验。图展示模型贡献，不代表材料性质的因果作用。

采用精确 `TreeExplainer(feature_perturbation="tree_path_dependent", model_output="raw")`，以冻结树中保存的历史训练路径样本计数为背景；配置依据 [SHAP 官方文档](https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html)。所有记录均检查 `base_value + sum(SHAP) = prediction`，新版最大绝对残差为 **1.1369×10⁻¹³ 个百分点**，低于 10⁻⁶ 的检查阈值。

粒径图加和 `size_final + log_size` 的有符号贡献；Zeta 图加和 `zeta_final + abs_zeta + zeta_missing`。按 Zeta 正负映射的 `Surface_Charge` 类别贡献单独保留。分类字段将全部 one-hot 列的有符号贡献加和；这种后处理不等同于重新定义一组变量联合进入 Shapley 博弈。

审计材料包含 `model_inputs.csv`、`transformed_inputs.csv`、全部 116 列的 `shap_encoded_values.csv`、`shap_grouped_values.csv`、`shap_feature_groups.json`、逐条件的 `shap_additivity_check.csv`、`audit.json`、`verification.json` 和图形审计 JSON。校验已确认：实验数值与原工作簿完全一致、单位换算正确、重新加载模型的预测与 CSV 完全一致、SHAP 加和通过；两张图的文字尺寸及碰撞审计通过。

Modifier Category 和修饰物 Molecular Weight 未提供，不能生成这两者的 SHAP 图。模型的 `Coat/Functional Group` 是名称字段，不等同于 Modifier Category。CS 映射到历史标签 `Chitosan (CS)`，PEG/PVP 原样匹配；Glucose、LET、PAH、PEI、Sucrose、TW80 是未知类别，由冻结编码器按 `handle_unknown="ignore"` 编为全零。LET 不展开成未经确认的化学名称。

缺失的年份、接种细胞数和合成路线由冻结插补器填入历史默认值 2016、10000 cells/well 和 `Chemical reduction`，并不代表已知实验条件。粒径与 Zeta 使用原报告值，测量方法及介质未提供；HUVEC 的组织标签映射为历史使用的 `Vascular endothelium`，电荷类别根据 Zeta 的符号映射。

## 复现与版本追溯

完整压缩包的 `reproduction/` 含冻结模型、输入数据、脚本、测试、依赖版本及图形审计工具；`manifest.json` 提供逐文件哈希。在项目根目录或压缩包的 `reproduction/` 中，使用已准备好的 Python 环境运行：

```powershell
.\.venv\Scripts\python.exe research\scripts\run_huvec_external.py --concentration-unit umol_l --molar-basis Se --output research\results\huvec_external_new_run --qa-scripts <图形审计脚本目录>
.\.venv\Scripts\python.exe -m unittest discover -s research\tests -p test_huvec_external.py
```

压缩包的图形审计目录为 `qa`。新的 PDF 先执行碰撞及文字尺寸审计，再运行 `research/scripts/verify_huvec_external.py <新运行目录>`。脚本拒绝覆盖非空输出目录；未明确摩尔浓度参考物质时，禁止正式推理。

旧版输出目录和压缩包只作为单位误认的历史记录保留，不用于合作同学的评价。本次预测仍生成于实验报告值已经提供之后，不能补称实验前封存的盲法前瞻验证。第 21、22、24、26、28 项及论文改写由合作同学后续处理。
