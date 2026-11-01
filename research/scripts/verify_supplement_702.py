"""独立核对补充实验的材料留出、锚点权限、数值与选择日志。"""
import argparse
from itertools import combinations
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator

from run_supplement_702 import ROOT, CURVE, KEYS, DOSES, X, FIXED, LAMBDAS, BASE_CANDIDATES, reconstruct, summary_scores, paired_comparison
from run_huvec_external import digest, write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    out=parser.parse_args().directory.resolve();plan=json.loads((out/'analysis_plan.json').read_text(encoding='utf-8'))
    source=Path(plan['source_directory']);assert digest(source/'paired_predictions.csv')==plan['source_sha256']
    assert digest(Path(__file__).with_name('run_supplement_702.py'))==plan['script_sha256']
    read=lambda name:pd.read_csv(out/name,float_precision='round_trip')
    data=pd.read_csv(source/'paired_predictions.csv',float_precision='round_trip')
    g=list(data.loc[data.concentration_reported.gt(0)].groupby(CURVE))
    meta=pd.DataFrame([dict(zip(CURVE,k)) for k,_ in g]);materials=sorted(meta.nanoparticle.unique())
    y=np.stack([v.sort_values('concentration_reported').viability_percent.to_numpy() for _,v in g])
    f=np.stack([v.sort_values('concentration_reported').predicted_viability_percent.to_numpy() for _,v in g])
    qmap={tuple(v):q for q,v in enumerate(meta[CURVE].values)};checks=0
    fixed=read('experiment1_predictions.csv')
    for method,values in fixed.groupby('method'):
        assert len(values)==432 and not values.duplicated(KEYS).any(),method
        for key,curve in values.groupby(CURVE):
            assert set(curve.concentration_reported)==set(DOSES)-set(DOSES[list(FIXED)])
            q=qmap[key]
            if method in ('loglinear','pchip'):
                p=np.interp(np.log(curve.concentration_reported),np.log(DOSES[list(FIXED)]),y[q,list(FIXED)]) if method=='loglinear' else PchipInterpolator(X[list(FIXED)],y[q,list(FIXED)])(np.log10(curve.concentration_reported))
                np.testing.assert_allclose(p,curve.prediction,atol=1e-10,rtol=0)
            checks+=1
    for method in ('loglinear','pchip','natural_spline','akima','4pl','gp','frozen_rf','rf_offset'):
        altered=y[0].copy();altered[[j for j in range(12) if j not in FIXED]]=-1000000
        a,_=reconstruct(method,FIXED,y[0],f[0]);b,_=reconstruct(method,FIXED,altered,f[0])
        np.testing.assert_allclose(a,b,atol=1e-12,rtol=0,equal_nan=True);checks+=1
    full=read('experiment1_full_grid.csv')
    base={m:np.stack([v.sort_values('concentration_reported').prediction.to_numpy() for _,v in z.groupby(CURVE)]) for m,z in full.groupby('method')}
    detail=f-np.stack([np.interp(X,X[list(FIXED)],v[list(FIXED)]) for v in f])
    selection=read('experiment2_selection_log.csv');queries=[j for j in range(12) if j not in FIXED]
    fusion=read('experiment2_predictions.csv')
    for row in selection.itertuples():
        train=np.where(meta.nanoparticle.ne(row.held_material))[0];test=np.where(meta.nanoparticle.eq(row.held_material))[0]
        assert len(train)==48 and len(test)==6
        if row.selection=='baseline_method':
            errors=[np.mean(abs((base[m]-y)[np.ix_(train,queries)])) for m in BASE_CANDIDATES]
            assert row.chosen==BASE_CANDIDATES[int(np.argmin(errors))]
        else:
            if row.selection=='cell_lambda':train=np.array([i for i in train if meta.iloc[i].cell_type==row.cell_type])
            errors=[np.mean(abs((base['loglinear']+v*detail-y)[np.ix_(train,queries)])) for v in LAMBDAS]
            assert float(row.chosen)==LAMBDAS[int(np.argmin(errors))]
        checks+=1
    for key,z in fusion.groupby(CURVE):
        q=qmap[key]
        for method in ('prior_lomo_global','prior_lomo_cell'):
            kind='global_lambda' if method=='prior_lomo_global' else 'cell_lambda'
            s=selection.loc[selection.held_material.eq(key[0])&selection.selection.eq(kind)]
            if kind=='cell_lambda':s=s.loc[s.cell_type.eq(key[1])]
            weight=float(s.iloc[0].chosen)
            part=z.loc[z.method.eq(method)].sort_values('concentration_reported')
            np.testing.assert_allclose(part.prediction,(base['loglinear']+weight*detail)[q,queries],atol=1e-12,rtol=0)
            checks+=1
    anchor_log=read('experiment4_anchor_selection.csv');anchor_predictions=read('experiment4_predictions.csv')
    search=read('experiment4_training_search.csv')
    for row in anchor_log.itertuples():
        dose=np.fromstring(row.anchors,sep=',');a=tuple(int(np.where(DOSES==d)[0][0]) for d in dose)
        if row.strategy=='training_optimized':
            s=search.loc[search.protocol.eq(row.protocol)&search.held_material.eq(row.held_material)]
            best=s.loc[s.training_mae.idxmin()]
            assert best.anchors==row.anchors
        subset=anchor_predictions.loc[anchor_predictions.protocol.eq(row.protocol)&anchor_predictions.method.eq(row.strategy)&anchor_predictions.nanoparticle.eq(row.held_material)]
        if row.strategy=='adaptive_observed_drop':subset=subset.loc[subset.cell_type.eq(row.cell_type)&subset.time_h.eq(float(row.time_h))]
        for key,z in subset.groupby(CURVE):
            q=qmap[key];query=np.array([int(np.where(DOSES==d)[0][0]) for d in z.concentration_reported])
            assert set(a).isdisjoint(query)
            if row.protocol=='matched4_queries':assert set(query)==set(plan['matched_anchor_query_indices'])
            expected=np.interp(X[query],X[list(a)],y[q,list(a)])
            np.testing.assert_allclose(expected,z.prediction,atol=1e-10,rtol=0);checks+=1
        if row.strategy=='training_optimized':
            train=np.where(meta.nanoparticle.ne(row.held_material))[0]
            available=[j for j in range(1,11) if row.protocol!='matched4_queries' or j not in plan['matched_anchor_query_indices']]
            candidate_errors=[];candidate_doses=[]
            for pair in combinations(available,2):
                candidate=(0,*pair,11);query=plan['matched_anchor_query_indices'] if row.protocol=='matched4_queries' else [j for j in range(12) if j not in candidate]
                errors=[]
                for q in train:
                    p=np.interp(X[query],X[list(candidate)],y[q,list(candidate)])
                    errors.extend(abs(p-y[q,query]))
                candidate_errors.append(np.mean(errors));candidate_doses.append(candidate)
            assert a==candidate_doses[int(np.argmin(candidate_errors))];checks+=1
    budget=read('experiment3_predictions.csv');budgets=read('experiment3_anchor_sets.csv')
    for row in budgets.itertuples():
        a=np.fromstring(row.anchors,sep=',');query=np.fromstring(row.queries,sep=',')
        assert len(a)==row.k and set(a).isdisjoint(query)
        z=budget.loc[budget.protocol.eq(row.protocol)&budget.k.eq(row.k)]
        for _,v in z.groupby(['method']+CURVE):assert set(v.concentration_reported)==set(query)
        checks+=1
    matched=budget.loc[budget.protocol.eq('nested_matched_queries')]
    for _,z in matched.loc[matched.method.eq('frozen_rf')].groupby(KEYS):
        assert z.prediction.max()==z.prediction.min();checks+=1
    inputs=pd.read_csv(source/'model_inputs.csv',float_precision='round_trip')
    audit=json.loads((source/'audit.json').read_text(encoding='utf-8'))
    zero=read('experiment5_zero_shot_predictions.csv')
    for held in materials:
        mask=data.nanoparticle.eq(held)
        for method in ('self_only_rf','historical_plus_residual_rf'):
            model=joblib.load(out/f'lomo_{held.replace("-SeNPs","")}_{method}.joblib')
            prediction=model.predict(inputs.loc[mask,audit['features']])
            if method=='historical_plus_residual_rf':prediction+=data.loc[mask,'predicted_viability_percent'].to_numpy()
            stored=zero.loc[zero.held_material.eq(held)&zero.method.eq(method)]
            assert len(stored)==78
            np.testing.assert_allclose(prediction,stored.prediction,atol=1e-10,rtol=0)
            coats=inputs.loc[mask,'Coat/Functional Group'].unique();known=model.named_steps['preprocess'].named_transformers_['categorical'].named_steps['onehot'].categories_[0]
            assert set(coats).isdisjoint(known);checks+=1
    source_model=ROOT/'models/improved_434/baseline_random_forest.joblib'
    assert digest(source_model)==audit['model_sha256']
    # 重新从保存的逐点预测计算每个方法的误差，避免只核对汇总表自身。
    for predictions,metrics_name,group_cols in [('experiment1_predictions.csv','experiment1_metrics.csv',['method']),
        ('experiment2_predictions.csv','experiment2_metrics.csv',['method']),('experiment3_predictions.csv','experiment3_metrics.csv',['protocol','k','method']),
        ('experiment4_predictions.csv','experiment4_metrics.csv',['protocol','method']),('experiment6_predictions.csv','experiment6_metrics.csv',['method'])]:
        actual=summary_scores(read(predictions),group_cols);saved=read(metrics_name)
        for column in ('mae','rmse','r2','bias','coverage'):
            np.testing.assert_allclose(actual[column],saved[column],atol=1e-11,rtol=0,equal_nan=True)
        checks+=len(saved)
    comparisons=[]
    for method in ('pchip','natural_spline','akima','4pl_or_loglinear','gp','rf_offset'):
        comparisons+=paired_comparison(fixed,method,'loglinear',[])
    save=pd.DataFrame(comparisons);save.to_csv(out/'experiment1_paired_comparisons.csv',index=False,encoding='utf-8',lineterminator='\n')
    budget_comparisons=[]
    for method in ('loglinear','pchip','rf_offset'):
        for k in range(3,7):
            target=matched.loc[matched.method.eq(method)&matched.k.eq(k)].copy();target['method']='k'+str(k)
            ref=matched.loc[matched.method.eq(method)&matched.k.eq(k-1)].copy();ref['method']='k'+str(k-1)
            values=paired_comparison(pd.concat([target,ref]),'k'+str(k),'k'+str(k-1),[])
            budget_comparisons += [dict(v,reconstruction_method=method,k=k) for v in values]
    pd.DataFrame(budget_comparisons).to_csv(out/'experiment3_matched_paired_comparisons.csv',index=False,encoding='utf-8',lineterminator='\n')
    ranges=[]
    for method,g in fixed.groupby('method'):
        ranges.append(dict(method=method,min_prediction=float(g.prediction.min()),max_prediction=float(g.prediction.max()),
                           predictions_below_zero=int((g.prediction<0).sum()),predictions_above_100=int((g.prediction>100).sum())))
    pd.DataFrame(ranges).to_csv(out/'prediction_ranges.csv',index=False,encoding='utf-8',lineterminator='\n')
    for p in out.glob('*.csv'):
        raw=p.read_bytes();assert not raw.startswith(b'\xef\xbb\xbf') and b'\r\n' not in raw,p
    write_json(out/'verification.json',dict(status='PASS',numerical_and_split_checks=checks,source_hash_unchanged=True,
        frozen_model_hash_unchanged=True,held_out_method_responds_only_to_permitted_anchors=True,
        lomo_weights_and_method_selection_rebuilt=True,anchor_selection_rebuilt_without_target_queries=True,
        zero_shot_fold_models_reloaded=True,held_material_coating_absent_from_fold_encoder=True,
        matched_query_protocols_checked=True,notes='exploratory existing-data evaluation; material bootstrap intervals condition on saved outer-fold predictions'))
    print('PASS',checks,'numerical/split checks')


if __name__=='__main__':main()
