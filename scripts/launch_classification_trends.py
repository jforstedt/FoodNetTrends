#!/usr/bin/env python3
"""24 parallel conditional classification fits, no incidence adjustment."""
import argparse,csv,json,math,re,shlex,shutil,subprocess,sys,tarfile
from datetime import datetime
from pathlib import Path
import launch_eligible_diagnostics as audit
sha=audit.sha
SOURCE='eligible_diagnostics_20260914_094654_276977'
PATHOGENS=('SALMONELLA','CAMPYLOBACTER','SHIGELLA','STEC','VIBRIO','YERSINIA')
FILES=('launch_classification_trends.py','fit_classification_trends.R','launch_eligible_diagnostics.py','county_forecast_protocol.py')
def rows(p):
 with Path(p).open(newline='') as f:return list(csv.DictReader(f))
def prepare(root,dest,verified=True):
 root=Path(root).resolve();dest=Path(dest).resolve();origin=root/'output'/SOURCE;inputs={};container=root/'foodnet-inla-fixed.sif'
 if verified:
  old=json.loads((origin/'plan.json').read_text());oh=sha(origin/'plan.json')
  if not old['verified'] or old.get('models_fitted') is not False:raise ValueError('Unexpected source audit')
  inputs[str(origin/'plan.json')]=oh;inputs[str(container)]=sha(container)
  for pathogen in PATHOGENS:
   work=origin/pathogen;r=json.loads((work/'task_status.json').read_text())
   if r.get('task')!=pathogen or r.get('status')!='COMPLETE' or r.get('exit_status')!=0 or r.get('plan_sha256')!=oh:raise ValueError('Incomplete source '+pathogen)
   audit.validate_result(work)
   for n,h in r['outputs'].items():
    if sha(work/n)!=h:raise ValueError('Changed eligible report')
    inputs[str(work/n)]=h
   inputs[str(work/'task_status.json')]=sha(work/'task_status.json')
 dest.mkdir(parents=True,exist_ok=False);(dest/'scripts').mkdir()
 for n in FILES:
  p=dest/'scripts'/n;shutil.copyfile(str(root/'scripts'/n),str(p));inputs[str(p)]=sha(p)
 protocol=dest/'classification_trends.md';shutil.copyfile(str(root/'docs/classification_trends.md'),str(protocol));inputs[str(protocol)]=sha(protocol)
 tasks=[]
 for pathogen in PATHOGENS:
  for kind,cutoff in (('hindcast',2016),('description',2019)):
   for model in ('shared','site_slopes'):
    name=pathogen+'_'+kind+'_'+model;seed=300000000+len(tasks)*1000000
    cmd=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/'scripts/fit_classification_trends.R'),str(origin/pathogen/'result/support.csv'),str(dest/name/'result'),str(cutoff),model,str(seed)]
    tasks.append(dict(id=name,pathogen=pathogen,kind=kind,cutoff=cutoff,model=model,seed=seed,command=cmd))
 plan=dict(version='classification_trends_v1',verified=verified,inputs=inputs,tasks=tasks,incidence_adjustment=False,independent_validation=False,accepted=False)
 (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');digest=sha(dest/'plan.json');q=shlex.quote;base='python3 '+q(str(dest/'scripts/launch_classification_trends.py'))
 script='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-undefined}" in\n'
 for i,t in enumerate(tasks,1):script+=str(i)+') task='+t['id']+';;\n'
 script+='*) exit 2;;\nesac\nexec '+base+' --worker '+q(str(dest))+' --task "$task" --digest '+digest+'\n'
 (dest/'run.sh').write_text(script);(dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+base+' --collect '+q(str(dest))+' --digest '+digest+'\n');return plan

def verify(dest,plan,digest):
 if not plan['verified'] or sha(dest/'plan.json')!=digest:raise ValueError('Unverified or changed plan')
 for p,h in plan['inputs'].items():
  if sha(p)!=h:raise ValueError('Changed input/source '+p)
def validate(work,t):
 out=work/'result'
 if (out/'status.txt').read_text().strip()!='CLASSIFICATION_FIT_COMPLETE':raise ValueError('Incomplete fit')
 numerical=rows(out/'numerical.csv')
 if len(numerical)!=1 or numerical[0]['fit_ok']!='TRUE' or float(numerical[0]['mode_status'])!=0 or not math.isfinite(float(numerical[0]['waic'])):raise ValueError('Numerical fit gate failed')
 s=rows(out/'settings.csv')
 if len(s)!=1 or int(s[0]['cutoff'])!=t['cutoff'] or s[0]['model']!=t['model'] or int(s[0]['seed'])!=t['seed'] or int(s[0]['streams'])!=4 or int(s[0]['draws_per_stream'])!=500 or s[0]['classification_target']!='TRUE' or s[0]['incidence_adjustment']!='FALSE' or s[0]['independent_validation']!='FALSE':raise ValueError('Settings mismatch')
 p=rows(out/'predictions.csv');keys={(s,y) for s in ('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN') for y in range(2012,2020)}
 if len(p)!=80 or {(r['state'],int(r['year'])) for r in p}!=keys:raise ValueError('Incomplete site/year domain')
 for r in p:
  v={k:float(r[k]) for k in ('observed_cidt','trials','observed_share','mean_probability','lower_probability','median_probability','upper_probability','lower_predictive','median_predictive','upper_predictive')}
  if any(not math.isfinite(x) for x in v.values()) or not 0<=v['observed_cidt']<=v['trials'] or v['trials']<=0 or not 0<=v['lower_probability']<=v['median_probability']<=v['upper_probability']<=1 or not 0<=v['mean_probability']<=1 or not 0<=v['lower_predictive']<=v['median_predictive']<=v['upper_predictive']<=v['trials']:raise ValueError('Invalid classification interval')
  if v['trials']!=int(v['trials']) or v['observed_cidt']!=int(v['observed_cidt']) or not math.isclose(v['observed_share'],v['observed_cidt']/v['trials'],abs_tol=1e-12):raise ValueError('Invalid observed proportion')
  if r['evaluation']!=('CONDITIONAL_HINDCAST' if int(r['year'])>t['cutoff'] else 'IN_SAMPLE_DESCRIPTION'):raise ValueError('Wrong evaluation label')
 scoring=rows(out/'scoring_input.csv')
 observed={(r['state'],r['year']):(float(r['observed_cidt']),float(r['trials'])) for r in p}
 if len(scoring)!=80 or {(r['state'],r['year']):(float(r['cidt_classified']),float(r['trials'])) for r in scoring}!=observed:raise ValueError('Scoring input mismatch')
 source=rows(Path(t['command'][-5]))
 expected={(r['state'],r['year']):(float(r['cidt_classified']),float(r['classification_denominator'])) for r in source if 2012<=int(r['year'])<=2019}
 if observed!=expected:raise ValueError('Source outcome mismatch')
 annual=rows(out/'annual.csv')
 if len(annual)!=8 or {int(r['year']) for r in annual}!=set(range(2012,2020)):raise ValueError('Incomplete annual domain')
 for r in annual:
  y=int(r['year']);n=sum(v[1] for k,v in observed.items() if int(k[1])==y);count=sum(v[0] for k,v in observed.items() if int(k[1])==y)
  if float(r['trials'])!=n or float(r['observed_cidt'])!=count or not 0<=float(r['lower_predictive'])<=float(r['median_predictive'])<=float(r['upper_predictive'])<=n or not 0<=float(r['mean_predicted_cidt'])<=n:raise ValueError('Invalid annual aggregate')
 scores=rows(out/'stream_scores.csv')
 if len(scores)!=400 or {(r['state'],int(r['year']),int(r['stream'])) for r in scores}!={k+(s,) for k in keys for s in range(5)}:raise ValueError('Incomplete score streams')
 for r in scores:
  if int(r['draws'])!=(2000 if r['stream']=='0' else 500) or not math.isfinite(float(r['log_score'])) or not math.isfinite(float(r['density_relative_mcse'])) or float(r['density_relative_mcse'])<0:raise ValueError('Invalid sampling diagnostic')
 if re.search(r'vb[.]correction[^\n]*aborted',(out/'warnings.txt').read_text(),re.I):raise ValueError('Aborted VB correction')
 if not(out/'fit_INTERNAL.rds').is_file():raise ValueError('Missing fit checkpoint')

def worker(dest,name,digest):
 dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());t=next(t for t in plan['tasks'] if t['id']==name);work=dest/name;work.mkdir(exist_ok=False);r=dict(task=name,status='FAILED',exit_status=1,plan_sha256=digest)
 try:
  verify(dest,plan,digest)
  with (work/'task.log').open('w') as log:code=subprocess.call(t['command'],stdout=log,stderr=subprocess.STDOUT)
  if code:raise ValueError('R exit '+str(code))
  validate(work,t);verify(dest,plan,digest)
  r.update(status='COMPLETE',exit_status=0,outputs={str(p.relative_to(work)):sha(p) for p in work.rglob('*') if p.is_file()})
 except (OSError,ValueError,KeyError) as e:r['reason']=str(e)
 (work/'task_status.json').write_text(json.dumps(r,indent=2)+'\n');return r['exit_status']
def collect(dest,digest):
 dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());results=[];issues=[];scores=[];predictions=[];valid={}
 try:verify(dest,plan,digest)
 except (OSError,ValueError,KeyError) as e:issues.append(str(e))
 for t in plan['tasks']:
  work=dest/t['id']
  try:
   r=json.loads((work/'task_status.json').read_text())
   if r.get('status')!='COMPLETE' or r.get('task')!=t['id'] or r.get('plan_sha256')!=digest or r.get('exit_status')!=0:raise ValueError(r.get('reason','Incomplete task'))
   validate(work,t)
   if not r.get('outputs') or any(sha(work/n)!=h for n,h in r['outputs'].items()):raise ValueError('Changed completed output')
   valid[t['id']]=r;results.append(dict(task=t['id'],status='COMPLETE'))
   for file,target in (('stream_scores.csv',scores),('predictions.csv',predictions)):
    target.extend(dict(task=t['id'],pathogen=t['pathogen'],kind=t['kind'],model=t['model'],**x) for x in rows(work/'result'/file))
  except (OSError,ValueError,KeyError) as e:results.append(dict(task=t['id'],status='FAILED_OR_MISSING',reason=str(e)))
 for p in PATHOGENS:
  for kind in ('hindcast','description'):
   a=p+'_'+kind+'_shared';b=p+'_'+kind+'_site_slopes'
   if a in valid and b in valid and valid[a]['outputs']['result/scoring_input.csv']!=valid[b]['outputs']['result/scoring_input.csv']:issues.append('Paired scoring inputs differ: '+p+' '+kind)
 for name,data in (('all_scores.csv',scores),('all_predictions.csv',predictions)):
  if data:
   with (dest/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 summary=dict(tasks=results,issues=issues,complete=sum(r['status']=='COMPLETE' for r in results),expected=24,incidence_adjustment=False,accepted=False,independent_validation=False)
 (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh','.md') and '_INTERNAL' not in p.name and p.name!='report_sha256.json']
 (dest/'report_sha256.json').write_text(json.dumps({str(p.relative_to(dest)):sha(p) for p in files},indent=2)+'\n')
 with tarfile.open(str(dest)+'.tar.gz','w:gz') as arc:
  for p in files+[dest/'report_sha256.json']:arc.add(str(p),arcname=str(p.relative_to(dest)))
 print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz');return 0 if summary['complete']==24 and not issues else 1

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-only',action='store_true');p.add_argument('--worker');p.add_argument('--task');p.add_argument('--collect');p.add_argument('--digest');a=p.parse_args()
 if a.worker or a.collect:
  if not a.digest or (a.worker and not a.task):p.error('Missing identity')
  return worker(a.worker,a.task,a.digest) if a.worker else collect(a.collect,a.digest)
 root=Path(__file__).resolve().parents[1];dest=root/'output'/('classification_trends_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
 if not a.prepare_only and any(not shutil.which(t) for t in ('qsub','singularity')):p.error('Load singularity on SGE host')
 try:prepare(root,dest,not a.prepare_only)
 except (OSError,ValueError,KeyError) as e:p.error(str(e))
 print('Output: '+str(dest),flush=True)
 if a.prepare_only:return 0
 base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y','-o',str(dest)]
 job=subprocess.check_output(base+['-N','foodnet_classification','-t','1-24','-pe','smp','4','-l','h_rt=12:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G',str(dest/'run.sh')],universal_newlines=True).strip()
 (dest/'submission.json').write_text(json.dumps(dict(array=job))+'\n');print('Fit array: '+job,flush=True);match=re.match(r'^(\d+)(?:[.\s]|$)',job)
 if not match:raise ValueError('Unexpected scheduler response; inspect queue before retry')
 col=subprocess.check_output(base+['-N','foodnet_class_collect','-hold_jid',match.group(1),'-pe','smp','1','-l','h_rt=02:00:00,h_rss=4096M,mem_free=4096M,h_vmem=8G',str(dest/'collect.sh')],universal_newlines=True).strip()
 (dest/'submission.json').write_text(json.dumps(dict(array=job,collector=col))+'\n');print('Collector: '+col+'\nArchive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
