#!/usr/bin/env python3
"""Launch the frozen monthly conditional-classification comparison in parallel."""
import argparse,csv,json,math,re,shlex,shutil,subprocess,sys,tarfile
from datetime import datetime
from pathlib import Path
import launch_classification_monthly_preparation as prep
sha=prep.sha
SOURCE='broader_combinations_20260914_130328_942214'
STATES=('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN')
FILES=tuple(dict.fromkeys(prep.monthly.FILES+prep.FILES+('launch_monthly_classification_models.py','run_monthly_classification_models.R','monthly_classification_model.R','audit_monthly_classification.R','monthly_spatial_combination.R','check_monthly_classification_priors.R','audit_saved_forecast_sampling.R')))
VERSION='monthly_classification_models_v1'
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def rows(p):return prep.rows(p)
def matrix():
 ts=[]
 for p in prep.PATHOGENS:
  for c in (2015,2016):
   for level,spatial in (('site','none'),('county','iid'),('county','bym2')):
    for temporal in ('rw1','ar1'):
     for seasonal in (False,True):
      name='{}_{}_{}_{}_{}_{}'.format(p,c,level,spatial,temporal,'seasonal' if seasonal else 'nonseasonal')
      ts.append(dict(id=name,pathogen=p,cutoff=c,level=level,spatial=spatial,temporal=temporal,seasonal=seasonal,seed=110000000+len(ts)*1000000))
 return ts

def inside(root,name):
 p=Path(name)
 if p.is_absolute() or '..' in p.parts or root.resolve() not in (root/p).resolve().parents:raise ValueError('Unsafe source artifact')
 return root/p

def verify_prior(root):
 folder=root/'analysis_configs/monthly_classification_priors';manifest=folder/'manifest.json';m=json.loads(manifest.read_text())
 if m.get('version')!='monthly_classification_priors_v1' or m.get('status')!='PRIOR_CHECK_PASS':raise ValueError('Prior checks not frozen')
 required={'scripts/monthly_classification_model.R','scripts/check_monthly_classification_priors.R','scripts/monthly_spatial_combination.R','analysis_configs/county_pilot/counties.csv','analysis_configs/county_pilot/edges.csv'}
 if not required.issubset(m.get('sources',{})) or not m.get('files'):raise ValueError('Incomplete prior-check provenance')
 for name,h in m['sources'].items():
  if sha(inside(root,name))!=h:raise ValueError('Changed prior-check source: '+name)
 files={str(manifest):sha(manifest)}
 for name,h in m['files'].items():
  p=inside(folder,name)
  if sha(p)!=h:raise ValueError('Changed prior report')
  files[str(p)]=h
 return files

def prepare(root,dest,verified=True):
 root=Path(root).resolve();dest=Path(dest).resolve();origin=root/'output'/SOURCE/'classification';inputs={};source_tasks={}
 if dest.exists():raise FileExistsError(str(dest))
 if verified:
  previous=json.loads((origin/'plan.json').read_text());digest=sha(origin/'plan.json');prep.verify(origin,previous,digest)
  summary=json.loads((origin/'summary.json').read_text())
  if summary.get('execution_complete') is not True or summary.get('issues') or {r['task'] for r in summary['tasks'] if r['status']=='COMPLETE'}!=set(prep.PATHOGENS) or len(summary['tasks'])!=6:raise ValueError('Source preparations incomplete')
  inputs.update({str(origin/n):sha(origin/n) for n in ('plan.json','summary.json')})
  for t in previous['tasks']:
   work=origin/t['id'];record=json.loads((work/'task_status.json').read_text())
   if record.get('task')!=t['id'] or record.get('status')!='COMPLETE' or record.get('exit_status')!=0 or record.get('plan_sha256')!=digest:raise ValueError('Source task identity differs')
   prep.validate(work,t);bound={str(work/'task_status.json'):sha(work/'task_status.json'),str(Path(t['annual_support'])):sha(t['annual_support'])}
   required={'result/classification_site.csv','result/classification_county_month_INTERNAL.rds','result/classification_annual.csv','result/classification_date_issues_by_category.csv','result/classification_readiness.csv','result/date_issues.csv','result/source_month_comparison.csv'}
   if not required.issubset(record.get('outputs',{})):raise ValueError('Unbound required source input')
   for n,h in record['outputs'].items():
    p=inside(work,n)
    if sha(p)!=h:raise ValueError('Changed source output')
    bound[str(p)]=h
   # The declared specimen-month target remains unchanged; absent auxiliary month is not a missing specimen date.
   date=rows(work/'result/date_issues.csv')
   if any(float(r[k]) for r in date for k in ('missing_specimen_date','specimen_year_disagreement','unassigned_records')):raise ValueError('Unassigned specimen dates')
   disagreements=sum(int(r['month_disagreement']) for r in date)
   if disagreements!={'SALMONELLA':1,'SHIGELLA':2}.get(t['id'],0):raise ValueError('Unreviewed specimen/source-month disagreements')
   source_tasks[t['id']]=bound
 prior_inputs=verify_prior(root) if verified else {}
 dest.mkdir(parents=True);(dest/'scripts').mkdir()
 for original,h in prior_inputs.items():
  source=Path(original);p=dest/'prior_checks'/source.name;p.parent.mkdir(exist_ok=True);shutil.copyfile(str(source),str(p));inputs[str(p)]=h
  if sha(p)!=h:raise ValueError('Prior report changed during snapshot')
 for n in FILES:
  p=dest/'scripts'/n;shutil.copyfile(str(root/'scripts'/n),str(p));inputs[str(p)]=sha(p)
 for n in ('classification_combination_protocol.md','monthly_classification_launch.md'):
  p=dest/n;shutil.copyfile(str(root/'docs'/n),str(p));inputs[str(p)]=sha(p)
 for n in ('counties.csv','edges.csv','provenance.json'):
  p=dest/'geography'/n;p.parent.mkdir(exist_ok=True);shutil.copyfile(str(root/'analysis_configs/county_pilot'/n),str(p));inputs[str(p)]=sha(p)
 if prior_inputs:
  prior_manifest=json.loads((dest/'prior_checks/manifest.json').read_text())
  for name,h in prior_manifest['sources'].items():
   copied=dest/'scripts'/Path(name).name if name.startswith('scripts/') else dest/'geography'/Path(name).name
   if not copied.is_file() or sha(copied)!=h:raise ValueError('Prior source and model snapshot differ')
 container=root/'foodnet-inla-fixed.sif'
 if verified:inputs[str(container)]=sha(container)
 tasks=matrix()
 for t in tasks:
  source=origin/t['pathogen']/'result';panel=source/('classification_site.csv' if t['level']=='site' else 'classification_county_month_INTERNAL.rds')
  t.update(inputs=source_tasks.get(t['pathogen'],{}),site_reference=str(source/'classification_site.csv'))
  t['command']=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=4','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/'scripts/run_monthly_classification_models.R'),str(panel),t['level'],t['temporal'],str(t['seasonal']).upper(),t['spatial'],str(t['cutoff']),str(dest/t['id']/'result'),str(t['seed']),str(dest/'geography/counties.csv'),str(dest/'geography/edges.csv')]
 plan=dict(version=VERSION,verified=verified,source=str(origin),inputs=inputs,tasks=tasks,incidence_adjustment=False,scientific_acceptance=False,coverage_certified=False,independent_validation=False,conditional_future_denominator=True,site_fits=48,county_fits=96,total_fits=144)
 if verified:plan['source_provenance']=previous['inputs']
 write(dest/'plan.json',plan);digest=sha(dest/'plan.json');q=shlex.quote;base='python3 '+q(str(dest/'scripts/launch_monthly_classification_models.py'))
 shell='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-undefined}" in\n'
 for i,t in enumerate(tasks,1):shell+=str(i)+') task='+t['id']+';;\n'
 shell+='*) exit 2;;\nesac\nexec '+base+' --worker '+q(str(dest))+' --task "$task" --digest '+digest+'\n'
 (dest/'run.sh').write_text(shell);(dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+base+' --collect '+q(str(dest))+' --digest '+digest+'\n');return plan

def verify(dest,plan,digest,task=None):
 if plan.get('version')!=VERSION or plan.get('verified') is not True or sha(dest/'plan.json')!=digest:raise ValueError('Unverified or changed model plan')
 expected=matrix()
 if (plan.get('site_fits'),plan.get('county_fits'),plan.get('total_fits'))!=(48,96,144) or plan.get('conditional_future_denominator') is not True:raise ValueError('Changed comparison scope')
 if len(plan['tasks'])!=144 or [t['id'] for t in plan['tasks']]!=[t['id'] for t in expected]:raise ValueError('Model matrix differs')
 for actual,want in zip(plan['tasks'],expected):
  if any(actual.get(k)!=v for k,v in want.items()):raise ValueError('Model identity differs')
 for k in ('incidence_adjustment','scientific_acceptance','coverage_certified','independent_validation'):
  if plan.get(k) is not False:raise ValueError('Scientific metadata changed')
 for p,h in dict(plan['inputs'],**(task['inputs'] if task else {})).items():
  if sha(p)!=h:raise ValueError('Changed frozen input: '+p)

def integer(x):
 n=float(x)
 if not math.isfinite(n) or n<0 or int(n)!=n:raise ValueError('Invalid count/index')
 return int(n)
def number(x):
 n=float(x)
 if not math.isfinite(n):raise ValueError('Nonfinite metric')
 return n

def validate(work,t):
 out=work/'result'
 if (out/'status.txt').read_text().strip()!='MONTHLY_CLASSIFICATION_MODEL_COMPLETE':raise ValueError('Incomplete classification fit')
 settings=rows(out/'settings.csv')
 if len(settings)!=1:raise ValueError('Missing unique settings')
 r=settings[0]
 for k in ('level','temporal','spatial'):
  if r[k]!=t[k]:raise ValueError('Changed fitted '+k)
 for k,v in dict(cutoff=t['cutoff'],base_seed=t['seed'],streams=4,draws_per_stream=2000,train_start=2012,horizon=36).items():
  if integer(r[k])!=v:raise ValueError('Changed sampling '+k)
 if r['seasonal']!=str(t['seasonal']).upper() or any(r[k]!='FALSE' for k in ('coverage_certified','incidence_adjustment','independent_validation')) or r['target']!='CIDT_CLASSIFICATION_GIVEN_ELIGIBLE_CX_OR_CIDT' or r['rng_protocol']!='explicit_config_v2' or r['fitting_threads']!='4:1':raise ValueError('Changed fitted flags')
 if not (out/'fit_INTERNAL.rds').is_file() or not (out/'rng_protocol.csv').is_file() or not (out/'input_checksums.csv').is_file():raise ValueError('Missing saved fit or sampling provenance')
 diagnostics=rows(out/'fit_diagnostics.csv')
 if len(diagnostics)!=1 or diagnostics[0]['fit_ok']!='TRUE' or integer(diagnostics[0]['mode_status'])!=0:raise ValueError('Numerical quality gate failed')
 # Independent site/year category totals provide the common paired identity for both resolutions.
 truth={};site_eligible={}
 for r in rows(t['site_reference']):
  year=integer(r['year'])
  if t['cutoff']<year<=t['cutoff']+3:
   key=(r['state'],year);n,y=truth.get(key,(0,0));truth[key]=(n+integer(r['classification_denominator']),y+integer(r['cidt_classified']));site_eligible[key]=site_eligible.get(key,0)+int(integer(r['classification_denominator'])>0)
 if set(truth)!={(s,y) for s in STATES for y in range(t['cutoff']+1,t['cutoff']+4)}:raise ValueError('Reference truth domain differs')
 for y in range(t['cutoff']+1,t['cutoff']+4):truth[('ALL',y)]=tuple(sum(truth[(s,y)][i] for s in STATES) for i in (0,1))
 seen=set();eligibility={}
 for r in rows(out/'aggregate_predictions.csv'):
  key=(r['state'],integer(r['year']),integer(r['stream']));n=integer(r['denominator']);observed=integer(r['observed'])
  if key in seen or key[:2] not in truth or key[2] not in range(5) or (n,observed)!=truth[key[:2]] or integer(r['draws'])!=(8000 if key[2]==0 else 2000):raise ValueError('Aggregate identity differs')
  seen.add(key)
  e=integer(r['eligible_cells']);bound=min(n,12*(1 if t['level']=='site' else 486)*(10 if key[0]=='ALL' and t['level']=='site' else 1))
  if e>bound or (e==0)!=(n==0) or (key[:2] in eligibility and eligibility[key[:2]]!=e):raise ValueError('Aggregate eligible-cell count differs')
  eligibility[key[:2]]=e
  if t['level']=='site' and key[0]!='ALL' and e!=site_eligible[key[:2]]:raise ValueError('Site eligible-cell count differs')
  for k in ('mean_expected','median_expected','lower95','median_predictive','upper95'):
   if not 0<=number(r[k])<=n:raise ValueError('Invalid binomial prediction')
  if not number(r['lower95'])<=number(r['median_predictive'])<=number(r['upper95']):raise ValueError('Invalid predictive interval')
 if seen!={(s,y,k) for s,y in truth for k in range(5)}:raise ValueError('Missing aggregate rows')
 for year in range(t['cutoff']+1,t['cutoff']+4):
  if eligibility[('ALL',year)]!=sum(eligibility[(state,year)] for state in STATES):raise ValueError('ALL eligible-cell sum differs')
 seen=set()
 for r in rows(out/'stream_scores.csv'):
  key=(r['state'],integer(r['year']),integer(r['stream']))
  if key in seen or key[:2] not in truth or key[0]=='ALL' or key[2] not in range(5):raise ValueError('Invalid score identity')
  seen.add(key)
  if integer(r['draws'])!=(8000 if key[2]==0 else 2000):raise ValueError('Invalid score draws')
  eligible=integer(r['eligible_cells'])
  if eligible!=eligibility[key[:2]] or (eligible==0)!=(truth[key[:2]][0]==0):raise ValueError('Score information differs from denominator')
  if not eligible:
   if r['mean_log_score'] not in ('','NA') or r['max_cell_density_relative_mcse'] not in ('','NA'):raise ValueError('Undefined score must remain missing')
  elif number(r['mean_log_score'])>1e-12 or number(r['max_cell_density_relative_mcse'])<0:raise ValueError('Invalid score value')
 if seen!={(s,y,k) for (s,y),(n,_) in truth.items() if s!='ALL' for k in range(5)}:raise ValueError('Missing scored state/year')
 return True

def worker(dest,name,digest):
 dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());task=next(t for t in plan['tasks'] if t['id']==name);work=dest/name;work.mkdir(exist_ok=False);record=dict(task=name,status='FAILED',exit_status=1,plan_sha256=digest)
 try:
  verify(dest,plan,digest,task)
  with (work/'task.log').open('w') as log:code=subprocess.call(task['command'],stdout=log,stderr=subprocess.STDOUT,cwd=str(dest))
  if code:raise ValueError('Model exit '+str(code))
  validate(work,task);verify(dest,plan,digest,task)
  record.update(status='COMPLETE',exit_status=0,outputs={str(p.relative_to(work)):sha(p) for p in work.rglob('*') if p.is_file()})
 except (OSError,ValueError,KeyError,subprocess.SubprocessError) as e:record['reason']=str(e)
 write(work/'task_status.json',record);return record['exit_status']

def collect(dest,digest):
 dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());results=[];issues=[]
 try:verify(dest,plan,digest)
 except (OSError,ValueError,KeyError) as e:issues.append(str(e))
 for task in plan['tasks']:
  work=dest/task['id'];r=dict(task=task['id'],level=task['level'],status='FAILED_OR_MISSING')
  try:
   if issues:raise ValueError('Global integrity failure')
   old=json.loads((work/'task_status.json').read_text())
   if old.get('task')!=task['id'] or old.get('status')!='COMPLETE' or old.get('exit_status')!=0 or old.get('plan_sha256')!=digest:raise ValueError('Incomplete task')
   for p,h in task['inputs'].items():
    if sha(p)!=h:raise ValueError('Changed task input')
   required={'result/status.txt','result/settings.csv','result/fit_diagnostics.csv','result/stream_scores.csv','result/aggregate_predictions.csv','result/fit_INTERNAL.rds','result/rng_protocol.csv','result/input_checksums.csv'}
   if not required.issubset(old.get('outputs',{})):raise ValueError('Unbound required outputs')
   for n,h in old['outputs'].items():
    if sha(inside(work,n))!=h:raise ValueError('Changed result')
   validate(work,task);r['status']='COMPLETE'
  except (OSError,ValueError,KeyError) as e:r['reason']=str(e)
  results.append(r)
 summary=dict(tasks=results,issues=issues,complete=sum(r['status']=='COMPLETE' for r in results),expected=144,execution_complete=not issues and all(r['status']=='COMPLETE' for r in results),scientific_acceptance=False,incidence_adjustment=False,independent_validation=False,compare_raw_scores_across_resolutions=False)
 write(dest/'summary.json',summary)
 files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and '_INTERNAL' not in p.name and p.name!='report_sha256.json' and p.suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh','.md')]
 manifest=dest/'report_sha256.json';write(manifest,{str(p.relative_to(dest)):sha(p) for p in files})
 with tarfile.open(str(dest)+'.tar.gz','w:gz') as a:
  for p in files+[manifest]:a.add(str(p),arcname=str(p.relative_to(dest)))
 print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz');return 0 if summary['execution_complete'] else 1

def launch(root,dest):
 prepare(root,dest);digest=sha(dest/'plan.json');base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y'];submission={}
 job=subprocess.check_output(base+['-N','foodnet_class_models','-t','1-144','-pe','smp','4','-l','h_rt=48:00:00,h_rss=53248M,mem_free=53248M,h_vmem=68G','-o',str(dest/'array.log'),str(dest/'run.sh')],universal_newlines=True).strip();submission['array']=job;write(dest/'submission.json',submission)
 m=re.match(r'^(\d+)(?:[.\s]|$)',job)
 if not m:raise ValueError('Unknown qsub response; inspect queue before resubmitting')
 col=subprocess.check_output(base+['-N','foodnet_class_collect','-hold_jid',m.group(1),'-pe','smp','1','-l','h_rt=04:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G','-o',str(dest/'collection.log'),str(dest/'collect.sh')],universal_newlines=True).strip();submission['collector']=col;write(dest/'submission.json',submission);print(json.dumps(submission),flush=True)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-only',action='store_true');p.add_argument('--worker');p.add_argument('--collect');p.add_argument('--task');p.add_argument('--digest');p.add_argument('--launch');p.add_argument('--root');a=p.parse_args()
 if a.worker or a.collect:
  if not a.digest or (a.worker and not a.task):p.error('Missing worker identity')
  return worker(a.worker,a.task,a.digest) if a.worker else collect(a.collect,a.digest)
 if a.launch:launch(Path(a.root),Path(a.launch));return 0
 root=Path(__file__).resolve().parents[1];dest=root/'output'/('monthly_classification_models_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
 if a.prepare_only:prepare(root,dest,False);print('Unverified plan: '+str(dest));return 0
 if any(not shutil.which(t) for t in ('qsub','singularity')):p.error('Load singularity on SGE host')
 logfile=Path(str(dest)+'_preparation.log');logfile.parent.mkdir(parents=True,exist_ok=True)
 with logfile.open('w') as log:proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--launch',str(dest),'--root',str(root)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,cwd=str(root))
 print('Preparation PID: '+str(proc.pid)+'\nPreparation log: '+str(logfile)+'\nCollection log: '+str(dest/'collection.log')+'\nArchive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
