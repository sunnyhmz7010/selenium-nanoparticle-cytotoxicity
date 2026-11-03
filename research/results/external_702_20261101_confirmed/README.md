# 最新702条实验数据分析（密度更正于2026-11-03）

来源：`实验数据(1).xlsx`，原文件逐字节归档为 [source_experiments.xlsx](source_experiments.xlsx)。
本次9材料×2细胞×3时间×13浓度=702条件、54曲线，无条件重复或空字段。原351条HUVEC的粒径、Zeta、存活率未改变。历史434条训练数据未改动。

## 模型与输入

沿用历史434条/24文献组的基础Random Forest及冻结预处理器；没有重训、调参、校准或按新响应选择模型。只评估这个预先选定的主模型，不使用含IC50的辅助模型冒充低信息预测。
浓度按源表明确的元素Se μM，乘0.078971转成μg/mL，512 μM对应40.433152 μg/mL；log浓度也由换算值生成。
接种密度按最终源表与用户2026-11-03更正：H9C2 3000、HUVEC 2300 cells/well，缺失标志均为0。旧记录把接种数量放大100倍，已撤回；本版预测、SHAP及下游评价均按更正后的输入重新计算。

HUVEC组织沿用历史标签Vascular endothelium。H9C2在历史模型中是未知细胞类别，编码为全零；源表未提供组织，主分析保持缺失，由冻结预处理器填入Liver。这个Liver是模型默认值，不是H9C2真实组织，H9C2指标仅为该缺失字段策略下的条件性结果。另提供“组织作为未知类别全零编码”的敏感性分析，不按表现择优。
缺失年份、合成路线仍由冻结插补器处理。Glucose、LET、PAH、PEI、Sucrose、TW80修饰名称为未知类别，CS沿用Chitosan (CS)，PEG/PVP原样匹配。具体编码、默认值、版本和哈希见 [audit.json](audit.json)。

## 外部预测误差

| 细胞 | 条件数 | MAE（百分点） | MAE 95%区间 | RMSE | R² |
|---|---:|---:|---|---:|---:|
| ALL | 702 | 11.239 | [9.480, 13.848] | 16.578 | 0.486 |
| H9C2 | 351 | 7.971 | [5.836, 11.136] | 12.053 | 0.543 |
| HUVEC | 351 | 14.508 | [12.110, 17.063] | 20.109 | 0.447 |

95%区间为固定模型下2000次材料整组bootstrap百分位区间（seed=20261101）。每次保留抽中材料的全部细胞/时间/浓度，仅有9材料；它描述材料组成抽样的不确定性，不代表生物学重复、批间重复性或模型训练不确定性。所有702条件保留，未截断超过100%的实测存活率，未强迫0浓度预测为100%。分细胞、时间结果见 [prediction_metrics.csv](prediction_metrics.csv)。

## 曲线、IC50与排序

- [54条曲线误差与IAE](curve_metrics_54.csv)：同时报告线性浓度轴与正浓度log10轴的积分绝对误差及轴宽归一化值。采用实测和预测在对应轴上分段线性连接，对残差过零段拆分精确积分；0浓度保留在线性轴，log10轴仅0.25–512 μM。IAE单位分别为百分点·μM和百分点·log10(μM)。这不是原24浓度设计。
- [实验侧IC50](experimental_ic50.csv)：HUVEC 19条可插值、8条>512；H9C2 5条可插值、22条>512；合计24条可插值、30条>512。
- [模型侧IC50](model_ic50.csv)：54条全部>512 μM。普通有限数值配对为0，所以[IC50配对表](ic50_pairs.csv)保留删失状态，log误差和R²不可计算；不把>512替换成512。
- [排序明细](toxicity_rankings_512.csv)与[排序一致性](ranking_agreement.csv)：按512 μM、每种细胞各时间的9材料比较，存活率越低毒性排名越靠前。均采用平均秩处理并列，Kendall为tau-b。72 h时HUVEC Spearman=0.133、Kendall=0.111；H9C2为0.233、0.167，最高时间点的排序一致性较弱。
- [高浓度时间汇总](high_dose_time_summary.csv)：512 μM下HUVEC平均实测存活率24/48/72 h为59.805/39.071/26.383%；H9C2为64.673/59.618/52.316%。这些是9材料的描述性均值，不是独立重复均值。另见[逐材料时间变化](observed_time_changes.csv)及[对应细胞条件差值](observed_cell_comparison.csv)。两种细胞接种密度同时不同，不能将差值解释为纯细胞类型因果效应。
- [粒径/Zeta相关性](property_associations_512.csv)：按细胞和时间分别以9种材料为单位，仅报告描述性Spearman，不报告未获实验重复支持的显著性。
- [SHAP汇总](shap_summary.csv)、[条件级SHAP](shap_grouped_values.csv)、[全部编码特征SHAP](shap_encoded_values.csv)：精确TreeExplainer，tree_path_dependent/raw，以冻结树训练路径为背景。派生特征和one-hot贡献作有符号加和，完整保留702条。SHAP描述模型归因，不证明机理；缺失修饰物类别与分子量不能补造SHAP。

## 映射敏感性与旧版变化

H9C2组织改用未知类别全零编码时，MAE=8.267、R²=0.530，单条件预测最大变化3.439个百分点。见[tissue_mapping_sensitivity.csv](tissue_mapping_sensitivity.csv)。此情景不等于提供了真实心脏组织信息。

HUVEC原实验值未变化，接种数量从旧记录230000更正为2300/孔后，相对旧密度情景的预测平均变化为4.081个百分点，最大绝对变化7.164。见[版本配对](huvec_prediction_version_comparison.csv)，旧密度情景从保留的历史源表重建。这属于输入信息修正，不能写成新增湿实验导致模型训练改善。

## 尚需实验或资料

1. 原方案每曲线24浓度，当前13点；若严格完成原方案还差11点×54曲线=594个条件（不含重复）。具体新增浓度应据实验曲线覆盖阈值设计，不能靠插值补足条件数。
2. 表中每条件一个报告值，未提供原始重复孔、独立实验批次、汇总方式、检测方法、孔板规格、测定介质等。应先追溯原始记录；若实际没有独立重复，需要补做，不能直接声称“无重复”或虚构置信区间。
3. 实验侧30条曲线>512 μM：若需要有限IC50，应设计能覆盖50%阈值且实验可行的浓度范围；模型侧54条不达阈值本身是预测局限，不能通过删样本或外推精确IC50消除。
4. 缺Se含量、稳定性、Se 3d/XPS、晶相，以及统一修饰类别和经核实分子量；前者需补表征，后者可先回查资料。
5. 这些实验结果已知，本次只能称回顾性外部评价。严格盲法前瞻验证需新批次、实验前封存预测及时间证据。
6. 原4+20点few-shot需24浓度数据；本次不改成4+9点后宣称完成原任务。

## 复现与核验

在仓库根目录，使用已有`.venv`环境，输出目录须不存在或为空：

```powershell
.venv/Scripts/python.exe research/scripts/run_external_702.py --source research/results/external_702_20261101_confirmed/source_experiments.xlsx --output research/results/external_702_new_run
.venv/Scripts/python.exe research/scripts/report_external_702.py research/results/external_702_new_run
```

报告脚本同步更新主目录实验对照表，保留旧恢复目录的历史表不变。模型重载预测一致、源表与冻结模型哈希不变、SHAP加和成立，IC50通过自然对数公式独立检查，IAE通过数值求积独立检查。见[verification.json](verification.json)。
