#!/usr/bin/env python3
"""Descriptive saved BYM2 forecast-error geography; no model fitting or sampling."""
import argparse
import csv
import math
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import launch_monthly_spatial_factorial as spatial
sha=spatial.s.f.sha
SOURCE='broader_combinations_20260914_130328_942214'
RECOVERY='monthly_spatial_recovery_20260914_151100_451135'
RESTART='shigella_numerical_restart_20260914_160320_966808'

def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def stat(p):
 s=Path(p).stat();return dict(size=s.st_size,mtime_ns=s.st_mtime_ns)
def check(bindings):spatial.s.f.check_hashes(bindings)
def archive(dest):
 files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and '_INTERNAL' not in p.name and p.suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh','.md') and p.name!='report_sha256.json']
 write(dest/'report_sha256.json',{str(p.relative_to(dest)):sha(p) for p in files})
 with tarfile.open(str(dest)+'.tar.gz','w:gz') as tar:
  for p in files+[dest/'report_sha256.json']:tar.add(str(p),arcname=str(p.relative_to(dest)))
 print('Archive: '+str(dest)+'.tar.gz',flush=True)
def verify(dest,plan,digest):
 if sha(dest/'plan.json')!=digest or plan.get('version')!='spatial_saved_residual_audit_v1' or plan.get('new_fits')!=0 or plan.get('posterior_resampling') is not False or len(plan.get('tasks',[]))!=162:raise ValueError('Unverified residual audit plan')
 check(plan['snapshots'])
 if stat(plan['container'])!=plan['container_stat']:raise ValueError('Prepared container snapshot changed')
def merge_bindings(*maps):
 result={}
 for mapping in maps:
  for path,digest in mapping.items():
   if path in result and result[path]!=digest:raise ValueError('Conflicting frozen hash for '+path)
   result[path]=digest
 return result
def bind_saved_outputs(work,record):
 if not record.get('outputs'):raise ValueError('Unbound source outputs')
 bound={}
 for local,h in record['outputs'].items():
  if Path(local).is_absolute() or '..' in Path(local).parts or '\\' in local:raise ValueError('Unsafe source output path')
  bound[str(work/local)]=h
  if '_INTERNAL' not in Path(local).name and Path(local).suffix.lower() in ('.csv','.json','.txt','.log') and sha(work/local)!=h:raise ValueError('Changed portable source output')
 return bound
def verify_graph_snapshot(dest,old,origin):
 for name in ('counties.csv','edges.csv','provenance.json'):
  if old['inputs'].get(str(origin/'graph'/name))!=sha(dest/'graph'/name):raise ValueError('Graph differs from frozen original')
def bootstrap(root,dest):
 dest.mkdir(parents=True,exist_ok=False);(dest/'scripts').mkdir();(dest/'graph').mkdir()
 names=set(spatial.FILES)|{'launch_spatial_residual_audit.py','audit_spatial_residuals.R'}
 for n in names:
  frozen=root/'output'/SOURCE/'spatial/scripts'/n;source=frozen if frozen.is_file() and n not in ('launch_spatial_residual_audit.py','audit_spatial_residuals.R') else root/'scripts'/n
  shutil.copyfile(str(source),str(dest/'scripts'/n))
 for n in ('counties.csv','edges.csv','provenance.json'):shutil.copyfile(str(root/'analysis_configs/county_pilot'/n),str(dest/'graph'/n))
 bindings={str(p):sha(p) for folder in ('scripts','graph') for p in (dest/folder).iterdir() if p.is_file()}
 write(dest/'bootstrap.json',dict(root=str(root),snapshots=bindings))
 cmd='python3 '+shlex.quote(str(dest/'scripts/launch_spatial_residual_audit.py'))+' --prepare '+shlex.quote(str(dest))+' --digest '+sha(dest/'bootstrap.json')
 (dest/'prepare.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+cmd+'\n')
def prepare(dest,digest):
 if not digest or sha(dest/'bootstrap.json')!=digest:raise ValueError('Bootstrap manifest changed')
 print('PREP: verifying frozen original spatial provenance',flush=True)
 b=json.loads((dest/'bootstrap.json').read_text());check(b['snapshots']);root=Path(b['root'])
 origin=root/'output'/SOURCE;origin=origin/'spatial';old=json.loads((origin/'plan.json').read_text());digest=sha(origin/'plan.json')
 if old.get('version')!='monthly_spatial_factorial_v1' or old.get('verified') is not True or len(old.get('tasks',[]))!=162 or len(old.get('references',[]))!=162 or {t['id'] for t in old['tasks']}!={t['id'] for t in spatial.matrix()}:raise ValueError('Invalid original spatial protocol')
 verify_graph_snapshot(dest,old,origin)
 summary=json.loads((origin/'summary.json').read_text())
 if summary.get('issues') or summary.get('complete')!=322:raise ValueError('Original spatial batch differs')
 recovery=root/'output'/RECOVERY;restart=root/'output'/RESTART
 rp=json.loads((recovery/'plan.json').read_text());sp=json.loads((restart/'plan.json').read_text())
 if rp.get('source_plan_sha256')!=digest or sp.get('source_plan_sha256')!=digest or sp.get('successful_recovery')!=str(recovery) or sp.get('version')!='shigella_numerical_restart_v1' or rp.get('version')!='monthly_spatial_recovery_v1':raise ValueError('Recovery lineage differs')
 print('PREP: verifying both targeted recovery input sets',flush=True)
 for p in (rp,sp):
  if p.get('model_changed') is not False or p.get('quality_gate_relaxed') is not False:raise ValueError('Recovery modified model/gate')
 maps=[old['inputs'],old['provenance'],rp['inputs'],sp['inputs']]+[t['inputs'] for t in old['tasks']]+[t['reference']['inputs'] for t in old['references']]
 historical=merge_bindings(*maps)
 print('PREP: validating portable consumed metadata; ancestral raw/control payload hashes preserved without re-reading',flush=True)
 for path,digest in b['snapshots'].items():
  name=Path(path).name;original=str(origin/'scripts'/name)
  if '/scripts/' in path and name not in ('launch_spatial_residual_audit.py','audit_spatial_residuals.R') and old['inputs'].get(original)!=digest:raise ValueError('Validation source differs from original snapshot')
 manifests={str(folder):json.loads((folder/'report_sha256.json').read_text()) for folder in (origin,recovery,restart)}
 for folder in (origin,recovery,restart):
  for name in ('plan.json','summary.json'):
   if manifests[str(folder)].get(name)!=sha(folder/name):raise ValueError('Changed source metadata')
 for local in ('plan.json','summary.json'):
  if sp['inputs'].get(str(recovery/local))!=sha(recovery/local):raise ValueError('Restart prior recovery binding differs')
 print('PREP: freezing and hashing container snapshot',flush=True)
 container=root/'foodnet-inla-fixed.sif';saved_container=dest/'runtime.sif';shutil.copyfile(str(container),str(saved_container));container_sha=sha(saved_container)
 if old['inputs'].get(str(container))!=container_sha:raise ValueError('Container differs from frozen original')
 saved_container.chmod(0o444)
 evidence=dest/'source_evidence';evidence.mkdir();snapshots=dict(b['snapshots'])
 for label,folder in (('original',origin),('recovery',recovery),('restart',restart)):
  for name in ('plan.json','summary.json','report_sha256.json'):
   out=evidence/(label+'_'+name);shutil.copyfile(str(folder/name),str(out));snapshots[str(out)]=sha(out)
 tasks=[]
 for t in old['tasks']:
  if t['id']=='LISTERIA_2011_ar1_seasonal_bym2':source=recovery;sourceplan=rp
  elif t['id']=='SHIGELLA_2011_ar1_seasonal_bym2':source=restart;sourceplan=sp
  else:source=origin;sourceplan=old
  candidate=next(x for x in sourceplan['tasks'] if x['id']==t['id'])
  if any(candidate.get(k)!=t.get(k) for k in ('pathogen','cutoff','temporal','seasonal','spatial','seed','end_year','inputs')):raise ValueError('Selected saved model changed')
  work=source/t['id'];r=json.loads((work/'task_status.json').read_text())
  if r.get('status')!='COMPLETE' or r.get('exit_status')!=0 or r.get('task')!=t['id'] or r.get('plan_sha256')!=sha(source/'plan.json'):raise ValueError('Unverified completed source')
  truth=spatial.validate(work,t)
  if truth!=r.get('truth_sha256'):raise ValueError('Saved truth differs')
  if manifests[str(source)].get(t['id']+'/task_status.json')!=sha(work/'task_status.json'):raise ValueError('Source completion record differs from manifest')
  bound=bind_saved_outputs(work,r)
  evidence_record=evidence/(t['id']+'_task_status.json');shutil.copyfile(str(work/'task_status.json'),str(evidence_record));snapshots[str(evidence_record)]=sha(evidence_record)
  paths=[work/'fit_INTERNAL.rds',work/'heldout_truth_INTERNAL.csv']
  if any(str(p) not in bound for p in paths):raise ValueError('Missing bound saved fit/truth')
  task=dict(id=t['id'],pathogen=t['pathogen'],cutoff=t['cutoff'],temporal=t['temporal'],seasonal=t['seasonal'],inputs={str(p):bound[str(p)] for p in paths})
  task['inputs'][str(work/'task_status.json')]=sha(work/'task_status.json');task['source_plan_sha256']=sha(source/'plan.json')
  task['command']=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1','--bind','/scicomp',str(saved_container),'Rscript','--vanilla',str(dest/'scripts/audit_spatial_residuals.R')]+[str(p) for p in paths]+[str(dest/'graph/counties.csv'),str(dest/'graph/edges.csv'),str(t['cutoff']),t['temporal'],'TRUE' if t['seasonal'] else 'FALSE',str(dest/t['id']/'result')]
  tasks.append(task)
  print('Bound saved fit '+t['id']+'; fit payload verification deferred to worker',flush=True)
 if len(tasks)!=162 or {t['id'] for t in tasks}!={t['id'] for t in spatial.matrix()}:raise ValueError('Unexpected residual task matrix')
 plan=dict(version='spatial_saved_residual_audit_v1',tasks=tasks,snapshots=snapshots,container=str(saved_container),container_sha256=container_sha,container_stat=stat(saved_container),new_fits=0,posterior_resampling=False,county_iid_control=False,scientific_acceptance=False,historical_inputs=historical,historical_verification='HISTORICAL_NOT_REHASHED',prepared_fit_content_verified=False,worker_fit_content_verification=True,fit_payload_verification='EACH_SELECTED_WORKER_BEFORE_AND_AFTER')
 write(dest/'plan.json',plan);digest=sha(dest/'plan.json');cmd='python3 '+shlex.quote(str(dest/'scripts/launch_spatial_residual_audit.py'));q=shlex.quote
 (dest/'run.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+cmd+' --worker '+q(str(dest))+' --index "${SGE_TASK_ID:?}" --digest '+digest+'\n')
 (dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+cmd+' --collect '+q(str(dest))+' --digest '+digest+'\n')
 return plan

def validate_result(work,task):
 def rows(name):
  with (work/'result'/name).open() as handle:return list(csv.DictReader(handle))
 def number(value):
  x=float(value)
  if not math.isfinite(x):raise ValueError('Nonfinite residual report value')
  return x
 settings=rows('settings.csv')
 if len(settings)!=1:raise ValueError('Missing residual settings')
 s=settings[0]
 for k,v in dict(cutoff=str(task['cutoff']),temporal=task['temporal'],seasonal='TRUE' if task['seasonal'] else 'FALSE',spatial='bym2',new_fit='FALSE',posterior_resampling='FALSE',period='heldout_forecast_only',expected_source='saved_INLA_marginal_fitted_mean_count_scale',residual='log1p_observed_minus_log1p_expected',graph_counties='486',graph_components='10',significance_test='FALSE',scientific_acceptance='FALSE').items():
  if s.get(k)!=v:raise ValueError('Changed residual setting '+k)
 states={'CA','CO','CT','GA','MD','MN','NM','NY','OR','TN','ALL'};years=set(range(task['cutoff']+1,task['cutoff']+4))
 annual=rows('state_year_residuals.csv');monthly=rows('monthly_global_residuals.csv')
 if len(annual)!=33 or {(r['state'],int(r['year'])) for r in annual}!={(state,year) for state in states for year in years}:raise ValueError('Incomplete residual state/year domain')
 if len(monthly)!=36 or {(int(r['year']),int(r['month'])) for r in monthly}!={(year,month) for year in years for month in range(1,13)}:raise ValueError('Incomplete residual month domain')
 for r in annual:
  for k in ('counties','edges','observed','expected','lag_pairs'):
   x=number(r[k])
   if x<0 or (k!='expected' and x!=int(x)):raise ValueError('Invalid residual count/index')
  if not 0<=number(r['fraction_counties_underpredicted'])<=1:raise ValueError('Invalid underprediction fraction')
  if r['within_county_centered_month_lag1'] and abs(number(r['within_county_centered_month_lag1']))>1+1e-12:raise ValueError('Invalid temporal correlation')
  if r['posterior_uncertainty_included']!='FALSE':raise ValueError('Residual uncertainty claim differs')
 for r in annual+monthly:
  if r['significance_test']!='FALSE':raise ValueError('Unrequested significance test')
  for k in ('log1p_residual_moran','within_state_centered_moran'):
   if r[k]:number(r[k]) # Moran has graph-dependent bounds, not necessarily [-1,1].
 if any(number(r['counties'])!=486 for r in monthly):raise ValueError('Monthly graph count differs')
 for year in years:
  allrow=next(r for r in annual if r['state']=='ALL' and int(r['year'])==year);parts=[r for r in annual if r['state']!='ALL' and int(r['year'])==year]
  if number(allrow['counties'])!=486:raise ValueError('Annual graph count differs')
  for field in ('counties','observed','expected','lag_pairs'):
   if not math.isclose(number(allrow[field]),sum(number(r[field]) for r in parts),rel_tol=1e-10,abs_tol=1e-8):raise ValueError('ALL and state residual totals differ')
 if (work/'result/status.txt').read_text().strip()!='SPATIAL_SAVED_RESIDUAL_AUDIT_COMPLETE':raise ValueError('Residual status differs')
 return True
def worker(dest,index,digest):
 p=json.loads((dest/'plan.json').read_text());t=p['tasks'][index-1];work=dest/t['id'];work.mkdir(exist_ok=False);r=dict(task=t['id'],status='FAILED',exit_status=1,plan_sha256=digest)
 try:
  verify(dest,p,digest);check(t['inputs'])
  with (work/'task.log').open('w') as log:code=subprocess.call(t['command'],stdout=log,stderr=subprocess.STDOUT)
  if code or (work/'result/status.txt').read_text().strip()!='SPATIAL_SAVED_RESIDUAL_AUDIT_COMPLETE':raise ValueError('Residual audit failed')
  validate_result(work,t);check(t['inputs']);verify(dest,p,digest)
  r.update(status='COMPLETE',exit_status=0,outputs={str(x.relative_to(work)):sha(x) for x in work.rglob('*') if x.is_file()})
 except (OSError,ValueError,KeyError) as e:r['reason']=str(e)
 write(work/'task_status.json',r);return r['exit_status']
def collect(dest,digest):
 p=json.loads((dest/'plan.json').read_text());issues=[];records=[]
 try:
  verify(dest,p,digest)
  if sha(p['container'])!=p['container_sha256']:raise ValueError('Container snapshot hash changed')
 except (OSError,ValueError,KeyError) as e:issues.append(str(e))
 for t in p['tasks']:
  row=dict(task=t['id'],status='FAILED_OR_MISSING')
  try:
   if issues:raise ValueError('Global integrity check failed')
   work=dest/t['id'];r=json.loads((work/'task_status.json').read_text())
   if r.get('task')!=t['id'] or r.get('status')!='COMPLETE' or r.get('exit_status')!=0 or r.get('plan_sha256')!=digest:raise ValueError('Incomplete residual audit')
   for local,h in r['outputs'].items():
    if Path(local).is_absolute() or '..' in Path(local).parts or '\\' in local or (work/local).is_symlink():raise ValueError('Unsafe residual output path')
    if sha(work/local)!=h:raise ValueError('Changed residual output')
   if not {'result/state_year_residuals.csv','result/monthly_global_residuals.csv','result/settings.csv','result/status.txt'}.issubset(r['outputs']):raise ValueError('Missing residual report')
   validate_result(work,t)
   row['status']='COMPLETE'
  except (OSError,ValueError,KeyError) as e:row['reason']=str(e)
  records.append(row)
 complete=sum(r['status']=='COMPLETE' for r in records);summary=dict(tasks=records,issues=issues,complete=complete,expected=162,new_fits=0,posterior_resampling=False,county_iid_control=False,scientific_acceptance=False)
 write(dest/'summary.json',summary);archive(dest);return 0 if complete==162 and not issues else 1

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare');p.add_argument('--worker');p.add_argument('--collect');p.add_argument('--index',type=int);p.add_argument('--digest');a=p.parse_args();base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y']
 if a.worker:
  if not a.index or not 1<=a.index<=162 or not a.digest:p.error('Valid task index/digest required')
  return worker(Path(a.worker),a.index,a.digest)
 if a.collect:return collect(Path(a.collect),a.digest)
 if a.prepare:
  dest=Path(a.prepare)
  try:
   prepare(dest,a.digest);array=subprocess.check_output(base+['-N','foodnet_residual','-t','1-162','-pe','smp','1','-l','h_rt=08:00:00,h_rss=24576M,mem_free=24576M,h_vmem=32G','-o',str(dest/'array.log'),str(dest/'run.sh')],universal_newlines=True).strip();write(dest/'submission.json',dict(array=array));match=re.match(r'^(\d+)(?:[.\s]|$)',array)
   if not match:raise ValueError('Unrecognized array response; inspect queue before retry')
   col=subprocess.check_output(base+['-N','foodnet_residual_collect','-hold_jid',match.group(1),'-pe','smp','1','-l','h_rt=04:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G','-o',str(dest/'collection.log'),str(dest/'collect.sh')],universal_newlines=True).strip();write(dest/'submission.json',dict(array=array,collector=col));print('Array: '+array+'; collector: '+col,flush=True);return 0
  except Exception as e:
   write(dest/'preparation_failure.json',dict(error=str(e),new_fits=0));archive(dest);raise
 root=Path(__file__).resolve().parents[1]
 if any(not shutil.which(x) for x in ('qsub','singularity')):p.error('Load Singularity on SGE host')
 dest=root/'output'/('spatial_residual_audit_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'));bootstrap(root,dest)
 job=subprocess.check_output(base+['-N','foodnet_residual_prepare','-pe','smp','1','-l','h_rt=12:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G','-o',str(dest/'preparation.log'),str(dest/'prepare.sh')],universal_newlines=True).strip();write(dest/'preparation_submission.json',dict(job=job));print('Preparation job: '+job+'\nLog: '+str(dest/'preparation.log')+'\nArchive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
