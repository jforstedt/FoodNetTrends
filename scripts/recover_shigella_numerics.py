#!/usr/bin/env python3
"""Diagnose and restart the one remaining Shigella optimizer failure."""
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
import launch_monthly_spatial_factorial as spatial

SOURCE='broader_combinations_20260914_130328_942214'
TARGETS={'SHIGELLA_2011_ar1_seasonal_bym2'}
sha=spatial.s.f.sha


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def prepare(root,dest):
 import recover_monthly_spatial as original
 root=Path(root).resolve();dest=Path(dest).resolve()
 recovery=root/'output/monthly_spatial_recovery_20260914_151100_451135'
 recovered=json.loads((recovery/'plan.json').read_text());rdigest=sha(recovery/'plan.json')
 original.verify(recovery,recovered,rdigest)
 evidence=json.loads((recovery/'summary.json').read_text())
 if evidence.get('issues') or evidence.get('complete')!=1 or {r['task']:r['status'] for r in evidence['tasks']}!={'LISTERIA_2011_ar1_seasonal_bym2':'COMPLETE','SHIGELLA_2011_ar1_seasonal_bym2':'FAILED_OR_MISSING'}:raise ValueError('Unexpected reviewed recovery inventory')
 lt=next(t for t in recovered['tasks'] if t['pathogen']=='LISTERIA');lw=recovery/lt['id'];lr=json.loads((lw/'task_status.json').read_text())
 if lr.get('status')!='COMPLETE' or lr.get('exit_status')!=0 or lr.get('plan_sha256')!=rdigest or lr.get('task')!=lt['id']:raise ValueError('Unverified Listeria recovery')
 ltruth=spatial.validate(lw,lt);spatial.s.f.bind_record(lw,lr)
 if ltruth!=lr.get('truth_sha256') or {x['reference']['truth_sha256'] for x in recovered['references'] if x['pathogen']=='LISTERIA'}!={ltruth}:raise ValueError('Changed Listeria paired truth')
 sw=recovery/'SHIGELLA_2011_ar1_seasonal_bym2';sr=json.loads((sw/'task_status.json').read_text())
 if sr.get('status')!='FAILED' or sr.get('task') not in TARGETS or sr.get('plan_sha256')!=rdigest:raise ValueError('Unverified Shigella failure')
 with (sw/'recovery_numerics.csv').open() as f:rows=list(csv.DictReader(f))
 if len(rows)!=1 or rows[0].get('mode_status')!='2' or rows[0].get('fit_ok')!='TRUE' or rows[0].get('quality_gate_relaxed')!='FALSE':raise ValueError('Unexpected Shigella numerical evidence')
 plan=original.prepare(root,dest)
 plan['tasks']=[t for t in plan['tasks'] if t['id'] in TARGETS]
 plan['references']=[t for t in plan['references'] if t['pathogen']=='SHIGELLA']
 for name in ('recover_shigella_numerics.py','run_shigella_numerical_restart.R','shigella_numerical_restart.R'):
  shutil.copyfile(str(root/'scripts'/name),str(dest/'scripts'/name));plan['inputs'][str(dest/'scripts'/name)]=sha(dest/'scripts'/name)
 for p in (recovery/'plan.json',recovery/'summary.json',lw/'task_status.json',sw/'task_status.json',sw/'recovery_numerics.csv'):
  plan['inputs'][str(p)]=sha(p)
 for rel,digest in lr['outputs'].items():plan['inputs'][str(lw/rel)]=digest
 t=plan['tasks'][0];t['command']=[str(dest/'scripts/run_shigella_numerical_restart.R') if x.endswith('/run_monthly_spatial_recovery.R') else x for x in t['command']]
 plan.update(version='shigella_numerical_restart_v1',reused_complete=323,numerical_strategy='INLA_inla.rerun_once',successful_recovery=str(recovery))
 write(dest/'plan.json',plan);digest=sha(dest/'plan.json');q=shlex.quote
 cmd='python3 '+q(str(dest/'scripts/recover_shigella_numerics.py'))
 (dest/'run.sh').write_text('#!/bin/bash\nset -eu\nexec '+cmd+' --worker '+q(str(dest))+' --task '+t['id']+' --digest '+digest+'\n')
 (dest/'collect.sh').write_text('#!/bin/bash\nset -eu\nexec '+cmd+' --collect '+q(str(dest))+' --digest '+digest+'\n')
 return plan


def verify(dest,plan,digest):
 if sha(dest/'plan.json')!=digest or plan.get('version')!='shigella_numerical_restart_v1' or len(plan['tasks'])!=1 or {t['id'] for t in plan['tasks']}!=TARGETS or plan.get('model_changed') is not False or plan.get('quality_gate_relaxed') is not False:raise ValueError('Changed recovery plan')
 spatial.s.f.check_hashes(plan['inputs'])


def worker(dest,name,digest):
 dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());task=next(t for t in plan['tasks'] if t['id']==name)
 work=dest/name;work.mkdir(exist_ok=False);record=dict(task=name,status='FAILED',exit_status=1,plan_sha256=digest)
 try:
  verify(dest,plan,digest)
  with (work/'task.log').open('w') as log:code=subprocess.call(task['command'],stdout=log,stderr=subprocess.STDOUT)
  if code:raise ValueError('R exit '+str(code))
  truth=spatial.validate(work,task)
  refs=[r['reference']['truth_sha256'] for r in plan['references'] if r['pathogen']==task['pathogen']]
  if refs!=[truth]:raise ValueError('Paired truth changed')
  verify(dest,plan,digest)
  record.update(status='COMPLETE',exit_status=0,truth_sha256=truth,outputs={str(p.relative_to(work)):sha(p) for p in work.rglob('*') if p.is_file()})
 except (OSError,ValueError,KeyError) as e:record['reason']=str(e)
 write(work/'task_status.json',record);return record['exit_status']


def collect(dest,digest):
 dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());issues=[];results=[]
 try:verify(dest,plan,digest)
 except (OSError,ValueError,KeyError) as e:issues.append(str(e))
 for t in plan['tasks']:
  result=dict(task=t['id'],status='FAILED_OR_MISSING')
  try:
   if issues:raise ValueError('Global integrity check failed')
   work=dest/t['id'];r=json.loads((work/'task_status.json').read_text())
   if r.get('status')!='COMPLETE' or r.get('exit_status')!=0 or r.get('task')!=t['id'] or r.get('plan_sha256')!=digest:raise ValueError(r.get('reason','Incomplete recovery'))
   truth=spatial.validate(work,t);spatial.s.f.bind_record(work,r)
   if truth!=r.get('truth_sha256') or {x['reference']['truth_sha256'] for x in plan['references'] if x['pathogen']==t['pathogen']}!={truth}:raise ValueError('Changed paired truth')
   result['status']='COMPLETE'
  except (OSError,ValueError,KeyError) as e:result['reason']=str(e)
  results.append(result)
 complete=sum(r['status']=='COMPLETE' for r in results)
 summary=dict(tasks=results,issues=issues,complete=complete,expected=1,source_complete=323,execution_complete=complete==1 and not issues,model_changed=False,quality_gate_relaxed=False,scientific_acceptance=False)
 write(dest/'summary.json',summary)
 files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and '_INTERNAL' not in p.name and p.suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh','.md') and p.name!='report_sha256.json']
 write(dest/'report_sha256.json',{str(p.relative_to(dest)):sha(p) for p in files})
 with tarfile.open(str(dest)+'.tar.gz','w:gz') as arc:
  for p in files+[dest/'report_sha256.json']:arc.add(str(p),arcname=str(p.relative_to(dest)))
 print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz');return 0 if summary['execution_complete'] else 1


def launch(root,dest):
 prepare(root,dest);base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y']
 raw=subprocess.check_output(base+['-N','foodnet_spatial_retry','-t','1-1','-pe','smp','1','-l','h_rt=48:00:00,h_rss=53248M,mem_free=53248M,h_vmem=68G','-o',str(dest/'array.log'),str(dest/'run.sh')],universal_newlines=True).strip()
 write(dest/'submission.json',dict(array=raw));m=re.match(r'^(\d+)(?:[.\s]|$)',raw)
 if not m:raise ValueError('Unrecognized response; inspect queue before retry')
 col=subprocess.check_output(base+['-N','foodnet_spatial_retry_collect','-hold_jid',m.group(1),'-pe','smp','1','-l','h_rt=04:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G','-o',str(dest/'collection.log'),str(dest/'collect.sh')],universal_newlines=True).strip()
 write(dest/'submission.json',dict(array=raw,collector=col));print('Array: '+raw+'; collector: '+col,flush=True)


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker');p.add_argument('--collect');p.add_argument('--task');p.add_argument('--digest');p.add_argument('--launch');p.add_argument('--root');a=p.parse_args()
 if a.worker or a.collect:
  if not a.digest or (a.worker and not a.task):p.error('Missing task/digest')
  return worker(a.worker,a.task,a.digest) if a.worker else collect(a.collect,a.digest)
 if a.launch:launch(Path(a.root),Path(a.launch));return 0
 root=Path(__file__).resolve().parents[1]
 if any(not shutil.which(t) for t in ('qsub','singularity')):p.error('Load singularity on SGE host')
 dest=root/'output'/('shigella_numerical_restart_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
 # Preparation hashes the frozen evidence; detach it without precreating its protected destination.
 log=Path(str(dest)+'_preparation.log')
 with log.open('w') as handle:
  proc=subprocess.Popen(['python3',str(Path(__file__).resolve()),'--launch',str(dest),'--root',str(root)],stdin=subprocess.DEVNULL,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True,cwd=str(root))
 print('Recovery: '+str(dest)+'\nPreparation log: '+str(log)+'\nArchive: '+str(dest)+'.tar.gz\nPreparation PID: '+str(proc.pid));return 0
if __name__=='__main__':sys.exit(main())
