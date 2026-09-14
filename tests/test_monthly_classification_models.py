import csv,json,sys,tempfile,unittest,subprocess,tarfile,ast
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import launch_monthly_classification_models as m
class ClassificationModelLauncherTests(unittest.TestCase):
 def csv(self,p,rs):
  p.parent.mkdir(parents=True,exist_ok=True)
  with p.open('w') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
 def prepared(self,root):
  (root/'scripts').mkdir();(root/'docs').mkdir();(root/'analysis_configs/county_pilot').mkdir(parents=True)
  for n in m.FILES:(root/'scripts'/n).write_text('# placeholder\n')
  for n in ['classification_combination_protocol.md','monthly_classification_launch.md']:(root/'docs'/n).write_text('protocol\n')
  for n in ['counties.csv','edges.csv','provenance.json']:(root/'analysis_configs/county_pilot'/n).write_text('fixture\n')
  dest=root/'run';plan=m.prepare(root,dest,False);return dest,plan
 def test_matrix(self):
  ts=m.matrix();self.assertEqual(len(ts),144);self.assertEqual(len({t['id'] for t in ts}),144);self.assertEqual(sum(t['level']=='site' for t in ts),48);self.assertEqual(sum(t['spatial']=='bym2' for t in ts),48);self.assertEqual({t['cutoff'] for t in ts},{2015,2016});self.assertFalse(any(t['temporal']=='spline' for t in ts))
 def test_prepare_only_refuses_execution_and_shells_parse(self):
  with tempfile.TemporaryDirectory() as td:
   d,p=self.prepared(Path(td));self.assertFalse(p['verified'])
   with self.assertRaises(ValueError):m.verify(d,p,m.sha(d/'plan.json'))
   for n in ['run.sh','collect.sh']:subprocess.check_call(['bash','-n',str(d/n)])
   self.assertEqual(len(p['tasks'][0]['command'][-10:]),10);self.assertEqual(p['tasks'][0]['command'][-9],'site')
 def test_changed_snapshot_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   d,p=self.prepared(Path(td));p['verified']=True;m.write(d/'plan.json',p);digest=m.sha(d/'plan.json');m.verify(d,p,digest)
   (d/'scripts'/m.FILES[0]).write_text('changed')
   with self.assertRaises(ValueError):m.verify(d,p,digest)
 def test_prior_source_and_report_hash_gate(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.prepared(root);folder=root/'analysis_configs/monthly_classification_priors';folder.mkdir();(folder/'quantiles.csv').write_text('prior-only')
   sources=['scripts/monthly_classification_model.R','scripts/check_monthly_classification_priors.R','scripts/monthly_spatial_combination.R','analysis_configs/county_pilot/counties.csv','analysis_configs/county_pilot/edges.csv']
   manifest=dict(version='monthly_classification_priors_v1',status='PRIOR_CHECK_PASS',sources={n:m.sha(root/n) for n in sources},files={'quantiles.csv':m.sha(folder/'quantiles.csv')});m.write(folder/'manifest.json',manifest)
   self.assertEqual(len(m.verify_prior(root)),2);(folder/'quantiles.csv').write_text('changed')
   with self.assertRaises(ValueError):m.verify_prior(root)
 def verified_source(self,root):
  origin=root/'output'/m.SOURCE/'classification';origin.mkdir(parents=True);tasks=[]
  for pathogen in m.prep.PATHOGENS:
   work=origin/pathogen;out=work/'result';out.mkdir(parents=True);support=work/'annual_support.csv';support.write_text('bound support')
   for n in ('classification_site.csv','classification_county_month_INTERNAL.rds','classification_annual.csv','classification_date_issues_by_category.csv','classification_readiness.csv','source_month_comparison.csv'):(out/n).write_text('bound source')
   self.csv(out/'date_issues.csv',[dict(missing_specimen_date=0,specimen_year_disagreement=0,unassigned_records=0,month_disagreement={'SALMONELLA':1,'SHIGELLA':2}.get(pathogen,0))])
   tasks.append(dict(id=pathogen,annual_support=str(support)))
  old=dict(tasks=tasks,inputs={});m.write(origin/'plan.json',old);digest=m.sha(origin/'plan.json')
  for t in tasks:
   work=origin/t['id'];m.write(work/'task_status.json',dict(task=t['id'],status='COMPLETE',exit_status=0,plan_sha256=digest,outputs={str(p.relative_to(work)):m.sha(p) for p in (work/'result').iterdir()}))
  m.write(origin/'summary.json',dict(execution_complete=True,issues=[],tasks=[dict(task=t['id'],status='COMPLETE') for t in tasks]));(root/'foodnet-inla-fixed.sif').write_text('container');return origin
 def test_source_mutation_between_prior_gate_and_copy_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.prepared(root);self.verified_source(root);folder=root/'analysis_configs/monthly_classification_priors';folder.mkdir();(folder/'quantiles.csv').write_text('prior-only')
   sources=['scripts/monthly_classification_model.R','scripts/check_monthly_classification_priors.R','scripts/monthly_spatial_combination.R','analysis_configs/county_pilot/counties.csv','analysis_configs/county_pilot/edges.csv']
   m.write(folder/'manifest.json',dict(version='monthly_classification_priors_v1',status='PRIOR_CHECK_PASS',sources={n:m.sha(root/n) for n in sources},files={'quantiles.csv':m.sha(folder/'quantiles.csv')}))
   check=m.verify_prior
   def mutate(root):
    bound=check(root);(root/'scripts/monthly_classification_model.R').write_text('changed after prior verification');return bound
   with patch.object(m.prep,'verify'),patch.object(m.prep,'validate'),patch.object(m,'verify_prior',side_effect=mutate),self.assertRaisesRegex(ValueError,'Prior source and model snapshot differ'):m.prepare(root,root/'verified',True)
 def test_verified_plan_binds_consumed_inputs(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.prepared(root);origin=self.verified_source(root)
   with patch.object(m.prep,'verify'),patch.object(m.prep,'validate'),patch.object(m,'verify_prior',return_value={}):plan=m.prepare(root,root/'verified',True)
   dest=root/'verified';digest=m.sha(dest/'plan.json');m.verify(dest,plan,digest,plan['tasks'][0]);self.assertTrue(plan['verified']);self.assertTrue(plan['tasks'][0]['inputs'])
   self.assertEqual(plan['tasks'][0]['site_reference'],str(origin/'SALMONELLA/result/classification_site.csv'))
   (origin/'SALMONELLA/result/classification_site.csv').write_text('changed after prepare')
   with self.assertRaises(ValueError):m.verify(dest,plan,digest,plan['tasks'][0])
 def test_source_hash_change_blocks_preparation(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.prepared(root);origin=self.verified_source(root)
   (origin/'SALMONELLA/result/classification_site.csv').write_text('changed')
   with patch.object(m.prep,'verify'),patch.object(m.prep,'validate'),self.assertRaises(ValueError):m.prepare(root,root/'verified',True)
 def test_source_task_identity_blocks_preparation(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.prepared(root);origin=self.verified_source(root);p=origin/'SALMONELLA/task_status.json';record=json.loads(p.read_text());record['task']='STEC';m.write(p,record)
   with patch.object(m.prep,'verify'),patch.object(m.prep,'validate'),self.assertRaises(ValueError):m.prepare(root,root/'verified',True)
 def fixture(self,root,zero=False):
  task=m.matrix()[0];out=root/'task/result';out.mkdir(parents=True);ref=root/'site.csv';task['site_reference']=str(ref)
  self.csv(ref,[dict(state=s,year=y,month=mo,cidt_classified=0 if zero and s=='CA' and y==2016 else 1,classification_denominator=0 if zero and s=='CA' and y==2016 else 2) for s in m.STATES for y in range(2016,2019) for mo in range(1,13)])
  (out/'status.txt').write_text('MONTHLY_CLASSIFICATION_MODEL_COMPLETE\n')
  self.csv(out/'settings.csv',[dict(level=task['level'],temporal=task['temporal'],spatial=task['spatial'],cutoff=2015,base_seed=task['seed'],streams=4,draws_per_stream=2000,seasonal='FALSE',coverage_certified='FALSE',incidence_adjustment='FALSE',independent_validation='FALSE',train_start=2012,horizon=36,target='CIDT_CLASSIFICATION_GIVEN_ELIGIBLE_CX_OR_CIDT',rng_protocol='explicit_config_v2',fitting_threads='4:1')])
  for n in ('fit_INTERNAL.rds','rng_protocol.csv','input_checksums.csv'):(out/n).write_text('fixture')
  self.csv(out/'fit_diagnostics.csv',[dict(fit_ok='TRUE',mode_status=0)])
  agg=[];scores=[]
  for s in m.STATES+('ALL',):
   for y in range(2016,2019):
    n=240 if s=='ALL' else 24
    if zero and y==2016:n-=24 if s in ('ALL','CA') else 0
    for k in range(5):
     common=dict(state=s,year=y,stream=k,draws=8000 if k==0 else 2000);agg.append(dict(common,eligible_cells=n//2,observed=n//2,denominator=n,mean_expected=n/2,median_expected=n/2,lower95=0,median_predictive=n/2,upper95=n))
     if s!='ALL':scores.append(dict(common,eligible_cells=12 if n else 0,mean_log_score=-1 if n else '',max_cell_density_relative_mcse=.01 if n else ''))
  self.csv(out/'aggregate_predictions.csv',agg);self.csv(out/'stream_scores.csv',scores);return root/'task',task
 def test_validated_conditional_counts_and_missing_score(self):
  for zero in [False,True]:
   with tempfile.TemporaryDirectory() as td:
    work,t=self.fixture(Path(td),zero);self.assertTrue(m.validate(work,t))
 def test_duplicate_scores_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   work,t=self.fixture(Path(td));p=work/'result/stream_scores.csv';rs=m.rows(p);self.csv(p,rs[:-1]+rs[:1])
   with self.assertRaises(ValueError):m.validate(work,t)
 def test_wrong_aggregate_or_numeric_failure_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   work,t=self.fixture(Path(td));p=work/'result/aggregate_predictions.csv';rs=m.rows(p);rs[0]['observed']='13';self.csv(p,rs)
   with self.assertRaises(ValueError):m.validate(work,t)
  with tempfile.TemporaryDirectory() as td:
   work,t=self.fixture(Path(td));self.csv(work/'result/fit_diagnostics.csv',[dict(fit_ok='TRUE',mode_status=2)])
   with self.assertRaises(ValueError):m.validate(work,t)
 def test_zero_denominator_score_not_zero(self):
  with tempfile.TemporaryDirectory() as td:
   work,t=self.fixture(Path(td),True);p=work/'result/stream_scores.csv';rs=m.rows(p);rs[0]['mean_log_score']='0';self.csv(p,rs)
   with self.assertRaises(ValueError):m.validate(work,t)
 def test_partial_collection_private_exclusion(self):
  with tempfile.TemporaryDirectory() as td:
   d,p=self.prepared(Path(td));(d/'private_INTERNAL.rds').write_text('PRIVATE')
   with patch.object(m,'verify'):
    self.assertEqual(m.collect(d,m.sha(d/'plan.json')),1)
   summary=json.loads((d/'summary.json').read_text());self.assertEqual(summary['complete'],0);self.assertFalse(summary['scientific_acceptance'])
   with tarfile.open(str(d)+'.tar.gz') as a:self.assertNotIn('private_INTERNAL.rds',a.getnames())
 def test_python36(self):ast.parse(Path(m.__file__).read_text(),feature_version=(3,6))
if __name__=='__main__':unittest.main()
