#!/usr/bin/env python3
"""Complete the nine-pathogen temporal-family by seasonality factorial."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import launch_monthly_comparison as comparison
import launch_monthly_expansion as expansion
import launch_monthly_ar1_comparison as ar1
import launch_saved_monthly_diagnostics as saved

PATHOGENS=tuple(expansion.prep.PATHOGENS)
BASE='saved_monthly_diagnostics_20260913_205110_899575'
AR1='monthly_ar1_comparison_20260913_215732_614498'
EXPANSION='monthly_expansion_20260913_223222_865377'
SHIGELLA='monthly_shigella_recovery_20260914_012243_682311'
FILES=tuple(sorted(set(expansion.FILES+expansion.prep.FILES+ar1.FILES+('launch_monthly_factorial.py','run_monthly_factorial.R'))))
sha=saved.sha
rows=saved.rows
STATES=('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN')

def origins(pathogen):return (2011,2013,2014) if pathogen=='CRYPTOSPORIDIUM' else (2011,2013,2016)
def task_id(p,c,m,s):return '%s_%s_%s_%s'%(p,c,m,'seasonal' if s else 'nonseasonal')
def matrix():
 return [dict(id=task_id(p,c,m,s),pathogen=p,cutoff=c,temporal=m,seasonal=s,end_year=2017 if p=='CRYPTOSPORIDIUM' else 2019,reused=s or (m=='rw1' and p in comparison.SOURCES)) for p in PATHOGENS for c in origins(p) for m in ('rw1','ar1') for s in (False,True)]

def reference_location(root,t):
 p,c,m,s=t['pathogen'],t['cutoff'],t['temporal'],t['seasonal']
 if not t['reused']:raise ValueError('Not a reused cell')
 if p in comparison.SOURCES:
  run=BASE if m=='rw1' else AR1;name='%s_%s_%s'%(p,c,'seasonal' if s else 'reference');pn='plan.json'
 else:
  run=SHIGELLA if p=='SHIGELLA' else EXPANSION;name='%s_%s_%s'%(p,c,m);pn='expansion.json'
 return Path(root)/'output'/run,name,pn

def check_hashes(bound):
 for path,digest in bound.items():
  if sha(path)!=digest:raise ValueError('Changed bound artifact: '+path)

def bind_record(work,record):
 if not record.get('outputs'):raise ValueError('Missing output binding')
 bound={str(work/n):h for n,h in record['outputs'].items()};check_hashes(bound)
 bound[str(work/'task_status.json')]=sha(work/'task_status.json');return bound

def truth_identity(path,cutoff):
 data=rows(path);keys={};domains={};county_states={}
 for r in data:
  key=(str(r['fips']).zfill(5),r['state'],int(r['year']),int(r['month']))
  value=float(r['observed'])
  if key in keys or key[1] not in STATES or key[2] not in range(cutoff+1,cutoff+4) or key[3] not in range(1,13) or not math.isfinite(value) or value<0 or value!=int(value):raise ValueError('Invalid held-out truth')
  keys[key]=int(value);domains.setdefault(key[0],set()).add((key[2],key[3]));county_states.setdefault(key[0],set()).add(key[1])
 counties={k[0] for k in keys}
 if len(counties)!=486 or len(keys)!=486*36 or {k[1] for k in keys}!=set(STATES):raise ValueError('Incomplete held-out truth')
 if any(v!={(y,m) for y in range(cutoff+1,cutoff+4) for m in range(1,13)} for v in domains.values()) or any(len(v)!=1 for v in county_states.values()):raise ValueError('Incomplete or inconsistent county/month truth')
 return hashlib.sha256(json.dumps(sorted((list(k),v) for k,v in keys.items()),separators=(',',':')).encode()).hexdigest()

def load_reference(root,t,plans):
 base,name,pn=reference_location(root,t);plan=plans[str(base)];digest=sha(base/pn)
 original=next(x for x in plan['tasks'] if x['id']==name);work=base/name
 if (original['pathogen'],original['cutoff'],original['seasonal'])!=(t['pathogen'],t['cutoff'],t['seasonal']):raise ValueError('Reference specification mismatch')
 model=original.get('temporal','ar1' if plan['version']=='monthly_ar1_comparison_v1' else 'rw1')
 if model!=t['temporal']:raise ValueError('Reference temporal family mismatch')
 record=json.loads((work/'task_status.json').read_text())
 if record.get('task')!=name or record.get('status')!='COMPLETE' or record.get('exit_status')!=0 or record.get('plan_sha256')!=digest:raise ValueError('Incomplete reference identity')
 if plan['version']=='monthly_expansion_v1':
  expansion.validate(work,original)
  if expansion.gate(base,plan,t['pathogen'])!=record['preparation_record_sha256']:raise ValueError('Reference preparation mismatch')
 elif plan['version']=='monthly_ar1_comparison_v1':ar1.validate(work,original)
 elif plan['version']=='saved_monthly_diagnostics_v1':saved.validate_result(work,original)
 else:raise ValueError('Unsupported reference source')
 bound=bind_record(work,record);bound[str(base/pn)]=digest
 if plan['version']=='saved_monthly_diagnostics_v1':
  possible=[x for x in original['inputs'] if x.endswith('/result/county_month_predictions.csv')]
  if len(possible)!=1:raise ValueError('Ambiguous baseline truth')
  truth=Path(possible[0]);check_hashes(original['inputs']);bound.update(original['inputs'])
 else:truth=work/'heldout_truth_INTERNAL.csv'
 if str(truth) not in bound:raise ValueError('Unbound reference truth')
 return dict(task=original,work=str(work),source_plan_sha256=digest,truth_sha256=truth_identity(truth,t['cutoff']),inputs=bound)

def source_contracts(root,plans):
 sources={}
 for p in PATHOGENS:
  if p in comparison.SOURCES:sources[p]=comparison.source_contract(root,p)
  else:
   base=root/'output'/(SHIGELLA if p=='SHIGELLA' else EXPANSION);plan=plans[str(base)]
   expansion.gate(base,plan,p);origin=Path(plan.get('preparation_root',base));prep=json.loads((origin/'plan.json').read_text())
   task=next(t for t in prep['tasks'] if t['id']==p);work=origin/p;record=json.loads((work/'task_status.json').read_text())
   evidence=expansion.prep.validate_source(p,task['source']);bound=bind_record(work,record)
   bound.update(evidence['evidence_sha256']);bound.update(prep['inputs']);bound[str(origin/'plan.json')]=sha(origin/'plan.json');bound[str(base/'expansion.json')]=sha(base/'expansion.json')
   sources[p]=dict(candidate=str(work/'result/candidate_monthly_INTERNAL.rds'),audit=task['source']['audit'],hashes=bound)
  # All files read by the model must have source evidence and immutable bytes.
  source=sources[p];runtime={source['candidate']:sha(source['candidate'])}
  for path in Path(source['audit']).rglob('*'):
   if path.is_file():runtime[str(path)]=sha(path)
  source['runtime_inputs']=runtime
 return sources

def prepare(root,dest,verified=True):
 root=Path(root).resolve();dest=Path(dest).resolve();plans={};sources={};references={};provenance={}
 if verified:
  for run,pn,verify in ((BASE,'plan.json',saved.verify),(AR1,'plan.json',ar1.verify),(EXPANSION,'expansion.json',expansion.verify),(SHIGELLA,'expansion.json',expansion.verify)):
   base=root/'output'/run;plan=json.loads((base/pn).read_text());verify(base,plan,sha(base/pn));plans[str(base)]=plan
   provenance[str(base/pn)]=sha(base/pn);provenance.update(plan['inputs'])
  sources=source_contracts(root,plans)
  for source in sources.values():provenance.update(source['hashes'])
  for t in matrix():
   if t['reused']:references[t['id']]=load_reference(root,t,plans)
  for pathogen in PATHOGENS:
   for cutoff in origins(pathogen):
    identities={references[t['id']]['truth_sha256'] for t in matrix() if t['reused'] and (t['pathogen'],t['cutoff'])==(pathogen,cutoff)}
    if len(identities)!=1:raise ValueError('Reused factorial arms have different held-out truth: '+pathogen+' '+str(cutoff))
 else:
  sources={p:dict(candidate='UNVERIFIED',audit='UNVERIFIED',runtime_inputs={}) for p in PATHOGENS}
 dest.mkdir(parents=True,exist_ok=False);(dest/'scripts').mkdir();inputs={}
 for name in FILES:
  path=dest/'scripts'/name;shutil.copyfile(str(root/'scripts'/name),str(path));inputs[str(path)]=sha(path)
 doc=dest/'monthly_factorial.md';shutil.copyfile(str(root/'docs/monthly_factorial.md'),str(doc));inputs[str(doc)]=sha(doc)
 container=root/'foodnet-inla-fixed.sif'
 if verified:inputs[str(container)]=sha(container)
 tasks=[];refcells=[]
 for t in matrix():
  if t['reused']:
   if verified:
    ref=references[t['id']];target=dest/'references'/t['id'];target.mkdir(parents=True)
    for name in ('stream_scores.csv','aggregate_tails.csv','settings.csv'):
     path=target/name;shutil.copyfile(str(Path(ref['work'])/'result'/name),str(path));inputs[str(path)]=sha(path)
    t.update(reference=ref)
   refcells.append(t);continue
  source=sources[t['pathogen']];t['seed']=500000000+len(tasks)*1000000
  t['inputs']=source['runtime_inputs'];t['command']=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/'scripts/run_monthly_factorial.R'),source['candidate'],source['audit'],str(t['cutoff']),str(dest/t['id']/'result'),str(t['seed']),t['temporal'],str(t['end_year'])]
  tasks.append(t)
 plan=dict(version='monthly_factorial_v1',verified=verified,inputs=inputs,provenance=provenance,tasks=tasks,references=refcells,new_fits=48,reused_fits=60,total_cells=108,accepted=False,coverage_certified=False,independent_validation=False,cpo_ranking=False)
 (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');digest=sha(dest/'plan.json');q=shlex.quote;base='python3 '+q(str(dest/'scripts/launch_monthly_factorial.py'))
 shell='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-undefined}" in\n'
 for i,t in enumerate(tasks,1):shell+=str(i)+') task='+t['id']+';;\n'
 shell+='*) exit 2;;\nesac\nexec '+base+' --worker '+q(str(dest))+' --task "$task" --digest '+digest+'\n'
 (dest/'run.sh').write_text(shell);(dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+base+' --collect '+q(str(dest))+' --digest '+digest+'\n')
 return plan

def verify(dest,plan,digest,task=None,all_inputs=False):
 if sha(dest/'plan.json')!=digest or not plan.get('verified') or plan.get('version')!='monthly_factorial_v1':raise ValueError('Unverified or changed factorial plan')
 check_hashes(plan['inputs'])
 if task:check_hashes(task['inputs'])
 if all_inputs:
  check_hashes(plan['provenance'])
  for t in plan['tasks']:check_hashes(t['inputs'])
  for t in plan['references']:check_hashes(t['reference']['inputs'])

def validate(work,t):
 saved.validate_result(work,t);settings=rows(work/'result/sensitivity_settings.csv')
 if len(settings)!=1 or settings[0].get('temporal_model')!=t['temporal'] or settings[0].get('seasonal')!='FALSE' or int(settings[0]['end_year'])!=t['end_year'] or float(settings[0]['rate_center'])!=.0002:raise ValueError('Wrong nonseasonal factorial specification')
 if not(work/'fit_INTERNAL.rds').is_file():raise ValueError('Missing new fit checkpoint')
 if re.search(r'vb[.]correction[^\n]*aborted',(work/'task.log').read_text(errors='replace'),re.I):raise ValueError('Aborted VB correction')
 return truth_identity(work/'heldout_truth_INTERNAL.csv',t['cutoff'])

def worker(dest,name,digest):
 dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());t=next(t for t in plan['tasks'] if t['id']==name);work=dest/name;work.mkdir(exist_ok=False)
 record=dict(task=name,status='FAILED',exit_status=1,plan_sha256=digest)
 try:
  verify(dest,plan,digest,t)
  with (work/'task.log').open('w') as log:code=subprocess.call(t['command'],stdout=log,stderr=subprocess.STDOUT)
  if code:raise ValueError('R exit '+str(code))
  truth=validate(work,t);expected={r['reference']['truth_sha256'] for r in plan['references'] if (r['pathogen'],r['cutoff'])==(t['pathogen'],t['cutoff'])}
  if expected!={truth}:raise ValueError('New and reused held-out truth differ')
  verify(dest,plan,digest,t);record.update(status='COMPLETE',exit_status=0,truth_sha256=truth,outputs={str(p.relative_to(work)):sha(p) for p in work.rglob('*') if p.is_file()})
 except (OSError,ValueError,KeyError,StopIteration) as e:record['reason']=str(e)
 (work/'task_status.json').write_text(json.dumps(record,indent=2)+'\n');return record['exit_status']

def contrasts(scores):
 index={};result=[]
 for r in scores:
  key=(r['pathogen'],int(r['cutoff']),r['state'],int(r['year']),int(r['stream']),r['temporal'],r['seasonal'])
  if key in index:raise ValueError('Duplicate factorial score cell')
  index[key]=float(r['mean_log_score'])
 for key in sorted({k[:5] for k in index}):
  values={(m,s):index.get(key+(m,s)) for m in ('rw1','ar1') for s in (False,True)}
  if any(v is None for v in values.values()):continue
  a,b,c,d=[values[k] for k in (('rw1',False),('ar1',False),('rw1',True),('ar1',True))]
  result.append(dict(pathogen=key[0],cutoff=key[1],state=key[2],year=key[3],stream=key[4],ar1_minus_rw1_nonseasonal=b-a,ar1_minus_rw1_seasonal=d-c,seasonality_under_rw1=c-a,seasonality_under_ar1=d-b,interaction=d-b-c+a))
 grouped={}
 for r in result:grouped.setdefault((r['pathogen'],r['cutoff'],r['year'],r['stream']),[]).append(r)
 equal=[]
 metrics=('ar1_minus_rw1_nonseasonal','ar1_minus_rw1_seasonal','seasonality_under_rw1','seasonality_under_ar1','interaction')
 for key,rs in sorted(grouped.items()):
  if len(rs)==10 and {r['state'] for r in rs}==set(STATES):equal.append(dict(pathogen=key[0],cutoff=key[1],year=key[2],stream=key[3],sites=10,**{k:sum(r[k] for r in rs)/10 for k in metrics}))
 return result,equal

def collect(dest,digest):
 dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());issues=[];summary=[];scores=[];tails=[];truths={}
 try:verify(dest,plan,digest,all_inputs=True)
 except (OSError,ValueError,KeyError) as e:issues.append(str(e))
 for t in plan['references']+plan['tasks']:
  try:
   if t['reused']:
    ref=t['reference'];check_hashes(ref['inputs']);out=dest/'references'/t['id'];truth=ref['truth_sha256']
    for name in ('stream_scores.csv','aggregate_tails.csv','settings.csv'):
     path=str(out/name)
     if path not in plan['inputs']:raise ValueError('Unbound copied reference: '+path)
     check_hashes({path:plan['inputs'][path]})
   else:
    work=dest/t['id'];record=json.loads((work/'task_status.json').read_text())
    if record.get('status')!='COMPLETE' or record.get('task')!=t['id'] or record.get('plan_sha256')!=digest or record.get('exit_status')!=0:raise ValueError(record.get('reason','Incomplete task'))
    truth=validate(work,t);bind_record(work,record);out=work/'result'
    if truth!=record.get('truth_sha256'):raise ValueError('Changed truth identity')
   block=(t['pathogen'],t['cutoff']);truths.setdefault(block,set()).add(truth)
   for name,target in (('stream_scores.csv',scores),('aggregate_tails.csv',tails)):
    target.extend(dict(task=t['id'],pathogen=t['pathogen'],cutoff=t['cutoff'],temporal=t['temporal'],seasonal=t['seasonal'],reused=t['reused'],**r) for r in rows(out/name))
   summary.append(dict(task=t['id'],status='COMPLETE',reused=t['reused']))
  except (OSError,ValueError,KeyError) as e:summary.append(dict(task=t['id'],status='FAILED_OR_MISSING',reason=str(e),reused=t['reused']))
 invalid={k for k,v in truths.items() if len(v)!=1}
 if invalid:issues.append('Inconsistent paired truth: '+str(sorted(invalid)))
 paired,equal=([],[]) if issues else contrasts([r for r in scores if (r['pathogen'],r['cutoff']) not in invalid])
 # A failed or now-incomplete recollection must not leave old comparison tables.
 for name in ('all_stream_scores.csv','all_aggregate_tails.csv','factorial_site_contrasts.csv','factorial_equal_site_contrasts.csv'):
  path=dest/name
  if path.exists():path.unlink()
 def write(name,data):
  if data:
   with (dest/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 write('all_stream_scores.csv',scores);write('all_aggregate_tails.csv',tails);write('factorial_site_contrasts.csv',paired);write('factorial_equal_site_contrasts.csv',equal)
 complete=sum(r['status']=='COMPLETE' for r in summary);result=dict(tasks=summary,issues=issues,complete=complete,expected=108,new_fits=48,reused_fits=60,accepted=False,independent_validation=False,cpo_ranking=False)
 (dest/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
 files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh','.md') and '_INTERNAL' not in p.name and p.name!='report_sha256.json']
 (dest/'report_sha256.json').write_text(json.dumps({str(p.relative_to(dest)):sha(p) for p in files},indent=2)+'\n')
 with tarfile.open(str(dest)+'.tar.gz','w:gz') as archive:
  for p in files+[dest/'report_sha256.json']:archive.add(str(p),arcname=str(p.relative_to(dest)))
 print(json.dumps(result,indent=2));print('Archive: '+str(dest)+'.tar.gz');return 0 if complete==108 and not issues else 1

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--worker');parser.add_argument('--task');parser.add_argument('--collect');parser.add_argument('--digest');args=parser.parse_args()
 if args.worker or args.collect:
  if not args.digest or (args.worker and not args.task):parser.error('Missing task identity')
  return worker(args.worker,args.task,args.digest) if args.worker else collect(args.collect,args.digest)
 root=Path(__file__).resolve().parents[1];dest=root/'output'/('monthly_factorial_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
 if not args.prepare_only and any(not shutil.which(t) for t in ('qsub','singularity')):parser.error('Load singularity and run on SGE host')
 try:prepare(root,dest,not args.prepare_only)
 except (OSError,ValueError,KeyError,StopIteration) as e:parser.error(str(e))
 print('Output: '+str(dest),flush=True)
 if args.prepare_only:return 0
 base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y'];ledger={}
 def submit(name,script,slots,time,rss,vmem,array=None,hold=None):
  cmd=base+['-N',name,'-pe','smp',str(slots),'-l','h_rt=%s,h_rss=%sM,mem_free=%sM,h_vmem=%sG'%(time,rss,rss,vmem),'-o',str(dest)]
  if array:cmd+=['-t',array]
  if hold:cmd+=['-hold_jid',hold]
  job=subprocess.check_output(cmd+[str(dest/script)],universal_newlines=True).strip();ledger[name]=job;(dest/'submission.json').write_text(json.dumps(ledger,indent=2)+'\n');print(name+': '+job,flush=True)
  match=re.match(r'^(\d+)(?:[.\s]|$)',job)
  if not match:raise ValueError('Unexpected submission response; inspect queue before retry')
  return match.group(1)
 fits=submit('foodnet_monthly_factorial','run.sh',4,'48:00:00',53248,68,'1-48')
 submit('foodnet_factorial_collect','collect.sh',1,'04:00:00',8192,16,hold=fits)
 print('48 new fits; 60 reused fits; archive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
