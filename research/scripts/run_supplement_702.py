"""八项补充计算实验；固定方案、按材料留出选择、保留全部方法结果。"""
import argparse
from datetime import datetime
import importlib.metadata
from itertools import combinations
import json
from pathlib import Path
import warnings
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator, CubicSpline, Akima1DInterpolator, RBFInterpolator
from scipy.optimize import least_squares
from scipy.special import expit
from scipy.stats import spearmanr
from sklearn.base import clone
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel

from analyze_reframed_702 import metrics, n_auc
from run_huvec_external import digest, write_json

ROOT = Path(__file__).resolve().parents[1]
CURVE = ['nanoparticle', 'cell_type', 'time_h']
KEYS = CURVE + ['concentration_reported']
DOSES = np.array([.25,.5,1,2,4,8,16,32,64,128,256,512.])
X = np.log10(DOSES)
FIXED = (0,4,8,11)
LAMBDAS = np.array([0.,.25,.5,.75,1.])
BASE_CANDIDATES = ('loglinear','pchip','natural_spline','akima','gp','4pl_or_loglinear')


def save(out, name, rows):
    pd.DataFrame(rows).to_csv(out/name,index=False,encoding='utf-8',lineterminator='\n')


def gp_fit_predict(x, y, query):
    kernel = ConstantKernel(1.,(.001,1000.))*RBF(np.ones(x.shape[1]),(.05,10.))+WhiteKernel(.01,(1e-5,1.))
    gp = GaussianProcessRegressor(kernel=kernel,normalize_y=True,n_restarts_optimizer=0,random_state=42)
    gp.fit(x,y)
    return gp.predict(query)


def reconstruct(method, a, y, f):
    a = np.asarray(a,dtype=int)
    xa, ya = X[a],y[a]
    detail = dict(status='ok',warnings='',identifiability='not_applicable')
    if method == 'loglinear': p = np.interp(X,xa,ya)
    elif method == 'pchip': p = PchipInterpolator(xa,ya)(X)
    elif method == 'natural_spline': p = CubicSpline(xa,ya,bc_type='natural')(X)
    elif method == 'akima': p = Akima1DInterpolator(xa,ya,method='akima')(X)
    elif method == 'frozen_rf': p = f.copy()
    elif method == 'rf_offset': p = f+np.mean(ya-f[a])
    elif method == 'gp':
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            p = gp_fit_predict(xa[:,None],ya,X[:,None])
        detail['warnings'] = ' | '.join(str(w.message) for w in caught)
    elif method == '4pl':
        def response(par, z):
            bottom,amplitude,mid,hill = par
            return bottom+amplitude*expit(-np.log(10)*hill*(z-mid))
        lower = np.array([-20.,.01,X[0]-2,.05])
        upper = np.array([150.,200.,X[-1]+2,8.])
        solutions = []
        for fraction,hill in ((.25,.5),(.5,1.),(.75,2.)):
            start = np.array([np.clip(min(ya),-19,149),np.clip(np.ptp(ya),.02,199),xa[0]+fraction*(xa[-1]-xa[0]),hill])
            fit = least_squares(lambda par:response(par,xa)-ya,start,bounds=(lower,upper),max_nfev=3000)
            if fit.success and np.isfinite(fit.x).all(): solutions.append(fit)
        if not solutions:
            detail.update(status='failed',identifiability='no_converged_fit')
            return np.full(12,np.nan),detail
        fit = min(solutions,key=lambda v:np.sum(v.fun**2))
        p = response(fit.x,X)
        condition = np.linalg.cond(fit.jac)
        boundary = bool(np.any((fit.x-lower)/(upper-lower)<1e-4) or np.any((upper-fit.x)/(upper-lower)<1e-4))
        detail.update(parameters=json.dumps(fit.x.tolist()),jacobian_condition=float(condition) if np.isfinite(condition) else None,
                      parameter_at_boundary=boundary,anchor_rmse=float(np.sqrt(np.mean(fit.fun**2))),
                      identifiability='weak_or_boundary' if boundary or condition>1e8 else 'four_points_four_parameters_no_residual_dof')
    else: raise ValueError(method)
    assert np.isfinite(p).all(),method
    return np.asarray(p),detail


def summary_scores(frame, groups):
    results = []
    for keys,g in frame.groupby(groups,dropna=False):
        if not isinstance(keys,tuple): keys=(keys,)
        base = dict(zip(groups,keys))
        views = [('ALL','ALL',g)]
        views += [(c,'ALL',s) for c,s in g.groupby('cell_type')]
        views += [(c,t,s) for (c,t),s in g.groupby(['cell_type','time_h'])]
        for cell,time,v in views:
            valid = np.isfinite(v.prediction)
            values = metrics(v.loc[valid,'observed'],v.loc[valid,'prediction']) if valid.any() else dict(n=0,mae=None,rmse=None,r2=None,bias=None)
            results.append(base | dict(cell_type=cell,time_h=time,expected_n=len(v),coverage=float(valid.mean())) | values)
    return pd.DataFrame(results)


def paired_comparison(frame, target, reference, group_columns, seed=20261103):
    identifiers = KEYS+group_columns
    a = frame.loc[frame.method.eq(target)]
    b = frame.loc[frame.method.eq(reference)]
    paired = a.merge(b,on=identifiers,suffixes=('_a','_b'),validate='one_to_one')
    assert len(paired)==len(a)==len(b)
    assert np.allclose(paired.observed_a,paired.observed_b)
    assert np.isfinite(paired.prediction_a).all() and np.isfinite(paired.prediction_b).all()
    paired['difference'] = abs(paired.prediction_a-paired.observed_a)-abs(paired.prediction_b-paired.observed_b)
    views = [('ALL','ALL',paired)]
    views += [(c,'ALL',s) for c,s in paired.groupby('cell_type')]
    rows=[]; rng=np.random.default_rng(seed)
    for cell,time,g in views:
        by_material=g.groupby('nanoparticle').difference.mean()
        assert len(by_material)==9
        draws=by_material.to_numpy()[rng.integers(0,9,(2000,9))].mean(axis=1)
        low,high=np.quantile(draws,[.025,.975])
        rows.append(dict(target=target,reference=reference,cell_type=cell,time_h=time,n_conditions=len(g),
                         materials=9,mae_difference=float(g.difference.mean()),ci_low=float(low),ci_high=float(high)))
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); out=args.output.resolve()
    if out.exists() and any(out.iterdir()): raise ValueError('请指定新的空输出目录')
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'results/external_702_20261101_confirmed'
    for name,h in json.loads((source/'manifest.json').read_text(encoding='utf-8')).items():
        assert digest(source/name)==h,name
    plan=dict(recorded_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),exploratory_after_previous_results=True,
        source_directory=str(source),source_sha256=digest(source/'paired_predictions.csv'),script_sha256=digest(Path(__file__)),
        fixed_anchors=DOSES[list(FIXED)].tolist(),dose_grid=DOSES.tolist(),zero_control_excluded_from_curve_reconstruction=True,
        methods=list(BASE_CANDIDATES)+['4pl','frozen_rf','rf_offset'],spline_boundary='natural',akima='akima',
        gp='C(1,.001..1000)*RBF(length=1,.05..10)+White(.01,1e-5..1), normalize_y=True; likelihood fit on allowed anchors only',
        four_pl='bottom+amplitude/(1+10**(hill*(log10c-mid))); three anchor-only starts; bounds [-20,.01,minlog-2,.05]..[150,200,maxlog+2,8]; numerical failures reported, explicit loglinear fallback',
        lambda_grid=LAMBDAS.tolist(),lambda_selection='minimum training-material MAE, ties prefer smaller lambda; outer held material excluded',
        baseline_selection='training-material MAE among fixed complete-coverage candidates, tie in listed order',
        outer_split='9 leave-one-material-out folds; both cell systems/all times/doses of target material held together',
        zero_shot_models='frozen historical RF; self-only clone RF; frozen historical RF+clone RF fitted to training-material residuals; 250 trees and fixed original parameters',
        anchor_strategies=dict(fixed=list(FIXED),equal_log=[0,4,7,11],low_dense=[0,1,3,11],high_dense=[0,8,10,11]),
        anchor_optimization='two endpoint anchors plus 2 of 10 interior positions (45 sets), selected using 8 other materials; loglinear objective',
        matched_anchor_query_indices=[2,5,6,9],matched_anchor_search='15 admissible endpoint-containing anchor sets exclude four fixed query concentrations',
        adaptive_rule='endpoint anchors then midpoint in remaining interval maximizing absolute observed endpoint drop times log-width; only opened anchors accessed',
        budget_k=[2,3,4,5,6],budget_indices='equal log grid rounding for varying tests; nested endpoints,+4,+8,+3,+9 for common queries',
        budget_common_query_indices=[1,2,5,6,7,10],
        dose_time_methods='2D thin-plate RBF smoothing=0; 2D GP likelihood fit only 12 observed anchors; other-material mean interpolation-residual template',
        shape_analysis='weighted discrete-grid PCA on 12 positive-dose responses; 3 descriptive KMeans clusters, seed=42; no cluster inferential tests',
        sensitivity='leave-one-material metric stability; raw versus source-control-normalized responses; primary log/secondary linear AUC; frozen H9C2 unknown tissue scenario',
        clipping='none for reported observations or predictions; 4PL parameter constraints are model assumptions, not data clipping',
        bootstrap=dict(repetitions=2000,unit='material',interval='exploratory percentile, no biological replicate inference'),
        figure_backend='Python/matplotlib; PDF/SVG/PNG; no AI image generation',
        software={p:importlib.metadata.version(p) for p in ('numpy','pandas','scipy','scikit-learn','joblib','matplotlib')})
    write_json(out/'analysis_plan.json',plan)
    data=pd.read_csv(source/'paired_predictions.csv',float_precision='round_trip')
    groups=list(data.loc[data.concentration_reported.gt(0)].groupby(CURVE))
    meta=pd.DataFrame([dict(zip(CURVE,key)) for key,_ in groups])
    y=np.stack([g.sort_values('concentration_reported').viability_percent.to_numpy() for _,g in groups])
    f=np.stack([g.sort_values('concentration_reported').predicted_viability_percent.to_numpy() for _,g in groups])
    materials=sorted(meta.nanoparticle.unique()); assert y.shape==(54,12) and len(materials)==9
    curve_keys=[tuple(r) for r in meta[CURVE].values]
    def long(method,pred,anchors=FIXED,protocol='fixed4',curve_indices=None,query_indices=None,**extra):
        records=[]
        for q in range(54) if curve_indices is None else curve_indices:
            query=[i for i in range(12) if i not in anchors] if query_indices is None else query_indices
            for j in query:
                records.append(meta.iloc[q].to_dict() | dict(concentration_reported=DOSES[j],method=method,
                    observed=y[q,j],prediction=pred[q,j],protocol=protocol) | extra)
        return records
    def matrix(method,anchors):
        values=[];logs=[]
        for q in range(54):
            p,detail=reconstruct(method,anchors,y[q],f[q]); values.append(p)
            logs.append(meta.iloc[q].to_dict() | dict(method=method,**detail))
        return np.stack(values),logs
    print('Experiment 1: fixed four-anchor baselines',flush=True)
    base={}; fit_logs=[]; records=[]
    for method in ('loglinear','pchip','natural_spline','akima','4pl','gp','frozen_rf','rf_offset'):
        pred,logs=matrix(method,FIXED);base[method]=pred;fit_logs+=logs;records+=long(method,pred)
        print(' ',method,flush=True)
    base['4pl_or_loglinear']=np.where(np.isfinite(base['4pl']),base['4pl'],base['loglinear'])
    records+=long('4pl_or_loglinear',base['4pl_or_loglinear'])
    fixed_frame=pd.DataFrame(records)
    save(out,'experiment1_predictions.csv',fixed_frame);save(out,'experiment1_fit_diagnostics.csv',fit_logs)
    save(out,'experiment1_metrics.csv',summary_scores(fixed_frame,['method']))
    save(out,'experiment1_full_grid.csv',[meta.iloc[q].to_dict() | dict(method=method,concentration_reported=DOSES[j],
        observed=y[q,j],prediction=p[q,j],is_anchor=j in FIXED) for method,p in base.items() for q in range(54) for j in range(12)])
    print('Experiments 2/5B: outer-material prior fusion and reference selection',flush=True)
    detail=f-np.stack([np.interp(X,X[list(FIXED)],row[list(FIXED)]) for row in f])
    fused={f'prior_lambda_{v:g}':base['loglinear']+v*detail for v in LAMBDAS}
    selected_global=np.zeros_like(y);selected_cell=np.zeros_like(y);selected_reference=np.zeros_like(y)
    selections=[];lomo_log=[]
    test_index=[j for j in range(12) if j not in FIXED]
    for material in materials:
        train=np.where(meta.nanoparticle.ne(material))[0];test=np.where(meta.nanoparticle.eq(material))[0]
        assert len(train)==48 and len(test)==6
        lomo_log.append(dict(held_material=material,training_materials=';'.join(m for m in materials if m!=material),
                             training_curves=len(train),test_curves=len(test),training_full_conditions=624,test_full_conditions=78,
                             permitted_target_anchors=24,test_positive_queries=48))
        lambda_errors=[np.mean(abs((base['loglinear']+v*detail-y)[np.ix_(train,test_index)])) for v in LAMBDAS]
        chosen=LAMBDAS[int(np.argmin(lambda_errors))]
        selected_global[test]=base['loglinear'][test]+chosen*detail[test]
        candidate_errors=[np.mean(abs((base[m]-y)[np.ix_(train,test_index)])) for m in BASE_CANDIDATES]
        best_method=BASE_CANDIDATES[int(np.argmin(candidate_errors))]
        selected_reference[test]=base[best_method][test]
        selections.append(dict(held_material=material,selection='global_lambda',cell_type='ALL',chosen=str(chosen),training_mae=min(lambda_errors),training_materials=8))
        selections.append(dict(held_material=material,selection='baseline_method',cell_type='ALL',chosen=best_method,training_mae=min(candidate_errors),training_materials=8))
        for cell in sorted(meta.cell_type.unique()):
            tr=[q for q in train if meta.iloc[q].cell_type==cell];te=[q for q in test if meta.iloc[q].cell_type==cell]
            errors=[np.mean(abs((base['loglinear']+v*detail-y)[np.ix_(tr,test_index)])) for v in LAMBDAS]
            choice=LAMBDAS[int(np.argmin(errors))]
            selected_cell[te]=base['loglinear'][te]+choice*detail[te]
            selections.append(dict(held_material=material,selection='cell_lambda',cell_type=cell,chosen=str(choice),training_mae=min(errors),training_materials=8))
    fused.update(prior_lomo_global=selected_global,prior_lomo_cell=selected_cell,baseline_lomo_selected=selected_reference,
                 loglinear=base['loglinear'],pchip=base['pchip'],gp=base['gp'])
    fusion_frame=pd.DataFrame([r for name,p in fused.items() for r in long(name,p)])
    save(out,'experiment2_predictions.csv',fusion_frame);save(out,'experiment2_selection_log.csv',selections)
    save(out,'experiment2_metrics.csv',summary_scores(fusion_frame,['method']));save(out,'lomo_fold_assignments.csv',lomo_log)
    fusion_compare=[]
    for target in ('prior_lomo_global','prior_lomo_cell'):
        for ref in ('loglinear','pchip','baseline_lomo_selected'):
            fusion_compare+=paired_comparison(fusion_frame,target,ref,[])
    save(out,'experiment2_paired_comparisons.csv',fusion_compare)
    auc_fusion=[]
    for method,p in fused.items():
        for q in range(54):
            auc_fusion.append(meta.iloc[q].to_dict() | dict(method=method,observed_nauc=n_auc(DOSES,y[q],True),
                 reconstructed_nauc=n_auc(DOSES,p[q],True),nauc_abs_error_pp=100*abs(n_auc(DOSES,p[q],True)-n_auc(DOSES,y[q],True)),
                 evaluation='anchor-conditioned full positive grid, includes measured anchors'))
    save(out,'experiment2_conditioned_auc.csv',auc_fusion)

    print('Experiment 3: measurement budget, varying and matched query sets',flush=True)
    budget_rows=[];budget_log=[];sequence=[0,11,4,8,3,9];common=[1,2,5,6,7,10]
    for protocol in ('equal_log_remaining','nested_matched_queries'):
        for k in range(2,7):
            a=tuple(sorted(np.rint(np.linspace(0,11,k)).astype(int))) if protocol=='equal_log_remaining' else tuple(sorted(sequence[:k]))
            query=[j for j in range(12) if j not in a] if protocol=='equal_log_remaining' else common
            budget_log.append(dict(protocol=protocol,k=k,anchors=','.join(str(DOSES[j]) for j in a),queries=','.join(str(DOSES[j]) for j in query)))
            for method in ('loglinear','pchip','rf_offset','frozen_rf'):
                p,_=matrix(method,a)
                budget_rows+=long(method,p,a,protocol=protocol,query_indices=query,k=k)
    budget_frame=pd.DataFrame(budget_rows)
    save(out,'experiment3_predictions.csv',budget_frame);save(out,'experiment3_anchor_sets.csv',budget_log)
    save(out,'experiment3_metrics.csv',summary_scores(budget_frame,['protocol','k','method']))

    print('Experiment 4: material-held-out anchor selection and adaptive sampling',flush=True)
    anchor_rows=[];anchor_logs=[];score_logs=[]
    for protocol in ('remaining8','matched4_queries'):
        query_fixed=plan['matched_anchor_query_indices'] if protocol=='matched4_queries' else None
        available=[j for j in range(1,11) if query_fixed is None or j not in query_fixed]
        candidates=[(0,*pair,11) for pair in combinations(available,2)]
        cache={a:matrix('loglinear',a)[0] for a in candidates}
        for held in materials:
            train=np.where(meta.nanoparticle.ne(held))[0];test=np.where(meta.nanoparticle.eq(held))[0]
            errors=[]
            for a in candidates:
                query=query_fixed if query_fixed is not None else [j for j in range(12) if j not in a]
                error=float(np.mean(abs((cache[a]-y)[np.ix_(train,query)])))
                errors.append(error)
                score_logs.append(dict(protocol=protocol,held_material=held,anchors=','.join(str(DOSES[j]) for j in a),training_mae=error))
            optimized=candidates[int(np.argmin(errors))]
            strategies={name:tuple(v) for name,v in plan['anchor_strategies'].items()}
            strategies['training_optimized']=optimized
            for strategy,a in strategies.items():
                assert query_fixed is None or set(a).isdisjoint(query_fixed)
                p=cache[a] if a in cache else matrix('loglinear',a)[0]
                anchor_rows+=long(strategy,p,a,protocol=protocol,curve_indices=test,query_indices=query_fixed)
                anchor_logs.append(dict(protocol=protocol,held_material=held,strategy=strategy,cell_type='ALL',time_h='ALL',anchors=','.join(str(DOSES[j]) for j in a),training_materials=8))
            for q in test:
                a=[0,11]
                for _ in range(2):
                    intervals=[]
                    for left,right in zip(sorted(a)[:-1],sorted(a)[1:]):
                        allowed=[j for j in range(left+1,right) if query_fixed is None or j not in query_fixed]
                        if allowed:
                            new=min(allowed,key=lambda j:(abs(X[j]-(X[left]+X[right])/2),j))
                            intervals.append((abs(y[q,right]-y[q,left])*(X[right]-X[left]),-new,new))
                    a.append(max(intervals)[2])
                a=tuple(sorted(a));p=np.zeros_like(y);p[q]=np.interp(X,X[list(a)],y[q,list(a)])
                anchor_rows+=long('adaptive_observed_drop',p,a,protocol=protocol,curve_indices=[q],query_indices=query_fixed)
                anchor_logs.append(meta.iloc[q].to_dict() | dict(protocol=protocol,held_material=held,strategy='adaptive_observed_drop',anchors=','.join(str(DOSES[j]) for j in a),training_materials=0))
    anchor_frame=pd.DataFrame(anchor_rows)
    save(out,'experiment4_predictions.csv',anchor_frame);save(out,'experiment4_anchor_selection.csv',anchor_logs)
    save(out,'experiment4_training_search.csv',score_logs);save(out,'experiment4_metrics.csv',summary_scores(anchor_frame,['protocol','method']))
    selection_comparisons=[]
    matched=anchor_frame.loc[anchor_frame.protocol.eq('matched4_queries')]
    for method in ('training_optimized','equal_log','low_dense','high_dense','adaptive_observed_drop'):
        selection_comparisons+=paired_comparison(matched,method,'fixed',[])
    save(out,'experiment4_matched_paired_comparisons.csv',selection_comparisons)

    print('Experiment 5A: zero-shot leave-one-material-out refits, no target responses',flush=True)
    pipeline=joblib.load(ROOT/'models/improved_434/baseline_random_forest.joblib')
    inputs=pd.read_csv(source/'model_inputs.csv',float_precision='round_trip')
    audit=json.loads((source/'audit.json').read_text(encoding='utf-8'))
    features=audit['features']; zero_rows=[];fit_warnings=[]
    assert inputs[KEYS].equals(data[KEYS])
    for held in materials:
        train=data.nanoparticle.ne(held);test=data.nanoparticle.eq(held)
        assert train.sum()==624 and test.sum()==78
        predictions={'frozen_historical_rf':data.loc[test,'predicted_viability_percent'].to_numpy()}
        for name,target in [('self_only_rf',data.viability_percent),('historical_plus_residual_rf',data.viability_percent-data.predicted_viability_percent)]:
            model=clone(pipeline)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always');model.fit(inputs.loc[train,features],target.loc[train]);p=model.predict(inputs.loc[test,features])
            if name=='historical_plus_residual_rf':p=p+data.loc[test,'predicted_viability_percent'].to_numpy()
            predictions[name]=p
            fit_warnings.append(dict(held_material=held,method=name,warnings=' | '.join(sorted({str(w.message) for w in caught}))))
            joblib.dump(model,out/f'lomo_{held.replace("-SeNPs","")}_{name}.joblib')
        for method,p in predictions.items():
            for row,prediction in zip(data.loc[test].to_dict('records'),p):
                zero_rows.append({k:row[k] for k in KEYS} | dict(method=method,observed=row['viability_percent'],prediction=float(prediction),held_material=held))
        print(' ',held,flush=True)
    zero_frame=pd.DataFrame(zero_rows)
    save(out,'experiment5_zero_shot_predictions.csv',zero_frame);save(out,'experiment5_fit_warnings.csv',fit_warnings)
    all_scores=summary_scores(zero_frame,['method']);all_scores['dose_scope']='all_13'
    positive_scores=summary_scores(zero_frame.loc[zero_frame.concentration_reported.gt(0)],['method']);positive_scores['dose_scope']='positive_12'
    save(out,'experiment5_zero_shot_metrics.csv',pd.concat([all_scores,positive_scores]))
    zero_comparisons=[]
    for target,reference in [('self_only_rf','frozen_historical_rf'),('historical_plus_residual_rf','frozen_historical_rf'),('historical_plus_residual_rf','self_only_rf')]:
        zero_comparisons+=paired_comparison(zero_frame,target,reference,[])
    save(out,'experiment5_paired_comparisons.csv',zero_comparisons)

    print('Experiment 6: joint dose-time reconstruction with the same 12 anchors/system',flush=True)
    joint={name:np.zeros_like(y) for name in ('joint_rbf','joint_gp','training_material_residual_template')}
    joint_logs=[]
    for material in materials:
        for cell in sorted(meta.cell_type.unique()):
            qids=[q for q in range(54) if meta.iloc[q].nanoparticle==material and meta.iloc[q].cell_type==cell]
            design=np.array([[(X[j]-X[0])/(X[-1]-X[0]),(meta.iloc[q].time_h-24)/48] for q in qids for j in FIXED])
            responses=np.array([y[q,j] for q in qids for j in FIXED])
            query=np.array([[(X[j]-X[0])/(X[-1]-X[0]),(meta.iloc[q].time_h-24)/48] for q in qids for j in range(12)])
            joint['joint_rbf'][qids]=RBFInterpolator(design,responses,kernel='thin_plate_spline',smoothing=0.)(query).reshape(3,12)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always');p=gp_fit_predict(design,responses,query)
            joint['joint_gp'][qids]=p.reshape(3,12)
            joint_logs.append(dict(nanoparticle=material,cell_type=cell,observed_anchors=12,warnings=' | '.join(str(w.message) for w in caught)))
            for q in qids:
                train=[i for i in range(54) if meta.iloc[i].nanoparticle!=material and meta.iloc[i].cell_type==cell and meta.iloc[i].time_h==meta.iloc[q].time_h]
                shape=(y-base['loglinear'])[train].mean(axis=0)
                joint['training_material_residual_template'][q]=base['loglinear'][q]+shape
    joint.update(loglinear=base['loglinear'],pchip=base['pchip'],gp=base['gp'])
    joint_frame=pd.DataFrame([r for method,p in joint.items() for r in long(method,p)])
    save(out,'experiment6_predictions.csv',joint_frame);save(out,'experiment6_fit_log.csv',joint_logs)
    save(out,'experiment6_metrics.csv',summary_scores(joint_frame,['method']))
    joint_comparisons=[]
    for method in ('joint_rbf','joint_gp','training_material_residual_template'):
        joint_comparisons+=paired_comparison(joint_frame,method,'loglinear',[])
    save(out,'experiment6_paired_comparisons.csv',joint_comparisons)

    print('Experiment 7: descriptive shape, weighted grid PCA and property associations',flush=True)
    weights=np.r_[np.diff(X)[0]/2,(np.diff(X)[:-1]+np.diff(X)[1:])/2,np.diff(X)[-1]/2];weights/=weights.sum()
    pca=PCA(n_components=3);scores=pca.fit_transform(y*np.sqrt(weights))
    clusters=KMeans(n_clusters=3,random_state=42,n_init=20).fit_predict(scores)
    shape_rows=[]
    for q in range(54):
        change=np.diff(y[q]);slope=change/np.diff(X);peak=int(np.argmin(slope));minimum=int(np.argmin(y[q]))
        shape_rows.append(meta.iloc[q].to_dict() | dict(nauc_log=n_auc(DOSES,y[q],True),nauc_linear=n_auc(np.r_[0,DOSES],np.r_[100,y[q]],False),
            min_viability=float(y[q,minimum]),min_dose=DOSES[minimum],max_viability=float(max(y[q])),
            endpoint_change=float(y[q,-1]-y[q,0]),maximum_local_drop=float(-min(change)),steepest_drop_log_slope=float(slope[peak]),
            steepest_interval_low=DOSES[peak],steepest_interval_high=DOSES[peak+1],upward_steps=int(sum(change>0)),
            upward_steps_over_5pp=int(sum(change>5)),cluster=int(clusters[q])+1,PC1=scores[q,0],PC2=scores[q,1],PC3=scores[q,2]))
    shapes=pd.DataFrame(shape_rows);save(out,'experiment7_curve_shapes.csv',shapes)
    save(out,'experiment7_pca_loadings.csv',[dict(component=k+1,dose=DOSES[j],weighted_loading=pca.components_[k,j],explained_variance_ratio=pca.explained_variance_ratio_[k]) for k in range(3) for j in range(12)])
    timeline=shapes.pivot(index=['nanoparticle','cell_type'],columns='time_h',values='nauc_log').reset_index()
    timeline['nauc_72_minus_24']=timeline[72]-timeline[24];save(out,'experiment7_nauc_time_changes.csv',timeline)
    props=data.groupby('nanoparticle')[['size_nm','zeta_mV']].first();association=[]
    for (cell,time),g in shapes.groupby(['cell_type','time_h']):
        g=g.merge(props,on='nanoparticle',validate='one_to_one')
        for descriptor in ('size_nm','zeta_mV'):
            for response in ('nauc_log','endpoint_change','min_viability'):
                association.append(dict(cell_type=cell,time_h=time,descriptor=descriptor,response=response,n_materials=9,
                    spearman_rho=float(spearmanr(g[descriptor],g[response]).statistic),inference='descriptive only, no causal or multiple-testing significance claim'))
    save(out,'experiment7_property_associations.csv',association)

    print('Experiment 8: stability and sensitivity checks',flush=True)
    per_material=fixed_frame.loc[fixed_frame.method.ne('4pl')].groupby(['method','nanoparticle']).apply(
        lambda g:pd.Series(metrics(g.observed,g.prediction)),include_groups=False).reset_index()
    save(out,'experiment8_method_material_metrics.csv',per_material)
    stability=[]
    for method,g in fixed_frame.loc[fixed_frame.method.ne('4pl')].groupby('method'):
        for excluded in materials:
            a=g.loc[g.nanoparticle.ne(excluded)]
            stability.append(dict(method=method,omitted_material=excluded,interpretation='post-hoc metric stability, no refitting',**metrics(a.observed,a.prediction)))
    save(out,'experiment8_omit_material_stability.csv',stability)
    control=data.loc[data.concentration_reported.eq(0)].set_index(CURVE).viability_percent
    control_delta=max(abs(control-100));assert control_delta==0
    base_inputs=pd.read_csv(source/'model_inputs.csv',float_precision='round_trip');alternative=base_inputs[features].copy()
    alternative.loc[base_inputs.cell_type.eq('H9C2'),'Cell_Tissue']='Unreported tissue'
    alt_prediction=pipeline.predict(alternative);alt_groups=data[KEYS].copy();alt_groups['prediction']=alt_prediction
    alt_f=np.stack([g.loc[g.concentration_reported.gt(0)].sort_values('concentration_reported').prediction.to_numpy() for _,g in alt_groups.groupby(CURVE)])
    sensitivity=[]
    for scenario,prior in [('frozen_default_tissue',f),('unknown_tissue_zero_encoding',alt_f)]:
        offset=prior+np.mean(y[:,list(FIXED)]-prior[:,list(FIXED)],axis=1)[:,None]
        for method,p in [('frozen_rf',prior),('rf_offset',offset)]:
            temp=pd.DataFrame(long(method,p));s=summary_scores(temp,['method']);s['scenario']=scenario;sensitivity.append(s)
    save(out,'experiment8_tissue_sensitivity.csv',pd.concat(sensitivity))
    write_json(out/'experiment8_control_normalization.json',dict(controls=54,reported_control_values=[100.],
        maximum_raw_vs_control_normalized_change=0.,note='all report controls are 100%; renormalizing these aggregated values is identity and cannot recover missing well-level absorbance'))
    auc_rows=[]
    for method,p in base.items():
        if not np.isfinite(p).all():continue
        for q in range(54):
            for axis,log in [('log_positive',True),('linear_including_control',False)]:
                dose=DOSES if log else np.r_[0,DOSES];observed=y[q] if log else np.r_[100,y[q]]
                pred=p[q] if log else np.r_[100,p[q]]
                auc_rows.append(meta.iloc[q].to_dict() | dict(method=method,axis=axis,observed_nauc=n_auc(dose,observed,log),
                    reconstructed_nauc=n_auc(dose,pred,log),absolute_error_pp=100*abs(n_auc(dose,observed,log)-n_auc(dose,pred,log)),
                    control_note='0 dose retained as known 100% for linear reconstruction evaluation, not a scored positive query'))
    save(out,'experiment8_auc_axis_sensitivity.csv',auc_rows)
    assert digest(source/'paired_predictions.csv')==plan['source_sha256']
    write_json(out/'run_complete.json',dict(finished_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),experiments=list(range(1,9)),
        material_folds=9,curves=54,positive_concentrations=12,clipped_observations=0,original_frozen_model_sha256=digest(ROOT/'models/improved_434/baseline_random_forest.joblib')))
    print('All eight computational experiments completed.',flush=True)


if __name__=='__main__':main()
