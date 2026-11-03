"""从最终密度下的预测生成HUVEC论文表格、误差图与删失状态图。"""
import argparse
from pathlib import Path
import shutil
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, kendalltau

from run_huvec_external import digest, write_json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'results/external_702_20261101_confirmed'
OUTPUT = ROOT/'results/huvec_external_20261013_umol_se'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qa-scripts', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.qa_scripts))
    from audit_panel_alignment import require_matplotlib_panel_alignment
    data = pd.read_csv(SOURCE/'paired_predictions.csv', float_precision='round_trip').query("cell_type == 'HUVEC'")
    archived = pd.read_csv(OUTPUT/'model_predictions.csv', float_precision='round_trip')
    keys = ['nanoparticle','time_h','concentration_reported']
    paired = data.merge(archived[keys+['predicted_viability_percent']], on=keys, validate='one_to_one', suffixes=('','_archive'))
    assert len(paired) == 351 and paired.cells_per_well.eq(2300).all()
    np.testing.assert_allclose(paired.predicted_viability_percent, paired.predicted_viability_percent_archive, atol=1e-10, rtol=0)
    metrics = []
    for time, g in [*list(data.groupby('time_h')), ('ALL', data)]:
        y, p = g.viability_percent.to_numpy(), g.predicted_viability_percent.to_numpy()
        e = p-y
        metrics.append(dict(time_h=time,n=len(g),mae=float(abs(e).mean()),rmse=float(np.sqrt(np.mean(e**2))),
                            r2=float(1-np.sum(e**2)/np.sum((y-y.mean())**2)),bias=float(e.mean()),
                            observed_mean=float(y.mean()),predicted_mean=float(p.mean())))
    pd.DataFrame(metrics).to_csv(OUTPUT/'paired_metrics.csv', index=False, lineterminator='\n')
    high = data.query('time_h == 72 and concentration_reported == 512').copy()
    high['observed_rank'] = high.viability_percent.rank(method='average')
    high['predicted_rank'] = high.predicted_viability_percent.rank(method='average')
    rho = spearmanr(high.viability_percent, high.predicted_viability_percent)
    tau = kendalltau(high.viability_percent, high.predicted_viability_percent)
    high.to_csv(OUTPUT/'paired_rankings_72h_512.csv', index=False, lineterminator='\n')
    summary = dict(cells_per_well=2300, source_prediction_sha256=digest(SOURCE/'paired_predictions.csv'),
                   metrics=metrics, spearman_rho=float(rho.statistic),spearman_p=float(rho.pvalue),
                   kendall_tau=float(tau.statistic),kendall_p=float(tau.pvalue),
                   high_dose_prediction_range=[float(high.predicted_viability_percent.min()),float(high.predicted_viability_percent.max())])
    write_json(OUTPUT/'paired_evaluation.json', summary)
    lines = [r'\begin{tabular}{lrrrrr}',r'\toprule',r'时间 & 条件数 & MAE & RMSE & 实测均值 & 预测均值 \\',r'\midrule']
    for r in metrics:
        label = '总体' if r['time_h']=='ALL' else f"{r['time_h']} h"
        lines.append(f"{label} & {r['n']} & {r['mae']:.2f} & {r['rmse']:.2f} & {r['observed_mean']:.2f} & {r['predicted_mean']:.2f}"+r' \\')
    lines += [r'\bottomrule',r'\end{tabular}']
    for version in ('v2','v3'):
        (ROOT.parent/f'paper/{version}/tables/huvec-external-performance.tex').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    figures = OUTPUT/'figures'
    plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Microsoft YaHei','Arial','DejaVu Sans'],
        'font.size':8,'axes.labelsize':8,'axes.titlesize':9,'xtick.labelsize':7,'ytick.labelsize':7,
        'legend.fontsize':7,'axes.spines.right':False,'axes.spines.top':False,'pdf.fonttype':42,'svg.fonttype':'none'})

    def save(fig, name):
        path = figures/name
        require_matplotlib_panel_alignment(fig,json_out=str(path)+'.alignment.json',strict=True,
                                          exclude_axes=fig.axes[1:])
        fig.savefig(str(path)+'.pdf')
        fig.savefig(str(path)+'.svg')
        fig.savefig(str(path)+'.png',dpi=300)
        plt.close(fig)
        for version in ('v2','v3'):
            shutil.copy2(str(path)+'.png',ROOT.parent/f'paper/{version}/figures/{name}.png')

    fig, ax = plt.subplots(figsize=(180/25.4,140/25.4))
    fig.subplots_adjust(left=.13,right=.96,bottom=.16,top=.88)
    for (time,g),color in zip(data.groupby('time_h'),('#4C78A8','#E49B55','#669C82')):
        ax.scatter(g.viability_percent,g.predicted_viability_percent,s=12,alpha=.65,color=color,label=f'{time} h')
    upper = max(120, np.ceil(max(data.viability_percent.max(),data.predicted_viability_percent.max())/10)*10)
    ax.plot([0,upper],[0,upper],ls='--',lw=.8,color='#555555',label='一致性线')
    ax.set(xlim=(0,upper),ylim=(0,upper),xlabel='实验存活率（%）',ylabel='模型预测存活率（%）',title='HUVEC：351个条件的预测与实测')
    ax.legend(loc='upper left',frameon=False)
    save(fig,'scatter-viability')

    curves = pd.read_csv(SOURCE/'curve_metrics_54.csv').query("cell_type == 'HUVEC'")
    heat = curves.pivot(index='nanoparticle',columns='time_h',values='normalized_iae_log10')
    fig, ax = plt.subplots(figsize=(180/25.4,140/25.4))
    fig.subplots_adjust(left=.22,right=.84,bottom=.14,top=.88)
    im = ax.imshow(heat.to_numpy(),aspect='auto',cmap='YlOrRd')
    ax.set(xticks=range(3),xticklabels=['24 h','48 h','72 h'],yticks=range(9),yticklabels=heat.index,
           xlabel='暴露时间',title='HUVEC：正浓度log10轴归一化曲线误差')
    for i in range(9):
        for j in range(3):
            value=heat.iloc[i,j]
            ax.text(j,i,f'{value:.2f}',ha='center',va='center',fontsize=7,color='white' if im.norm(value)>.62 else '#222222')
    cax=fig.add_axes([.88,.14,.025,.74])
    fig.colorbar(im,cax=cax,label='归一化IAE（存活率百分点）')
    save(fig,'iae-heatmap')

    fig, ax = plt.subplots(figsize=(180/25.4,155/25.4))
    fig.subplots_adjust(left=.13,right=.96,bottom=.13,top=.88)
    for r in high.itertuples():
        ax.plot([0,1],[r.observed_rank,r.predicted_rank],color='#8BA5BC',alpha=.75,lw=1)
        ax.scatter([0,1],[r.observed_rank,r.predicted_rank],s=16,color='#4C78A8')
        ax.text(-.035,r.observed_rank,r.nanoparticle,ha='right',va='center',fontsize=7)
        ax.text(1.035,r.predicted_rank,r.nanoparticle,ha='left',va='center',fontsize=7)
    ax.set(xlim=(-.5,1.5),ylim=(9.5,.5),xticks=[0,1],xticklabels=['实验排序','预测排序'],yticks=range(1,10),
           ylabel='毒性排名（1表示存活率最低）',title='HUVEC：72 h、512 μM Se 的材料排序')
    save(fig,'rank-consistency')

    ic=pd.read_csv(SOURCE/'ic50_pairs.csv').query("cell_type == 'HUVEC'").sort_values(['nanoparticle','time_h']).reset_index(drop=True)
    assert len(ic)==27 and ic.status_model.eq('not_reached').all()
    fig, ax = plt.subplots(figsize=(180/25.4,175/25.4))
    fig.subplots_adjust(left=.28,right=.95,bottom=.18,top=.91)
    finite=ic.status_experimental.eq('interpolated')
    positions=np.arange(27)
    ax.scatter(ic.loc[finite,'ic50_reported_scale_experimental'],positions[finite]-.13,s=16,color='#4C78A8',label='实验：可插值IC50')
    ax.scatter(np.full((~finite).sum(),512),positions[~finite]-.13,s=25,marker='>',color='#4C78A8',label='实验：>512 μM')
    ax.scatter(np.full(27,512),positions+.13,s=25,marker='>',color='#D18A4E',label='模型：>512 μM（全部27条）')
    ax.set_xscale('log',base=2)
    ax.set(xlim=(1,850),ylim=(26.7,-.7),yticks=positions,yticklabels=[f'{r.nanoparticle}  {r.time_h} h' for r in ic.itertuples()],
           xticks=[1,4,16,64,256,512],xticklabels=['1','4','16','64','256','512'],xlabel='浓度（μM Se）；右向三角表示超过测试上限',
           title='HUVEC：IC50阈值与右删失状态')
    ax.tick_params(axis='y',labelsize=6.5)
    ax.legend(loc='upper center',bbox_to_anchor=(.45,-.11),frameon=False,ncol=1)
    save(fig,'ic50-pairing')
    print(pd.DataFrame(metrics).to_string(index=False))
    print('Rank correlation:',rho.statistic,tau.statistic)


if __name__=='__main__':
    main()
