"""核验固定4+8方案和AUC，输出证据约束的中文报告与范围调整表。"""
import argparse
import bisect
import json
import math
from pathlib import Path
from statistics import mean

import numpy as np
import pandas as pd
from scipy.integrate import quad

from analyze_reframed_702 import ANCHORS, TEST_DOSES, CURVE, KEYS, METHODS, COMPARISONS, fit_offset
from run_huvec_external import digest, write_json

ROOT = Path(__file__).resolve().parents[1]


def check_outputs(out):
    plan = json.loads((out/'analysis_plan.json').read_text(encoding='utf-8'))
    source = Path(plan['source_directory'])
    assert list(ANCHORS) == plan['calibration_points'] and list(TEST_DOSES) == plan['test_points']
    assert digest(source/'paired_predictions.csv') == plan['source_prediction_sha256']
    assert digest(source/'manifest.json') == plan['source_manifest_sha256']
    assert digest(Path(__file__).with_name('analyze_reframed_702.py')) == plan['script_sha256']
    read = lambda name: pd.read_csv(out/name, float_precision='round_trip')
    data = pd.read_csv(source/'paired_predictions.csv', float_precision='round_trip')
    test = read('heldout_predictions_432.csv')
    anchors = read('calibration_anchors_216.csv')
    controls = read('controls_54.csv')
    auc = read('auc_curve_values_54.csv')
    assert (len(test),len(anchors),len(controls),len(auc)) == (432,216,54,54)
    assert not test.duplicated(KEYS).any()
    assert set(test.concentration_reported) == set(TEST_DOSES)
    assert set(anchors.concentration_reported) == set(ANCHORS)
    assert set(controls.concentration_reported) == {0}
    assert set(map(tuple,test[KEYS].values)).isdisjoint(set(map(tuple,anchors[KEYS].values)))
    expected = data.loc[data.concentration_reported.isin(TEST_DOSES)].reset_index(drop=True)
    pd.testing.assert_frame_equal(test[expected.columns],expected)
    checks = 0
    offset_table = read('calibration_offsets_54.csv').set_index(CURVE)
    auc_lookup = auc.set_index(CURVE)
    for key,g in data.groupby(CURVE):
        g = g.sort_values('concentration_reported')
        a = g.loc[g.concentration_reported.isin(ANCHORS)]
        t = test.loc[test.nanoparticle.eq(key[0])&test.cell_type.eq(key[1])&test.time_h.eq(key[2])]
        shift = mean([float(y-p) for y,p in zip(a.viability_percent,a.predicted_viability_percent)])
        assert math.isclose(shift,offset_table.loc[key,'offset_pp'],abs_tol=1e-12)
        np.testing.assert_allclose(t.offset_prediction, t.predicted_viability_percent+shift,atol=1e-12,rtol=0)
        log_a = [math.log(float(c)) for c in a.concentration_reported]
        for r in t.itertuples():
            c = math.log(r.concentration_reported)
            upper = bisect.bisect_right(log_a,c)
            lower = upper-1
            weight = (c-log_a[lower])/(log_a[upper]-log_a[lower])
            interpolation = (1-weight)*a.viability_percent.iloc[lower]+weight*a.viability_percent.iloc[upper]
            assert math.isclose(interpolation,r.anchor_interpolation_prediction,abs_tol=1e-10)
            checks += 1
        # 把所有非锚点响应改成极端数值，拟合偏移仍须逐位不变。
        changed = g.copy()
        changed.loc[~changed.concentration_reported.isin(ANCHORS),'viability_percent'] = -1000000.
        assert fit_offset(changed.loc[changed.concentration_reported.isin(ANCHORS)]) == fit_offset(a)
        for axis,positive in [('log10_positive',True),('linear_including_control',False)]:
            q = g.loc[g.concentration_reported.gt(0)] if positive else g
            x = np.log10(q.concentration_reported.to_numpy(float)) if positive else q.concentration_reported.to_numpy(float)
            for label,column in [('observed','viability_percent'),('predicted','predicted_viability_percent')]:
                y = q[column].to_numpy(float)/100
                integral = sum(quad(lambda value: np.interp(value,x,y),left,right,epsabs=1e-12)[0]
                               for left,right in zip(x[:-1],x[1:]))
                assert math.isclose(integral/(x[-1]-x[0]),auc_lookup.loc[key,f'{label}_nauc_{axis}'],rel_tol=1e-12)
                checks += 1
        checks += 2
    metric_table = read('fewshot_metrics.csv')
    for r in metric_table.itertuples():
        g = test if r.cell_type=='ALL' else test.loc[test.cell_type.eq(r.cell_type)]
        if str(r.time_h) != 'ALL': g = g.loc[g.time_h.eq(float(r.time_h))]
        errors = g[METHODS[r.method]].to_numpy()-g.viability_percent.to_numpy()
        observed = g.viability_percent.to_numpy()
        mae = math.fsum(map(abs,errors))/len(errors)
        mse = math.fsum(e*e for e in errors)/len(errors)
        ss = math.fsum((float(y)-mean(observed))**2 for y in observed)
        assert math.isclose(mae,r.mae,rel_tol=1e-12)
        assert math.isclose(math.sqrt(mse),r.rmse,rel_tol=1e-12)
        assert math.isclose(1-mse*len(errors)/ss,r.r2,rel_tol=1e-12)
        checks += 1
    for r in read('heldout_curve_metrics_162.csv').itertuples():
        g = test.loc[test.nanoparticle.eq(r.nanoparticle)&test.cell_type.eq(r.cell_type)&test.time_h.eq(r.time_h)].sort_values('concentration_reported')
        x = np.log10(g.concentration_reported.to_numpy(float))
        errors = (g[METHODS[r.method]]-g.viability_percent).to_numpy()
        integral = 0.
        for left,right,a,b in zip(x[:-1],x[1:],errors[:-1],errors[1:]):
            points = [left+(right-left)*abs(a)/(abs(a)+abs(b))] if a*b<0 else None
            integral += quad(lambda value:abs(a+(b-a)*(value-left)/(right-left)),left,right,points=points,epsabs=1e-8)[0]
        assert math.isclose(integral/(x[-1]-x[0]),r.test_niae_log10,rel_tol=1e-10,abs_tol=1e-10)
        checks += 1
    for r in read('auc_prediction_metrics.csv').itertuples():
        g = auc if r.cell_type=='ALL' else auc.loc[auc.cell_type.eq(r.cell_type)]
        if str(r.time_h) != 'ALL': g = g.loc[g.time_h.eq(float(r.time_h))]
        y = g['observed_nauc_'+r.axis].to_numpy()*100
        p = g['predicted_nauc_'+r.axis].to_numpy()*100
        errors = p-y
        assert math.isclose(mean(abs(errors)),r.mae,rel_tol=1e-12)
        assert math.isclose(math.sqrt(mean(errors**2)),r.rmse,rel_tol=1e-12)
        assert math.isclose(1-sum(errors**2)/sum((y-mean(y))**2),r.r2,abs_tol=1e-12)
        checks += 1
    # 与点级数组计算不同，以每种材料的配对MAE差重建全部重采样区间。
    rng = np.random.default_rng(plan['bootstrap']['seed'])
    comparisons = read('paired_mae_comparisons.csv')
    views = [('ALL','ALL',test)]
    views += [(c,'ALL',g) for c,g in test.groupby('cell_type')]
    views += [(c,t,g) for (c,t),g in test.groupby(['cell_type','time_h'])]
    for cell,time,g in views:
        indices = rng.integers(0,9,(plan['bootstrap']['resamples'],9))
        blocks = [g.loc[g.nanoparticle.eq(m)] for m in sorted(g.nanoparticle.unique())]
        for target,reference in COMPARISONS:
            changes = np.array([np.mean(abs(b[METHODS[target]]-b.viability_percent))-np.mean(abs(b[METHODS[reference]]-b.viability_percent)) for b in blocks])
            limits = np.quantile(changes[indices].mean(axis=1),[.025,.975])
            row = comparisons.loc[comparisons.cell_type.eq(cell)&comparisons.time_h.astype(str).eq(str(time))&comparisons.target.eq(target)&comparisons.reference.eq(reference)].iloc[0]
            np.testing.assert_allclose(limits,[row.material_bootstrap_ci_low,row.material_bootstrap_ci_high],atol=1e-12,rtol=0)
            checks += 1
    for path in out.glob('*.csv'):
        raw = path.read_bytes()
        assert not raw.startswith(b'\xef\xbb\xbf') and b'\r\n' not in raw
    verification = dict(status='PASS',numerical_checks=checks,source_prediction_hash_verified=True,
        disjoint_anchor_test_control_keys=True,all_54_curves_have_4_anchors_and_8_test_doses=True,
        heldout_response_mutation_leaves_calibration_unchanged=True,auc_checked_by_independent_quadrature=True,
        auc_metrics_independently_verified=True,heldout_iae_independently_verified=True,
        anchor_interpolation_checked_by_natural_logs_and_brackets=True,material_bootstrap_intervals_independently_rebuilt=True,
        no_response_clipping=True,source_model_not_retrained=True)
    write_json(out/'verification.json',verification)
    return plan, source


def reports(out, plan, source):
    read = lambda name: pd.read_csv(out/name)
    metrics = read('fewshot_metrics.csv')
    changes = read('paired_mae_comparisons.csv')
    summary = json.loads((out/'summary.json').read_text(encoding='utf-8'))
    selection = metrics.loc[metrics.time_h.eq('ALL')]
    lookup = selection.set_index(['cell_type','method'])
    all_delta = changes.loc[changes.cell_type.eq('ALL')&changes.time_h.eq('ALL')&changes.target.eq('rf_offset_4pt')&changes.reference.eq('frozen_rf')].iloc[0]
    method_names = {'frozen_rf':'冻结RF','rf_offset_4pt':'冻结RF＋四点偏移','anchor_log_interpolation':'仅四锚点对数插值'}
    primary_auc = read('auc_prediction_metrics.csv').query("axis == 'log10_positive' and time_h == 'ALL'")
    report = '''# 现有702条数据的研究范围调整与分析结论

## 研究问题与范围调整记录

范围调整记录：2026-11-01（数据已查看后）。本研究以现有9种SeNP、HUVEC/H9C2两种实验体系、24/48/72 h和13个浓度的702条报告值为全部新增实验资料，形成54条曲线。浓度为元素Se计μM。没有补造浓度点、重复孔、独立批次或缺失表征。

研究问题改为：历史文献模型在这批真实响应上能够预测到什么程度；整条剂量响应及材料比较是否被准确再现；每条曲线已知四个实测点后，能否更好地估计其余八个正浓度点。

原24浓度、完整化学表征、四级信息增益、实验前盲法、独立新批次及4+20校准等目标经方案调整移出本研究范围。它们不再作为当前分析的未完成任务，也不被改称为已经完成的实验。原始重复次数、测定方法与汇总方式未提供，是现有证据边界，不是本轮待办。

## 固定术语与分析定义

| 术语 | 本报告的固定含义 |
|---|---|
| 冻结模型外部评价 | 原模型与预处理器不重训；已知实验结果上的回顾性评价 |
| nAUC | 固定浓度区间上的梯形面积除以轴宽和100，即平均存活率比例；越低表示该范围内总体抑制越强 |
| IAE | 预测与实测分段线性曲线之间的积分绝对误差；同时保留原线性轴和正浓度log轴结果 |
| 四点校准 | 每个材料—细胞—时间组合仅估计一个存活率偏移量 |
| 八点检验 | 同一曲线上未用于拟合的八个正浓度点，不包括0浓度对照 |
| 少样本回顾性模拟 | 同曲线浓度内插的模拟，不代表新材料、新细胞、未来时间或实验前预测 |

## 1. 冻结模型的外部表现

沿用基础Random Forest，未用这批702条数据更新树、编码器或插补器。全条件MAE=11.686、RMSE=16.303个百分点、R²=0.503；HUVEC MAE=14.857、R²=0.478，H9C2 MAE=8.516、R²=0.530。HUVEC在24/48/72 h的MAE分别为9.885/14.124/20.561个百分点，长时间预测仍存在更大偏差。

这些数值来自[已核验冻结评价](../external_702_20261101_confirmed/README.md)，保留其[误差](../external_702_20261101_confirmed/prediction_metrics.csv)、[54条曲线IAE](../external_702_20261101_confirmed/curve_metrics_54.csv)、[时间变化](../external_702_20261101_confirmed/observed_time_changes.csv)和[模型SHAP](../external_702_20261101_confirmed/shap_summary.csv)。

H9C2是历史编码器的未知类别，源表没有组织字段，主分析由冻结插补器将组织填为Liver。Liver是模型默认值，绝非实验细胞的真实组织描述。旧评价提供未知组织编码的敏感性分析，H9C2 MAE由8.516变为8.892，说明该数值属于特定缺失字段策略下的条件性表现。两种细胞的接种数量分别为230000和300000/孔，均已确认；响应差异描述为两种实验体系差异，不单独归因于细胞类型。

## 2. 覆盖全部54条曲线的nAUC

主要nAUC采用12个正浓度点0.25–512 μM上的log10浓度轴：

`nAUC_log = integral[viability_percent d(log10 concentration)] / (100 × log10(512/0.25))`

次要nAUC采用0–512 μM线性浓度轴，并包括0浓度。两种轴定义在计算前固定，不按结果选择；原始存活率超过100%的值保留，所以归一化面积可以超过1，不能自动解释为增殖促进。nAUC较低只代表本范围较低的平均报告存活率。

| 范围 | 曲线数 | nAUC误差MAE（×100，百分点） | RMSE（×100） | R² |
|---|---:|---:|---:|---:|
'''
    for r in primary_auc.itertuples():
        report += f'| {r.cell_type} | {r.n} | {r.mae:.3f} | {r.rmse:.3f} | {r.r2:.3f} |\n'
    report += '''
逐条件R²约0.50并不意味着整曲线综合响应能被同样准确地预测。主要nAUC在54曲线上的R²只有0.084，HUVEC为−0.042，表明曲线综合反应的区分仍有限。线性轴结果也完整保留，避免隐藏轴定义对结论的影响。

主要nAUC实测均值：HUVEC在24/48/72 h分别为0.825/0.746/0.726，H9C2为0.843/0.826/0.830。H9C2在整个正浓度区间的时间变化并非严格单调，不能仅凭最高浓度的下降概括全部剂量范围。nAUC材料排序也随体系、时间和积分轴变化，不给出跨条件的统一毒性序列。

依据：[54条面积值](auc_curve_values_54.csv)、[面积预测误差](auc_prediction_metrics.csv)、[面积描述汇总](auc_descriptive_summary.csv)、[面积排序一致性](auc_ranking_agreement.csv)。

## 3. 四点校准、八点检验

在本轮分析计算前，将锚点固定为0.25、4、64、512 μM；检验点为0.5、1、2、8、16、32、128、256 μM。0浓度对照单独保留。54条曲线共216个校准条件、432个检验条件和54个对照条件。

偏移量为四锚点的平均“实测−冻结预测”差值。校准预测为冻结预测加偏移，没有缩放、截断或单调化。四锚点直接插值参照完全不使用历史模型，只在log浓度轴上连接相邻锚点；它与偏移校准使用相同四个响应值。三个方法均只在同一432个检验点上计分。

| 数据 | 方法 | 检验条件数 | MAE（百分点） | RMSE | R² |
|---|---|---:|---:|---:|---:|
'''
    for r in selection.itertuples():
        report += f'| {r.cell_type} | {method_names[r.method]} | {r.n} | {r.mae:.3f} | {r.rmse:.3f} | {r.r2:.3f} |\n'
    report += f'''
总体偏移校准的MAE由11.714降至10.303，点估计降低{all_delta.relative_mae_reduction*100:.2f}%；配对差值为{all_delta.mae_delta:.3f}个百分点，材料组bootstrap 95%区间为[{all_delta.material_bootstrap_ci_low:.3f}, {all_delta.material_bootstrap_ci_high:.3f}]，跨0。54条曲线中{summary['curves_improved_vs_frozen']}条的MAE下降，这些曲线不等于独立实验重复。

HUVEC校准MAE由15.174降至12.703，配对差值−2.471，区间[−4.193, −1.017]；H9C2由8.254降至7.903，差值−0.351，区间[−1.462, 1.382]。改善具有实验体系差异，不能概括为普遍稳定增益。

仅四锚点对数插值的总体MAE为5.711、R²为0.854，优于冻结RF和四点偏移RF。偏移RF相对直接插值的MAE差为+4.592个百分点，区间[2.898, 6.849]。因此可以说固定四点提供了同曲线补全信息，不能据此说历史模型贡献了额外优势，也不能将0.854写成零样本外部预测性能。

所有区间均为2000次按9材料整组重采样的百分位区间（seed=20261102），每次保留对应材料的两体系、三时间及全部检验点。区间描述这9材料组成下的抽样变化，不代替未知生物重复、批间差异或模型训练不确定性。总体与分体系比较为探索性描述，未设置多重检验显著性结论。

本方案使用最高与最低正浓度作为锚点，八个检验点全部位于已测范围内。因此结果只适用于回顾性浓度内插，不说明能够预测未测高浓度、未见材料或未来时间。选点与方法发生在已有全表可见之后，不能称为预注册或盲法验证。未搜索其他锚点或校准方法。

依据：[拟合偏移](calibration_offsets_54.csv)、[216锚点](calibration_anchors_216.csv)、[432检验条件](heldout_predictions_432.csv)、[各方法误差](fewshot_metrics.csv)、[配对差值与区间](paired_mae_comparisons.csv)、[各曲线检验误差](heldout_curve_metrics_162.csv)。

## 4. IC50、排序与性质解释的保留位置

IC50不再是本研究必须输出有限数值的主终点。实验侧24条可插值、30条>512 μM；冻结模型54条全部>512，普通有限配对为0。保留[阈值与删失结果](../external_702_20261101_confirmed/ic50_pairs.csv)，不将>512记为512，不外推精确IC50，不用四个拟合锚点评价后的“全曲线IC50”冒充独立检验。

72 h、512 μM的冻结预测—实测Spearman为HUVEC 0.217、H9C2 0.167。固定高浓度排名和nAUC排名回答不同问题，不能互相替代。粒径、Zeta、修饰名称在材料间共同变化；已有[探索性关联](../external_702_20261101_confirmed/property_associations_512.csv)和SHAP只用于描述响应与模型行为，不作因果机制结论。

历史434条文献分组建模、化学增强、迁移与交互的阴性对照继续保留。没有将新增702条并回训练集，也没有开展新模型训练，因此不存在本轮按材料留出的新训练成绩可报告。

## 5. 可用于V3的结论草稿

'''
    conclusion = '''本研究将历史文献建模与双细胞实验体系的剂量—时间响应相结合，在9种纳米硒材料、两种实验体系、三个时间和13个浓度构成的702个条件上评价冻结随机森林的适用范围。模型不使用实测IC50作为输入，总体存活率预测MAE为11.69个百分点、R²为0.503，但对较长暴露时间、材料间差异和综合曲线响应的再现仍有限，54条曲线的主要归一化AUC预测R²为0.084。该结果说明，逐条件的总体预测表现不能替代材料比较和整曲线评价。

在固定四个正浓度实测点后，对其余八个正浓度点的回顾性检验中，单一偏移校准将RF的总体MAE由11.71降至10.30个百分点，但总体材料组重采样区间跨0，且改善在两种体系间不同。仅使用相同四锚点的对数浓度插值达到MAE 5.71个百分点，优于偏移校准RF，提示少量同曲线实测信息有助于浓度内插，但当前历史模型未显示超越简单插值的附加价值。

本研究据此明确了基础模型在现有实验范围内的预测边界，以及少量实测点用于曲线补全的条件性价值。相关结论限于已测材料、体系和浓度区间，不构成新材料安全性判定、可靠的跨体系泛化或实验前盲法验证。归一化AUC作为全曲线终点，IC50作为阈值与删失信息补充；缺失化学表征和实验重复资料限制机制与重复性解释，但不再作为调整后研究方案的待完成目标。'''
    report += conclusion+'\n'
    report += '''
## 6. 证据、复现与核验

主张—证据对应：冻结模型有部分预测能力见原702条件误差；整曲线区分有限见nAUC误差；单一偏移校准总体增益不稳定见配对材料bootstrap；历史模型未优于简单锚点插值见同一432检验条件的公平比较。所有结果均保留，不依据结果更换主轴、锚点或模型。

方法上将检验响应排除在偏移拟合之外，符合[scikit-learn关于数据泄漏的原则](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage)。这里使用材料整组bootstrap，不是LeaveOneGroupOut重训练；[分组验证文档](https://scikit-learn.org/stable/modules/cross_validation.html#leave-one-group-out)仅作为未来若另行开发模型时的分组原则。本研究没有新增训练。用户提供的Assay Guidance Manual链接本次因访问验证未能读取，不将其作为已核实的nAUC定义依据；以上面积定义为本研究明确固定的数学指标。

研究设计与参数见[analysis_plan.json](analysis_plan.json)，数值复核见[verification.json](verification.json)。原对照表归档为[范围调整前版本](experiment_status_before_scope_change.md)，当前对照表见[主目录最新版](../../../paper/revision/improvement-recommendations-status.md)。

```powershell
.venv/Scripts/python.exe research/scripts/analyze_reframed_702.py --output research/results/reframed_702_new_run
.venv/Scripts/python.exe research/scripts/report_reframed_702.py research/results/reframed_702_new_run
```

第二条命令生成报告并同步当前范围对照表；V3正文的完整重排不属于本轮数据分析，结论草稿单独交付。源数据、冻结预测和历史模型均保留。
'''
    (out/'README.md').write_text(report,encoding='utf-8',newline='\n')
    (out/'conclusion_for_v3.md').write_text('# 基于调整后研究范围的V3结论草稿\n\n'+conclusion+'\n',encoding='utf-8',newline='\n')
    write_scope_table(out)


def write_scope_table(out):
    old = pd.read_csv(ROOT/'results/external_702_20261101_confirmed/experiment_status_36.csv')
    suggestions = old.set_index('number').recommendation.to_dict()
    updates = '''1|现有分析已完成|历史建模→双体系剂量时间响应→冻结外部评价→少量测点模拟|完整证据链已形成；不要求原方案所有湿实验完成|README.md
2|现有分析已完成|通用、历史SeNP与702外部实验数据分别管理|702不并回历史434训练集|README.md
3|现有分析已完成|保留历史General基准|3889条、144文献组的固定预算计算已有|historical
4|现有分析已完成|保留General→SeNP迁移对照|未获稳定增益作为结果，不以证明有效为完成条件|historical
5|现有分析已完成|使用已有粒径、Zeta、修饰名称、暴露和体系信息|真实接种数量已纳入冻结输入；缺失默认值已审计|README.md
6|经方案调整移出范围|不要求补齐Modifier Category与MW|不伪造类别或分子量；结论限于已有名称字段|README.md
7|现有分析已完成|保留暴露特征与历史交互消融|阴性交互结果照实报告，外部按时间分层评价|README.md
8|现有分析已完成|描述两种实验体系，不宣称完整生物背景编码|H9C2未知类别及组织默认值作为解释边界|README.md
9|现有分析已完成|以既有冻结RF为主模型|四分支融合架构移出当前目标，不追加新模型训练|README.md
10|现有分析已完成|保留历史基础与化学增强对照|未获稳定改善；没有外部化学增强结果可推断|historical
11|现有分析已完成|报告现有化学描述符的历史增量评价|历史阴性结果保留；新增化学表征移出范围|historical
12|经方案调整移出范围|取消完整L1—L4信息等级设计|缺失字段不再作为当前研究待办|README.md
13|现有分析已完成|保留文献分组历史评价|434记录24文献组，不与外部702混算|historical
14|经方案调整移出范围|不开展缺可靠配方ID的分组CV|不将材料名称冒充配方或批次ID|README.md
15|现有分析已完成|保留历史Nested Grouped CV|5外层×3内层；外部响应不用于调参|historical
16|现有分析已完成|保留选择折与报告折分离|新校准锚点不搜索，八检验点不拟合偏移|analysis_plan.json
17|经方案调整移出范围|完整Se含量、稳定性、Se 3d/XPS、晶相表征|不再列为本研究未完成实验；放弃相关机制主张|README.md
18|现有分析已完成|以9×2×3×13=702作为实际研究设计|54曲线完整覆盖；24点设计正式移出范围|README.md
19|现有分析已完成|评价实际0–512 μM浓度范围|不强求曲线穿越50%；以nAUC覆盖全部曲线|auc_curve_values_54.csv
20|现有分析已完成|18个材料—体系剂量时间网格的描述性评价|比较时间变化；H9C2综合AUC非严格单调；不做重复显著性|auc_descriptive_summary.csv
21|经方案调整移出范围|取消对已有实验追补事前盲法的要求|保留实际模型冻结、源数据和分析时间记录|analysis_plan.json
22|现有分析已完成|冻结模型的回顾性外部评价|702条件MAE11.686/R²0.503，不称前瞻盲测|README.md
23|现有分析已完成|MAE、RMSE、R²与材料组区间|校准在同一432检验条件上公平比较|fewshot_metrics.csv
24|现有分析已完成|54曲线IAE与归一化AUC|主要log正浓度nAUC R²0.084；线性轴结果完整保留|auc_prediction_metrics.csv
25|现有分析已完成|不使用实测IC50输入，报告预测阈值状态|冻结模型54曲线均>512，不外推有限数值|README.md
26|现有分析已完成|IC50阈值与删失作为辅助终点|实验24可插值/30右删失；有限配对0，log误差/R²不可计算|README.md
27|现有分析已完成|固定高浓度与整曲线nAUC分别比较材料|不用一种条件下排名代表全局毒性序列|auc_ranking_agreement.csv
28|现有分析已完成|分体系和时间报告Spearman/Kendall|描述性n=9材料，不冒充独立实验显著性|auc_ranking_agreement.csv
29|现有分析已完成|性质—响应探索性关联|粒径/Zeta/名称同时变化；取消因果机制目标|README.md
30|现有分析已完成|仅解释模型已有特征的SHAP行为|702条件加和已核验；不提供不存在的MW/类别SHAP|README.md
31|现有分析已完成|保留SeNP-only与迁移的阴性对照|不因阴性结果要求额外实验|historical
32|现有分析已完成|保留显式dose-time交互消融|没有稳定改善为有效结果|historical
33|经方案调整移出范围|不新增同口径随机/分组受控对照|历史两种口径保留，不能将差异全归因于拆分|README.md
34|现有分析已完成|历史验证、冻结外部评价、校准模拟三者分列|702全条件与432检验条件成绩不能直接混比|README.md
35|现有分析已完成|四点校准、八个正浓度点检验|偏移MAE11.714→10.303；简单锚点插值5.711，RF未获额外优势|paired_mae_comparisons.csv
36|现有分析已完成|按调整后证据链交付报告与V3结论草稿|本轮完成分析写作；正式V3全文重排不属于本轮范围|conclusion_for_v3.md'''
    rows = []
    table = ['# 论文实验与分析对照表（按现有数据调整后的研究范围）','',
        '范围调整记录：2026-11-01（数据已查看后）。用户确认新增实验数据仅此一份，现有9材料×2体系×3时间×13浓度=702条件、54曲线构成本研究全部外部实验数据。调整后研究主线为历史文献建模→双体系剂量—时间响应→冻结模型外部评价→少量测点回顾性模拟。','',
        '状态定义：“现有分析已完成”指调整后范围内的分析与结果已交付，包括阴性结果与不可计算的阈值指标；“现有数据可补算”只标识尚未完成的可执行计算；“经方案调整移出范围”不代表原任务已经完成。重复次数、方法、汇总方式和缺失字段作为报告边界，不再挂为本轮待完成实验。','',
        f'[调整后完整分析](../../research/results/{out.name}/README.md) · [范围调整前对照表](../../research/results/{out.name}/experiment_status_before_scope_change.md) · [计算前固定方案](../../research/results/{out.name}/analysis_plan.json)','',
        '| 原序号 | 原方案条目 | 调整后目标/处理 | 当前状态 | 结果或边界 | 证据 |',
        '|---:|---|---|---|---|---|']
    for line in updates.splitlines():
        number,status,target,result,evidence = line.split('|')
        number = int(number)
        if evidence == 'historical':
            folder = 'general_benchmark' if number==3 else 'transfer_comparison' if number in (4,31) else 'dose_time_interaction' if number==32 else 'improved_434'
            link = f'[历史结果](../../research/results/{folder}/summary.json)'
        else: link = f'[结果](../../research/results/{out.name}/{evidence})'
        table.append(f'| {number} | {suggestions[number]} | {target} | {status} | {result} | {link} |')
        rows.append(dict(number=number,original_recommendation=suggestions[number],revised_target=target,status=status,result_or_boundary=result,evidence=evidence))
    table += ['', '本次没有按新702条训练新模型，也没有以四点响应为输入后的0.854 R²替代冻结模型外部0.503 R²。54曲线、432检验条件来自9种材料，重复实验数未知；材料bootstrap不能代替生物学重复。','']
    destination = ROOT.parent/'paper/revision/improvement-recommendations-status.md'
    destination.write_text('\n'.join(table),encoding='utf-8',newline='\n')
    pd.DataFrame(rows).to_csv(out/'experiment_status_reframed_36.csv',index=False,encoding='utf-8',lineterminator='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args = parser.parse_args()
    out = args.directory.resolve()
    plan, source = check_outputs(out)
    reports(out,plan,source)
    write_json(out/'manifest.json',{p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='manifest.json'})
    print((out/'verification.json').read_text(encoding='utf-8'))


if __name__ == '__main__':
    main()
