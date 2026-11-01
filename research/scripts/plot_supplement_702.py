"""补充实验的定量比较、测点预算、固定案例和响应形态图。"""
import argparse
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

QA = Path('C:/Users/Sunny/.agents/skills/nature-skills/skills/nature-figure/scripts')
sys.path.insert(0,str(QA))
from audit_panel_alignment import require_matplotlib_panel_alignment

plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],
    'font.size':8,'axes.labelsize':8,'axes.titlesize':9,'xtick.labelsize':7,'ytick.labelsize':7,
    'legend.fontsize':7,'axes.spines.right':False,'axes.spines.top':False,'axes.linewidth':.7,
    'pdf.fonttype':42,'svg.fonttype':'none','legend.frameon':False})


def save(fig,path):
    require_matplotlib_panel_alignment(fig,json_out=str(path)+'.alignment.json',strict=True,tolerance_pt=1.5)
    fig.savefig(str(path)+'.pdf')
    fig.savefig(str(path)+'.svg')
    fig.savefig(str(path)+'.png',dpi=300)
    plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    out=parser.parse_args().directory.resolve();figures=out/'figures';figures.mkdir(exist_ok=True)
    read=lambda name:pd.read_csv(out/name)
    fixed=read('experiment1_predictions.csv');rng=np.random.default_rng(20261104)
    # 核心比较使用全部54曲线的432个检验条件，区间以9材料整组抽样。
    methods=['loglinear','pchip','natural_spline','akima','4pl','gp','rf_offset','frozen_rf']
    labels=['Log-linear','PCHIP','Natural cubic spline','Akima','4PL','Gaussian process','RF + offset','Frozen RF']
    summary=[]
    for method in methods:
        z=fixed.loc[fixed.method.eq(method)].copy();z['error']=abs(z.prediction-z.observed)
        v=z.groupby('nanoparticle').error.mean().to_numpy()
        low,high=np.quantile(v[rng.integers(0,9,(2000,9))].mean(axis=1),[.025,.975])
        summary.append((v.mean(),low,high))
    fig,ax=plt.subplots(figsize=(180/25.4,115/25.4));fig.subplots_adjust(left=.26,right=.96,bottom=.20,top=.89)
    for i,(center,low,high) in enumerate(summary):
        color='#0072B2' if methods[i] in ('loglinear','pchip') else '#666666'
        ax.errorbar(center,i,xerr=[[center-low],[high-center]],fmt='o',color=color,ecolor=color,markersize=4,capsize=2,linewidth=1)
    ax.set_yticks(range(len(methods)),labels);ax.invert_yaxis();ax.set_xlim(left=0)
    ax.set_xlabel('Held-out MAE (viability percentage points)');ax.set_title('Fixed four-anchor reconstruction')
    fig.text(.26,.055,'432 test conditions; 9 materials. Intervals: material bootstrap (95%).',fontsize=7)
    save(fig,figures/'method_comparison')

    budget=read('experiment3_predictions.csv');budget=budget.loc[budget.protocol.eq('nested_matched_queries')]
    fig,ax=plt.subplots(figsize=(180/25.4,105/25.4));fig.subplots_adjust(left=.16,right=.96,bottom=.23,top=.85)
    for method,label,color,marker in [('loglinear','Log-linear','#0072B2','o'),('pchip','PCHIP','#D55E00','s')]:
        center=[];lower=[];upper=[]
        for k in range(2,7):
            z=budget.loc[budget.method.eq(method)&budget.k.eq(k)].copy();z['error']=abs(z.prediction-z.observed)
            values=z.groupby('nanoparticle').error.mean().to_numpy()
            lo,hi=np.quantile(values[rng.integers(0,9,(2000,9))].mean(axis=1),[.025,.975])
            center.append(values.mean());lower.append(lo);upper.append(hi)
        ax.plot(range(2,7),center,color=color,marker=marker,markersize=4,label=label,linewidth=1.3)
        ax.fill_between(range(2,7),lower,upper,color=color,alpha=.12,linewidth=0)
    ax.set_xticks(range(2,7));ax.set_xlabel('Measured positive-dose anchors')
    ax.set_ylabel('Matched-query MAE\n(viability percentage points)');ax.set_ylim(bottom=0)
    fig.legend(loc='upper right',bbox_to_anchor=(.96,.98),ncol=2)
    fig.text(.16,.055,'Same 324 test conditions at every budget; bands: material bootstrap (95%).',fontsize=7)
    save(fig,figures/'budget_matched_queries')

    # 固定CS-SeNPs、72h作为示例，不按最佳误差选择；完整54曲线见数值源表。
    grid=read('experiment1_full_grid.csv');assert grid.concentration_reported.gt(0).all()
    example=grid.loc[grid.nanoparticle.eq('CS-SeNPs')&grid.time_h.eq(72)]
    fig,axes=plt.subplots(1,2,figsize=(180/25.4,100/25.4),sharey=True)
    fig.subplots_adjust(left=.10,right=.97,bottom=.29,top=.78,wspace=.30)
    for label,ax,cell in zip(('a','b'),axes,('HUVEC','H9C2')):
        z=example.loc[example.cell_type.eq(cell)]
        observed=z.loc[z.method.eq('loglinear')].sort_values('concentration_reported')
        xx=np.log10(observed.concentration_reported)
        ax.scatter(xx,observed.observed,s=12,color='#888888',zorder=4,label='Reported test values')
        a=observed.loc[observed.is_anchor]
        ax.scatter(np.log10(a.concentration_reported),a.observed,s=22,color='black',zorder=5,label='Measured anchors')
        for method,text,color,style in [('loglinear','Log-linear','#0072B2','-'),('pchip','PCHIP','#009E73','--'),('rf_offset','RF + offset','#D55E00',':')]:
            v=z.loc[z.method.eq(method)].sort_values('concentration_reported')
            ax.plot(np.log10(v.concentration_reported),v.prediction,color=color,linestyle=style,linewidth=1.1,label=text)
        ax.set_xticks(np.log10([.25,4,64,512]),['0.25','4','64','512']);ax.set_ylim(0,125)
        ax.set_xlabel('Concentration (umol/L Se)');ax.set_title(cell)
        ax.text(-.08,1.13,label,transform=ax.transAxes,fontweight='bold',fontsize=9)
    axes[0].set_ylabel('Reported viability (%)')
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',bbox_to_anchor=(.5,.085),ncol=3,fontsize=7)
    fig.suptitle('CS-SeNPs at 72 h: fixed illustration',y=.97,fontsize=9)
    fig.text(.10,.025,'Positive-dose grid only. All 54 curves contribute to the method comparison.',fontsize=7)
    save(fig,figures/'fixed_curve_examples')

    shapes=read('experiment7_curve_shapes.csv');load=read('experiment7_pca_loadings.csv').groupby('component').explained_variance_ratio.first()
    fig,ax=plt.subplots(figsize=(180/25.4,110/25.4));fig.subplots_adjust(left=.15,right=.96,bottom=.22,top=.90)
    for cell,color,marker in [('HUVEC','#0072B2','o'),('H9C2','#D55E00','s')]:
        z=shapes.loc[shapes.cell_type.eq(cell)];ax.scatter(z.PC1,z.PC2,s=20,color=color,marker=marker,alpha=.75,label=cell,edgecolors='none')
    ax.set_xlabel(f'Weighted PC1 ({load.loc[1]*100:.1f}% variance)');ax.set_ylabel(f'Weighted PC2 ({load.loc[2]*100:.1f}% variance)')
    ax.legend(loc='lower right');ax.set_title('Dose-response shape variation')
    fig.text(.15,.055,'54 curves from 9 materials. Discrete-grid weighted PCA; descriptive analysis.',fontsize=7)
    save(fig,figures/'weighted_response_pca')
    print('Four figures exported as PDF/SVG/PNG.')


if __name__=='__main__':main()
