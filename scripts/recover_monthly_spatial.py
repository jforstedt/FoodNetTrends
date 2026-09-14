#!/usr/bin/env python3
"""Retry only the two failed spatial fits, preserving their original snapshots."""
import argparse
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
TARGETS={'LISTERIA_2011_ar1_seasonal_bym2','SHIGELLA_2011_ar1_seasonal_bym2'}
sha=spatial.s.f.sha


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')


def prepare(root,dest):
 root=Path(root).resolve();dest=Path(dest).resolve();origin=root/'output'/SOURCE/'spatial'
 old=json.loads((origin/'plan.json').read_text());digest=sha(origin/'plan.json')
 spatial.verify(origin,old,digest,all_inputs=True)
 summary=json.loads((origin/'summary.json').read_text())
 expected={t['id'] for t in spatial.matrix()}|{t['id'][:-5] for t in spatial.matrix()}
 if len(summary['tasks'])!=324 or {r['task'] for r in summary['tasks']}!=expected or sum(r['status']=='COMPLETE' for r in summary['tasks'])!=322:raise ValueError('Source task inventory differs')
 failed={r['task'] for r in summary['tasks'] if r['status']!='COMPLETE'}
 if summary.get('issues') or summary.get('complete')!=322 or failed!=TARGETS:raise ValueError('Source is not the reviewed 322-complete/two-failed batch')
 selected=[t for t in old['tasks'] if t['id'] in TARGETS]
 if len(selected)!=2:raise ValueError('Missing recovery task')
 for t in selected:
  r=json.loads((origin/t['id']/'task_status.json').read_text())
  if r.get('status')!='FAILED' or r.get('plan_sha256')!=digest or r.get('task')!=t['id']:raise ValueError('Original failure record differs')
 dest.mkdir(parents=True,exist_ok=False);shutil.copytree(str(origin/'scripts'),str(dest/'scripts'))
 for name in ('recover_monthly_spatial.py','run_monthly_spatial_recovery.R'):
  shutil.copyfile(str(root/'scripts'/name),str(dest/'scripts'/name))
 inputs=dict(old['inputs']);inputs[str(origin/'plan.json')]=digest;inputs[str(origin/'summary.json')]=sha(origin/'summary.json')
 for p in (dest/'scripts').iterdir():
  if p.is_file():inputs[str(p)]=sha(p)
 tasks=[]
 for original in selected:
  t=dict(original);command=list(t['command']);i=next(i for i,x in enumerate(command) if x.endswith('/run_monthly_spatial_factorial.R'))
  command[i]=str(dest/'scripts/run_monthly_spatial_recovery.R')
  if command[i+4]!=str(origin/t['id']/'result'):raise ValueError('Unexpected output argument')
  command[i+4]=str(dest/t['id']/'result');t['command']=command;tasks.append(t)
  inputs.update(t['inputs']);inputs[str(origin/t['id']/'task_status.json')]=sha(origin/t['id']/'task_status.json')
  (dest/'source_evidence'/t['id']).mkdir(parents=True)
  for name in ('task_status.json','task.log','fit_warnings.txt'):
   src=origin/t['id']/name
   if src.exists():shutil.copyfile(str(src),str(dest/'source_evidence'/t['id']/name))
 references=[t for t in old['references'] if (t['pathogen'],t['cutoff'],t['temporal'],t['seasonal']) in {(x['pathogen'],x['cutoff'],x['temporal'],x['seasonal']) for x in tasks}]
 if len(references)!=2:raise ValueError('Missing paired IID references')
 for r in references:inputs.update(r['reference']['inputs'])
 for p in (dest/'source_evidence').rglob('*'):
  if p.is_file():inputs[str(p)]=sha(p)
 plan=dict(version='monthly_spatial_recovery_v1',source=str(origin),source_plan_sha256=digest,inputs=inputs,tasks=tasks,references=references,reused_complete=322,fitting_threads='1:1',model_changed=False,quality_gate_relaxed=False)
 write(dest/'plan.json',plan);digest=sha(dest/'plan.json');q=shlex.quote;cmd='python3 '+q(str(dest/'scripts/recover_monthly_spatial.py'))
 shell='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-}" in\n'
 for i,t in enumerate(tasks,1):shell+=str(i)+') task='+t['id']+';;\n'
 shell+='*) exit 2;;\nesac\nexec '+cmd+' --worker '+q(str(dest))+' --task "$task" --digest '+digest+'\n'
 (dest/'run.sh').write_text(shell);(dest/'collect.sh').write_text('#!/bin/bash\nset -eu\nexec '+cmd+' --collect '+q(str(dest))+' --digest '+digest+'\n');return plan


def verify(dest,plan,digest):
 if sha(dest/'plan.json')!=digest or plan.get('version')!='monthly_spatial_recovery_v1' or len(plan['tasks'])!=2 or {t['id'] for t in plan['tasks']}!=TARGETS or plan.get('model_changed') is not False or plan.get('quality_gate_relaxed') is not False:raise ValueError('Changed recovery plan')
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
 summary=dict(tasks=results,issues=issues,complete=complete,expected=2,source_complete=322,execution_complete=complete==2 and not issues,model_changed=False,quality_gate_relaxed=False,scientific_acceptance=False)
 write(dest/'summary.json',summary)
 files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and '_INTERNAL' not in p.name and p.suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh','.md') and p.name!='report_sha256.json']
 write(dest/'report_sha256.json',{str(p.relative_to(dest)):sha(p) for p in files})
 with tarfile.open(str(dest)+'.tar.gz','w:gz') as arc:
  for p in files+[dest/'report_sha256.json']:arc.add(str(p),arcname=str(p.relative_to(dest)))
 print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz');return 0 if summary['execution_complete'] else 1


def launch(root,dest):
 prepare(root,dest);base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y']
 raw=subprocess.check_output(base+['-N','foodnet_spatial_retry','-t','1-2','-pe','smp','1','-l','h_rt=48:00:00,h_rss=53248M,mem_free=53248M,h_vmem=68G','-o',str(dest/'array.log'),str(dest/'run.sh')],universal_newlines=True).strip()
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
 dest=root/'output'/('monthly_spatial_recovery_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
 # Preparation hashes the frozen evidence; detach it without precreating its protected destination.
 log=Path(str(dest)+'_preparation.log')
 with log.open('w') as handle:
  proc=subprocess.Popen(['python3',str(Path(__file__).resolve()),'--launch',str(dest),'--root',str(root)],stdin=subprocess.DEVNULL,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True,cwd=str(root))
 print('Recovery: '+str(dest)+'\nPreparation log: '+str(log)+'\nArchive: '+str(dest)+'.tar.gz\nPreparation PID: '+str(proc.pid));return 0
if __name__=='__main__':sys.exit(main())
