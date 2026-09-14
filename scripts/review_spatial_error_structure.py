#!/usr/bin/env python3
"""Describe state/origin concentration in verified spatial comparisons; no fitting."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import review_monthly_spatial_results as spatial


def mean(values):
    values=list(values)
    return sum(values)/len(values)


def read_verified(folder):
    folder=Path(folder)
    summary=json.loads((folder/'review_summary.json').read_text())
    if summary.get('complete')!=324 or summary.get('complete_three_origin_configurations')!=54 or summary.get('scientific_acceptance') is not False:
        raise ValueError('Expected complete exploratory spatial review')
    with (folder/'paired_site_metrics_LOCAL.csv').open(newline='') as handle:
        rows=list(csv.DictReader(handle))
    expected=set()
    for t in spatial.matrix().values():
        for state in spatial.base.STATES:
            for year in range(t['cutoff']+1,t['cutoff']+4):
                for stream in range(5):
                    expected.add((t['pathogen'],t['cutoff'],t['temporal'],t['seasonal'],state,year,stream))
    seen=set()
    for r in rows:
        for k in ('cutoff','year','stream'):r[k]=spatial.base.integer(r[k])
        r['seasonal']=spatial.base.boolean(r['seasonal'])
        key=tuple(r[k] for k in ('pathogen','cutoff','temporal','seasonal','state','year','stream'))
        if key in seen:raise ValueError('Duplicate comparison cell')
        seen.add(key)
        for k in r:
            if k not in ('pathogen','cutoff','temporal','seasonal','state','year','stream'):
                r[k]=spatial.base.number(r[k])
        for mode in ('iid','bym2'):
            if r[mode+'_covered'] not in (0,1) or r[mode+'_width']<0 or r[mode+'_expected']<0:raise ValueError('Invalid predictive summary')
            if not math.isclose(r[mode+'_abs_error'],abs(r[mode+'_expected']-r['observed']),rel_tol=1e-9,abs_tol=1e-8):raise ValueError('Inconsistent prediction error')
        if r['observed']<0:raise ValueError('Negative observed count')
    if seen!=expected:raise ValueError('Incomplete state/origin/horizon/stream grid')
    return rows


def summarize(rows):
    pooled=[r for r in rows if r['stream']==0]
    output=dict(n_state_year_evaluations=len(pooled),score_gain=mean(r['score_gain'] for r in pooled))
    for mode in ('iid','bym2'):
        output[mode+'_coverage']=mean(r[mode+'_covered'] for r in pooled)
        output[mode+'_mean_width']=mean(r[mode+'_width'] for r in pooled)
        output[mode+'_mean_absolute_error']=mean(r[mode+'_abs_error'] for r in pooled)
        observed=sum(r['observed'] for r in pooled)
        output[mode+'_relative_bias']=(sum(r[mode+'_expected']-r['observed'] for r in pooled)/observed) if observed else ''
    stream_gains=[mean(r['score_gain'] for r in rows if r['stream']==s) for s in range(1,5)]
    output.update(stream_gain_min=min(stream_gains),stream_gain_max=max(stream_gains))
    return output


def tables(rows):
    groups={}
    for r in rows:groups.setdefault((r['pathogen'],r['temporal'],r['seasonal']),[]).append(r)
    grouped=[];sensitivity=[];concentration=[]
    for key,records in sorted(groups.items()):
        identity=dict(zip(('pathogen','temporal','seasonal'),key))
        overall=summarize(records)
        for dimension in ('state','cutoff','horizon'):
            value=lambda r:r['year']-r['cutoff'] if dimension=='horizon' else r[dimension]
            labels=sorted({value(r) for r in records})
            block=[]
            for label in labels:
                subset=[r for r in records if value(r)==label]
                result=dict(identity,dimension=dimension,value=label,**summarize(subset))
                grouped.append(result);block.append(result)
                omitted=summarize([r for r in records if value(r)!=label])
                sensitivity.append(dict(identity,dimension=dimension,omitted=label,full_score_gain=overall['score_gain'],remaining_score_gain=omitted['score_gain'],sign_changes=overall['score_gain']*omitted['score_gain']<0))
            total=sum(abs(r['score_gain']) for r in block)
            dominant=max(block,key=lambda r:abs(r['score_gain']))
            concentration.append(dict(identity,dimension=dimension,full_score_gain=overall['score_gain'],positive_blocks=sum(r['score_gain']>0 for r in block),blocks=len(block),largest_absolute_block=dominant['value'],largest_absolute_share=abs(dominant['score_gain'])/total if total else 0))
    return grouped,sensitivity,concentration


def review(source,out,plots=True):
    source=Path(source);out=Path(out)
    if out.exists():raise ValueError('Refusing existing review output')
    rows=read_verified(source);grouped,sensitivity,concentration=tables(rows)
    out.mkdir(parents=True)
    for name,data in [('geographic_origin_horizon_LOCAL.csv',grouped),('leave_one_block_out_LOCAL.csv',sensitivity),('gain_concentration_LOCAL.csv',concentration)]:
        spatial.base.write_csv(out/name,data)
    provenance=dict(source=str(source.resolve()),source_sha256={name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in ('review_summary.json','paired_site_metrics_LOCAL.csv')},level='state',county_residuals_available=False,independent_validation=False,model_changed=False,significance_tests_performed=False)
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    if plots:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        for pathogen in spatial.base.PATHOGENS:
            data=[r for r in grouped if r['pathogen']==pathogen and r['dimension']=='state']
            arms=sorted({(r['temporal'],r['seasonal']) for r in data});states=spatial.base.STATES
            lookup={(r['temporal'],r['seasonal'],r['value']):r['score_gain'] for r in data}
            values=[[lookup[(m,s,state)] for state in states] for m,s in arms]
            vmax=max(abs(v) for row in values for v in row) or 1e-9
            fig,ax=plt.subplots(figsize=(10,4));im=ax.imshow(values,cmap='RdBu',vmin=-vmax,vmax=vmax,aspect='auto')
            ax.set_xticks(range(len(states)));ax.set_xticklabels(states)
            ax.set_yticks(range(len(arms)));ax.set_yticklabels([m+(' + season' if s else '') for m,s in arms])
            ax.set_title(pathogen+': spatial minus IID score by state\nDevelopment data; color scale differs by pathogen')
            fig.colorbar(im,ax=ax,label='Mean predictive log-score difference');fig.tight_layout();fig.savefig(out/(pathogen+'_state_gains.png'),dpi=140);plt.close(fig)
    (out/'interpretation.md').write_text('''# Geographic error structure review — local

These summaries describe state-level forecast errors and score gains, not county
adjacency or residual spatial autocorrelation. County evidence is unavailable in
these portable summaries. Higher log-score differences favor spatial smoothing.
Scores average marginal county-month log scores within state; they are not
state-count predictive log densities. Each evaluation receives equal weight
within the reported means. Relative bias is instead a ratio of totals, weighted
by observed burden, not a mean of state-relative biases.
Errors and interval widths are counts, so comparisons across states also reflect
population and burden. Absolute-share concentration uses absolute block means;
it is not a fraction of net improvement when gains and losses cancel.

Leave-one-block-out summaries describe sensitivity of the existing results.
They are not refits, independent validation, confidence intervals or significance
tests. Forecast origins overlap in outcome years; posterior streams measure
Monte Carlo variation rather than new data. No model is selected by these tables.
''')
    return provenance


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source');parser.add_argument('--output',required=True);parser.add_argument('--no-plots',action='store_true');args=parser.parse_args()
    print(json.dumps(review(args.source,args.output,not args.no_plots),indent=2))
