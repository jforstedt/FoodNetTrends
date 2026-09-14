#!/usr/bin/env python3
"""Compare singleton group CV with explicitly masked observed cells, in parallel."""
import argparse,csv,hashlib,json,math,re,shlex,shutil,subprocess,sys,tarfile
from datetime import datetime
from pathlib import Path
SOURCE='classification_diagnostics_20260914_102549_452910'
import launch_classification_diagnostics as prior
PATHOGENS=('SALMONELLA','CAMPYLOBACTER','SHIGELLA','STEC','VIBRIO','YERSINIA')
STATES=('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN')
FILES=('launch_classification_crosscheck.py','launch_classification_diagnostics.py','crosscheck_classification.R','diagnose_classification_saved.R','fit_classification_trends.R')
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
def rows(path):
 with Path(path).open(newline='') as f:return list(csv.DictReader(f))
def selected(source):
 tasks=[];absent=[]
 for t in source['tasks']:
  if (t['mode'],t['kind'],t['model'])!=('inspect','hindcast','shared'):continue
  work=Path(source['_origin'])/t['id'];prior.validate(work,t)
  support={(r['state'],int(r['year'])):r for r in rows(t['support'])}
  flags=rows(work/'result/row_diagnostics.csv')
  for flagged in (True,False):
   for zero in (True,False):
    candidates=[]
    for r in flags:
     key=(r['state'],int(r['year']));failure=number(r['cpo_failure'])
     if r['observed']!='TRUE' or key[1]>2016:continue
     if not math.isfinite(failure) or failure<0:raise ValueError('Undefined observed CPO flag')
     s=support[key];y=number(s['cidt_classified']);n=number(s['classification_denominator'])
     if not math.isfinite(y) or not math.isfinite(n) or y<0 or n<=0 or y>n or int(y)!=y or int(n)!=n:raise ValueError('Invalid selection outcome')
     if (failure>0)==flagged and (y==0)==zero:candidates.append((key,r,y,n))
    stratum=('flagged' if flagged else 'unflagged')+'_'+('zero' if zero else 'nonzero')
    if not candidates:absent.append(dict(pathogen=t['pathogen'],stratum=stratum));continue
    key,r,y,n=min(candidates,key=lambda z:(z[0][1],z[0][0]))
    tasks.append((t,dict(state=key[0],year=key[1],stratum=stratum,observed_cidt=int(y),trials=int(n),original_failure=number(r['cpo_failure']),original_cpo=number(r['cpo']))))
 return tasks,absent

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
   if (t['mode'],t['kind'],t['model'])!=('inspect','hindcast','shared'):continue
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
  old['_origin']=str(origin);chosen,absent=selected(old)
  if not chosen:raise ValueError('No eligible observed cells')
 else:
  chosen=[];absent=[]
  for pathogen in PATHOGENS:
   source_id=pathogen+'_hindcast_shared'
   t=dict(id=source_id+'_inspect',pathogen=pathogen,kind='hindcast',cutoff=2016,model='shared',fit=str(root/'output/classification_trends_20260914_100228_401966'/source_id/'result/fit_INTERNAL.rds'),support=str(root/'output/eligible_diagnostics_20260914_094654_276977'/pathogen/'result/support.csv'))
   for i,stratum in enumerate(('flagged_zero','flagged_nonzero','unflagged_zero','unflagged_nonzero')):
    chosen.append((t,dict(state='CA',year=2012+i,stratum=stratum,observed_cidt=0 if i%2==0 else 1,trials=100,original_failure=1 if i<2 else 0,original_cpo=.1)))
 dest.mkdir(parents=True,exist_ok=False);(dest/'scripts').mkdir()
 for n in FILES:
  p=dest/'scripts'/n;shutil.copyfile(str(root/'scripts'/n),str(p));inputs[str(p)]=sha(p)
 protocol=dest/'classification_crosscheck.md';shutil.copyfile(str(root/'docs/classification_crosscheck.md'),str(protocol));inputs[str(protocol)]=sha(protocol)
 tasks=[]
 for t,cell in chosen:
  name=t['pathogen']+'_'+cell['stratum'];flags=origin/t['id']/'result/row_diagnostics.csv';seed=700000000+len(tasks)*1000000
  command=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/'scripts/crosscheck_classification.R'),t['fit'],t['support'],str(flags),str(dest/name/'result'),cell['state'],str(cell['year']),str(seed)]
  tasks.append(dict(id=name,source_id=t['id'],pathogen=t['pathogen'],kind=t['kind'],cutoff=t['cutoff'],model=t['model'],seed=seed,flags=str(flags),support=t['support'],fit=t['fit'],command=command,**cell))
 plan=dict(version='classification_crosscheck_v1',verified=verified,inputs=inputs,tasks=tasks,absent_strata=absent,selection='earliest year then state in each observed flag/outcome stratum; no score selection',scientific_model_changed=False,accepted=False,independent_validation=False)
 (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');digest=sha(dest/'plan.json');q=shlex.quote;base='python3 '+q(str(dest/'scripts/launch_classification_crosscheck.py'))
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
 if (out/'status.txt').read_text().strip()!='CROSSCHECK_COMPLETE':raise ValueError('Incomplete crosscheck')
 identity=rows(out/'identity.csv')
 if len(identity)!=1 or any(identity[0].get(k)!=str(t[k]) for k in ('state','year','seed','observed_cidt','trials')) or identity[0].get('original_preserved')!='TRUE' or identity[0].get('accepted')!='FALSE':raise ValueError('Crosscheck identity mismatch')
 if int(identity[0]['row_id'])!=STATES.index(t['state'])*8+t['year']-2012+1:raise ValueError('Invalid row identity')
 d=rows(out/'comparison.csv')
 if len(d)!=1 or d[0]['state']!=t['state'] or int(d[0]['year'])!=t['year']:raise ValueError('Comparison identity mismatch')
 r=d[0]
 for key in ('original_cpo','original_failure'):
  a,b=number(r[key]),number(t[key])
  if not (a==b or (math.isnan(a) and math.isnan(b))):raise ValueError('Original diagnostic changed')
 for key in ('group_cv','explicit_log_score','explicit_relative_mcse','eb_log_score','eb_relative_mcse'):
  if not math.isfinite(number(r[key])):raise ValueError('Nonfinite comparison '+key)
 if not 0<number(r['group_cv'])<=1 or any(number(r[k])>0 for k in ('explicit_log_score','eb_log_score')) or any(number(r[k])<0 for k in ('explicit_relative_mcse','eb_relative_mcse')):raise ValueError('Invalid probability or precision')
 streams=rows(out/'stream_scores.csv')
 if len(streams)!=8 or {(s['method'],int(s['stream'])) for s in streams}!={(m,i) for m in ('full','eb') for i in range(1,5)}:raise ValueError('Incomplete posterior streams')
 for s in streams:
  if int(s['draws'])!=1000 or not math.isfinite(number(s['log_score'])) or number(s['log_score'])>0 or not math.isfinite(number(s['relative_mcse'])) or number(s['relative_mcse'])<0:raise ValueError('Invalid posterior stream')
 numerical=rows(out/'numerical.csv')
 if len(numerical)!=2 or {s['method'] for s in numerical}!={'full','eb'} or any(s['fit_ok']!='TRUE' or number(s['mode_status'])!=0 for s in numerical):raise ValueError('Explicit fit numerical failure')
 if any(not (out/n).is_file() for n in ('explicit_INTERNAL.rds','eb_INTERNAL.rds')):raise ValueError('Missing explicit fit')
 return dict(group_cv=number(r['group_cv']),explicit_log_score=number(r['explicit_log_score']),explicit_relative_mcse=number(r['explicit_relative_mcse']))

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
   for name in ('comparison.csv','stream_scores.csv'):
    merged.setdefault(name,[]).extend(dict(task=t['id'],pathogen=t['pathogen'],kind=t['kind'],model=t['model'],**x) for x in rows(work/'result'/name))
  except (OSError,ValueError,KeyError) as e:results.append(dict(task=t['id'],status='FAILED_OR_MISSING',reason=str(e)))
 for name,data in merged.items():
  with (dest/('all_'+name)).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 summary=dict(tasks=results,issues=issues,complete=sum(r['status']=='COMPLETE' for r in results),expected=len(plan['tasks']),absent_strata=plan['absent_strata'],scientific_model_changed=False,accepted=False,independent_validation=False)
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
 root=Path(__file__).resolve().parents[1];dest=root/'output'/('classification_crosscheck_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
 if not a.prepare_only and any(not shutil.which(t) for t in ('qsub','singularity')):p.error('Load singularity on SGE host')
 try:plan=prepare(root,dest,not a.prepare_only)
 except (OSError,ValueError,KeyError) as e:p.error(str(e))
 print('Output: '+str(dest),flush=True)
 if a.prepare_only:return 0
 base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y','-o',str(dest)]
 job=subprocess.check_output(base+['-N','foodnet_class_cross','-t','1-'+str(len(plan['tasks'])),'-pe','smp','4','-l','h_rt=06:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G',str(dest/'run.sh')],universal_newlines=True).strip()
 (dest/'submission.json').write_text(json.dumps(dict(array=job))+'\n');print('Diagnostic array: '+job,flush=True);match=re.match(r'^(\d+)(?:[.\s]|$)',job)
 if not match:raise ValueError('Unexpected scheduler response; inspect queue before retry')
 col=subprocess.check_output(base+['-N','foodnet_class_collect','-hold_jid',match.group(1),'-pe','smp','1','-l','h_rt=02:00:00,h_rss=4096M,mem_free=4096M,h_vmem=8G',str(dest/'collect.sh')],universal_newlines=True).strip()
 (dest/'submission.json').write_text(json.dumps(dict(array=job,collector=col))+'\n');print('Collector: '+col+'\nArchive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
