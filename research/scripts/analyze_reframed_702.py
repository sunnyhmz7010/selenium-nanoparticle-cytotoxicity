"""固定范围的双细胞外部评价、归一化AUC和4点校准/8点检验模拟。"""
import argparse
from datetime import datetime
import importlib.metadata
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, kendalltau

from run_huvec_external import digest, write_json

ROOT = Path(__file__).resolve().parents[1]
CURVE = ['nanoparticle', 'cell_type', 'time_h']
KEYS = CURVE + ['concentration_reported']
ANCHORS = (0.25, 4., 64., 512.)
TEST_DOSES = (0.5, 1., 2., 8., 16., 32., 128., 256.)
METHODS = {
    'frozen_rf': 'predicted_viability_percent',
    'rf_offset_4pt': 'offset_prediction',
    'anchor_log_interpolation': 'anchor_interpolation_prediction',
}
COMPARISONS = (
    ('rf_offset_4pt', 'frozen_rf'),
    ('anchor_log_interpolation', 'frozen_rf'),
    ('rf_offset_4pt', 'anchor_log_interpolation'),
)


def save(output, name, frame):
    frame.to_csv(output / name, index=False, encoding='utf-8', lineterminator='\n')


def metrics(y, p):
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    e = p-y
    denominator = np.sum((y-y.mean())**2)
    return dict(n=len(y), mae=float(np.mean(abs(e))), rmse=float(np.sqrt(np.mean(e**2))),
                r2=float(1-np.sum(e**2)/denominator), bias=float(e.mean()))


def n_auc(doses, viability, log_axis):
    x, y = np.asarray(doses, float), np.asarray(viability, float)/100
    if log_axis:
        mask = x > 0
        x, y = np.log10(x[mask]), y[mask]
    return float(np.trapezoid(y, x)/(x[-1]-x[0]))


def fit_offset(anchors):
    # 只读四个锚点响应；检验点的实测值不参与任何拟合或选点。
    assert len(anchors) == 4 and set(anchors.concentration_reported) == set(ANCHORS)
    return float(np.mean(anchors.viability_percent-anchors.predicted_viability_percent))


def absolute_linear_integral(x, residual):
    total = 0.
    for width, a, b in zip(np.diff(x), residual[:-1], residual[1:]):
        total += width * ((a*a+b*b)/(2*(abs(a)+abs(b))) if a*b < 0 else (abs(a)+abs(b))/2)
    return float(total)


def material_bootstrap(frame, value_columns, rng, resamples):
    materials = sorted(frame.nanoparticle.unique())
    assert len(materials) == 9
    blocks = [frame.loc[frame.nanoparticle.eq(m)] for m in materials]
    count = {len(block) for block in blocks}
    assert len(count) == 1
    y = np.stack([b.viability_percent.to_numpy(float) for b in blocks])
    predictions = {name: np.stack([b[column].to_numpy(float) for b in blocks]) for name, column in value_columns.items()}
    indices = rng.integers(0, len(materials), (resamples, len(materials)))
    by = y[indices].reshape(resamples, -1)
    total = np.sum((by-by.mean(axis=1, keepdims=True))**2, axis=1)
    bootstrap = {}
    for name, p in predictions.items():
        errors = p[indices].reshape(resamples, -1)-by
        bootstrap[name] = dict(mae=np.mean(abs(errors), axis=1),
                               rmse=np.sqrt(np.mean(errors**2, axis=1)),
                               r2=1-np.sum(errors**2, axis=1)/total)
    return bootstrap


def grouped_views(frame):
    yield 'ALL', 'ALL', frame
    for cell, group in frame.groupby('cell_type'):
        yield cell, 'ALL', group
    for (cell, time), group in frame.groupby(['cell_type', 'time_h']):
        yield cell, time, group


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-directory', type=Path, default=ROOT/'results/external_702_20261101_confirmed')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bootstrap-resamples', type=int, default=2000)
    args = parser.parse_args()
    source, out = args.source_directory.resolve(), args.output.resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('输出目录必须为空，避免覆盖分析记录')
    out.mkdir(parents=True, exist_ok=True)
    source_manifest = json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    for name, checksum in source_manifest.items():
        assert digest(source/name) == checksum, name
    table = ROOT.parent/'paper/revision/improvement-recommendations-status.md'
    shutil.copyfile(table, out/'experiment_status_before_scope_change.md')
    plan = dict(recorded_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                scope='9 materials x 2 experimental cell systems x 3 times x 13 concentrations; existing 702 records only',
                scope_change_after_viewing_data=True, prior_responses_already_available=True,
                primary_auc='trapezoidal mean viability fraction over log10 positive doses 0.25..512 umol/L Se',
                secondary_auc='trapezoidal mean viability fraction over linear doses 0..512 umol/L Se',
                calibration_points=list(ANCHORS), test_points=list(TEST_DOSES),
                control_dose=0, control_usage='reported separately; excluded from calibration and eight-point test metrics',
                calibration='one unweighted mean observed-minus-frozen-predicted offset per material-cell-time curve',
                comparison='same eight test doses, frozen RF vs RF+offset vs four-anchor-only log10 interpolation',
                test_outcomes_used_to_fit=False, dose_or_method_search='none; fixed from user-approved plan before this new computation',
                endpoint_coverage='concentration interpolation only; includes lowest and highest dose as calibration anchors',
                calibration_is_not_new_material_or_new_time_generalization=True,
                no_clipping_no_monotonic_adjustment=True, no_retraining=True,
                bootstrap=dict(resamples=args.bootstrap_resamples, seed=20261102, unit='material, retaining both cells/all times/test doses'),
                source_directory=str(source), source_manifest_sha256=digest(source/'manifest.json'),
                source_prediction_sha256=digest(source/'paired_predictions.csv'), script_sha256=digest(Path(__file__)),
                removed_from_scope=['24-dose wet experiments','additional chemical characterization','new prospective blinded experiments',
                                    '4+20 few-shot','mechanistic causality','new model training on 702 records'],
                software={p:importlib.metadata.version(p) for p in ('numpy','pandas','scipy')})
    write_json(out/'analysis_plan.json', plan)
    data = pd.read_csv(source/'paired_predictions.csv', float_precision='round_trip')
    assert len(data) == 702 and not data.duplicated(KEYS).any()
    auc_records, offsets, anchors_all, tests_all, curve_scores = [], [], [], [], []
    for key, group in data.groupby(CURVE):
        group = group.sort_values('concentration_reported')
        identity = dict(zip(CURVE, key))
        assert len(group) == 13
        auc = identity.copy()
        for axis, log_axis in [('log10_positive', True), ('linear_including_control', False)]:
            observed = n_auc(group.concentration_reported, group.viability_percent, log_axis)
            predicted = n_auc(group.concentration_reported, group.predicted_viability_percent, log_axis)
            auc.update({f'observed_nauc_{axis}':observed, f'predicted_nauc_{axis}':predicted,
                        f'nauc_error_pp_{axis}':100*(predicted-observed)})
        auc_records.append(auc)
        anchors = group.loc[group.concentration_reported.isin(ANCHORS)].copy()
        test = group.loc[group.concentration_reported.isin(TEST_DOSES)].copy()
        assert len(anchors) == 4 and len(test) == 8
        shift = fit_offset(anchors)
        offsets.append(identity | dict(offset_pp=shift, calibration_points=4, test_points=8))
        anchors['anchor_observed_minus_prediction'] = anchors.viability_percent-anchors.predicted_viability_percent
        anchors_all.append(anchors)
        test['offset_prediction'] = test.predicted_viability_percent+shift
        test['anchor_interpolation_prediction'] = np.interp(np.log10(test.concentration_reported),
                                                           np.log10(anchors.concentration_reported), anchors.viability_percent)
        tests_all.append(test)
        for method, column in METHODS.items():
            errors = test[column].to_numpy()-test.viability_percent.to_numpy()
            log_doses = np.log10(test.concentration_reported.to_numpy())
            curve_scores.append(identity | dict(method=method, **metrics(test.viability_percent, test[column]),
                test_niae_log10=absolute_linear_integral(log_doses, errors)/(log_doses[-1]-log_doses[0])))
    auc = pd.DataFrame(auc_records)
    heldout = pd.concat(tests_all).reset_index(drop=True)
    assert len(heldout) == 432 and len(auc) == 54
    save(out, 'auc_curve_values_54.csv', auc)
    save(out, 'calibration_offsets_54.csv', pd.DataFrame(offsets))
    save(out, 'calibration_anchors_216.csv', pd.concat(anchors_all))
    save(out, 'heldout_predictions_432.csv', heldout)
    save(out, 'heldout_curve_metrics_162.csv', pd.DataFrame(curve_scores))
    save(out, 'controls_54.csv', data.loc[data.concentration_reported.eq(0)])
    rng = np.random.default_rng(plan['bootstrap']['seed'])
    fewshot_metrics, deltas = [], []
    for cell, time, group in grouped_views(heldout):
        bootstrap = material_bootstrap(group, METHODS, rng, args.bootstrap_resamples)
        for method, column in METHODS.items():
            record = dict(cell_type=cell, time_h=time, method=method, **metrics(group.viability_percent, group[column]))
            for metric in ('mae','rmse','r2'):
                record[metric+'_ci_low'], record[metric+'_ci_high'] = np.quantile(bootstrap[method][metric], [.025,.975])
            fewshot_metrics.append(record)
        for target, reference in COMPARISONS:
            change = bootstrap[target]['mae']-bootstrap[reference]['mae']
            low, high = np.quantile(change, [.025,.975])
            target_mae = np.mean(abs(group[METHODS[target]]-group.viability_percent))
            ref_mae = np.mean(abs(group[METHODS[reference]]-group.viability_percent))
            deltas.append(dict(cell_type=cell,time_h=time,target=target,reference=reference,
                               paired_test_conditions=len(group),materials=9,mae_delta=float(target_mae-ref_mae),
                               relative_mae_reduction=float((ref_mae-target_mae)/ref_mae),
                               material_bootstrap_ci_low=float(low),material_bootstrap_ci_high=float(high),
                               interval_entirely_below_zero=bool(high<0)))
    fewshot_metrics = pd.DataFrame(fewshot_metrics)
    deltas = pd.DataFrame(deltas)
    save(out, 'fewshot_metrics.csv', fewshot_metrics)
    save(out, 'paired_mae_comparisons.csv', deltas)
    auc_metrics, auc_descriptive, auc_rankings = [], [], []
    for cell,time,group in grouped_views(auc):
        for axis in ('log10_positive', 'linear_including_control'):
            y = group['observed_nauc_'+axis]*100
            p = group['predicted_nauc_'+axis]*100
            auc_metrics.append(dict(cell_type=cell,time_h=time,axis=axis,**metrics(y,p)))
            auc_descriptive.append(dict(cell_type=cell,time_h=time,axis=axis,curves=len(group),
                observed_mean=float(y.mean()/100),observed_min=float(y.min()/100),observed_max=float(y.max()/100),
                predicted_mean=float(p.mean()/100)))
            if time != 'ALL':
                auc_rankings.append(dict(cell_type=cell,time_h=time,axis=axis,n_materials=9,
                    spearman_rho=float(spearmanr(y,p).statistic),kendall_tau_b=float(kendalltau(y,p).statistic)))
    save(out, 'auc_prediction_metrics.csv', pd.DataFrame(auc_metrics))
    save(out, 'auc_descriptive_summary.csv', pd.DataFrame(auc_descriptive))
    save(out, 'auc_ranking_agreement.csv', pd.DataFrame(auc_rankings))
    assert digest(source/'manifest.json') == plan['source_manifest_sha256']
    assert digest(source/'paired_predictions.csv') == plan['source_prediction_sha256']
    write_json(out/'summary.json',dict(auc_log10_primary=pd.DataFrame(auc_metrics).query("axis == 'log10_positive' and time_h == 'ALL'").to_dict('records'),
        fewshot_all_times=fewshot_metrics.loc[fewshot_metrics.time_h.eq('ALL')].to_dict('records'),
        paired_changes_all_times=deltas.loc[deltas.time_h.eq('ALL')].to_dict('records'),
        curves_improved_vs_frozen=int((pd.DataFrame(curve_scores).pivot(index=CURVE,columns='method',values='mae').rf_offset_4pt <
                                       pd.DataFrame(curve_scores).pivot(index=CURVE,columns='method',values='mae').frozen_rf).sum())))
    print(fewshot_metrics.loc[fewshot_metrics.time_h.eq('ALL'),['cell_type','method','n','mae','rmse','r2']].to_string(index=False))
    print(deltas.loc[deltas.time_h.eq('ALL')].to_string(index=False))
    print(pd.DataFrame(auc_metrics).query("axis == 'log10_positive' and time_h == 'ALL'").to_string(index=False))


if __name__ == '__main__':
    main()
