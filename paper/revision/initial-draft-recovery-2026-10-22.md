# 历史初稿恢复与核查（2026-10-22）

核查目标为 [`2e4b970e35893faf950c03ca11720c0c0e97087e`](https://github.com/sunnyhmz7010/selenium-nanoparticle-cytotoxicity/tree/2e4b970e35893faf950c03ca11720c0c0e97087e)，即 2026-09-08 21:18:52（北京时间）合并 PR #83 后的英文初稿。

## 恢复结果

已在独立目录 [`paper/v1/initial-draft-2e4b970/`](../v1/initial-draft-2e4b970/) 恢复一套完整稿源：

- [英文入口 manuscript.tex](../v1/initial-draft-2e4b970/manuscript.tex)、`sections/` 五章、`references.bib`：直接取自目标提交。
- `sections_zh/` 五章：直接取自目标提交，保留真实历史中文。
- [中文入口 manuscript-zh.tex](../v1/initial-draft-2e4b970/manuscript-zh.tex)：从历史 `main_zh.tex` 恢复，仅修改文件名，内容字节保持一致。

中文入口来自 [`7a3aeb6c8b690b4974414b00427f88cae69f5522`](https://github.com/sunnyhmz7010/selenium-nanoparticle-cytotoxicity/commit/7a3aeb6c8b690b4974414b00427f88cae69f5522)。该提交在 9 月 8 日 16:28:32 从 `d0e26df529be95a76e406d3b3d14c343540202b7` 恢复入口和五章；16:30:12 的 [`42decef`](https://github.com/sunnyhmz7010/selenium-nanoparticle-cytotoxicity/commit/42decef3e47d85bbcbab69a2bcb8da385e3d710c) 又删除了入口，五章仍保留在目标提交中。

已通过 Git blob 哈希确认：找回的中文入口、五章和文献库全部与 `d0e26df` 相同；五章和文献库也全部与目标提交相同。入口原本已使用 `references.bib`，不需要调整正文或文献库。恢复文件共 13 个，均逐字节验证来源。原稿中的模板标题、作者、Keywords、Supporting information 等占位内容也按原样保留。

当前 `paper/v1/` 原有的中英文内容已混入后续 434 条记录、24 文献组及严格分组评价的重建结果，因此本次采用独立目录，避免将现有 V1 误当历史原稿。原有 12 个 V1 文件逐一重算 SHA256，与操作前一致；V2 和研究材料也未改动。本次没有提交或推送 Git。

## 英文是否包含文献库全部文献

**文献库包含全部 66 篇，但英文稿实际只引用并生成其中 23 篇，缺少另外 43 篇数据来源文献。**

| 核查项 | 英文历史稿 | 对应中文历史稿 |
| --- | ---: | ---: |
| 共享 `references.bib` 条目数 | 66 | 66 |
| 正文 cite 指令数 | 31 | 33 |
| 实际引用的不同文献数 | 23 | 66 |
| 文献库中未被引用的条目 | 43 | 0 |
| 无定义引用键 | 0 | 0 |
| 完整编译生成的 BBL 条目 | 23 | 66 |

核查递归跟踪入口及全部五章，排除注释；没有 `nocite`、交叉条目或其他额外纳入机制。英文入口第 49 行加载 `references.bib`，第 199 行直接 `printbibliography`，因此文献库“存着 66 篇”并不等于正文末尾会列出 66 篇。XeLaTeX 的 BCF 与 Biber 的 BBL 也独立确认了上述 23/66 的数量和引用键集合。

缺少的 43 篇正是中文方法第 14、23 行及中文结论第 5 行整组引用的数据来源。英文方法第 9 行改称完整清单及每篇提取记录数见补充表 Table S1，结论也删除了整组引用。然而目标提交完整树中没有对应补充表文件，英文入口第 182 行的 Supporting information 仍为模板。因此只能确认“英文改称见 Table S1”，无法确认这些文献已在该提交的补充材料中完整交付。

原始证据：[英文方法](https://github.com/sunnyhmz7010/selenium-nanoparticle-cytotoxicity/blob/2e4b970e35893faf950c03ca11720c0c0e97087e/sections/02-methods.tex#L9)、[中文方法](https://github.com/sunnyhmz7010/selenium-nanoparticle-cytotoxicity/blob/2e4b970e35893faf950c03ca11720c0c0e97087e/sections_zh/02-methods.tex#L14)、[英文参考文献输出](https://github.com/sunnyhmz7010/selenium-nanoparticle-cytotoxicity/blob/2e4b970e35893faf950c03ca11720c0c0e97087e/manuscript.tex#L199)。

## 是否先翻译、再独立修改英文

**是，提交补丁明确支持这一判断。** 下列时间均为北京时间，日期均为 2026-09-08：

| 时间 | 提交 | 实际变化 |
| --- | --- | --- |
| 15:16–15:49 | `1e34cd3`、`957aeb9`、`045f13b`、`5fc10a0`、`b50ae68` 等 | 分别加入摘要、结论、引言、方法、结果的英文正文；部分中文暂存为注释或重复正文 |
| 16:31–16:33 | `610c03f`、`bda6c7e`、`a6346c3`、`3bd403e`、`b2014a0` | 清除英文正文文件中的中文备份 |
| 18:09:47 | [`73139ab`](https://github.com/sunnyhmz7010/selenium-nanoparticle-cytotoxicity/commit/73139ab55642beba7a15804aa8a25e94816fdee5) | 独立修改英文方法：删除 43 篇长引用，新增融合描述，补充阈值来源 |
| 18:11:36 | [`d11ac2a`](https://github.com/sunnyhmz7010/selenium-nanoparticle-cytotoxicity/commit/d11ac2a3fe7796092c0db1374118712f0167d2ce) | 独立修改英文结果，呼应融合框架 |
| 18:14:15 | [`cf35554`](https://github.com/sunnyhmz7010/selenium-nanoparticle-cytotoxicity/commit/cf35554845d73797665de64490fd4b248eb18c69) | 独立修改英文结论，删除长引用，加入融合与后续验证表述 |
| 21:18:52 | `2e4b970` | 合并为本次目标初稿 |

不能仅凭早先 `english-translation` 分支名判断翻译时间：9 月 7 日 `d0e26df` 的 `sections_en/` 五个文件仍全部为空。中文正文主要保留 5–6 月的内容，其中摘要、方法、结论最后的实质修改在 6 月 16 日；9 月的恢复没有同步英文后期修订。

### 主要内容差异

| 事项 | 中文历史稿 | 最终英文初稿 |
| --- | --- | --- |
| 43 篇数据来源 | 方法与结论保留完整引用 | 删除长引用，改称见 Table S1；对应补充表未随该提交保存 |
| 多模态融合 | 方法第 147–150 行划分基础与增强特征，没有联合注意力流程 | 方法第 110–115 行新增模态划分、特征拼接、IC50 可选查询的 cross-attention、旁路及残差连接；属于文字流程，没有新增注意力数学公式 |
| 融合结果 | 没有“所有增强配置均使用融合”及与简单拼接的比较陈述 | 结果第 52、104 行新增这些陈述，称注意力相对简单拼接未显著提升 |
| 85% 阈值 | 方法第 156 行已有阈值 | 方法第 122 行新增归因于 Masarkar 的说明和引用；阈值本身并非英文首次引入 |
| IC50 边界 | 已强调它与响应终点相关，只适合作辅助解释 | 保留并重组谨慎定位，另赋予融合中可选查询的角色；不能将全部谨慎措辞都视为英文新增 |
| 特征名称 | 结果第 75、77 行使用 `IC50_uM` | 结果第 81、83 行改为 `IC50` |
| 后续验证及模型定位 | 结论泛称新增实验、外部验证，将随机森林作比较基线 | 结论进一步强调部署候选，新增“正在表征的自合成 SeNP 数据”将用于外部验证 |

上述三个英文后期提交没有更新表列的核心模型性能数字。这里核实的是历史文字差异，不将原稿的融合或实验陈述当作本次已经验证的算法结果。恢复稿保留这些真实差异，没有把英文新增内容反译进中文，也没有补改英文的缺失引用。

## 验证与复核

- 13 个恢复文件的 Git blob 和 SHA256、引用键及完整出现位置、中文来源对照、编译结果见[机器可读核验记录](initial-draft-recovery-2026-10-22.json)。
- 使用既有 TeX Live、XeLaTeX 和 Biber 2.21，执行 XeLaTeX → Biber → XeLaTeX → XeLaTeX。英文生成 16 页、中文生成 20 页；最终日志无未定义引用、空参考文献或要求重跑 Biber 的提示。BBL 分别包含 23 和 66 个条目。
- 保留原稿字体及版面问题：存在破折号、部分希腊字母的缺字警告，中文还有字号替代警告。编译成功不代表这些历史排版问题已修复。Codex 内置编译尝试曾超时，以上成功结果来自本地 TeX Live 完整编译。
- 构建产物与日志在 `work/initial-draft-audit-20261022/build/`；原始 API 元数据、提交补丁、下载快照和审计脚本在同一任务目录的 `history/`、`citations/` 中。

在恢复目录内可使用 `latexmk -xelatex manuscript-zh.tex` 或 `latexmk -xelatex manuscript.tex` 编译；需保留同目录文献库及两个章节目录。

## 英文未引用的 43 篇文献

| 文献键 | 定义位置 |
| --- | --- |
| `chen_selenium_2008` | references.bib:176 |
| `li_reversal_2011` | references.bib:188 |
| `zheng_sialic_2011` | references.bib:200 |
| `liu_selenium_2012` | references.bib:212 |
| `wu_surface_2012` | references.bib:224 |
| `chen_surface_2012` | references.bib:235 |
| `yu_positive_2012` | references.bib:245 |
| `chen_peg-nanolized_2012` | references.bib:257 |
| `pi_pathway_2013` | references.bib:267 |
| `wu_induction_2013` | references.bib:279 |
| `feng_differential_2014` | references.bib:291 |
| `huang_selective_2013` | references.bib:302 |
| `li_functionalized_2013` | references.bib:314 |
| `zhang_enhancement_2013` | references.bib:325 |
| `jiang_gracilaria_2014` | references.bib:337 |
| `yu_ph-responsive_2014` | references.bib:349 |
| `zeng_construction_2015` | references.bib:360 |
| `liu_sequentially_2016` | references.bib:371 |
| `liu_facile_2016` | references.bib:383 |
| `yu_x-ray-responsive_2016` | references.bib:395 |
| `fu_rgd_2016` | references.bib:406 |
| `fang_targeting_2017` | references.bib:418 |
| `chen_efficient_2018` | references.bib:429 |
| `fang_dualtargeted_2018` | references.bib:441 |
| `huang_autophagy_2018` | references.bib:453 |
| `liu_highly_2018` | references.bib:464 |
| `wang_regulating_2016` | references.bib:475 |
| `hu_selenium_2019` | references.bib:486 |
| `zeng_potentiation_2019` | references.bib:497 |
| `huang_dual-targeting_2019` | references.bib:509 |
| `huang_highly_2019` | references.bib:520 |
| `zhang_systematic_2019` | references.bib:532 |
| `zheng_thermosensitive_2019` | references.bib:543 |
| `huang_chiralitydriven_2020` | references.bib:554 |
| `yang_lentinan-functionalized_2020` | references.bib:566 |
| `liu_rapid_2021` | references.bib:577 |
| `an_functionalized_2021` | references.bib:588 |
| `song_translational_2021` | references.bib:599 |
| `yang_atherosclerotic_2022` | references.bib:611 |
| `yang_functionalized_2021` | references.bib:622 |
| `liang_translational_2022` | references.bib:633 |
| `liu_specific_2022` | references.bib:644 |
| `du_highly_2022` | references.bib:655 |
