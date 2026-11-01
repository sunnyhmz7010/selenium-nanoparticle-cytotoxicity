"""独立复核702条分析产物，并更新36项实验对照表。"""
from pathlib import Path
import argparse
import json
import math
import numpy as np
import pandas as pd
import joblib
from scipy.integrate import quad
from scipy.stats import spearmanr, kendalltau
from run_huvec_external import digest, write_json

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    args=parser.parse_args()
    out=args.directory.resolve()
    read=lambda name:pd.read_csv(out/name,float_precision='round_trip')
    pairs=read('paired_predictions.csv')
    curves=read('curve_metrics_54.csv')
    metrics=read('prediction_metrics.csv')
    ranks=read('ranking_agreement.csv')
    audit=json.loads((out/'audit.json').read_text(encoding='utf-8'))
    checks=0
    for label in ('experimental','model'):
        ic=read(label+'_ic50.csv')
        assert len(ic)==54
        for r in ic.to_dict('records'):
            g=pairs.loc[pairs.nanoparticle.eq(r['nanoparticle'])&pairs.cell_type.eq(r['cell_type'])&pairs.time_h.eq(r['time_h'])].sort_values('concentration_reported')
            response='viability_percent' if label=='experimental' else 'predicted_viability_percent'
            if r['status']=='interpolated':
                c1,c2=r['lower_concentration'],r['upper_concentration']
                y1,y2=r['lower_viability_percent'],r['upper_viability_percent']
                assert y1>50>=y2 and 0<c1<c2
                assert np.isclose(g.loc[g.concentration_reported.eq(c1),response].item(),y1)
                assert np.isclose(g.loc[g.concentration_reported.eq(c2),response].item(),y2)
                value=math.exp(math.log(c1)+(y1-50)/(y1-y2)*math.log(c2/c1))
                assert math.isclose(value,r['ic50_reported_scale'],rel_tol=1e-12)
            else:
                assert r['status']=='not_reached'
                assert g.loc[g.concentration_reported.gt(0),response].gt(50).all()
            checks+=1
    for r in curves.to_dict('records'):
        g=pairs.loc[pairs.nanoparticle.eq(r['nanoparticle'])&pairs.cell_type.eq(r['cell_type'])&pairs.time_h.eq(r['time_h'])].sort_values('concentration_reported')
        x=g.concentration_reported.to_numpy(float)
        error=g.predicted_viability_percent.to_numpy()-g.viability_percent.to_numpy()
        for axis,e,field in [(x,error,'iae_linear_umol_l'),(np.log10(x[1:]),error[1:],'iae_log10_positive')]:
            result=0.
            for left,right,a,b in zip(axis[:-1],axis[1:],e[:-1],e[1:]):
                # 数值求积与生成器的解析过零公式相互独立。
                result+=quad(lambda t:abs(a+(b-a)*(t-left)/(right-left)),left,right,
                             epsabs=1e-7,points=[left+(right-left)*abs(a)/(abs(a)+abs(b))] if a*b<0 else None)[0]
            assert math.isclose(result,r[field],rel_tol=1e-10,abs_tol=1e-7)
            checks+=1
    for r in ranks.to_dict('records'):
        g=pairs.loc[pairs.cell_type.eq(r['cell_type'])&pairs.time_h.eq(r['time_h'])&pairs.concentration_reported.eq(512)]
        observed=g.viability_percent.rank().to_numpy()
        predicted=g.predicted_viability_percent.rank().to_numpy()
        assert math.isclose(np.corrcoef(observed,predicted)[0,1],r['spearman_rho'],abs_tol=1e-12)
        assert math.isclose(kendalltau(observed,predicted).statistic,r['kendall_tau_b'],abs_tol=1e-12)
        checks+=1
    model=joblib.load(audit['model'])
    inputs=read('model_inputs.csv')
    prediction=model.predict(inputs[audit['features']])
    assert np.max(abs(prediction-pairs.predicted_viability_percent))<1e-10
    assert digest(out/'source_experiments.xlsx')==audit['source_sha256']
    assert digest(Path(audit['model']))==audit['model_sha256']
    for r in metrics.loc[metrics.time_h.eq('ALL')].to_dict('records'):
        g=pairs if r['cell_type']=='ALL' else pairs.loc[pairs.cell_type.eq(r['cell_type'])]
        e=g.predicted_viability_percent-g.viability_percent
        assert math.isclose(abs(e).mean(),r['mae'],rel_tol=1e-12)
        assert math.isclose(np.sqrt(np.mean(e**2)),r['rmse'],rel_tol=1e-12)
        assert math.isclose(1-sum(e**2)/sum((g.viability_percent-g.viability_percent.mean())**2),r['r2'],rel_tol=1e-12)
        checks+=1
    verification=json.loads((out/'verification.json').read_text(encoding='utf-8'))
    verification.update(independent_check_count=checks,ic50_interpolation_checked=True,
                        iae_independent_quadrature_checked=True,ranking_and_metrics_checked=True)
    write_json(out/'verification.json',verification)

    rows=['| 细胞 | 条件数 | MAE（百分点） | MAE 95%区间 | RMSE | R² |', '|---|---:|---:|---|---:|---:|']
    for r in metrics.loc[metrics.time_h.eq('ALL')].to_dict('records'):
        rows.append(f"| {r['cell_type']} | {r['n']} | {r['mae']:.3f} | [{r['mae_ci_low']:.3f}, {r['mae_ci_high']:.3f}] | {r['rmse']:.3f} | {r['r2']:.3f} |")
    text='''# 最新702条实验数据分析（2026-11-01）

来源：`实验数据(3).xlsx`，原文件逐字节归档为 [source_experiments.xlsx](source_experiments.xlsx)。
本次9材料×2细胞×3时间×13浓度=702条件、54曲线，无条件重复或空字段。原351条HUVEC的粒径、Zeta、存活率未改变。历史434条训练数据未改动。

## 模型与输入

沿用历史434条/24文献组的基础Random Forest及冻结预处理器；没有重训、调参、校准或按新响应选择模型。只评估这个预先选定的主模型，不使用含IC50的辅助模型冒充低信息预测。
浓度按源表明确的元素Se μM，乘0.078971转成μg/mL，512 μM对应40.433152 μg/mL；log浓度也由换算值生成。
接种密度按源表与用户2026-11-01确认：HUVEC 230000、H9C2 300000 cells/well，缺失标志均为0。这与旧版填入10000的预测不同，新版取代旧版的该批预测。

HUVEC组织沿用历史标签Vascular endothelium。H9C2在历史模型中是未知细胞类别，编码为全零；源表未提供组织，主分析保持缺失，由冻结预处理器填入Liver。这个Liver是模型默认值，不是H9C2真实组织，H9C2指标仅为该缺失字段策略下的条件性结果。另提供“组织作为未知类别全零编码”的敏感性分析，不按表现择优。
缺失年份、合成路线仍由冻结插补器处理。Glucose、LET、PAH、PEI、Sucrose、TW80修饰名称为未知类别，CS沿用Chitosan (CS)，PEG/PVP原样匹配。具体编码、默认值、版本和哈希见 [audit.json](audit.json)。

## 外部预测误差

'''+ '\n'.join(rows)+'''

95%区间为固定模型下2000次材料整组bootstrap百分位区间（seed=20261101）。每次保留抽中材料的全部细胞/时间/浓度，仅有9材料；它描述材料组成抽样的不确定性，不代表生物学重复、批间重复性或模型训练不确定性。所有702条件保留，未截断超过100%的实测存活率，未强迫0浓度预测为100%。分细胞、时间结果见 [prediction_metrics.csv](prediction_metrics.csv)。

## 曲线、IC50与排序

- [54条曲线误差与IAE](curve_metrics_54.csv)：同时报告线性浓度轴与正浓度log10轴的积分绝对误差及轴宽归一化值。采用实测和预测在对应轴上分段线性连接，对残差过零段拆分精确积分；0浓度保留在线性轴，log10轴仅0.25–512 μM。IAE单位分别为百分点·μM和百分点·log10(μM)。这不是原24浓度设计。
- [实验侧IC50](experimental_ic50.csv)：HUVEC 19条可插值、8条>512；H9C2 5条可插值、22条>512；合计24条可插值、30条>512。
- [模型侧IC50](model_ic50.csv)：54条全部>512 μM。普通有限数值配对为0，所以[IC50配对表](ic50_pairs.csv)保留删失状态，log误差和R²不可计算；不把>512替换成512。
- [排序明细](toxicity_rankings_512.csv)与[排序一致性](ranking_agreement.csv)：按512 μM、每种细胞各时间的9材料比较，存活率越低毒性排名越靠前。均采用平均秩处理并列，Kendall为tau-b。72 h时HUVEC Spearman=0.217、Kendall=0.167；H9C2为0.167、0.111，最高时间点的排序一致性较弱。
- [高浓度时间汇总](high_dose_time_summary.csv)：512 μM下HUVEC平均实测存活率24/48/72 h为59.805/39.071/26.383%；H9C2为64.673/59.618/52.316%。这些是9材料的描述性均值，不是独立重复均值。另见[逐材料时间变化](observed_time_changes.csv)及[对应细胞条件差值](observed_cell_comparison.csv)。两种细胞接种密度同时不同，不能将差值解释为纯细胞类型因果效应。
- [粒径/Zeta相关性](property_associations_512.csv)：按细胞和时间分别以9种材料为单位，仅报告描述性Spearman，不报告未获实验重复支持的显著性。
- [SHAP汇总](shap_summary.csv)、[条件级SHAP](shap_grouped_values.csv)、[全部编码特征SHAP](shap_encoded_values.csv)：精确TreeExplainer，tree_path_dependent/raw，以冻结树训练路径为背景。派生特征和one-hot贡献作有符号加和，完整保留702条。SHAP描述模型归因，不证明机理；缺失修饰物类别与分子量不能补造SHAP。

## 映射敏感性与旧版变化

'''
    sensitivity=read('tissue_mapping_sensitivity.csv')
    h=sensitivity.loc[sensitivity.cell_type.eq('H9C2')].iloc[0]
    change=read('huvec_prediction_version_comparison.csv').prediction_change_new_minus_old
    text+=f"H9C2组织改用未知类别全零编码时，MAE={h.mae:.3f}、R²={h.r2:.3f}，单条件预测最大变化{h.max_prediction_change:.3f}个百分点。见[tissue_mapping_sensitivity.csv](tissue_mapping_sensitivity.csv)。此情景不等于提供了真实心脏组织信息。\n\nHUVEC原实验值未变化，但加入真实接种数量后，相对旧版预测的平均变化为{change.mean():.3f}个百分点，最大绝对变化{abs(change).max():.3f}。见[版本配对](huvec_prediction_version_comparison.csv)。这属于输入信息修正，不能写成新增湿实验导致模型训练改善。\n"
    text+='''
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
.venv/Scripts/python.exe research/scripts/run_external_702.py --source "D:/xwechat_files/wxid_mcit9monl47p22_de92/msg/file/2026-10/实验数据(3).xlsx" --output research/results/external_702_new_run
.venv/Scripts/python.exe research/scripts/report_external_702.py research/results/external_702_new_run
```

报告脚本同步更新主目录实验对照表，保留旧恢复目录的历史表不变。模型重载预测一致、源表与冻结模型哈希不变、SHAP加和成立，IC50通过自然对数公式独立检查，IAE通过数值求积独立检查。见[verification.json](verification.json)。
'''
    (out/'README.md').write_text(text,encoding='utf-8',newline='\n')
    update_table(out)
    write_json(out/'manifest.json',{p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file() and p.name!='manifest.json'})
    print(f'PASS: {checks} independent numerical checks; report and 36-item table written')


def update_table(out):
    archive=ROOT.parent/'work/output-publish-restore/paper/revision/improvement-recommendations-status.md'
    suggestions={}
    for line in archive.read_text(encoding='utf-8').splitlines():
        columns=[c.strip() for c in line.split('|')]
        if len(columns)>3 and columns[1].isdigit(): suggestions[int(columns[1])]=columns[2]
    assert set(suggestions)==set(range(1,37))
    # 状态区分计算完成、阴性结果和仍需湿实验，不沿用旧表过时数值。
    updates='''1|部分完成|历史建模与702条件回顾性外部评价已完成|需新批次盲法验证；完整信息增益设计仍缺字段|README.md
2|部分完成|通用3889条、历史434条、新实验702条分开管理|24浓度和重复资料尚不齐|experimental_data.csv
3|已完成历史计算|通用144文献组3889条基准已归档|无需因新增外部表而重训历史基准|historical
4|已完成计算，未获稳定增益|迁移严格对照已归档，bootstrap区间跨0|不能写成稳定迁移收益|historical
5|部分完成|粒径/Zeta/修饰名称及真实接种数量进入冻结模型|统一Modifier Category和MW需回查|model_inputs.csv
6|待补资料|未伪造修饰类别与分子量|回查文献/材料信息建立经核实映射|README.md
7|已完成现有计算|历史log时间、交互消融已运行；外部54曲线已评价|交互未改善历史结果；不等于机制验证|curve_metrics_54.csv
8|部分完成|新增两种细胞分别报告，H9C2未知类别已审计|补组织/物种等标准化信息；冻结模型无心脏标签|audit.json
9|部分完成|RF基础主模型外部预测已完成|原四分支融合模型未实现；不擅自重构模型|paired_predictions.csv
10|已完成计算，未获增益|历史基础/化学增强对照已归档|新数据无化学表征，不能新增外部化学增强对照|historical
11|已完成历史计算，需补外部表征|历史化学增强未证明稳定改善|9材料仍需Se含量、稳定性、Se 3d及晶相|historical
12|部分完成|历史基础/化学/IC50三层结果保留|完整L1—L4缺Modifier Category和MW|historical
13|已完成历史计算|434条24文献组OOF已有|外部702条不混入历史训练或OOF|historical
14|待补资料|未构造伪配方ID|提供可靠formulation/批次标识后再分组验证|README.md
15|已完成历史计算|历史5外层×3内层分组选择结果已有|本次未用外部响应调参|historical
16|已完成历史计算|特征选择与外层性能报告分开|不以外部结果重新挑选主模型|historical
17|仍需补实验|9材料已有粒径和Zeta|补Se含量、稳定性时间序列、Se 3d/XPS、晶相|README.md
18|部分完成，仍需补实验/记录|9×2×3×13=702条件，第二细胞H9C2已补上|原24浓度还差594条件；重复孔和批次资料待追溯|experimental_data.csv
19|部分完成，仍需补实验|13点浓度已核对，实验24条可插值、30条>512|扩充浓度设计和阈值覆盖；不插值伪造24点|experimental_ic50.csv
20|现有数据分析已完成|18组材料—细胞剂量时间网格、54条曲线及时间差值已分析|重复不确定性待补；细胞比较受接种密度混杂|observed_time_changes.csv
21|仍需新的前瞻实验|冻结模型复用、哈希及当前时间已记录|不能倒补实验前封存；新批次应先封存再测|audit.json
22|回顾性评价已完成，盲法前瞻未完成|702条件分组误差和材料bootstrap区间已生成|真正Prospective Zero-Shot需新实验与预封存证据|prediction_metrics.csv
23|现有评价已完成|整体MAE11.686、RMSE16.303、R²0.503，分细胞/时间和材料组区间已给出|区间不能代替生物重复；H9C2指标受组织缺失策略限制|prediction_metrics.csv
24|54条现有曲线分析已完成|54曲线误差、线性轴与正浓度log轴IAE均已独立复核|原24浓度曲线和重复设计仍未完成|curve_metrics_54.csv
25|预测曲线阈值分析已完成|主输入不含实测IC50；54模型曲线均>512|不能外推出有限精确IC50|model_ic50.csv
26|删失配对已完成，数值指标不可计算|实验24有限/30右删失；模型54右删失，有限配对0|不能将>512当512；模型需未来独立改进验证|ic50_pairs.csv
27|现有排序分析已完成|两细胞×三时间的实测/预测9材料排序配对|只限512 μM条件，不能推广为总体毒性序列|toxicity_rankings_512.csv
28|一致性计算已完成，72h一致性弱|72h HUVECρ0.217/τ0.167；H9C2ρ0.167/τ0.111|n=9材料，描述性结果不能证明稳定排序能力|ranking_agreement.csv
29|现有性质分析已完成，机制仍缺实验|两细胞各时间粒径/Zeta描述性关联、时间与细胞差值已生成|补修饰类别/MW/化学表征；相关不代表因果|property_associations_512.csv
30|现有特征SHAP已完成|702条件精确TreeSHAP，全部编码特征和派生组保留，加和通过|Modifier/MW不存在；SHAP不能替代机理实验|shap_summary.csv
31|已完成历史计算，未获稳定增益|SeNP-only与General迁移对照已归档|无需用这批外部响应再调迁移策略|historical
32|已完成历史计算，阴性结果|剂量时间交互消融无稳定收益|不能把计算完成写成性能提升|historical
33|历史比较已归档，解释受限|随机与分组结果存在，但样本/切分/R²口径不同|不能仅据旧非同口径数字断言分组造成全部差异|historical
34|已完成当前数据分离|历史OOF与702条件回顾性外部评价分别保存|外部结果不称实验前盲法验证|README.md
35|原设计未完成|没有把13浓度改称24浓度或用外部全量调参|原4+20设计需24浓度；4+9是另一方案，需另定|README.md
36|分析证据与表已更新，论文未重排|本表和独立分析报告已更新|论文正文结构/图表写入尚未执行；不是缺湿实验|README.md'''
    table=['# 论文修改建议实施与实验结果对照表（更新于2026-11-01）','',
           '本表取代旧恢复目录中的状态表，保留其36项建议编号。当前依据是最新《实验数据(3).xlsx》：9种SeNP、HUVEC/H9C2、24/48/72 h、13浓度，共702个条件和54条曲线。历史434条/24文献组结果未重训。', '',
           '**“已完成分析”不表示达到预期性能，也不表示原湿实验方案全部完成。** 本次为已有响应数据的回顾性外部评价；每条件一条报告值，实际重复次数和汇总方式未知。接种数量已由用户确认。H9C2为冻结模型未知类别，组织缺失被历史默认Liver填充，其数值属于条件性结果，另有映射敏感性分析。','',
           f'[最新分析报告](../../research/results/{out.name}/README.md) · [数值核验](../../research/results/{out.name}/verification.json) · [旧表存档](../../work/output-publish-restore/paper/revision/improvement-recommendations-status.md)','',
           '| 序号 | 原建议 | 当前状态 | 已完成内容/结果 | 仍需补什么 | 证据 |',
           '|---:|---|---|---|---|---|']
    flat=[]
    for line in updates.splitlines():
        number,status,done,need,evidence=line.split('|')
        number=int(number)
        target='../../research/results/'
        if evidence=='historical':
            folder='general_benchmark' if number==3 else 'transfer_comparison' if number in (4,31) else 'dose_time_interaction' if number in (7,32) else 'improved_434'
            link=f'[历史结果]({target}{folder}/summary.json)'
        else: link=f'[结果]({target}{out.name}/{evidence})'
        table.append(f'| {number} | {suggestions[number]} | {status} | {done} | {need} | {link} |')
        flat.append(dict(number=number,recommendation=suggestions[number],status=status,completed=done,remaining=need,evidence=evidence))
    table+=['','## 需补实验与需补资料分开处理','',
            '- **湿实验**：按原方案扩充浓度；原始资料若证实未做独立重复则补重复；补Se含量、稳定性、Se 3d/XPS、晶相；另做实验前封存的新批次前瞻验证。',
            '- **先回查资料**：重复孔、独立批次和汇总方式，检测方法、孔板规格、介质；统一修饰类别、经核实分子量、可靠配方/批次ID和细胞上下文。不能把缺资料一律等同于实验未做。',
            '- **原24浓度设计**：当前每曲线13点，缺11×54=594个条件，不含重复。浓度位置应重新设计，不靠插值凑数。',
            '- **不能追补成已完成**：已有实验的事前盲法封存；模型侧IC50未达阈值时的普通有限IC50误差和R²；缺失变量的SHAP及机制结论。','']
    destination=ROOT.parent/'paper/revision/improvement-recommendations-status.md'
    destination.write_text('\n'.join(table),encoding='utf-8',newline='\n')
    pd.DataFrame(flat).to_csv(out/'experiment_status_36.csv',index=False,encoding='utf-8',lineterminator='\n')


if __name__=='__main__': main()
