"""以冻结模型分析两种细胞的702个条件；不重训、不补造重复或表征。"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import sys
import importlib.metadata
from datetime import datetime
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import openpyxl
import pandas as pd
import shap
from scipy.stats import spearmanr, kendalltau
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from run_huvec_external import build_inputs, curve_records, shap_groups, digest, write_json
from summarize_huvec_for_paper import MATERIALS, TIMES, CONCENTRATIONS

KEYS = ['nanoparticle', 'cell_type', 'time_h', 'concentration_reported']
CURVE = KEYS[:3]


def save(output, name, frame):
    frame.to_csv(output / name, index=False, lineterminator='\n', encoding='utf-8')


def scores(frame):
    y, p = frame.viability_percent, frame.predicted_viability_percent
    return dict(n=len(frame), mae=float(mean_absolute_error(y, p)),
                rmse=float(np.sqrt(mean_squared_error(y, p))), r2=float(r2_score(y, p)),
                bias=float(np.mean(p-y)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output
    if output.exists() and any(output.iterdir()):
        raise ValueError('请指定新的空输出目录')
    output.mkdir(parents=True, exist_ok=True)
    original_hash = digest(args.source)
    archived = output / 'source_experiments.xlsx'
    shutil.copyfile(args.source, archived)
    workbook = openpyxl.load_workbook(archived, read_only=True, data_only=True)
    source_rows = list(workbook['Sheet1'].values)
    headers = list(source_rows.pop(0))
    expected_headers = ['药物类型','粒径（nm）','zeta电位（mv）','细胞类型','接种密度','药物浓度（按Se计μM）','处理时间（h）','存活率（%）']
    assert headers == expected_headers, headers
    records = []
    for index, r in enumerate(source_rows, 2):
        if not any(v is not None for v in r):
            continue
        assert all(v is not None for v in r), index
        match = re.fullmatch(r'(\d+(?:\.\d+)?)(万)?/孔', r[4])
        assert match, r[4]
        records.append(dict(nanoparticle=r[0], size_nm=r[1], zeta_mV=r[2], cell_type=r[3],
                            seeding_density_reported=r[4], cells_per_well=float(match[1])*(10000 if match[2] else 1),
                            concentration_reported=r[5], time_h=r[6], viability_percent=r[7],
                            concentration_unit='umol/L', source_excel_row=index))
    workbook.close()
    data = pd.DataFrame(records).sort_values(KEYS).reset_index(drop=True)
    expected = {(m,c,t,d) for m in MATERIALS for c in ('HUVEC','H9C2') for t in TIMES for d in CONCENTRATIONS}
    assert len(data) == 702 and not data.duplicated(KEYS).any()
    assert set(data[KEYS].itertuples(index=False, name=None)) == expected
    assert np.isfinite(data.select_dtypes('number')).all().all()
    save(output, 'experimental_data.csv', data)

    model_path = ROOT / 'models/improved_434/baseline_random_forest.joblib'
    model_hash = digest(model_path)
    pipeline = joblib.load(model_path)
    meta = json.loads((ROOT / 'models/improved_434/metadata.json').read_text(encoding='utf-8'))['baseline_random_forest']
    features = meta['selected_features']
    frame = build_inputs(data.to_dict('records'), 0.078971, features)
    # H9C2的组织未在源表中提供：保持缺失并明确记录冻结插补，不伪造已知组织。
    frame.loc[data.cell_type.eq('H9C2'), 'Cell_Tissue'] = np.nan
    frame['No_of_Cells (cells/well)'] = data.cells_per_well
    frame['cell_count_missing'] = 0
    without_targets = data.drop(columns='viability_percent').to_dict('records')
    independent = build_inputs(without_targets, 0.078971, features)
    independent.loc[data.cell_type.eq('H9C2'), 'Cell_Tissue'] = np.nan
    independent['No_of_Cells (cells/well)'] = data.cells_per_well
    independent['cell_count_missing'] = 0
    pd.testing.assert_frame_equal(frame, independent)
    prediction = pipeline.predict(frame)
    assert prediction.shape == (702,) and np.isfinite(prediction).all()
    paired = data.copy()
    paired['predicted_viability_percent'] = prediction
    paired['residual_pred_minus_observed'] = prediction-data.viability_percent
    paired['model_concentration_ug_ml'] = data.concentration_reported*0.078971
    save(output, 'paired_predictions.csv', paired)
    save(output, 'model_inputs.csv', pd.concat([data[KEYS],frame],axis=1))
    sensitivity=[]
    alt=frame.copy()
    alt.loc[data.cell_type.eq('H9C2'),'Cell_Tissue']='Unreported tissue'
    alt_prediction=pipeline.predict(alt)
    for cell,g in paired.groupby('cell_type'):
        mask=data.cell_type.eq(cell)
        varied=g.copy()
        varied['predicted_viability_percent']=alt_prediction[mask]
        sensitivity.append(dict(cell_type=cell,scenario='unreported_tissue_encoded_unknown',**scores(varied),
                                max_prediction_change=float(max(abs(alt_prediction[mask]-prediction[mask])))))
    save(output,'tissue_mapping_sensitivity.csv',pd.DataFrame(sensitivity))
    # 用保留的旧源表重建旧密度情景，不依赖会随本次修正更新的HUVEC预测副本。
    previous_source = ROOT/'results/external_702_20261101/source_experiments.xlsx'
    previous_book = openpyxl.load_workbook(previous_source, read_only=True, data_only=True)
    previous_densities = {r[3]: float(re.fullmatch(r'(\d+(?:\.\d+)?)万/孔', r[4])[1])*10000
                          for r in list(previous_book['Sheet1'].values)[1:] if any(v is not None for v in r)}
    previous_book.close()
    previous_frame = frame.copy()
    previous_frame['No_of_Cells (cells/well)'] = data.cell_type.map(previous_densities)
    old_prediction = data[KEYS].copy()
    old_prediction['predicted_viability_percent'] = pipeline.predict(previous_frame)
    old_prediction = old_prediction.loc[old_prediction.cell_type.eq('HUVEC')]
    old_comparison=paired.loc[paired.cell_type.eq('HUVEC')].merge(
        old_prediction[['nanoparticle','time_h','concentration_reported','predicted_viability_percent']],
        on=['nanoparticle','time_h','concentration_reported'],suffixes=('_new','_old'),validate='one_to_one')
    old_comparison['prediction_change_new_minus_old']=old_comparison.predicted_viability_percent_new-old_comparison.predicted_viability_percent_old
    save(output,'huvec_prediction_version_comparison.csv',old_comparison)

    metrics = []
    rng = np.random.default_rng(20261101)
    for cell, group in [('ALL',paired), *list(paired.groupby('cell_type'))]:
        record = dict(cell_type=cell, time_h='ALL', **scores(group))
        # 材料级重采样，保留同一材料的所有细胞/时间/浓度相关结构。
        boot = []
        blocks = [group.loc[group.nanoparticle.eq(m)] for m in MATERIALS]
        for _ in range(2000):
            sampled = pd.concat([blocks[i] for i in rng.integers(0,9,9)])
            boot.append(scores(sampled))
        for metric in ('mae','rmse','r2'):
            record[metric+'_ci_low'], record[metric+'_ci_high'] = np.quantile([b[metric] for b in boot],[.025,.975])
        metrics.append(record)
    for (cell,time),group in paired.groupby(['cell_type','time_h']):
        metrics.append(dict(cell_type=cell,time_h=time,**scores(group)))
    metric_frame=pd.DataFrame(metrics)
    save(output,'prediction_metrics.csv',metric_frame)
    curve_metrics=[]
    for key,g in paired.groupby(CURVE):
        g=g.sort_values('concentration_reported')
        x=g.concentration_reported.to_numpy(float)
        e=g.residual_pred_minus_observed.to_numpy(float)
        # 对分段线性残差精确积分；过零区间分成两个三角形。
        def iae(axis, errors):
            total=0.0
            for dx,a,b in zip(np.diff(axis),errors[:-1],errors[1:]):
                total += dx*((a*a+b*b)/(2*(abs(a)+abs(b))) if a*b<0 else (abs(a)+abs(b))/2)
            return float(total)
        raw=iae(x,e)
        log=iae(np.log10(x[1:]),e[1:])
        curve_metrics.append(dict(zip(CURVE,key)) | scores(g) | dict(
            iae_linear_umol_l=raw, normalized_iae_linear=raw/(x[-1]-x[0]),
            iae_log10_positive=log, normalized_iae_log10=log/np.log10(x[-1]/x[1])))
    save(output,'curve_metrics_54.csv',pd.DataFrame(curve_metrics))

    ic_frames={}
    for label,response in [('experimental','viability_percent'),('model','predicted_viability_percent')]:
        rec=[]
        for cell,g in paired.groupby('cell_type'):
            rec.extend(dict(r,cell_type=cell,concentration_unit='umol/L') for r in curve_records(g.to_dict('records'),response))
        ic_frames[label]=pd.DataFrame(rec)
        save(output,label+'_ic50.csv',ic_frames[label])
    ic=ic_frames['experimental'].merge(ic_frames['model'],on=CURVE,suffixes=('_experimental','_model'),validate='one_to_one')
    a=pd.to_numeric(ic.ic50_reported_scale_experimental,errors='coerce')
    b=pd.to_numeric(ic.ic50_reported_scale_model,errors='coerce')
    valid=a.gt(0)&b.gt(0)
    ic['log10_pred_minus_experimental']=np.where(valid,np.log10(b)-np.log10(a),np.nan)
    save(output,'ic50_pairs.csv',ic)
    ic_summary={'finite_pairs':int(valid.sum()),'log10_mae':None,'log10_r2':None}
    if valid.any(): ic_summary['log10_mae']=float(np.mean(abs(np.log10(b[valid])-np.log10(a[valid]))))
    if valid.sum()>1: ic_summary['log10_r2']=float(r2_score(np.log10(a[valid]),np.log10(b[valid])))

    ranks=[]; associations=[]; ranked=[]
    for (cell,time),g in paired.loc[paired.concentration_reported.eq(512)].groupby(['cell_type','time_h']):
        g=g.copy()
        g['observed_toxicity_rank']=g.viability_percent.rank(method='average')
        g['predicted_toxicity_rank']=g.predicted_viability_percent.rank(method='average')
        ranked.append(g)
        ranks.append(dict(cell_type=cell,time_h=time,n_materials=len(g),
                          spearman_rho=float(spearmanr(g.viability_percent,g.predicted_viability_percent).statistic),
                          kendall_tau_b=float(kendalltau(g.viability_percent,g.predicted_viability_percent).statistic)))
        for feature in ('size_nm','zeta_mV'):
            associations.append(dict(cell_type=cell,time_h=time,feature=feature,n_materials=len(g),
                                     spearman_rho=float(spearmanr(g[feature],g.viability_percent).statistic)))
    save(output,'toxicity_rankings_512.csv',pd.concat(ranked))
    save(output,'ranking_agreement.csv',pd.DataFrame(ranks))
    save(output,'property_associations_512.csv',pd.DataFrame(associations))
    save(output,'high_dose_time_summary.csv',paired.loc[paired.concentration_reported.eq(512)].groupby(['cell_type','time_h']).agg(
        n_materials=('nanoparticle','size'),mean_viability=('viability_percent','mean'),mean_prediction=('predicted_viability_percent','mean')).reset_index())
    time_changes=paired.pivot(index=['nanoparticle','cell_type','concentration_reported'],columns='time_h',values='viability_percent').reset_index()
    time_changes['change_72_minus_24']=time_changes[72]-time_changes[24]
    save(output,'observed_time_changes.csv',time_changes)
    cell_comparison=paired.pivot(index=['nanoparticle','time_h','concentration_reported'],columns='cell_type',values='viability_percent').reset_index()
    cell_comparison['H9C2_minus_HUVEC']=cell_comparison.H9C2-cell_comparison.HUVEC
    save(output,'observed_cell_comparison.csv',cell_comparison)

    pre=pipeline.named_steps['preprocess']; forest=pipeline.named_steps['model']
    transformed=pre.transform(frame)
    names=list(pre.get_feature_names_out())
    explainer=shap.TreeExplainer(forest,feature_perturbation='tree_path_dependent',model_output='raw')
    values=np.asarray(explainer.shap_values(transformed,check_additivity=True,approximate=False))
    base=float(np.asarray(explainer.expected_value).ravel()[0])
    groups=shap_groups(names)
    grouped=pd.DataFrame({k:values[:,v].sum(axis=1) for k,v in groups.items()})
    residual=base+values.sum(axis=1)-prediction
    assert np.max(abs(residual))<1e-6
    assert np.allclose(grouped.sum(axis=1),values.sum(axis=1),atol=1e-10,rtol=0)
    for filename,values_frame in [('transformed_inputs.csv',pd.DataFrame(transformed,columns=names)),
                                  ('shap_encoded_values.csv',pd.DataFrame(values,columns=names)),('shap_grouped_values.csv',grouped)]:
        save(output,filename,pd.concat([data[KEYS],values_frame],axis=1))
    save(output,'shap_additivity_check.csv',pd.concat([data[KEYS],pd.DataFrame(dict(base_value=base,prediction=prediction,residual=residual))],axis=1))
    shap_summary=[]
    for cell in ('HUVEC','H9C2'):
        for feature in grouped:
            v=grouped.loc[data.cell_type.eq(cell),feature]
            shap_summary.append(dict(cell_type=cell,feature=feature,mean_abs_shap=float(abs(v).mean()),mean_signed_shap=float(v.mean())))
    save(output,'shap_summary.csv',pd.DataFrame(shap_summary))
    cat=pre.named_transformers_['categorical']
    unknown={n:sorted(set(frame[n].dropna())-set(c)) for n,c in zip(cat.feature_names_in_,cat.named_steps['onehot'].categories_)}
    imputation={n:str(v) for n,v in zip(cat.feature_names_in_,cat.named_steps['imputer'].statistics_) if frame[n].isna().any()}
    old=pd.read_csv(ROOT/'data/prospective/experimental_huvec_dose_time.csv')
    old_pair=old.merge(data,on=KEYS,suffixes=('_old','_new'),validate='one_to_one')
    assert len(old_pair)==351
    for col in ('size_nm','zeta_mV','viability_percent'):
        assert np.allclose(old_pair[col+'_old'],old_pair[col+'_new'],atol=1e-9,rtol=0)
    reloaded=pd.read_csv(output/'model_inputs.csv',float_precision='round_trip')
    reproduced=joblib.load(model_path).predict(reloaded[features])
    assert np.max(abs(reproduced-prediction))<1e-10
    assert np.allclose(frame['Concentration (ug/ml)'],data.concentration_reported*.078971,atol=1e-12)
    assert np.array_equal(frame['No_of_Cells (cells/well)'],data.cells_per_well)
    assert digest(model_path)==model_hash and digest(args.source)==digest(archived)==original_hash
    for path in output.glob('*.csv'):
        raw=path.read_bytes(); assert not raw.startswith(b'\xef\xbb\xbf') and b'\r\n' not in raw
    audit=dict(run_time=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),source=str(args.source.resolve()),
               source_sha256=original_hash,model=str(model_path.resolve()),model_sha256=model_hash,
               rows=702,curves=54,features=features,concentration_scale=.078971,
               validation='retrospective_external_evaluation; no retraining, tuning, calibration or prospective blinding',
               unknown_categories=unknown,categorical_imputations=imputation,
               cell_tissue_mapping='HUVEC: historical Vascular endothelium; H9C2: missing, frozen mode imputation',
               density_mapping=data[['cell_type','seeding_density_reported','cells_per_well']].drop_duplicates().to_dict('records'),
               previous_density_source=str(previous_source.relative_to(ROOT)), previous_density_source_sha256=digest(previous_source),
               replicate_status='one reported value per condition; raw replicates/aggregation unknown',
               bootstrap='2000 material-cluster resamples; 9 materials; descriptive sampling uncertainty, not replicate precision',
               software={p:importlib.metadata.version(p) for p in ('numpy','pandas','scipy','scikit-learn','shap','joblib','openpyxl')},
               ic50=ic_summary,experimental_ic50_counts=ic_frames['experimental'].groupby(['cell_type','status']).size().rename('count').reset_index().to_dict('records'),
               max_shap_residual=float(max(abs(residual))),max_reloaded_prediction_delta=float(max(abs(reproduced-prediction))),
               unknown_modifier_category_and_mw=True,old_huvec_values_unchanged=True)
    write_json(output/'audit.json',audit)
    write_json(output/'verification.json',dict(status='PASS',rows=702,curves=54,unique_condition_keys=True,
               complete_factorial_coverage=True,source_hash_unchanged=True,model_hash_unchanged=True,
               input_independent_of_response=True,model_reload_agrees=True,shap_additivity=True,
               unit_and_cell_count_checked=True,old_huvec_values_unchanged=True))
    print(metric_frame.to_string(index=False))
    print(pd.DataFrame(ranks).to_string(index=False))
    print('IC50',json.dumps(ic_summary))
    print('EXPERIMENTAL',ic_frames['experimental'].groupby(['cell_type','status']).size())
    print('MODEL',ic_frames['model'].groupby(['cell_type','status']).size())


if __name__=='__main__':
    main()
