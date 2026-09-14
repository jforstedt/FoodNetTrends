#!/usr/bin/env python3
"""Recompute flagged observed CPO rows from saved classification fits in parallel."""
import argparse,csv,hashlib,json,math,re,shlex,shutil,subprocess,sys,tarfile
from datetime import datetime
from pathlib import Path
SOURCE='classification_diagnostics_20260914_102549_452910'
import launch_classification_diagnostics as prior
PATHOGENS=('SALMONELLA','CAMPYLOBACTER','SHIGELLA','STEC','VIBRIO','YERSINIA')
STATES=('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN')
FILES=('launch_classification_cpo.py','launch_classification_diagnostics.py','recompute_classification_cpo.R','diagnose_classification_saved.R','fit_classification_trends.R')
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
def rows(path):
 with Path(path).open(newline='') as f:return list(csv.DictReader(f))
def selected(source):
 tasks=[]
 for t in source['tasks']:
  if t['mode']!='inspect':continue
  work=Path(source['_origin'])/t['id']
  prior.validate(work,t)
  flagged=[r for r in rows(work/'result/row_diagnostics.csv') if r['observed']=='TRUE' and number(r['cpo_failure'])>0]
  if flagged:tasks.append((t,len(flagged)))
 return tasks

def number(value):
 return float('nan') if value in ('','NA','NaN') else float(value)
def prepare(root,dest,verified=True):
 root=Path(root).resolve();dest=Path(dest).resolve();origin=root/'output'/SOURCE;container=root/'foodnet-inla-fixed.sif';inputs={}
 if verified:
  old=json.loads((origin/'plan.json').read_text());oh=sha(origin/'plan.json')
  if old.get('version')!='classification_saved_diagnostics_v1' or not old.get('verified'):raise ValueError('Unexpected source plan')
  expected={p+'_'+k+'_'+m+'_'+mode for p in PATHOGENS for k in ('hindcast','description') for m in ('shared','site_slopes') for mode in (('inspect','precision') if k=='hindcast' else ('inspect',))}
  if len(old['tasks'])!=36 or {t['id'] for t in old['tasks']}!=expected:raise ValueError('Source task domain differs')
  inputs[str(origin/'plan.json')]=oh
  if old['inputs'].get(str(container))!=sha(container):raise ValueError('Source container changed')
  inputs[str(container)]=sha(container)
  for t in old['tasks']:
   if t['mode']!='inspect':continue
   expected_id=t['pathogen']+'_'+t['kind']+'_'+t['model']+'_inspect'
   if t['id']!=expected_id or t['cutoff']!={'hindcast':2016,'description':2019}[t['kind']]:raise ValueError('Source identity mismatch')
   work=origin/t['id'];record=work/'task_status.json';r=json.loads(record.read_text())
   if r.get('task')!=t['id'] or r.get('status')!='COMPLETE' or r.get('exit_status')!=0 or r.get('plan_sha256')!=oh:raise ValueError('Incomplete source '+t['id'])
   actual={str(p.relative_to(work)):sha(p) for p in work.rglob('*') if p.is_file() and p.name!='task_status.json'}
   if actual!=r.get('outputs'):raise ValueError('Source output changed')
   for rel,h in actual.items():inputs[str(work/rel)]=h
   inputs[str(record)]=sha(record)
   for key in ('fit','support'):
    path=Path(t[key])
    if old['inputs'].get(str(path))!=sha(path):raise ValueError('Source '+key+' changed')
    inputs[str(path)]=sha(path)
  old['_origin']=str(origin);chosen=selected(old)
  if not chosen:raise ValueError('No flagged observed CPO rows require recomputation')
 else:
  chosen=[]
  for pathogen in PATHOGENS:
   for kind,cutoff in (('hindcast',2016),('description',2019)):
    for model in ('shared','site_slopes'):
     if pathogen not in PATHOGENS[:3] and (pathogen,kind,model)!=('VIBRIO','hindcast','shared'):continue
     source_id=pathogen+'_'+kind+'_'+model
     chosen.append((dict(id=source_id+'_inspect',pathogen=pathogen,kind=kind,cutoff=cutoff,model=model,fit=str(root/'output/classification_trends_20260914_100228_401966'/source_id/'result/fit_INTERNAL.rds'),support=str(root/'output/eligible_diagnostics_20260914_094654_276977'/pathogen/'result/support.csv')),None))
 dest.mkdir(parents=True,exist_ok=False);(dest/'scripts').mkdir()
 for n in FILES:
  p=dest/'scripts'/n;shutil.copyfile(str(root/'scripts'/n),str(p));inputs[str(p)]=sha(p)
 protocol=dest/'classification_cpo_repair.md';shutil.copyfile(str(root/'docs/classification_cpo_repair.md'),str(protocol));inputs[str(protocol)]=sha(protocol)
 tasks=[]
 for t,count in chosen:
  name=t['id'].replace('_inspect','_cpo');flags=origin/t['id']/'result/row_diagnostics.csv'
  command=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/'scripts/recompute_classification_cpo.R'),t['fit'],t['support'],str(flags),str(dest/name/'result'),str(t['cutoff']),t['model']]
  tasks.append(dict(id=name,source_id=t['id'],pathogen=t['pathogen'],kind=t['kind'],cutoff=t['cutoff'],model=t['model'],requested=count,flags=str(flags),support=t['support'],fit=t['fit'],command=command))
 plan=dict(version='classification_cpo_v1',verified=verified,inputs=inputs,tasks=tasks,scientific_model_changed=False,accepted=False,independent_validation=False)
 (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');digest=sha(dest/'plan.json');q=shlex.quote;base='python3 '+q(str(dest/'scripts/launch_classification_cpo.py'))
 script='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-undefined}" in\n'
 for i,t in enumerate(tasks,1):script+=str(i)+') task='+t['id']+';;\n'
 script+='*) exit 2;;\nesac\nexec '+base+' --worker '+q(str(dest))+' --task "$task" --digest '+digest+'\n'
 (dest/'run.sh').write_text(script);(dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+base+' --collect '+q(str(dest))+' --digest '+digest+'\n');return plan

def verify(dest,plan,digest):
 if not plan.get('verified') or sha(dest/'plan.json')!=digest:raise ValueError('Unverified or changed plan')
 for p,h in plan['inputs'].items():
  if sha(p)!=h:raise ValueError('Changed input/source '+p)
def validate(work,t):
 out=work/'result'
 if (out/'status.txt').read_text().strip()!='CPO_RECOMPUTATION_COMPLETE':raise ValueError('Incomplete recomputation')
 identity=rows(out/'identity.csv')
 if len(identity)!=1 or any(identity[0].get(k)!=str(t[k]) for k in ('cutoff','model')) or int(identity[0]['rows'])!=80 or int(identity[0]['requested'])!=t['requested'] or any(identity[0].get(k)!=v for k,v in (('original_preserved','TRUE'),('scientific_model_changed','FALSE'),('accepted','FALSE'))):raise ValueError('CPO identity mismatch')
 d=rows(out/'comparison.csv');flags=rows(t['flags']);keys={(s,y) for s in STATES for y in range(2012,2020)}
 if len(d)!=80 or {(r['state'],int(r['year'])) for r in d}!=keys or len(flags)!=80 or {(r['state'],int(r['year'])) for r in flags}!=keys:raise ValueError('Incomplete row domain')
 before={(r['state'],int(r['year'])):r for r in flags};requested=remaining=invalid=unresolved=0
 for r in d:
  k=(r['state'],int(r['year']));b=before[k];observed=k[1]<=t['cutoff'];target=observed and number(b['cpo_failure'])>0
  if r['observed']!=str(observed).upper() or r['requested']!=str(target).upper():raise ValueError('CPO observed/requested mask mismatch')
  for original,new in (('cpo_failure','before_failure'),('cpo','before_cpo'),('pit','before_pit')):
   a,z=number(b[original]),number(r[new])
   if not (a==z or (math.isnan(a) and math.isnan(z))):raise ValueError('Original diagnostic differs')
  if not target:
   for suffix in ('failure','cpo','pit'):
    a,z=number(r['before_'+suffix]),number(r['after_'+suffix])
    if not (a==z or (math.isnan(a) and math.isnan(z))):raise ValueError('Unrequested diagnostic changed')
  f,c,p=number(r['after_failure']),number(r['after_cpo']),number(r['after_pit'])
  if target:
   requested+=1;bad=not math.isfinite(f) or not math.isfinite(c) or c<=0 or not math.isfinite(p) or not 0<=p<=1
   remaining+=int(f>0);invalid+=int(bad);unresolved+=int(bad or f>0)
 summary=rows(out/'summary.csv')
 expected=dict(requested=requested,remaining_flagged=remaining,invalid_requested=invalid,resolved=requested-unresolved)
 if requested!=t['requested'] or len(summary)!=1 or any(int(summary[0][k])!=v for k,v in expected.items()):raise ValueError('CPO summary mismatch')
 if not (out/'repaired_INTERNAL.rds').is_file():raise ValueError('Missing repaired fit')
 return expected

def worker(dest,name,digest):
 dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());matches=[t for t in plan['tasks'] if t['id']==name]
 if len(matches)!=1:raise ValueError('Unknown task identity')
 t=matches[0];work=dest/name;work.mkdir(exist_ok=False);r=dict(task=name,status='FAILED',exit_status=1,plan_sha256=digest)
 try:
  verify(dest,plan,digest)
  with (work/'task.log').open('w') as log:code=subprocess.call(t['command'],stdout=log,stderr=subprocess.STDOUT)
  if code:raise ValueError('R exit '+str(code))
  validate(work,t);verify(dest,plan,digest)
  r.update(status='COMPLETE',exit_status=0,outputs={str(p.relative_to(work)):sha(p) for p in work.rglob('*') if p.is_file()})
 except (OSError,ValueError,KeyError) as e:r['reason']=str(e)
 (work/'task_status.json').write_text(json.dumps(r,indent=2)+'\n');return r['exit_status']
def collect(dest,digest):
 dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());results=[];issues=[];merged={}
 try:verify(dest,plan,digest)
 except (OSError,ValueError,KeyError) as e:issues.append(str(e))
 for t in plan['tasks']:
  work=dest/t['id']
  try:
   r=json.loads((work/'task_status.json').read_text())
   if r.get('status')!='COMPLETE' or r.get('task')!=t['id'] or r.get('plan_sha256')!=digest or r.get('exit_status')!=0:raise ValueError(r.get('reason','Incomplete task'))
   validate(work,t)
   actual={str(p.relative_to(work)):sha(p) for p in work.rglob('*') if p.is_file() and p.name!='task_status.json'}
   if not r.get('outputs') or actual!=r['outputs']:raise ValueError('Changed completed output')
   results.append(dict(task=t['id'],status='COMPLETE',**validate(work,t)))
   for name in ('comparison.csv','summary.csv'):
    merged.setdefault(name,[]).extend(dict(task=t['id'],pathogen=t['pathogen'],kind=t['kind'],model=t['model'],**x) for x in rows(work/'result'/name))
  except (OSError,ValueError,KeyError) as e:results.append(dict(task=t['id'],status='FAILED_OR_MISSING',reason=str(e)))
 for name,data in merged.items():
  with (dest/('all_'+name)).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 summary=dict(tasks=results,issues=issues,complete=sum(r['status']=='COMPLETE' for r in results),expected=len(plan['tasks']),scientific_model_changed=False,accepted=False,independent_validation=False,diagnostics_resolved=not issues and len(results)==len(plan['tasks']) and all(r.get('status')=='COMPLETE' and r.get('resolved')==r.get('requested') for r in results))
 (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh','.md') and '_INTERNAL' not in p.name and p.name!='report_sha256.json']
 (dest/'report_sha256.json').write_text(json.dumps({str(p.relative_to(dest)):sha(p) for p in files},indent=2)+'\n')
 with tarfile.open(str(dest)+'.tar.gz','w:gz') as arc:
  for p in files+[dest/'report_sha256.json']:arc.add(str(p),arcname=str(p.relative_to(dest)))
 print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz');return 0 if summary['complete']==len(plan['tasks']) and not issues else 1

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-only',action='store_true');p.add_argument('--worker');p.add_argument('--task');p.add_argument('--collect');p.add_argument('--digest');a=p.parse_args()
 if a.worker or a.collect:
  if not a.digest or (a.worker and not a.task):p.error('Missing identity')
  return worker(a.worker,a.task,a.digest) if a.worker else collect(a.collect,a.digest)
 root=Path(__file__).resolve().parents[1];dest=root/'output'/('classification_cpo_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
 if not a.prepare_only and any(not shutil.which(t) for t in ('qsub','singularity')):p.error('Load singularity on SGE host')
 try:plan=prepare(root,dest,not a.prepare_only)
 except (OSError,ValueError,KeyError) as e:p.error(str(e))
 print('Output: '+str(dest),flush=True)
 if a.prepare_only:return 0
 base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y','-o',str(dest)]
 job=subprocess.check_output(base+['-N','foodnet_class_cpo','-t','1-'+str(len(plan['tasks'])),'-pe','smp','4','-l','h_rt=12:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G',str(dest/'run.sh')],universal_newlines=True).strip()
 (dest/'submission.json').write_text(json.dumps(dict(array=job))+'\n');print('Diagnostic array: '+job,flush=True);match=re.match(r'^(\d+)(?:[.\s]|$)',job)
 if not match:raise ValueError('Unexpected scheduler response; inspect queue before retry')
 col=subprocess.check_output(base+['-N','foodnet_class_collect','-hold_jid',match.group(1),'-pe','smp','1','-l','h_rt=02:00:00,h_rss=4096M,mem_free=4096M,h_vmem=8G',str(dest/'collect.sh')],universal_newlines=True).strip()
 (dest/'submission.json').write_text(json.dumps(dict(array=job,collector=col))+'\n');print('Collector: '+col+'\nArchive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
