#!/usr/bin/env python3
"""Review verified spatial comparisons and optional targeted recovery, without fitting."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import review_monthly_factorial as base
from review_broader_combinations import Archive


def matrix():
 result={}
 for p in base.PATHOGENS:
  for c in ((2011,2013,2014) if p=='CRYPTOSPORIDIUM' else (2011,2013,2016)):
   for m in ('rw1','ar1','spline'):
    for s in (False,True):
     for spatial in ('iid','bym2'):
      name='{}_{}_{}_{}'.format(p,c,m,'seasonal' if s else 'nonseasonal')+('_bym2' if spatial=='bym2' else '')
      result[name]=dict(pathogen=p,cutoff=c,temporal=m,seasonal=s,spatial=spatial,reused=spatial=='iid',end_year=2017 if p=='CRYPTOSPORIDIUM' else 2019)
 return result


def csvrows(archive,name):return list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8-sig'))))
def assert_hash(archive,name,digest):
 if hashlib.sha256(archive.read(name)).hexdigest()!=digest:raise ValueError('Changed bound file: '+name)


def validate_settings(archive,t,prefix):
 settings=csvrows(archive,prefix+'/settings.csv')
 if len(settings)!=1:raise ValueError('Missing unique settings')
 r=settings[0]
 for k,v in dict(cutoff=t['cutoff'],streams=4,draws_per_stream=2000).items():
  if base.integer(r[k])!=v:raise ValueError('Changed sampler setting: '+k)
 for k,v in dict(seasonal=t['seasonal'],coverage_certified=False,refitted=False).items():
  if base.boolean(r[k])!=v:raise ValueError('Changed sampler flag: '+k)
 if 'seed' in t and base.integer(r['base_seed'])!=t['seed']:raise ValueError('Changed posterior seed')
 if prefix+'/rng_protocol.csv' in archive.files:raise ValueError('Mixed posterior RNG protocols')
 if t['spatial']=='bym2':
  rows=csvrows(archive,prefix+'/sensitivity_settings.csv')
  if len(rows)!=1:raise ValueError('Missing spatial settings')
  row=rows[0]
  for k,v in dict(temporal_model=t['temporal'],comparison='monthly_spatial_factorial_v1',spatial='bym2').items():
   if row[k]!=v:raise ValueError('Changed model identity')
  for k,v in dict(end_year=t['end_year'],rate_center=.0002,sd_upper=1,sd_tail=.01,phi_u=.5,phi_probability=.5,n_counties=486,n_components=10,n_edges=1210).items():
   if base.number(row[k])!=v:raise ValueError('Changed spatial specification: '+k)
  if base.boolean(row['seasonal'])!=t['seasonal'] or base.boolean(row['coverage_certified']):raise ValueError('Changed spatial flag')


def add_recovery(path,original,plan,summary,scores,tails):
 recovery=Archive(path,'report_sha256.json')
 try:
  rp=recovery.json('plan.json');rs=recovery.json('summary.json')
  if rp.get('version')!='monthly_spatial_recovery_v1' or rp.get('model_changed') is not False or rp.get('quality_gate_relaxed') is not False:raise ValueError('Unrecognized recovery protocol')
  if rp['source_plan_sha256']!=hashlib.sha256(original.read('plan.json')).hexdigest():raise ValueError('Recovery source differs')
  names={'LISTERIA_2011_ar1_seasonal_bym2','SHIGELLA_2011_ar1_seasonal_bym2'}
  if len(rp['tasks'])!=2 or {t['id'] for t in rp['tasks']}!=names or len(rs['tasks'])!=2 or {t['task'] for t in rs['tasks']}!=names or rs.get('issues'):raise ValueError('Invalid recovery scope/summary')
  roots=[p.rsplit('/scripts/',1)[0] for p in rp['inputs'] if p.endswith('/scripts/recover_monthly_spatial.py')]
  if len(roots)!=1:raise ValueError('Unknown recovery snapshot')
  for absolute,digest in rp['inputs'].items():
   for root,archive in ((roots[0],recovery),(rp['source'],original)):
    if absolute.startswith(root+'/'):
     name=absolute[len(root)+1:]
     if name in archive.files:assert_hash(archive,name,digest)
     elif root==roots[0] or Path(name).suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh','.md') and '_INTERNAL' not in Path(name).name:raise ValueError('Missing frozen recovery input')
  added=[]
  for record in rs['tasks']:
   if record['status']!='COMPLETE':continue
   name=record['task'];t=next(t for t in rp['tasks'] if t['id']==name);old=next(t for t in plan['tasks'] if t['id']==name)
   if any(t.get(k)!=old.get(k) for k in ('pathogen','cutoff','temporal','seasonal','spatial','seed','end_year','inputs')):raise ValueError('Recovery task differs')
   previous=next(x for x in summary['tasks'] if x['task']==name)
   if previous['status']=='COMPLETE':raise ValueError('Recovery would replace a successful fit')
   done=recovery.json(name+'/task_status.json')
   if done.get('task')!=name or done.get('status')!='COMPLETE' or done.get('exit_status')!=0 or done.get('plan_sha256')!=hashlib.sha256(recovery.read('plan.json')).hexdigest():raise ValueError('Invalid recovered completion')
   if not done.get('outputs'):raise ValueError('Unbound recovered outputs')
   for local,digest in done['outputs'].items():
    if '_INTERNAL' in Path(local).name:continue
    assert_hash(recovery,name+'/'+local,digest)
   ref=next(x for x in plan['references'] if all(x[k]==t[k] for k in ('pathogen','cutoff','temporal','seasonal')))
   if done['truth_sha256']!=ref['reference']['truth_sha256']:raise ValueError('Recovery truth differs')
   required={'result/status.txt','result/settings.csv','result/sensitivity_settings.csv','result/stream_scores.csv','result/aggregate_tails.csv','recovery_numerics.csv'}
   if not required.issubset(done['outputs']):raise ValueError('Required recovery output not bound')
   if recovery.read(name+'/result/status.txt').decode().strip()!='SAVED_MONTHLY_DIAGNOSTICS_COMPLETE':raise ValueError('Recovered diagnostic status differs')
   validate_settings(recovery,t,name+'/result')
   numerics=csvrows(recovery,name+'/recovery_numerics.csv')
   if len(numerics)!=1 or not base.boolean(numerics[0]['fit_ok']) or base.integer(numerics[0]['mode_status'])!=0 or base.boolean(numerics[0]['quality_gate_relaxed']) or numerics[0]['fitting_threads']!='1:1' or numerics[0]['recovery']!='single_thread_same_model':raise ValueError('Failed recovery numerical gate')
   for file,destination,states in (('stream_scores.csv',scores,base.STATES),('aggregate_tails.csv',tails,base.STATES+('ALL',))):
    data=csvrows(recovery,name+'/result/'+file);seen=set()
    for r in data:
     for k in ('year','stream','draws'):r[k]=base.integer(r[k])
     key=(r['state'],r['year'],r['stream'])
     if key in seen or r['draws']!=(8000 if r['stream']==0 else 2000):raise ValueError('Recovered metric identity/draws differ')
     seen.add(key)
     for k in r:
      if k not in ('state','year','stream','draws'):r[k]=base.number(r[k])
     validate_metric(r,file=='aggregate_tails.csv')
     destination.append(dict(task=name,pathogen=t['pathogen'],cutoff=t['cutoff'],temporal=t['temporal'],seasonal=t['seasonal'],spatial=t['spatial'],reused=False,**r))
    if seen!={(s,y,k) for s in states for y in range(t['cutoff']+1,t['cutoff']+4) for k in range(5)}:raise ValueError('Incomplete recovered domain')
   added.append(name)
  return added
 finally:recovery.close()


def validate_metric(r,tail):
 if tail:
  fields=('observed','mean_expected','median_expected','p975_expected','max_expected','top_one_percent_mean_share','lower95','median_predictive','upper95','prob_above_twice_observed')
  if any(base.number(r[k])<0 for k in fields):raise ValueError('Negative tail value')
  if r['observed']!=int(r['observed']) or not r['lower95']<=r['median_predictive']<=r['upper95'] or not r['median_expected']<=r['p975_expected']<=r['max_expected']:raise ValueError('Invalid tail order/count')
  if any(r[k]>1 for k in ('top_one_percent_mean_share','prob_above_twice_observed')):raise ValueError('Invalid probability/share')
 else:
  if base.number(r['mean_log_score'])>1e-12 or base.number(r['max_cell_density_relative_mcse'])<0:raise ValueError('Invalid score/MCSE')


def paired(scores,tails):
 ix={};tx={}
 def key(r):return (r['pathogen'],int(r['cutoff']),r['temporal'],base.boolean(r['seasonal']),r['state'],int(r['year']),int(r['stream']))
 for r in scores:
  k=key(r)+(r['spatial'],)
  if k in ix:raise ValueError('Duplicate score cell')
  ix[k]=r
 for r in tails:
  k=key(r)+(r['spatial'],)
  if k in tx:raise ValueError('Duplicate tail cell')
  tx[k]=r
 result=[]
 for k in sorted({k[:-1] for k in ix}):
  if not all(k+(mode,) in ix for mode in ('iid','bym2')):continue
  a,b=(tx[k+(mode,)] for mode in ('iid','bym2'))
  if a['observed']!=b['observed']:raise ValueError('Observed paired outcome differs')
  observed=a['observed']
  result.append(dict(zip(('pathogen','cutoff','temporal','seasonal','state','year','stream'),k),
   score_gain=ix[k+('bym2',)]['mean_log_score']-ix[k+('iid',)]['mean_log_score'],
   iid_covered=int(a['lower95']<=observed<=a['upper95']),bym2_covered=int(b['lower95']<=observed<=b['upper95']),
   iid_width=a['upper95']-a['lower95'],bym2_width=b['upper95']-b['lower95'],
   observed=observed,iid_expected=a['mean_expected'],bym2_expected=b['mean_expected'],
   iid_abs_error=abs(a['mean_expected']-observed),bym2_abs_error=abs(b['mean_expected']-observed),
   iid_tail_share=a['top_one_percent_mean_share'],bym2_tail_share=b['top_one_percent_mean_share']))
 return result


def summaries(rows):
 grouped={}
 for r in rows:grouped.setdefault((r['pathogen'],r['temporal'],r['seasonal']),[]).append(r)
 result=[]
 for (p,m,s),rs in sorted(grouped.items()):
  pooled=[r for r in rs if r['stream']==0];origins={r['cutoff'] for r in pooled}
  expected={(c,state,y,stream) for c in origins for state in base.STATES for y in range(c+1,c+4) for stream in range(5)}
  actual=[(r['cutoff'],r['state'],r['year'],r['stream']) for r in rs]
  allowed={2011,2013,2014} if p=='CRYPTOSPORIDIUM' else {2011,2013,2016}
  if not origins or not origins.issubset(allowed) or len(actual)!=len(expected) or set(actual)!=expected:raise ValueError('Incomplete paired state/year/stream block')
  avg=lambda field:sum(r[field] for r in pooled)/len(pooled)
  stream_gains=[sum(r['score_gain'] for r in rs if r['stream']==i)/sum(r['stream']==i for r in rs) for i in range(1,5)]
  row=dict(pathogen=p,temporal=m,seasonal=s,origins=len(origins),complete_three_origins=len(origins)==3,
    score_gain=avg('score_gain'),stream_gain_min=min(stream_gains),stream_gain_max=max(stream_gains),
    iid_coverage=avg('iid_covered'),bym2_coverage=avg('bym2_covered'),coverage_change=avg('bym2_covered')-avg('iid_covered'),
    iid_mean_width=avg('iid_width'),bym2_mean_width=avg('bym2_width'),absolute_error_change=avg('bym2_abs_error')-avg('iid_abs_error'),
    iid_max_tail_share=max(r['iid_tail_share'] for r in pooled),bym2_max_tail_share=max(r['bym2_tail_share'] for r in pooled))
  total=sum(r['observed'] for r in pooled)
  for mode in ('iid','bym2'):row[mode+'_relative_bias']=(sum(r[mode+'_expected'] for r in pooled)-total)/total if total else ''
  result.append(row)
 return result


def review(bundle,recovery,out,plots=True):
 out=Path(out)
 if out.exists():raise ValueError('Refusing existing review directory')
 outer=Archive(bundle,'archive_sha256.json')
 try:
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'spatial.tar.gz';path.write_bytes(outer.read('spatial.tar.gz'));report=base.Report(path)
   try:
    protocol=dict(version='monthly_spatial_factorial_v1',launcher='launch_monthly_spatial_factorial.py',matrix=matrix,counts=(324,162,162))
    plan,summary,scores,tails,invalid,issues,complete=base.validate(report,protocol)
    if invalid or issues:raise ValueError('Invalid paired truth or collector integrity issues')
    for t in plan['tasks']+plan['references']:
     if next(r for r in summary['tasks'] if r['task']==t['id'])['status']=='COMPLETE':
      validate_settings(report,t,('references/'+t['id']) if t['reused'] else t['id']+'/result')
    expected_matrix=matrix()
    for data in (scores,tails):
     for r in data:
      if r['spatial']!=expected_matrix[r['task']]['spatial']:raise ValueError('Merged spatial identity differs')
    original_pairs=paired(scores,tails)
    pub=report.rows('spatial_site_contrasts.csv')
    keys=lambda r:(r['pathogen'],int(r['cutoff']),r['temporal'],base.boolean(r['seasonal']),r['state'],int(r['year']),int(r['stream']))
    expected={keys(r):r['score_gain'] for r in original_pairs}
    if len(pub)!=len(expected) or {keys(r) for r in pub}!=set(expected):raise ValueError('Published pair domain differs')
    if any(not math.isclose(float(r['bym2_minus_iid']),expected[keys(r)],rel_tol=1e-10,abs_tol=1e-10) for r in pub):raise ValueError('Published pair values differ')
    added=add_recovery(recovery,report,plan,summary,scores,tails) if recovery else []
   finally:report.close()
 finally:outer.close()
 data=paired(scores,tails);aggregate=summaries(data);out.mkdir(parents=True)
 base.write_csv(out/'paired_site_metrics_LOCAL.csv',data);base.write_csv(out/'spatial_tradeoffs_LOCAL.csv',aggregate)
 result=dict(original_complete=complete,recovered=added,complete=complete+len(added),expected=324,original_paired_score_rows_verified=len(original_pairs),complete_three_origin_configurations=sum(r['complete_three_origins'] for r in aggregate),expected_configurations=54,scientific_acceptance=False,independent_validation=False)
 (out/'review_summary.json').write_text(json.dumps(result,indent=2)+'\n')
 if plots:
  import matplotlib;matplotlib.use('Agg')
  import matplotlib.pyplot as plt
  for pathogen in base.PATHOGENS:
   rs=[r for r in aggregate if r['pathogen']==pathogen];fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
   labels=[r['temporal'].upper()+(' + season' if r['seasonal'] else '')+(' *' if not r['complete_three_origins'] else '') for r in rs]
   for ax,field,title in zip(axes,('score_gain','coverage_change','absolute_error_change'),('Predictive log score gain\nHigher favors spatial','Coverage change\nCheck alongside interval width','Absolute error change\nLower favors spatial')):
    ax.barh(labels,[r[field] for r in rs]);ax.axvline(0,color='black',linewidth=.7);ax.set_title(title)
   fig.suptitle(pathogen+' — BYM2 minus IID; * incomplete origins; exploratory')
   fig.savefig(str(out/(pathogen+'_spatial_tradeoffs.png')),dpi=150);plt.close(fig)
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('bundle');p.add_argument('--recovery');p.add_argument('--output',required=True);p.add_argument('--no-plots',action='store_true');a=p.parse_args()
 print(json.dumps(review(a.bundle,a.recovery,a.output,not a.no_plots),indent=2))
