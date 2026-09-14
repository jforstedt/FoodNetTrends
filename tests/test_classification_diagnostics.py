import ast,csv,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import launch_classification_diagnostics as mod
class DiagnosticsTests(unittest.TestCase):
 def test_python36(self):ast.parse((ROOT/'scripts/launch_classification_diagnostics.py').read_text(),feature_version=(3,6))
 def test_frozen_array(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'plan';p=mod.prepare(ROOT,dest,False)
   self.assertEqual(len(p['tasks']),36);self.assertEqual(len({t['seed'] for t in p['tasks']}),36)
   self.assertEqual(sum(t['mode']=='inspect' for t in p['tasks']),24)
   self.assertEqual(sum(t['mode']=='precision' and t['cutoff']==2016 for t in p['tasks']),12)
   self.assertTrue(all(t['command'][-1]==t['mode'] for t in p['tasks']))
   subprocess.check_call(['bash','-n',str(dest/'run.sh')])
   self.assertNotEqual(subprocess.call(['bash',str(dest/'run.sh')],env={'SGE_TASK_ID':'37'}),0)
   with self.assertRaises(ValueError):mod.verify(dest,p,mod.sha(dest/'plan.json'))
   with self.assertRaisesRegex(ValueError,'Unknown task'):mod.worker(dest,'invalid',mod.sha(dest/'plan.json'))
   with patch.object(mod.subprocess,'call') as call:
    self.assertEqual(mod.worker(dest,p['tasks'][0]['id'],mod.sha(dest/'plan.json')),1);call.assert_not_called()
 def fixture(self,work,mode='inspect'):
  out=work/'result';out.mkdir()
  def write(name,data):
   with (out/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
  task=dict(cutoff=2016,model='shared',seed=600000000,mode=mode,support=str(out/'support.csv'))
  (out/'status.txt').write_text('DIAGNOSTICS_COMPLETE')
  write('identity.csv',[dict(cutoff=2016,model='shared',seed=600000000,mode=mode,rows=80,draws_per_stream=2500 if mode=='precision' else 0,refitted='FALSE',accepted='FALSE')])
  domain=[(s,y) for s in mod.STATES for y in range(2012,2020)]
  write('support.csv',[dict(state=s,year=y,cidt_classified=2,classification_denominator=10) for s,y in domain])
  write('row_diagnostics.csv',[dict(state=s,year=y,observed='TRUE' if y<=2016 else 'FALSE',cpo_failure=0,cpo=.2 if y<=2016 else 'NA',pit=.4) for s,y in domain])
  write('summary.csv',[dict(observed='TRUE',rows=50,flagged=0,missing_failure=0,nonfinite_cpo=0,nonpositive_cpo=0),dict(observed='FALSE',rows=30,flagged=0,missing_failure=0,nonfinite_cpo=30,nonpositive_cpo=0)]);write('hyperparameters.csv',[dict(mean=1)])
  write('predictions.csv',[dict(state=s,year=y,observed_cidt=2,trials=10,mean_probability=.2,lower_probability=.1,median_probability=.2,upper_probability=.4,lower_predictive=0,median_predictive=2,upper_predictive=6,evaluation='CONDITIONAL_HINDCAST' if y>2016 else 'IN_SAMPLE_DESCRIPTION') for s,y in domain])
  write('stream_scores.csv',[dict(state=s,year=y,stream=k,draws=10000 if k==0 else 2500,log_score=-2,density_relative_mcse=.01) for s,y in domain for k in range(5)])
  write('annual.csv',[dict(year=y,trials=100,observed_cidt=20,mean_predicted_cidt=20,lower_predictive=10,median_predictive=20,upper_predictive=30) for y in range(2012,2020)])
  return task
 def test_inspection_mask_and_identity(self):
  with tempfile.TemporaryDirectory() as tmp:
   work=Path(tmp);task=self.fixture(work);mod.validate(work,task)
   p=work/'result/row_diagnostics.csv';original=p.read_text();p.write_text(original.replace('FALSE','TRUE'))
   with self.assertRaisesRegex(ValueError,'mask'):mod.validate(work,task)
   p.write_text(original);p=work/'result/identity.csv';p.write_text(p.read_text().replace('600000000','600000001'))
   with self.assertRaisesRegex(ValueError,'identity'):mod.validate(work,task)
 def test_precision_rejects_incomplete_streams(self):
  with tempfile.TemporaryDirectory() as tmp:
   work=Path(tmp);task=self.fixture(work,'precision');mod.validate(work,task)
   p=work/'result/stream_scores.csv';p.write_text(p.read_text().replace('2500','500'))
   with self.assertRaisesRegex(ValueError,'score'):mod.validate(work,task)
 def test_verified_source_binding_rejects_changed_fit(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'output'/mod.SOURCE).mkdir(parents=True);(root/'scripts').mkdir();(root/'docs').mkdir()
   import shutil
   for name in mod.FILES:shutil.copyfile(str(ROOT/'scripts'/name),str(root/'scripts'/name))
   shutil.copyfile(str(ROOT/'docs/classification_saved_diagnostics.md'),str(root/'docs/classification_saved_diagnostics.md'))
   container=root/'foodnet-inla-fixed.sif';container.write_text('container');origin=root/'output'/mod.SOURCE
   tasks=[];inputs={str(container):mod.sha(container)}
   for pathogen in mod.PATHOGENS:
    support=root/(pathogen+'.csv');support.write_text('support');inputs[str(support)]=mod.sha(support)
    for kind,cutoff in (('hindcast',2016),('description',2019)):
     for model in ('shared','site_slopes'):
      name=pathogen+'_'+kind+'_'+model;out=origin/name/'result';out.mkdir(parents=True)
      (out/'fit_INTERNAL.rds').write_text('saved fit')
      (out/'settings.csv').write_text('cutoff,model,seed\n'+str(cutoff)+','+model+',1\n')
      tasks.append(dict(id=name,pathogen=pathogen,kind=kind,cutoff=cutoff,model=model,seed=1,command=[str(support),'out',str(cutoff),model,'1']))
   (origin/'plan.json').write_text(json.dumps(dict(version='classification_trends_v1',verified=True,tasks=tasks,inputs=inputs)))
   for t in tasks:
    work=origin/t['id'];out=work/'result'
    (work/'task_status.json').write_text(json.dumps(dict(task=t['id'],status='COMPLETE',exit_status=0,plan_sha256=mod.sha(origin/'plan.json'),outputs={'result/fit_INTERNAL.rds':mod.sha(out/'fit_INTERNAL.rds'),'result/settings.csv':mod.sha(out/'settings.csv')})))
   plan=mod.prepare(root,root/'prepared',True);mod.verify(root/'prepared',plan,mod.sha(root/'prepared/plan.json'))
   (origin/tasks[0]['id']/'result/fit_INTERNAL.rds').write_text('changed')
   with self.assertRaisesRegex(ValueError,'Changed input'):mod.verify(root/'prepared',plan,mod.sha(root/'prepared/plan.json'))
   with self.assertRaisesRegex(ValueError,'Saved fit changed'):mod.prepare(root,root/'other',True)
 def test_partial_archive(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'plan';mod.prepare(ROOT,dest,False)
   self.assertEqual(mod.collect(dest,mod.sha(dest/'plan.json')),1)
   summary=json.loads((dest/'summary.json').read_text());self.assertEqual(summary['complete'],0);self.assertFalse(summary['accepted']);self.assertFalse(summary['models_refitted'])
   self.assertTrue(Path(str(dest)+'.tar.gz').is_file())
if __name__=='__main__':unittest.main()
