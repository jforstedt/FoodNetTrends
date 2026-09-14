#!/usr/bin/env python3
"""Validate portable conditional-classification reports and paired component contrasts."""
import argparse
import csv
import hashlib
import io
import itertools
import json
import math
import re
from pathlib import Path
import tempfile
import launch_monthly_classification_models as model
from review_broader_combinations import Archive


def rows(archive,name):return list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8-sig'))))
def digest(data):return hashlib.sha256(data).hexdigest()
def bound(archive,name,expected):
    if digest(archive.read(name))!=expected:raise ValueError('Changed bound artifact: '+name)
def write_csv(path,data):
    if not data:return
    with path.open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(data[0]),lineterminator='\n');writer.writeheader();writer.writerows(data)
def mean(values):
    values=[v for v in values if v is not None]
    return sum(values)/len(values) if values else None


def validate_rng(archive,prefix):
    data=rows(archive,prefix+'/rng_protocol.csv')
    if len(data)!=1:raise ValueError('Missing unique RNG record')
    expected=dict(protocol='explicit_config_v2',config_offset='20000',predictive_offset='10000',stream_spacing='50000',R_version='4.5.2',INLA_version='26.8.7',RNG_kind='Mersenne-Twister;Inversion;Rejection')
    if any(data[0].get(k)!=v for k,v in expected.items()):raise ValueError('Changed RNG/software protocol')


def contrasts(scores):
    fields=('pathogen','cutoff','level','spatial','temporal','seasonal','state','year','stream')
    lookup={tuple(r[k] for k in fields):r for r in scores}
    if len(lookup)!=len(scores):raise ValueError('Duplicate score key')
    result=[]
    for r in scores:
        changes=[]
        if r['seasonal']:changes.append(('seasonal_minus_nonseasonal',dict(seasonal=False)))
        if r['temporal']=='ar1':changes.append(('ar1_minus_rw1',dict(temporal='rw1')))
        if r['spatial']=='bym2':changes.append(('bym2_minus_iid',dict(spatial='iid')))
        for label,change in changes:
            comparator=dict(r,**change);key=tuple(comparator[k] for k in fields)
            if key not in lookup:raise ValueError('Missing paired comparator')
            other=lookup[key]
            if r['eligible_cells']!=other['eligible_cells']:raise ValueError('Paired scoring support differs')
            if (r['mean_log_score'] is None)!=(other['mean_log_score'] is None):raise ValueError('Paired missing scores differ')
            gain=None if r['mean_log_score'] is None else r['mean_log_score']-other['mean_log_score']
            result.append(dict({k:r[k] for k in fields[:6]},contrast=label,state=r['state'],year=r['year'],stream=r['stream'],eligible_cells=r['eligible_cells'],score_gain=gain))
    return result


def interactions(scores):
    groups={}
    for r in scores:groups.setdefault(tuple(r[k] for k in ('pathogen','cutoff','level','state','year','stream')),[]).append(r)
    result=[]
    for key,data in groups.items():
        lookup={(r['spatial'],r['temporal'],r['seasonal']):r for r in data}
        if len(lookup)!=len(data):raise ValueError('Duplicate interaction cell')
        level=key[2];spaces=('none',) if level=='site' else ('iid','bym2')
        if set(lookup)!=set(itertools.product(spaces,('rw1','ar1'),(False,True))):raise ValueError('Incomplete interaction grid')
        specs=[('temporal_x_seasonality',dict(spatial=space)) for space in spaces]
        if level=='county':specs += [('spatial_x_seasonality',dict(temporal=t)) for t in ('rw1','ar1')]+[('spatial_x_temporal',dict(seasonal=s)) for s in (False,True)]+[('spatial_x_temporal_x_seasonality',{})]
        for label,fixed in specs:
            selected=[r for r in data if all(r[k]==v for k,v in fixed.items())]
            if len({r['eligible_cells'] for r in selected})!=1:raise ValueError('Interaction support differs')
            missing=[r['mean_log_score'] is None for r in selected]
            if any(missing) and not all(missing):raise ValueError('Interaction missingness differs')
            value=None
            if not all(missing):
                value=0
                for r in selected:
                    sign=1
                    for field,upper in (('spatial','bym2'),('temporal','ar1'),('seasonal',True)):
                        if field not in fixed and not(field=='spatial' and level=='site'):sign*=1 if r[field]==upper else -1
                    value+=sign*r['mean_log_score']
            result.append(dict(zip(('pathogen','cutoff','level','state','year','stream'),key),interaction=label,fixed_spatial=fixed.get('spatial',''),fixed_temporal=fixed.get('temporal',''),fixed_seasonal=fixed.get('seasonal',''),eligible_cells=selected[0]['eligible_cells'],score_interaction=value))
    return result


def plot_shares(out,source,aggregates):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(6,2,figsize=(12,19),sharex=True,sharey=True)
    for i,pathogen in enumerate(model.prep.PATHOGENS):
        annual={}
        for r in rows(source,pathogen+'/result/classification_site.csv'):
            year=int(r['year'])
            if 2012<=year<=2019:
                n,y=annual.get(year,(0,0));annual[year]=(n+int(r['classification_denominator']),y+int(r['cidt_classified']))
        for j,cutoff in enumerate((2015,2016)):
            ax=axes[i,j];years=sorted(annual);ax.plot(years,[annual[y][1]/annual[y][0] if annual[y][0] else float('nan') for y in years],color='black',marker='o',label='Observed share')
            for temporal,color in (('rw1','tab:blue'),('ar1','tab:orange')):
                data=sorted([r for r in aggregates if r['pathogen']==pathogen and r['cutoff']==cutoff and r['level']=='site' and r['temporal']==temporal and not r['seasonal'] and r['stream']==0 and r['state']=='ALL'],key=lambda r:r['year'])
                x=[r['year'] for r in data];ax.plot(x,[r['mean_expected']/r['denominator'] for r in data],color=color,label=temporal.upper())
                ax.fill_between(x,[r['lower95']/r['denominator'] for r in data],[r['upper95']/r['denominator'] for r in data],color=color,alpha=.16)
            ax.axvline(cutoff+.5,color='gray',linestyle=':');ax.set_title(pathogen+' | origin '+str(cutoff));ax.set_ylim(0,1)
            if j==0:ax.set_ylabel('CIDT / (CX + CIDT)')
    axes[0,0].legend(fontsize=8);fig.suptitle('Conditional classification shares: matched nonseasonal site models\nBands: annual 95% predictive intervals; future denominators observed; development data',fontsize=12)
    fig.tight_layout(rect=(0,0,1,.96));fig.savefig(out/'site_classification_trajectories_LOCAL.png',dpi=130);plt.close(fig)


def review(archive_path,source_bundle,out):
    out=Path(out)
    if out.exists():raise ValueError('Refusing existing output')
    arc=Archive(archive_path,'report_sha256.json');outer=Archive(source_bundle,'archive_sha256.json');source=Archive(outer.read('classification.tar.gz'),'report_sha256.json')
    try:
        plan=arc.json('plan.json');summary=arc.json('summary.json');expected=model.matrix()
        if plan.get('version')!=model.VERSION or plan.get('verified') is not True or plan.get('tasks') is None or len(plan['tasks'])!=144:raise ValueError('Unknown model plan')
        for k in ('incidence_adjustment','scientific_acceptance','coverage_certified','independent_validation'):
            if plan.get(k) is not False:raise ValueError('Changed target/status flag')
        if plan.get('conditional_future_denominator') is not True:raise ValueError('Changed conditioning')
        if any(summary.get(k) is not False for k in ('incidence_adjustment','scientific_acceptance','independent_validation','compare_raw_scores_across_resolutions')):raise ValueError('Changed result interpretation flags')
        if summary.get('issues') or summary.get('complete')!=144 or summary.get('execution_complete') is not True or len(summary.get('tasks',[]))!=144 or {r['task'] for r in summary['tasks'] if r['status']=='COMPLETE'}!={r['id'] for r in expected}:raise ValueError('Incomplete classification experiment')
        for actual,wanted in zip(plan['tasks'],expected):
            if any(actual.get(k)!=v for k,v in wanted.items()):raise ValueError('Changed task matrix or seed')
        roots=[p.rsplit('/scripts/',1)[0] for p in plan['inputs'] if p.endswith('/scripts/launch_monthly_classification_models.py')]
        if len(roots)!=1:raise ValueError('Unknown model snapshot root')
        root=roots[0];source_root=plan['source'];source_plan=source.json('plan.json');binding_count=0
        if plan.get('source_provenance')!=source_plan['inputs']:raise ValueError('Historical source lineage differs')
        for mapping in [plan['inputs']]+[t['inputs'] for t in plan['tasks']]:
            for absolute,h in mapping.items():
                for prefix,archive in ((root,arc),(source_root,source)):
                    if absolute.startswith(prefix+'/'):
                        local=absolute[len(prefix)+1:]
                        if local in archive.files:bound(archive,local,h);binding_count+=1
                        elif '_INTERNAL' not in Path(local).name:raise ValueError('Missing bound portable input: '+local)
        bound(source,'plan.json',plan['inputs'][source_root+'/plan.json'])
        prior=arc.json('prior_checks/manifest.json')
        if prior.get('status')!='PRIOR_CHECK_PASS' or prior.get('version')!='monthly_classification_priors_v1':raise ValueError('Unverified prior calibration')
        required_prior={'scripts/monthly_classification_model.R','scripts/check_monthly_classification_priors.R','scripts/monthly_spatial_combination.R','analysis_configs/county_pilot/counties.csv','analysis_configs/county_pilot/edges.csv'}
        if not required_prior.issubset(prior.get('sources',{})) or prior.get('outcome_data_used') is not False:raise ValueError('Incomplete prior provenance')
        if not {'prior_trajectories.csv','prior_parameters.csv','prior_check_settings.csv','status.txt'}.issubset(prior.get('files',{})):raise ValueError('Incomplete prior reports')
        for name,h in prior['sources'].items():bound(arc,'scripts/'+Path(name).name if name.startswith('scripts/') else 'geography/'+Path(name).name,h)
        for name,h in prior['files'].items():bound(arc,'prior_checks/'+name,h)
        scores=[];aggregates=[];warnings=[];history=[]
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td)
            for t in plan['tasks']:
                name=t['id'];record=arc.json(name+'/task_status.json')
                prepared=source.json(t['pathogen']+'/task_status.json')
                if prepared.get('status')!='COMPLETE' or prepared.get('plan_sha256')!=digest(source.read('plan.json')):raise ValueError('Unverified source preparation')
                for local,h in prepared['outputs'].items():
                    if t['inputs'].get(source_root+'/'+t['pathogen']+'/'+local)!=h:raise ValueError('Prepared output identity differs, including recorded private input')
                if record.get('task')!=name or record.get('status')!='COMPLETE' or record.get('exit_status')!=0 or record.get('plan_sha256')!=digest(arc.read('plan.json')):raise ValueError('Unverified fit record')
                required={'result/fit_INTERNAL.rds','result/status.txt','result/settings.csv','result/fit_diagnostics.csv','result/aggregate_predictions.csv','result/stream_scores.csv','result/rng_protocol.csv','result/input_checksums.csv'}
                if not required.issubset(record.get('outputs',{})):raise ValueError('Missing bound result')
                for local,h in record['outputs'].items():
                    model.inside(temp,local)
                    if '_INTERNAL' not in Path(local).name and name+'/'+local in arc.files:bound(arc,name+'/'+local,h)
                    elif '_INTERNAL' not in Path(local).name:raise ValueError('Missing recorded portable output')
                prefix=name+'/result';work=temp/name;(work/'result').mkdir(parents=True)
                for filename in ('status.txt','settings.csv','fit_diagnostics.csv','aggregate_predictions.csv','stream_scores.csv','rng_protocol.csv','input_checksums.csv'):(work/'result'/filename).write_bytes(arc.read(prefix+'/'+filename))
                reference=t['pathogen']+'/result/classification_site.csv';site=temp/(t['pathogen']+'_site.csv');site.write_bytes(source.read(reference))
                if t['site_reference']!=source_root+'/'+reference:raise ValueError('Changed site reference')
                model.validate(work,dict(t,site_reference=str(site)),require_internal=False)
                validate_rng(arc,prefix)
                checks=rows(arc,prefix+'/input_checksums.csv');panel=source_root+'/'+t['pathogen']+'/result/'+('classification_site.csv' if t['level']=='site' else 'classification_county_month_INTERNAL.rds')
                if len(checks)!=3 or {c['file'] for c in checks}!={panel,root+'/geography/counties.csv',root+'/geography/edges.csv'}:raise ValueError('Changed runtime input identity')
                for c in checks:
                    if c['file'].startswith(root+'/'):raw=arc.read(c['file'][len(root)+1:])
                    elif t['level']=='site' and c['file']==panel:raw=source.read(reference)
                    else:continue
                    if hashlib.md5(raw).hexdigest()!=c['md5']:raise ValueError('Runtime checksum differs')
                warning=arc.read(prefix+'/fit_warnings.txt').decode().strip()
                if warning:warnings.append(dict(task=name,warning=warning))
                log=arc.read(name+'/task.log').decode(errors='replace')
                events=dict(segmentation_fault=bool(re.search('segmentation fault|segfault',log,re.I)),internal_retry=bool(re.search('inla[.]core[.]safe|will rerun',log,re.I)),variational_abort=bool(re.search(r'vb[.]correction[^\n]*aborted',log,re.I)))
                if events['variational_abort'] or re.search(r'vb[.]correction[^\n]*aborted',warning,re.I):raise ValueError('Aborted variational correction: '+name)
                if any(events.values()):history.append(dict(task=name,final_fit_passed=True,**events))
                identity={k:t[k] for k in ('pathogen','cutoff','level','spatial','temporal','seasonal')}
                for r in rows(arc,prefix+'/stream_scores.csv'):
                    for k in ('year','stream','draws','eligible_cells'):r[k]=int(r[k])
                    for k in ('mean_log_score','max_cell_density_relative_mcse'):r[k]=None if r[k] in ('','NA') else float(r[k])
                    scores.append(dict(identity,task=name,**r))
                for r in rows(arc,prefix+'/aggregate_predictions.csv'):
                    for k in ('year','stream','draws','eligible_cells','observed','denominator'):r[k]=int(r[k])
                    for k in ('mean_expected','median_expected','lower95','median_predictive','upper95'):r[k]=float(r[k])
                    n=r['denominator'];r.update(covered=int(r['lower95']<=r['observed']<=r['upper95']),interval_width=r['upper95']-r['lower95'],absolute_error=abs(r['mean_expected']-r['observed']),share_error=(r['mean_expected']-r['observed'])/n if n else None,share_width=(r['upper95']-r['lower95'])/n if n else None)
                    aggregates.append(dict(identity,task=name,**r))
        pairs=contrasts(scores);interaction_rows=interactions(scores);out.mkdir(parents=True)
        for name,data in [('scores_LOCAL.csv',scores),('aggregate_calibration_LOCAL.csv',aggregates),('component_contrasts_LOCAL.csv',pairs),('factorial_interactions_LOCAL.csv',interaction_rows),('warnings_LOCAL.csv',warnings),('numerical_history_LOCAL.csv',history)]:write_csv(out/name,data)
        plot_shares(out,source,aggregates)
        result=dict(complete=144,archive_files=len(arc.files),portable_binding_checks=binding_count,score_rows=len(scores),aggregate_rows=len(aggregates),component_contrast_rows=len(pairs),interaction_rows=len(interaction_rows),warning_tasks=len(warnings),numerical_history_tasks=len(history),private_fit_objects_reverified=False,county_internal_panels_reverified=False,source_archive=str(source_bundle),archive_sha256=digest(Path(archive_path).read_bytes()),source_archive_sha256=digest(Path(source_bundle).read_bytes()),incidence_adjustment=False,scientific_acceptance=False,independent_validation=False)
        (out/'review_summary.json').write_text(json.dumps(result,indent=2)+'\n');return result
    finally:arc.close();source.close();outer.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive');p.add_argument('--source-bundle',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(review(a.archive,a.source_bundle,a.output),indent=2))
