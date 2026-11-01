# 论文实验与分析对照表（按现有数据调整后的研究范围）

范围调整记录：2026-11-01（数据已查看后）。用户确认新增实验数据仅此一份，现有9材料×2体系×3时间×13浓度=702条件、54曲线构成本研究全部外部实验数据。调整后研究主线为历史文献建模→双体系剂量—时间响应→冻结模型外部评价→少量测点回顾性模拟。

状态定义：“现有分析已完成”指调整后范围内的分析与结果已交付，包括阴性结果与不可计算的阈值指标；“现有数据可补算”只标识尚未完成的可执行计算；“经方案调整移出范围”不代表原任务已经完成。重复次数、方法、汇总方式和缺失字段作为报告边界，不再挂为本轮待完成实验。

[调整后完整分析](../../research/results/external_702_reframed_20261101/README.md) · [范围调整前对照表](../../research/results/external_702_reframed_20261101/experiment_status_before_scope_change.md) · [计算前固定方案](../../research/results/external_702_reframed_20261101/analysis_plan.json)

| 原序号 | 原方案条目 | 调整后目标/处理 | 当前状态 | 结果或边界 | 证据 |
|---:|---|---|---|---|---|
| 1 | 建立“历史建模—低信息预测—前瞻验证—信息增益分析”体系 | 历史建模→双体系剂量时间响应→冻结外部评价→少量测点模拟 | 现有分析已完成 | 完整证据链已形成；不要求原方案所有湿实验完成 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 2 | 将数据分为通用纳米材料、历史SeNP和前瞻实验三部分 | 通用、历史SeNP与702外部实验数据分别管理 | 现有分析已完成 | 702不并回历史434训练集 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 3 | Phase I：训练General Nanotoxicity Backbone | 保留历史General基准 | 现有分析已完成 | 3889条、144文献组的固定预算计算已有 | [历史结果](../../research/results/general_benchmark/summary.json) |
| 4 | Phase II：实现General-to-SeNP迁移 | 保留General→SeNP迁移对照 | 现有分析已完成 | 未获稳定增益作为结果，不以证明有效为完成条件 | [历史结果](../../research/results/transfer_comparison/summary.json) |
| 5 | Phase III：建立低信息材料表示 | 使用已有粒径、Zeta、修饰名称、暴露和体系信息 | 现有分析已完成 | 真实接种数量已纳入冻结输入；缺失默认值已审计 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 6 | 修饰物使用Modifier Category和Molecular Weight，而非具体名称 | 不要求补齐Modifier Category与MW | 经方案调整移出范围 | 不伪造类别或分子量；结论限于已有名称字段 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 7 | Exposure使用log浓度、log时间及dose×time交互 | 保留暴露特征与历史交互消融 | 现有分析已完成 | 阴性交互结果照实报告，外部按时间分层评价 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 8 | Biological Context结构化为物种、组织、正常/肿瘤和细胞类型 | 描述两种实验体系，不宣称完整生物背景编码 | 现有分析已完成 | H9C2未知类别及组织默认值作为解释边界 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 9 | Phase V：融合材料、暴露、生物环境及通用表示建立主模型 | 以既有冻结RF为主模型 | 现有分析已完成 | 四分支融合架构移出当前目标，不追加新模型训练 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 10 | Phase VI：比较Minimal Model与材料化学增强模型 | 保留历史基础与化学增强对照 | 现有分析已完成 | 未获稳定改善；没有外部化学增强结果可推断 | [历史结果](../../research/results/improved_434/summary.json) |
| 11 | 加入Se含量、稳定性、Se 3d和晶相并评估增量价值 | 报告现有化学描述符的历史增量评价 | 现有分析已完成 | 历史阴性结果保留；新增化学表征移出范围 | [历史结果](../../research/results/improved_434/summary.json) |
| 12 | 建立L1—L4四级Information-Level实验 | 取消完整L1—L4信息等级设计 | 经方案调整移出范围 | 缺失字段不再作为当前研究待办 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 13 | Phase VII：使用Publication-grouped CV | 保留文献分组历史评价 | 现有分析已完成 | 434记录24文献组，不与外部702混算 | [历史结果](../../research/results/improved_434/summary.json) |
| 14 | 进一步采用Formulation-grouped CV | 不开展缺可靠配方ID的分组CV | 经方案调整移出范围 | 不将材料名称冒充配方或批次ID | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 15 | Feature Selection与调参使用Nested Grouped CV | 保留历史Nested Grouped CV | 现有分析已完成 | 5外层×3内层；外部响应不用于调参 | [历史结果](../../research/results/improved_434/summary.json) |
| 16 | 避免31种组合筛选后在同一CV上直接报告性能 | 保留选择折与报告折分离 | 现有分析已完成 | 新校准锚点不搜索，八检验点不拟合偏移 | [结果](../../research/results/external_702_reframed_20261101/analysis_plan.json) |
| 17 | Phase VIII：测量9种新SeNP的Se含量、稳定性、Se 3d和晶相 | 完整Se含量、稳定性、Se 3d/XPS、晶相表征 | 经方案调整移出范围 | 不再列为本研究未完成实验；放弃相关机制主张 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 18 | Phase IX：完成9×2×3×24细胞毒性实验 | 以9×2×3×13=702作为实际研究设计 | 现有分析已完成 | 54曲线完整覆盖；24点设计正式移出范围 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 19 | 24个浓度采用对数间隔并覆盖完整毒性区间 | 评价实际0–512 μM浓度范围 | 现有分析已完成 | 不强求曲线穿越50%；以nAUC覆盖全部曲线 | [结果](../../research/results/external_702_reframed_20261101/auc_curve_values_54.csv) |
| 20 | 用三个时间点验证dose×time二维响应面 | 18个材料—体系剂量时间网格的描述性评价 | 现有分析已完成 | 比较时间变化；H9C2综合AUC非严格单调；不做重复显著性 | [结果](../../research/results/external_702_reframed_20261101/auc_descriptive_summary.csv) |
| 21 | 先冻结模型，再测新材料毒性 | 取消对已有实验追补事前盲法的要求 | 经方案调整移出范围 | 保留实际模型冻结、源数据和分析时间记录 | [结果](../../research/results/external_702_reframed_20261101/analysis_plan.json) |
| 22 | Phase X：Prospective Zero-Shot Validation | 冻结模型的回顾性外部评价 | 现有分析已完成 | 702条件MAE11.686/R²0.503，不称前瞻盲测 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 23 | 报告MAE、RMSE、R²和95%区间 | MAE、RMSE、R²与材料组区间 | 现有分析已完成 | 校准在同一432检验条件上公平比较 | [结果](../../research/results/external_702_reframed_20261101/fewshot_metrics.csv) |
| 24 | Phase XI：验证54条Dose-Response Curve并计算IAE | 54曲线IAE与归一化AUC | 现有分析已完成 | 主要log正浓度nAUC R²0.084；线性轴结果完整保留 | [结果](../../research/results/external_702_reframed_20261101/auc_prediction_metrics.csv) |
| 25 | Phase XII：不把真实IC50作为主模型输入，应从预测曲线估算IC50 | 不使用实测IC50输入，报告预测阈值状态 | 现有分析已完成 | 冻结模型54曲线均>512，不外推有限数值 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 26 | 比较预测IC50与实验IC50，并报告log误差和R² | IC50阈值与删失作为辅助终点 | 现有分析已完成 | 实验24可插值/30右删失；有限配对0，log误差/R²不可计算 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 27 | Phase XIII：比较9种修饰SeNP的真实与预测毒性排序 | 固定高浓度与整曲线nAUC分别比较材料 | 现有分析已完成 | 不用一种条件下排名代表全局毒性序列 | [结果](../../research/results/external_702_reframed_20261101/auc_ranking_agreement.csv) |
| 28 | 用Spearman ρ和Kendall τ评价排序 | 分体系和时间报告Spearman/Kendall | 现有分析已完成 | 描述性n=9材料，不冒充独立实验显著性 | [结果](../../research/results/external_702_reframed_20261101/auc_ranking_agreement.csv) |
| 29 | Phase XIV：开展结构—性质—毒性分析 | 性质—响应探索性关联 | 现有分析已完成 | 粒径/Zeta/名称同时变化；取消因果机制目标 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 30 | 使用SHAP解释Modifier、MW、粒径和Zeta作用 | 仅解释模型已有特征的SHAP行为 | 现有分析已完成 | 702条件加和已核验；不提供不存在的MW/类别SHAP | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 31 | 比较SeNP-only与General→SeNP | 保留SeNP-only与迁移的阴性对照 | 现有分析已完成 | 不因阴性结果要求额外实验 | [历史结果](../../research/results/transfer_comparison/summary.json) |
| 32 | 比较Without与With dose-time interaction | 保留显式dose-time交互消融 | 现有分析已完成 | 没有稳定改善为有效结果 | [历史结果](../../research/results/dose_time_interaction/summary.json) |
| 33 | 比较Random CV与Publication-grouped CV | 不新增同口径随机/分组受控对照 | 经方案调整移出范围 | 历史两种口径保留，不能将差异全归因于拆分 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 34 | 将Historical Validation与Prospective Validation分开 | 历史验证、冻结外部评价、校准模拟三者分列 | 现有分析已完成 | 702全条件与432检验条件成绩不能直接混比 | [结果](../../research/results/external_702_reframed_20261101/README.md) |
| 35 | Few-shot：每条24点曲线用4点校准并预测剩余20点 | 四点校准、八个正浓度点检验 | 现有分析已完成 | 偏移MAE11.714→10.303；简单锚点插值5.711，RF未获额外优势 | [结果](../../research/results/external_702_reframed_20261101/paired_mae_comparisons.csv) |
| 36 | 按General→Transfer→Minimal→消融→历史→前瞻的证据链重排论文 | 按调整后证据链交付报告与V3结论草稿 | 现有分析已完成 | 本轮完成分析写作；正式V3全文重排不属于本轮范围 | [结果](../../research/results/external_702_reframed_20261101/conclusion_for_v3.md) |

本次没有按新702条训练新模型，也没有以四点响应为输入后的0.854 R²替代冻结模型外部0.503 R²。54曲线、432检验条件来自9种材料，重复实验数未知；材料bootstrap不能代替生物学重复。
