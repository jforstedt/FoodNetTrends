#!/usr/bin/env python3
"""Inspect 24 saved classification fits and resample 12 hindcasts in parallel."""
import argparse,csv,hashlib,json,math,re,shlex,shutil,subprocess,sys,tarfile
from datetime import datetime
from pathlib import Path
SOURCE='classification_trends_20260914_100228_401966'
PATHOGENS=('SALMONELLA','CAMPYLOBACTER','SHIGELLA','STEC','VIBRIO','YERSINIA')
STATES=('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN')
FILES=('launch_classification_diagnostics.py','diagnose_classification_saved.R','fit_classification_trends.R')
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
def rows(path):
 with Path(path).open(newline='') as f:return list(csv.DictReader(f))
def prepare(root,dest,verified=True):
 root=Path(root).resolve();dest=Path(dest).resolve();origin=root/'output'/SOURCE;container=root/'foodnet-inla-fixed.sif';inputs={}
 if verified:
  old=json.loads((origin/'plan.json').read_text());oh=sha(origin/'plan.json')
  if old.get('version')!='classification_trends_v1' or not old.get('verified'):raise ValueError('Unexpected source plan')
  inputs[str(origin/'plan.json')]=oh
  if old['inputs'].get(str(container))!=sha(container):raise ValueError('Source container changed')
  inputs[str(container)]=sha(container)
  original={t['id']:t for t in old['tasks']}
  expected={p+'_'+k+'_'+m for p in PATHOGENS for k in ('hindcast','description') for m in ('shared','site_slopes')}
  if len(old['tasks'])!=24 or set(original)!=expected:raise ValueError('Source task domain differs')
 else:original={}
 dest.mkdir(parents=True,exist_ok=False);(dest/'scripts').mkdir()
 for n in FILES:
  p=dest/'scripts'/n;shutil.copyfile(str(root/'scripts'/n),str(p));inputs[str(p)]=sha(p)
 protocol=dest/'classification_saved_diagnostics.md';shutil.copyfile(str(root/'docs/classification_saved_diagnostics.md'),str(protocol));inputs[str(protocol)]=sha(protocol)
 tasks=[]
 for pathogen in PATHOGENS:
  for kind,cutoff in (('hindcast',2016),('description',2019)):
   for model in ('shared','site_slopes'):
    source_id=pathogen+'_'+kind+'_'+model;work=origin/source_id;fit=work/'result/fit_INTERNAL.rds'
    support=root/'output/eligible_diagnostics_20260914_094654_276977'/pathogen/'result/support.csv'
    if verified:
     t=original[source_id];support=Path(t['command'][-5]);record=work/'task_status.json';r=json.loads(record.read_text())
     if any(t.get(k)!=v for k,v in (('pathogen',pathogen),('kind',kind),('cutoff',cutoff),('model',model))):raise ValueError('Source identity mismatch')
     if r.get('task')!=source_id or r.get('status')!='COMPLETE' or r.get('exit_status')!=0 or r.get('plan_sha256')!=oh:raise ValueError('Incomplete source '+source_id)
     if r.get('outputs',{}).get('result/fit_INTERNAL.rds')!=sha(fit):raise ValueError('Saved fit changed')
     if old['inputs'].get(str(support))!=sha(support):raise ValueError('Source support changed')
     settings=work/'result/settings.csv'
     if r['outputs'].get('result/settings.csv')!=sha(settings):raise ValueError('Source settings changed')
     s=rows(settings)
     if len(s)!=1 or int(s[0]['cutoff'])!=cutoff or s[0]['model']!=model or int(s[0]['seed'])!=t['seed']:raise ValueError('Source settings identity mismatch')
     for p in (fit,support,record,settings):inputs[str(p)]=sha(p)
    for mode in (('inspect','precision') if kind=='hindcast' else ('inspect',)):
     name=source_id+'_'+mode;seed=600000000+len(tasks)*1000000
     command=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/'scripts/diagnose_classification_saved.R'),str(fit),str(support),str(dest/name/'result'),str(cutoff),model,str(seed),mode]
     tasks.append(dict(id=name,source_id=source_id,pathogen=pathogen,kind=kind,cutoff=cutoff,model=model,seed=seed,mode=mode,support=str(support),fit=str(fit),command=command))
 plan=dict(version='classification_saved_diagnostics_v1',verified=verified,inputs=inputs,tasks=tasks,models_refitted=False,accepted=False,independent_validation=False)
 (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');digest=sha(dest/'plan.json');q=shlex.quote;base='python3 '+q(str(dest/'scripts/launch_classification_diagnostics.py'))
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
 if (out/'status.txt').read_text().strip()!='DIAGNOSTICS_COMPLETE':raise ValueError('Incomplete diagnostics')
 s=rows(out/'identity.csv');draws=2500 if t['mode']=='precision' else 0
 if len(s)!=1 or any(s[0].get(k)!=str(t[k]) for k in ('cutoff','model','seed','mode')) or int(s[0]['rows'])!=80 or int(s[0]['draws_per_stream'])!=draws or s[0].get('refitted')!='FALSE' or s[0].get('accepted')!='FALSE':raise ValueError('Diagnostic identity mismatch')
 keys={(state,y) for state in STATES for y in range(2012,2020)}
 source={(r['state'],int(r['year'])):(float(r['cidt_classified']),float(r['classification_denominator'])) for r in rows(t['support']) if 2012<=int(r['year'])<=2019}
 if set(source)!=keys:raise ValueError('Source domain mismatch')
 def domain(data):
  if len(data)!=80 or {(r['state'],int(r['year'])) for r in data}!=keys:raise ValueError('Incomplete row domain')
 def finite(x):return math.isfinite(float(x))
 if t['mode']=='inspect':
  d=rows(out/'row_diagnostics.csv');domain(d)
  for r in d:
   k=(r['state'],int(r['year']))
   if r['observed']!=('TRUE' if k[1]<=t['cutoff'] else 'FALSE'):raise ValueError('Observed mask mismatch')
   for name in ('cpo_failure','cpo','pit'):
    if r[name] not in ('','NA'):float(r[name]) # Preserve numerical diagnostic failures as findings.
  summary=rows(out/'summary.csv')
  if not rows(out/'hyperparameters.csv') or len(summary)!=2 or {r['observed'] for r in summary}!={'TRUE','FALSE'}:raise ValueError('Missing fit inspection')
  for r in summary:
   subset=[x for x in d if x['observed']==r['observed']]
   if int(r['rows'])!=len(subset):raise ValueError('Summary mask mismatch')
   number=lambda x:float('nan') if x in ('','NA','NaN') else float(x)
   expected=dict(flagged=sum(number(x['cpo_failure'])>0 for x in subset),missing_failure=sum(math.isnan(number(x['cpo_failure'])) for x in subset),nonfinite_cpo=sum(not math.isfinite(number(x['cpo'])) for x in subset),nonpositive_cpo=sum(number(x['cpo'])<=0 for x in subset))
   if any(int(r[k])!=v for k,v in expected.items()):raise ValueError('Inspection summary differs from rows')
 else:
  d=rows(out/'predictions.csv');domain(d)
  for r in d:
   k=(r['state'],int(r['year']));y,n=source[k]
   if float(r['observed_cidt'])!=y or float(r['trials'])!=n:raise ValueError('Observed count mismatch')
   if r['evaluation']!=('CONDITIONAL_HINDCAST' if k[1]>t['cutoff'] else 'IN_SAMPLE_DESCRIPTION'):raise ValueError('Wrong evaluation label')
   for name in ('mean_probability','lower_probability','median_probability','upper_probability'):
    if not finite(r[name]) or not 0<=float(r[name])<=1:raise ValueError('Invalid probability')
   if not float(r['lower_probability'])<=float(r['median_probability'])<=float(r['upper_probability']):raise ValueError('Reversed interval')
   if not 0<=float(r['lower_predictive'])<=float(r['median_predictive'])<=float(r['upper_predictive'])<=n:raise ValueError('Invalid predictive interval')
  scores=rows(out/'stream_scores.csv')
  if len(scores)!=400 or {(r['state'],int(r['year']),int(r['stream'])) for r in scores}!={k+(s,) for k in keys for s in range(5)}:raise ValueError('Incomplete score streams')
  for r in scores:
   if int(r['draws'])!=(10000 if int(r['stream'])==0 else 2500) or not finite(r['log_score']) or float(r['log_score'])>1e-10 or not finite(r['density_relative_mcse']) or float(r['density_relative_mcse'])<0:raise ValueError('Invalid score')
  annual=rows(out/'annual.csv')
  if len(annual)!=8 or {int(r['year']) for r in annual}!=set(range(2012,2020)):raise ValueError('Incomplete annual domain')
  for r in annual:
   year=int(r['year']);y=sum(v[0] for k,v in source.items() if k[1]==year);n=sum(v[1] for k,v in source.items() if k[1]==year)
   if float(r['trials'])!=n or float(r['observed_cidt'])!=y or not 0<=float(r['mean_predicted_cidt'])<=n or not 0<=float(r['lower_predictive'])<=float(r['median_predictive'])<=float(r['upper_predictive'])<=n:raise ValueError('Invalid annual aggregate')

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
   results.append(dict(task=t['id'],status='COMPLETE'))
   for name in (('row_diagnostics.csv','summary.csv') if t['mode']=='inspect' else ('stream_scores.csv','predictions.csv','annual.csv')):
    merged.setdefault(name,[]).extend(dict(task=t['id'],pathogen=t['pathogen'],kind=t['kind'],model=t['model'],**x) for x in rows(work/'result'/name))
  except (OSError,ValueError,KeyError) as e:results.append(dict(task=t['id'],status='FAILED_OR_MISSING',reason=str(e)))
 for name,data in merged.items():
  with (dest/('all_'+name)).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 summary=dict(tasks=results,issues=issues,complete=sum(r['status']=='COMPLETE' for r in results),expected=36,models_refitted=False,accepted=False,independent_validation=False)
 (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh','.md') and '_INTERNAL' not in p.name and p.name!='report_sha256.json']
 (dest/'report_sha256.json').write_text(json.dumps({str(p.relative_to(dest)):sha(p) for p in files},indent=2)+'\n')
 with tarfile.open(str(dest)+'.tar.gz','w:gz') as arc:
  for p in files+[dest/'report_sha256.json']:arc.add(str(p),arcname=str(p.relative_to(dest)))
 print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz');return 0 if summary['complete']==36 and not issues else 1

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-only',action='store_true');p.add_argument('--worker');p.add_argument('--task');p.add_argument('--collect');p.add_argument('--digest');a=p.parse_args()
 if a.worker or a.collect:
  if not a.digest or (a.worker and not a.task):p.error('Missing identity')
  return worker(a.worker,a.task,a.digest) if a.worker else collect(a.collect,a.digest)
 root=Path(__file__).resolve().parents[1];dest=root/'output'/('classification_diagnostics_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
 if not a.prepare_only and any(not shutil.which(t) for t in ('qsub','singularity')):p.error('Load singularity on SGE host')
 try:prepare(root,dest,not a.prepare_only)
 except (OSError,ValueError,KeyError) as e:p.error(str(e))
 print('Output: '+str(dest),flush=True)
 if a.prepare_only:return 0
 base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y','-o',str(dest)]
 job=subprocess.check_output(base+['-N','foodnet_class_diag','-t','1-36','-pe','smp','2','-l','h_rt=06:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G',str(dest/'run.sh')],universal_newlines=True).strip()
 (dest/'submission.json').write_text(json.dumps(dict(array=job))+'\n');print('Diagnostic array: '+job,flush=True);match=re.match(r'^(\d+)(?:[.\s]|$)',job)
 if not match:raise ValueError('Unexpected scheduler response; inspect queue before retry')
 col=subprocess.check_output(base+['-N','foodnet_class_collect','-hold_jid',match.group(1),'-pe','smp','1','-l','h_rt=02:00:00,h_rss=4096M,mem_free=4096M,h_vmem=8G',str(dest/'collect.sh')],universal_newlines=True).strip()
 (dest/'submission.json').write_text(json.dumps(dict(array=job,collector=col))+'\n');print('Collector: '+col+'\nArchive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
