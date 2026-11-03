"""汇总八项补充实验，保留阴性结果、拟合诊断与选点可比性。"""
import argparse
import json
from pathlib import Path
import shutil

import pandas as pd

from run_huvec_external import digest,write_json

ROOT=Path(__file__).resolve().parents[1]


def table(frame,columns,labels):
    lines=['| '+' | '.join(labels)+' |','|'+'|'.join(['---']*len(labels))+'|']
    for row in frame.to_dict('records'):
        values=[f'{row[c]:.3f}' if isinstance(row[c],float) else str(row[c]) for c in columns]
        lines.append('| '+' | '.join(values)+' |')
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    out=parser.parse_args().directory.resolve();read=lambda n:pd.read_csv(out/n)
    select=lambda f:f.loc[f.cell_type.eq('ALL')&f.time_h.eq('ALL')]
    one=select(read('experiment1_metrics.csv'));two=select(read('experiment2_metrics.csv'))
    three=select(read('experiment3_metrics.csv'));four=select(read('experiment4_metrics.csv'))
    five=select(read('experiment5_zero_shot_metrics.csv'));six=select(read('experiment6_metrics.csv'))
    validation=json.loads((out/'verification.json').read_text(encoding='utf-8'))
    assert validation['status']=='PASS'
    fusion=two.set_index('method')
    selections=read('experiment2_selection_log.csv')
    global_choices=selections.loc[selections.selection.eq('global_lambda'),'chosen'].value_counts().sort_index()
    fusion_delta=read('experiment2_paired_comparisons.csv').query("cell_type == 'ALL' and target == 'prior_lomo_global' and reference == 'loglinear'").iloc[0]
    zero=five.loc[five.dose_scope.eq('all_13')].set_index('method')
    zero_comparisons=read('experiment5_paired_comparisons.csv').query("cell_type == 'ALL'").set_index(['target','reference'])
    self_delta=zero_comparisons.loc[('self_only_rf','frozen_historical_rf')]
    residual_delta=zero_comparisons.loc[('historical_plus_residual_rf','self_only_rf')]
    report='''# 纳米硒702条数据的八项补充计算实验

## 核心结果

八项现有数据计算已完成。固定四个锚点、相同432个检验条件下，PCHIP MAE=5.655、R²=0.8544；对数线性插值MAE=5.711、R²=0.8538，二者配对MAE差为−0.056个百分点，材料bootstrap 95%区间[−0.326, 0.186]，不支持稳定优于。

文献RF曲率先验、按其他材料选择权重以及本次剂量—时间联合方法均未显示稳定增益。最有补充价值的正面观察是：在同一组目标浓度上，将锚点数从2增至4可降低误差，而4之后的增量较小；此结论仅适用于固定网格、锚点顺序与这9种材料的回顾性模拟，不等于普适最优测点数或已经证实的湿实验成本节约。

## 数据、分割与统计口径

- 原始自测汇总为9材料×2实验体系×3时间×13浓度=702条件；重建任务使用12个正浓度，0浓度对照单列。四锚点固定0.25、4、64、512 μM Se；其余8点共432个检验条件。
- 文献基础RF与冻结预测保留，模型文件哈希未变。补充的“自测RF”和“文献RF＋残差RF”每折只使用其他8材料的624条件，留出材料的两体系、三时间和全部浓度78条件一起留出。不是把全部702条拟合后再报告训练精度。
- λ、最佳基线方法和优化锚点仅用其他8材料选择；留出材料只允许访问规定锚点的实测响应。各曲线的八个检验点不参与该曲线拟合。所有分析是在既有数据和先前结果已查看后开展的探索性计算，不称预注册或新批次盲法验证。
- 区间均按9材料整组重采样2000次，保留其两体系、全部时间与条件；基于保存的外层折预测计算，没有在每次bootstrap内重做方法选择或RF训练，属于条件性探索区间。未作多重检验校正，不将区间排除0表述为生物重复意义的显著性。
- V3记载HUVEC为MTT、5技术复孔汇总、1次独立实验。当前计算读取的是条件汇总值，没有原始孔级吸光度或逐孔误差；不能恢复独立重复标准差。H9C2方法不能仅凭HUVEC记录自动推定。两种体系接种数量不同，体系差异不是纯细胞类型效应。
- 源表存活率及所有预测均未按0–100%截断；约束4PL参数属于显式模型假设。没有填补新的实验浓度或化学表征。

方案在计算前记录于[analysis_plan.json](analysis_plan.json)，原702条件评价及数据审计见[前次冻结评价](../external_702_20261101_confirmed/README.md)。

## 实验1：固定四点、多方法重建

'''
    display=one.loc[one.method.ne('4pl_or_loglinear')].sort_values('mae')
    report+=table(display,['method','n','mae','rmse','r2','coverage'],['方法','检验条件','MAE（百分点）','RMSE','R²','预测覆盖率'])
    report+='''

全部方法均覆盖432检验条件。4PL数值拟合54曲线均有返回，但25条出现参数边界或Jacobian条件数过大，其余29条也是4锚点拟合4参数、没有残差自由度，因此不能据此声称参数可辨识或IC50估计可靠。明确记录的4PL→对数线性回退本次未触发，复合方法与原4PL数值相同。

自然样条使用natural边界，Akima使用原akima形式。GP为常数×RBF＋白噪声核，核参数只用允许的锚点最大化边际似然，不使用检验响应；收敛/边界警告逐曲线保留。PCHIP的微小点估计优势不能作为新算法或普适优越性。

证据：[逐点预测](experiment1_predictions.csv)、[完整分层指标](experiment1_metrics.csv)、[配对区间](experiment1_paired_comparisons.csv)、[拟合诊断](experiment1_fit_diagnostics.csv)、[预测范围](prediction_ranges.csv)。图：[方法比较PDF](figures/method_comparison.pdf)。

## 实验2：历史RF曲率先验融合

模型为 `I_observed(x) + lambda × [RF(x) − I_RF(x)]`，所有插值均在log10浓度轴上。固定λ=0/0.25/0.5/0.75/1全部报告；λ=0退化为原线性插值，λ=1为RF加插值残差。外层按材料留一，分别用其他8材料选择全局λ、分体系λ和最优基线。平局优先较小λ或预先列出的基线顺序。

'''
    report+=table(two,['method','mae','rmse','r2'],['方案','MAE','RMSE','R²'])
    report+=f'''

全局λ选择为{'、'.join(f'{value}（{count}折）' for value,count in global_choices.items())}；分体系选择也只选0或0.25，说明大权重RF曲率没有得到训练材料支持。外层全局融合MAE={fusion.loc['prior_lomo_global','mae']:.3f}、分体系融合{fusion.loc['prior_lomo_cell','mae']:.3f}，均未优于线性插值{fusion.loc['loglinear','mae']:.3f}或PCHIP{fusion.loc['pchip','mae']:.3f}。全局融合相对线性插值差值{fusion_delta.mae_difference:+.3f}，材料区间[{fusion_delta.ci_low:.3f}, {fusion_delta.ci_high:.3f}]。按材料选择的基线为8折PCHIP、1折线性插值，外层MAE={fusion.loc['baseline_lomo_selected','mae']:.3f}。

完整正浓度网格nAUC另行保留为“锚点条件下的重建面积”指标，包含已测锚点，不能当作全新曲线的独立外部预测。现有融合不具备同时改善主要MAE和曲线指标的稳定证据。

证据：[权重/方法选择日志](experiment2_selection_log.csv)、[逐点外层预测](experiment2_predictions.csv)、[分层指标](experiment2_metrics.csv)、[配对比较](experiment2_paired_comparisons.csv)、[条件性nAUC](experiment2_conditioned_auc.csv)。

## 实验3：2—6个测点的预算消融

同时给出两类协议：等log间距锚点、评价各自剩余点；以及嵌套锚点、始终评价同一6个查询浓度（0.5、1、8、16、32、256 μM），共324条件。前者不同K的查询组成变化，不能直接把误差差异全部归因于预算；后者用于配对比较。

同查询协议的锚点顺序为端点0.25/512，再加4、64、2、128 μM，顺序在本轮运行前固定。结果如下：

'''
    report+=table(three.loc[three.protocol.eq('nested_matched_queries')&three.method.isin(['loglinear','pchip'])],['k','method','n','mae','r2'],['锚点数','方法','同查询条件数','MAE','R²'])
    report+='''

线性插值3→4点的配对MAE差为−1.237，区间[−2.266, −0.156]；PCHIP为−1.821，区间[−3.021, −0.490]。4→5、5→6的两种方法区间均跨0，提示该固定查询设计下4点附近出现收益平台。不能从这一个锚点序列得出“任何四点都最优”，也不能将不同查询协议的6.26与原432点的5.71直接当作性能升降。

证据：[两类完整分层指标](experiment3_metrics.csv)、[锚点与查询浓度](experiment3_anchor_sets.csv)、[逐点预测](experiment3_predictions.csv)、[相同目标的配对区间](experiment3_matched_paired_comparisons.csv)。图：[同查询预算PDF](figures/budget_matched_queries.pdf)。

## 实验4：固定、优化和自适应锚点位置

比较原固定、等log间距、低浓度密集、高浓度密集、其他8材料优化、基于已开放锚点的自适应策略。所有方案包含最低和最高正浓度；优化仅搜索10个内部浓度中选2的45种组合。自适应规则先测端点，然后选择“已测端点差×log间隔”最大区间的中间可测点，只读取已经开放的锚点。

另固定1、8、16、128 μM为所有策略共同查询点，禁止作为锚点；优化因此只搜索15个可用锚点组合。这一共同查询比较避免不同选点把难点移进训练集后产生表面优势。

'''
    report+=table(four,['protocol','method','n','mae','r2'],['协议','策略','检验条件','MAE','R²'])
    report+='''

各自剩余8点协议下，自适应MAE=5.604略低于原固定5.711，但检验浓度不同，不能直接认定改善；共同4查询协议中自适应与固定预测完全相同（MAE均6.996）。训练材料优化为7.104，没有优于原固定。低/高浓度密集策略在共同查询上误差较高；目前不支持一个稳定优于原方案的跨材料优化位置规则。

证据：[具体锚点](experiment4_anchor_selection.csv)、[所有训练材料搜索分数](experiment4_training_search.csv)、[外层逐点预测](experiment4_predictions.csv)、[指标](experiment4_metrics.csv)、[共同查询配对比较](experiment4_matched_paired_comparisons.csv)。

## 实验5：留一材料的零样本预测与四点辅助任务

每折训练8材料624条件，留出1材料78条件。A任务不使用留出材料任何响应；B任务只允许该材料各曲线4个锚点，另8点计分。B任务的权重和方法选择已在实验2报告，绝不把其成绩称作零样本预测。

A任务用冻结历史RF、自测RF、冻结历史RF＋自测残差RF比较。两种新拟合使用克隆的原250树、min_samples_leaf=4、seed=42固定配置，没有调参。每折只在8材料上拟合预处理；自测表整列缺失的Year和Synthesis_Method被插补器明确剔除，H9C2组织由折内模式处理，均非新测得生物信息。目标材料修饰类别没有进入该折编码器。9折×2种模型共18个模型另存，原历史模型不覆盖。

'''
    report+=table(five,['dose_scope','method','n','mae','rmse','r2'],['浓度范围','模型','条件数','MAE','RMSE','R²'])
    report+=f'''

全702条件下自测RF的MAE最低（{zero.loc['self_only_rf','mae']:.3f}），但R²为{zero.loc['self_only_rf','r2']:.3f}，低于冻结历史模型{zero.loc['frozen_historical_rf','r2']:.3f}；其相对冻结模型MAE差区间[{self_delta.ci_low:.3f}, {self_delta.ci_high:.3f}]跨0。历史＋残差RF相对自测RF差值{residual_delta.mae_difference:+.3f}，区间[{residual_delta.ci_low:.3f}, {residual_delta.ci_high:.3f}]跨0。没有建立稳定的历史知识增量，不能只选择MAE改善而忽略RMSE/R²变化。正浓度648条件结果也完整报告，避免对照值影响解释。

证据：[材料折分配](lomo_fold_assignments.csv)、[A任务外层预测](experiment5_zero_shot_predictions.csv)、[分层误差](experiment5_zero_shot_metrics.csv)、[配对比较](experiment5_paired_comparisons.csv)、[预处理警告](experiment5_fit_warnings.csv)。

## 实验6：剂量—时间联合重建

每个材料—体系允许读取3时间×4浓度=12个锚点，预测相同三个时间网格的其余正浓度。比较二维薄板RBF、二维GP、其他8材料的平均插值残差模板，以及原独立时间线性/PCHIP/GP。联合方法使用其他已测时间的锚点，属于已测时间网格内重建，不是未来时间预测。

'''
    report+=table(six,['method','n','mae','rmse','r2'],['方法','检验条件','MAE','RMSE','R²'])
    report+='''

二维RBF相对线性插值的MAE差为+0.205，区间[−0.101, 0.443]；二维GP误差更大，其他材料残差模板也未显示稳定收益。当前三时间的联合方案不能作为已获性能提升的成果。

证据：[逐点预测](experiment6_predictions.csv)、[指标](experiment6_metrics.csv)、[配对区间](experiment6_paired_comparisons.csv)、[拟合记录](experiment6_fit_log.csv)。

## 实验7：响应形态及材料关联

54条曲线均提取正浓度最低/最高报告存活率、最低值浓度、端点变化、最陡下降区间、局部回升次数及nAUC。另列18个材料—体系的24→72 h nAUC差值。

以log浓度梯形权重对12个响应做离散网格加权PCA，PC1解释74.49%、PC2解释10.77%、PC3解释6.04%的响应变异；这不是连续函数基展开的完整FPCA。预先固定3组KMeans只用于描述，不将簇解释为经独立实验验证的毒性类型。粒径/Zeta与nAUC、端点变化和最低响应的关联按体系与时间以9材料计算Spearman，只报告系数，不作机制或多重检验显著性主张。

证据：[逐曲线形态](experiment7_curve_shapes.csv)、[PCA权重](experiment7_pca_loadings.csv)、[时间变化](experiment7_nauc_time_changes.csv)、[性质关联](experiment7_property_associations.csv)。图：[响应形态PCA PDF](figures/weighted_response_pca.pdf)。

## 实验8：稳定性与敏感性

已给出各材料MAE、从汇总评价中每次删除一个材料的指标稳定性、材料bootstrap配对区间、线性/对数轴nAUC对照、H9C2组织处理敏感性及所有预测范围。指标删除材料的分析不重新拟合，与实验5的训练留一材料任务明确区分。

54个报告对照均为100%，因此在这些汇总值上再按对照归一化是恒等操作，最大变化为0；这不能替代缺失的原始吸光度校正。所有超过100%的原始报告值保留，未进行平滑后替换或任意截断。

证据：[逐材料误差](experiment8_method_material_metrics.csv)、[删组指标稳定性](experiment8_omit_material_stability.csv)、[nAUC轴敏感性](experiment8_auc_axis_sensitivity.csv)、[组织编码敏感性](experiment8_tissue_sensitivity.csv)、[对照归一化说明](experiment8_control_normalization.json)。

## 可以写入论文的新结论

1. 在固定四锚点、相同432个查询条件下，线性与PCHIP是当前较强的简洁重建基线；PCHIP虽数值略低，但没有稳定超越线性插值的证据。
2. 在固定目标浓度与嵌套测点顺序下，2→4个锚点降低了重建误差；4之后增加到5/6点的收益较小且不稳定，为本数据范围内的测点预算权衡提供描述性依据。
3. 复杂插值、RF曲率融合、按材料训练权重、二维剂量时间模型和残差迁移尚未形成稳定的额外优势。方法创新或历史知识增益不能由本次结果预先成立。
4. 当前研究较稳妥的新增主线是“严格材料留出下的稀疏响应重建方法比较与测点预算评价”；所有结论限于已有9材料、两体系和固定已测区间，不扩展为新批次安全性或生物机制。

## 图形、复现与交付记录

四幅图均为Python/matplotlib绘制，PDF/SVG为可编辑矢量图，300 dpi PNG为预览。方法与预算图的区间均是材料组bootstrap，不是生物重复误差条。固定案例图预先指定CS-SeNPs、72 h的两体系，不按最优重建误差挑选；仅示例排除其他曲线，全部54曲线都进入定量比较。PCA图使用全部54曲线。图中的0浓度因log轴与正浓度重建任务定义而不展示，原始对照保留。

[固定曲线案例PDF](figures/fixed_curve_examples.pdf)。布局对齐、字体和PDF碰撞审计文件与图同目录。静态源码审计的非阻断项已经核对：随机数只用于真实数据bootstrap，不生成模拟观测；PNG是预览，PDF/SVG是正式矢量产物；使用180 mm宽度并独立核对；所有log浓度均为正。未指定投稿期刊，未冒称满足某刊全部投稿要求。

```
.venv/Scripts/python.exe research/scripts/run_supplement_702.py --output research/results/supplement_702_new_run
.venv/Scripts/python.exe research/scripts/verify_supplement_702.py research/results/supplement_702_new_run
.venv/Scripts/python.exe research/scripts/plot_supplement_702.py research/results/supplement_702_new_run
.venv/Scripts/python.exe research/scripts/report_supplement_702.py research/results/supplement_702_new_run
```

绘图后还需运行随工程既有图形技能提供的字体、对齐和碰撞审计；本次最终核验见[verification.json](verification.json)与[figure_qa.json](figure_qa.json)。源数据与历史冻结模型哈希保持一致。另存的18个折模型仅用于本次验证，不替换历史模型。
'''
    (out/'README.md').write_text(report,encoding='utf-8',newline='\n')
    statuses=[(1,'固定四点多方法比较','PCHIP 5.655；线性5.711，配对区间跨0','experiment1_metrics.csv'),
        (2,'RF先验曲率融合','材料留出全局/分体系权重未获稳定增益','experiment2_metrics.csv'),
        (3,'2—6点预算消融','相同查询下2→4改善、4→6增益有限','experiment3_matched_paired_comparisons.csv'),
        (4,'锚点策略优化与自适应','共同查询下未稳定优于原固定方案','experiment4_metrics.csv'),
        (5,'按材料留一的零样本与四点辅助','9折各624训练/78留出；四点辅助另报','experiment5_zero_shot_metrics.csv'),
        (6,'剂量—时间联合重建','二维RBF/GP及其他材料残差模板均未稳定提升','experiment6_metrics.csv'),
        (7,'响应形态与性质关联','54曲线形态、加权PCA及描述性相关已完成','experiment7_curve_shapes.csv'),
        (8,'稳定性和敏感性','材料删组、轴/编码/归一化敏感性及配对区间已完成','experiment8_tissue_sensitivity.csv')]
    status=pd.DataFrame(statuses,columns=['number','experiment','finding','evidence']);status['status']='已完成现有数据计算'
    status.to_csv(out/'supplement_experiment_status_8.csv',index=False,encoding='utf-8',lineterminator='\n')
    canonical=ROOT.parent/'paper/revision/improvement-recommendations-status.md'
    backup=out/'experiment_status_before_supplement.md'
    if not backup.exists():shutil.copyfile(canonical,backup)
    marker='## 2026-11-01：八项补充计算实验'
    text=canonical.read_text(encoding='utf-8').split(marker)[0].rstrip()
    text=text.replace('四分支融合架构移出当前目标，不追加新模型训练','四分支融合架构移出；新增模型训练在材料留出补充任务中单列')
    text=text.replace('本次没有按新702条训练新模型，也没有以','原冻结评价未用自测响应训练；本次补充另列材料留出训练。未以')
    extra=['',marker,'','本次补充研究使用同一份数据，全部计算已完成。新增的自测RF及残差RF每折只拟合其他8材料，原冻结评价与源模型保持独立。','',
        '| 补充序号 | 任务 | 状态 | 结果 | 证据 |','|---:|---|---|---|---|']
    for n,name,finding,evidence in statuses:
        extra.append(f'| {n} | {name} | 已完成现有数据计算 | {finding} | [结果](../../research/results/{out.name}/{evidence}) |')
    extra+=['',f'[补充实验完整报告](../../research/results/{out.name}/README.md) · [数值核验](../../research/results/{out.name}/verification.json)','']
    canonical.write_text(text+'\n'+'\n'.join(extra),encoding='utf-8',newline='\n')
    write_json(out/'manifest.json',{p.relative_to(out).as_posix():digest(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'})
    print('Eight-experiment report, status table and manifest saved.')


if __name__=='__main__':main()
