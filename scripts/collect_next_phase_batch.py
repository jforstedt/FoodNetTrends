#!/usr/bin/env python3
import csv
import json
import math
import re
from pathlib import Path
import statistics
import sys
import tarfile
from run_next_phase_task import rows,sha,validate,prerequisite,execution_provenance,verify_checkpoints


def write(path,data):
    if data:
        with Path(path).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)


def numerical_log_flags(dest, task):
    path=Path(dest)/task['id']/'task.log'
    if not path.is_file():return 'LOG_UNAVAILABLE'
    log=path.read_text(errors='replace')
    aborted=len(re.findall(r"vb[.]correction[\x27\x22]?\s+is\s+aborted",log,re.I))
    return 'VB_CORRECTION_ABORTED:%s; SAVED_FIT_REVIEW_REQUIRED'%aborted if aborted else 'NO_VB_ABORT_DETECTED_NOT_A_CONVERGENCE_CERTIFICATE'


def spline_comparisons(dest, good):
    comparisons=[]
    sampling={(t['pathogen'],t['origin'],t['model']):t for t in good.values() if t['kind']=='sampling'}
    for task in good.values():
        if task['kind']!='spline':continue
        other=sampling.get((task['pathogen'],task['origin'],task['variant']+'_county_time'))
        if other is None:continue
        streams={}
        for r in rows(dest/other['id']/'result/seed_cells_INTERNAL.csv'):
            key=(r['fips'],r['state'],r['year'])
            streams.setdefault(key,[]).append(float(r['log_predictive_density']))
        candidate=rows(dest/task['id']/'result/heldout_cells_INTERNAL.csv')
        if set(streams)!={(r['fips'],r['state'],r['year']) for r in candidate}:raise ValueError('Spline/RW1 target mismatch')
        # Equal draw counts: pool predictive densities, never average their logarithms.
        pooled=0.0
        for values in streams.values():
            if len(values)!=4:raise ValueError('Missing pooled sampling stream')
            m=max(values);pooled+=m+math.log(sum(math.exp(x-m) for x in values)/len(values))
        spline=sum(float(r['log_predictive_density']) for r in candidate)
        comparisons.append(dict(pathogen=task['pathogen'],origin=task['origin'],variant=task['variant'],cells=len(candidate),
          spline_log_score=spline,rw1_pooled_log_score=pooled,spline_minus_rw1=spline-pooled,
          numerical_review=numerical_log_flags(dest,task),
          spline_95_coverage=sum(float(r['lower95'])<=float(r['observed'])<=float(r['upper95']) for r in candidate)/len(candidate),
          interpretation='Do not rank candidates flagged for aborted correction before saved-fit review. Exploratory point comparison; spline 4000 draws versus RW1 4 x 4000 pooled draws; distinct priors; assess Monte Carlo error and overlapping origins before interpretation'))
    return comparisons


def collect(dest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());results=[];good={};issues=[]
    checked={}
    def checked_sha(path):
        path=Path(path);st=path.stat();key=(str(path),st.st_size,st.st_mtime_ns,st.st_ctime_ns)
        if key not in checked:checked[key]=sha(path)
        return checked[key]
    for task in plan['tasks']:
        try:
            work=dest/task['id'];r=json.loads((work/'task_status.json').read_text())
            if r['status']=='COMPLETE':
                if not plan.get('verified'):raise ValueError('Unverified plan cannot claim completion')
                if r.get('exit_status')!=0:raise ValueError('Nonzero completion code')
                r.update(execution_provenance(dest,plan,task,r))
                r['checkpoint_integrity_verified']=verify_checkpoints(work,r)
                for dep in task.get('requires',[]):prerequisite(dest,plan,dep)
                for path,digest in dict(plan['fingerprints'],**task.get('inputs',{})).items():
                    if checked_sha(path)!=digest:raise ValueError('Changed source/input')
                validate(dest,task)
                if not r.get('outputs') or any(sha(work/p)!=h for p,h in r['outputs'].items()):raise ValueError('Output fingerprint mismatch')
                good[task['id']]=task
        except (OSError,ValueError,KeyError) as e:r=dict(status='MISSING_OR_INVALID',reason=str(e))
        results.append(dict(task=task['id'],kind=task['kind'],**{k:v for k,v in r.items() if k not in ('task','kind','outputs')}))
    paired={}
    for task in good.values():
        if task['kind']=='sampling':paired.setdefault((task['pathogen'],task['origin']),{})[task['model']]=task
    stability=[]
    for (pathogen,origin),models in paired.items():
        if set(models)!={'spatial_county_time','iid_county_time'}:continue
        try:
            values={}
            keys={}
            for model,task in models.items():
                scores=rows(dest/task['id']/'result/seed_state_year_scores.csv');values[model]={};keys[model]=set()
                for r in scores:
                    key=(r['seed'],r['state'],r['year'])
                    if key in keys[model]:raise ValueError('Duplicate seed-state-year')
                    keys[model].add(key);v=float(r['sum_log_predictive_density'])
                    if not math.isfinite(v):raise ValueError('Nonfinite score')
                    values[model][r['seed']]=values[model].get(r['seed'],0)+v
            if len(set(map(frozenset,keys.values())))!=1:raise ValueError('Unmatched sampling targets')
            differences=[values['spatial_county_time'][seed]-values['iid_county_time'][seed] for seed in sorted(values['spatial_county_time'])]
            stability.append(dict(pathogen=pathogen,origin=origin,streams=len(differences),mean_spatial_minus_iid=statistics.mean(differences),
              sd_stream_difference=statistics.stdev(differences),minimum=min(differences),maximum=max(differences),
              interpretation='Four Monte Carlo streams only; not uncertainty across future epidemics or independent forecast origins'))
        except (OSError,ValueError,KeyError) as e:issues.append(str(e))
    write(dest/'paired_sampling_stability_INTERNAL.csv',stability)
    try:write(dest/'spline_rw1_comparison_INTERNAL.csv',spline_comparisons(dest,good))
    except (OSError,ValueError,KeyError) as e:issues.append(str(e))
    summary=dict(tasks=results,collection_issues=issues,identity_verified=bool(results) and all(r.get('identity_verified',False) for r in results),
      provenance_status='LEGACY_IDENTITY_UNVERIFIED' if any(r.get('provenance_status')=='LEGACY_IDENTITY_UNVERIFIED' for r in results) else 'SEE_TASK_PROVENANCE',execution_complete=bool(results) and all(r['status']=='COMPLETE' for r in results) and not issues,
      scientific_status='REVIEW_REQUIRED',note='Experimental county spline candidate, saved posterior sampling and targeted definitions. No state replacement or automatic dashboard promotion.')
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as t:
        for p in sorted(dest.rglob('*')):
            if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.csv','.json','.txt','.log','.r','.py','.sh','.pdf'):
                t.add(str(p),arcname=str(p.relative_to(dest)),recursive=False)
    print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz')
    return 0 if summary['execution_complete'] and not issues else 1


if __name__=='__main__':sys.exit(collect(sys.argv[1]))
