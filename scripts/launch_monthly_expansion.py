#!/usr/bin/env python3
"""Seven monthly audits followed by up to 42 gated exploratory comparisons."""
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import launch_monthly_preparation as prep
from launch_saved_monthly_diagnostics import rows,validate_result as validate_sampling

PATHOGENS=tuple(p for p in prep.PATHOGENS if p not in ('SALMONELLA','CAMPYLOBACTER'))
FILES=('launch_monthly_expansion.py','run_monthly_expansion.R','run_monthly_comparison.R','monthly_seasonal_model.R','county_forecast_model.R','audit_saved_monthly.R','audit_saved_forecast_sampling.R','launch_saved_monthly_diagnostics.py','launch_monthly_comparison.py')
sha=prep.sha

def prepare(root,dest,verified=True):
 root=Path(root).resolve();dest=Path(dest).resolve()
 clean=root/'output/20260911_140750/preprocessed/clean_mmwr.csv'
 pp=prep.prepare(root,dest,Path('/scicomp/groups-pure/EDEB/foodnet/trends/data/mmwr9625.sas7bdat'),clean,clean.with_name('clean_mmwr_preprocessing_report.csv'),verified,PATHOGENS)
 for n in FILES:
  target=dest/'scripts'/n;shutil.copyfile(str(root/'scripts'/n),str(target))
 protocol=dest/'monthly_expansion.md';shutil.copyfile(str(root/'docs/monthly_expansion.md'),str(protocol))
 inputs={str(p):sha(p) for p in (dest/'scripts').iterdir()};inputs[str(protocol)]=sha(protocol)
 container=root/'foodnet-inla-fixed.sif'
 if verified:inputs[str(container)]=sha(container)
 tasks=[]
 for pt in pp['tasks']:
  pathogen=pt['id'];end=2017 if pathogen=='CRYPTOSPORIDIUM' else 2019
  for cutoff in ((2011,2013,2014) if end==2017 else (2011,2013,2016)):
   for temporal in ('rw1','ar1'):
    name='%s_%s_%s'%(pathogen,cutoff,temporal);seed=100000000+len(tasks)*1000000
    cmd=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/'scripts/run_monthly_expansion.R'),str(dest/pathogen/'result/candidate_monthly_INTERNAL.rds'),pt['source']['audit'],str(cutoff),str(dest/name/'result'),str(seed),temporal,str(end)]
    tasks.append(dict(id=name,pathogen=pathogen,cutoff=cutoff,seasonal=True,temporal=temporal,end_year=end,seed=seed,command=cmd))
 plan=dict(version='monthly_expansion_v1',verified=verified,preparation_sha256=sha(dest/'plan.json'),inputs=inputs,tasks=tasks,coverage_certified=False,accepted=False,maximum_fits=42,interpretation='Exploratory development; not independent final validation')
 (dest/'expansion.json').write_text(json.dumps(plan,indent=2)+'\n');digest=sha(dest/'expansion.json');q=shlex.quote
 base='python3 '+q(str(dest/'scripts/launch_monthly_expansion.py'))
 shell='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-undefined}" in\n'
 for i,t in enumerate(tasks,1):shell+=str(i)+') task='+t['id']+';;\n'
 shell+='*) exit 2;;\nesac\nexec '+base+' --worker '+q(str(dest))+' --task "$task" --digest '+digest+'\n'
 (dest/'fit.sh').write_text(shell)
 (dest/'finish.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+base+' --collect '+q(str(dest))+' --digest '+digest+'\n')
 return plan

def verify(dest,plan,digest):
 if not plan['verified'] or sha(dest/'expansion.json')!=digest:raise ValueError('Unverified/changed expansion')
 origin=Path(plan.get('preparation_root',dest))
 pp=json.loads((origin/'plan.json').read_text());prep.verify(origin,pp,plan['preparation_sha256'])
 for p,h in plan['inputs'].items():
  if sha(p)!=h:raise ValueError('Changed expansion source/input: '+p)

def gate(dest,plan,pathogen):
 work=Path(plan.get('preparation_root',dest))/pathogen;record=json.loads((work/'task_status.json').read_text())
 if record.get('status')!='COMPLETE' or record.get('exit_status')!=0 or record.get('task')!=pathogen or record.get('plan_sha256')!=plan['preparation_sha256']:raise ValueError('Monthly preparation unavailable or failed')
 prep.validate_result(work)
 if not record.get('outputs') or any(sha(work/n)!=h for n,h in record['outputs'].items()):raise ValueError('Preparation artifacts changed')
 if any(float(r['unassigned_records'])!=0 for r in rows(work/'result/annual_reconciliation.csv')):raise ValueError('Unassigned specimen dates require review')
 if any(float(r['month_disagreement'])!=0 for r in rows(work/'result/date_issues.csv')):
  reviewed=plan.get('month_decision')=='SHIGELLA_SPECIMEN_20260913' and pathogen=='SHIGELLA'
  expected={'result/date_issues.csv':'bbeae4d38a0098ce763e24fe05fdba708b1a776ba3202f28f1863e0e80615546','result/source_month_comparison.csv':'bfd18daf5f5a88fd6bd60cd20fd5ada35b21f554b04f18176b76d235d0bc60f8','task_status.json':'2f92d7b5b7913ae9ba9b68add879b17b077fd91fd1269bee71a5440aac337c16'}
  if not reviewed or any(sha(work/n)!=h for n,h in expected.items()):raise ValueError('Month-definition disagreements require review')
 return sha(work/'task_status.json')

def validate(work,t):
 validate_sampling(work,t)
 settings=rows(work/'result/sensitivity_settings.csv')
 if len(settings)!=1 or settings[0]['temporal_model']!=t['temporal'] or int(settings[0]['end_year'])!=t['end_year']:raise ValueError('Wrong fitted specification')
 if not(work/'fit_INTERNAL.rds').is_file():raise ValueError('Missing saved fit')
 if re.search(r'vb[.]correction[^\n]*aborted',(work/'task.log').read_text(errors='replace'),re.I):raise ValueError('Aborted VB correction')

def worker(dest,name,digest):
 dest=Path(dest);plan=json.loads((dest/'expansion.json').read_text());t=next(t for t in plan['tasks'] if t['id']==name);work=dest/name;work.mkdir(exist_ok=False)
 record=dict(task=name,status='BLOCKED',exit_status=1,plan_sha256=digest)
 try:
  verify(dest,plan,digest);proof=gate(dest,plan,t['pathogen']);record['status']='FAILED'
  with (work/'task.log').open('w') as log:code=subprocess.call(t['command'],stdout=log,stderr=subprocess.STDOUT)
  if code:raise ValueError('R exit '+str(code))
  validate(work,t);verify(dest,plan,digest)
  if gate(dest,plan,t['pathogen'])!=proof:raise ValueError('Preparation changed during fit')
  record.update(status='COMPLETE',exit_status=0,preparation_record_sha256=proof,outputs={str(p.relative_to(work)):sha(p) for p in work.rglob('*') if p.is_file()})
 except (OSError,ValueError,KeyError) as e:record['reason']=str(e)
 (work/'task_status.json').write_text(json.dumps(record,indent=2)+'\n');return record['exit_status']

def collect(dest,digest):
 dest=Path(dest);plan=json.loads((dest/'expansion.json').read_text());summary=[];issues=[];scores=[];tails=[]
 try:verify(dest,plan,digest)
 except (OSError,ValueError,KeyError) as e:issues.append(str(e))
 for t in plan['tasks']:
  work=dest/t['id']
  try:
   r=json.loads((work/'task_status.json').read_text())
   if r.get('status')!='COMPLETE':raise ValueError(r.get('reason','Incomplete fit'))
   if r.get('plan_sha256')!=digest or r.get('task')!=t['id'] or r.get('exit_status')!=0:raise ValueError('Wrong completion identity')
   validate(work,t)
   if gate(dest,plan,t['pathogen'])!=r['preparation_record_sha256'] or not r.get('outputs') or any(sha(work/n)!=h for n,h in r['outputs'].items()):raise ValueError('Changed completed output')
   for name,target in (('stream_scores.csv',scores),('aggregate_tails.csv',tails)):
    target.extend(dict(task=t['id'],pathogen=t['pathogen'],cutoff=t['cutoff'],variant=t['temporal'],**x) for x in rows(work/'result'/name))
   summary.append(dict(task=t['id'],status='COMPLETE'))
  except (OSError,ValueError,KeyError) as e:summary.append(dict(task=t['id'],status='FAILED_OR_BLOCKED',reason=str(e)))
 def write(name,data):
  if data:
   with (dest/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 write('all_stream_scores.csv',scores);write('all_aggregate_tails.csv',tails)
 paired=[]
 index={(r['pathogen'],r['cutoff'],r['state'],r['year'],r['stream'],r['variant']):r for r in scores}
 for key,r in index.items():
  if key[-1]!='ar1':continue
  b=index.get(key[:-1]+('rw1',))
  if b is None:continue
  left=dest/r['task']/'heldout_truth_INTERNAL.csv';right=dest/b['task']/'heldout_truth_INTERNAL.csv'
  if sha(left)!=sha(right):
   issues.append('Paired truth differs: '+r['task']);continue
  paired.append(dict(pathogen=r['pathogen'],cutoff=r['cutoff'],state=r['state'],year=r['year'],stream=r['stream'],log_score_ar1_minus_rw1=float(r['mean_log_score'])-float(b['mean_log_score'])))
 write('paired_site_stream_scores.csv',paired)
 result=dict(tasks=summary,issues=issues,complete=sum(r['status']=='COMPLETE' for r in summary),expected=len(plan['tasks']),accepted=False,coverage_certified=False)
 (dest/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
 files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh','.md') and '_INTERNAL' not in p.name and p.name!='report_sha256.json']
 (dest/'report_sha256.json').write_text(json.dumps({str(p.relative_to(dest)):sha(p) for p in files},indent=2)+'\n')
 with tarfile.open(str(dest)+'.tar.gz','w:gz') as arc:
  for p in files+[dest/'report_sha256.json']:arc.add(str(p),arcname=str(p.relative_to(dest)))
 print(json.dumps(result,indent=2));print('Archive: '+str(dest)+'.tar.gz');return 0 if result['complete']==len(plan['tasks']) and not issues else 1

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-only',action='store_true');p.add_argument('--worker');p.add_argument('--task');p.add_argument('--collect');p.add_argument('--digest');a=p.parse_args()
 if a.worker or a.collect:
  if not a.digest or (a.worker and not a.task):p.error('Missing identity')
  return worker(a.worker,a.task,a.digest) if a.worker else collect(a.collect,a.digest)
 root=Path(__file__).resolve().parents[1];dest=root/'output'/('monthly_expansion_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
 if not a.prepare_only and any(not shutil.which(t) for t in ('qsub','singularity')):p.error('Load singularity and run on SGE host')
 try:prepare(root,dest,not a.prepare_only)
 except (OSError,ValueError,KeyError) as e:p.error(str(e))
 print('Output: '+str(dest),flush=True)
 if a.prepare_only:return 0
 base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y'];ledger={}
 def submit(name,script,slots,time,rss,vmem,array=None,hold=None):
  cmd=base+['-N',name,'-pe','smp',str(slots),'-l','h_rt=%s,h_rss=%sM,mem_free=%sM,h_vmem=%sG'%(time,rss,rss,vmem),'-o',str(dest)]
  if array:cmd+=['-t',array]
  if hold:cmd+=['-hold_jid',hold]
  job=subprocess.check_output(cmd+[str(dest/script)],universal_newlines=True).strip();ledger[name]=job;(dest/'submission.json').write_text(json.dumps(ledger,indent=2)+'\n');print(name+': '+job,flush=True)
  m=re.match(r'^(\d+)(?:[.\s]|$)',job)
  if not m:raise ValueError('Unexpected submission response; inspect queue before retry')
  return m.group(1)
 audit=submit('foodnet_monthly_audit','run.sh',2,'04:00:00',32768,64,'1-7')
 fits=submit('foodnet_monthly_expand','fit.sh',4,'48:00:00',53248,68,'1-42',audit)
 submit('foodnet_monthly_finish','finish.sh',1,'04:00:00',8192,16,hold=fits)
 print('Final report: '+str(dest/'summary.json')+'\nArchive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
