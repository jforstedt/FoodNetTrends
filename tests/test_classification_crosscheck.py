import ast,csv,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import launch_classification_crosscheck as mod
class CrosscheckTests(unittest.TestCase):
 def write(self,path,data):
  with path.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 def fixture(self,work):
  out=work/'result';out.mkdir()
  t=dict(state='CA',year=2012,seed=700000000,observed_cidt=0,trials=100,original_cpo=.1,original_failure=1)
  self.write(out/'identity.csv',[dict(row_id=1,original_preserved='TRUE',accepted='FALSE',**{k:t[k] for k in ('state','year','seed','observed_cidt','trials')})])
  self.write(out/'comparison.csv',[dict(state='CA',year=2012,original_cpo=.1,original_failure=1,group_cv=.12,explicit_log_score=-2.1,explicit_relative_mcse=.01,eb_log_score=-2,eb_relative_mcse=.01)])
  self.write(out/'stream_scores.csv',[dict(method=m,stream=i,draws=1000,log_score=-2,relative_mcse=.01) for m in ('full','eb') for i in range(1,5)])
  self.write(out/'numerical.csv',[dict(method=m,fit_ok='TRUE',mode_status=0) for m in ('full','eb')])
  (out/'status.txt').write_text('CROSSCHECK_COMPLETE')
  for n in ('explicit_INTERNAL.rds','eb_INTERNAL.rds'):(out/n).write_text('saved')
  return t
 def test_python36(self):ast.parse((ROOT/'scripts/launch_classification_crosscheck.py').read_text(),feature_version=(3,6))
 def test_validator_identity_precision_and_numerics(self):
  with tempfile.TemporaryDirectory() as tmp:
   w=Path(tmp);t=self.fixture(w);mod.validate(w,t)
   for file,key,bad,regex in [('identity.csv','year','2013','identity'),('comparison.csv','original_cpo','.2','Original'),('comparison.csv','group_cv','NA','Nonfinite'),('stream_scores.csv','method','wrong','streams'),('numerical.csv','fit_ok','FALSE','numerical')]:
    path=w/'result'/file;original=path.read_text();d=mod.rows(path);d[0][key]=bad;self.write(path,d)
    with self.assertRaisesRegex(ValueError,regex):mod.validate(w,t)
    path.write_text(original)
 def test_selection_prespecified_and_missing_strata(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);work=root/'inspect';(work/'result').mkdir(parents=True);support=root/'support.csv'
   d=[dict(state=s,year=y,observed='TRUE' if y<=2016 else 'FALSE',cpo_failure=flag,cpo=score) for s,y,flag,score in [('CO',2012,1,.00001),('CA',2012,1,.9),('CA',2013,0,.001),('CO',2014,0,.2),('CA',2017,1,.3)]]
   self.write(work/'result/row_diagnostics.csv',d)
   self.write(support,[dict(state=r['state'],year=r['year'],cidt_classified=1 if r['year']==2014 else 0,classification_denominator=100) for r in d])
   t=dict(id='inspect',pathogen='STEC',mode='inspect',kind='hindcast',model='shared',support=str(support))
   with patch.object(mod.prior,'validate'):
    chosen,absent=mod.selected(dict(_origin=str(root),tasks=[t,dict(t,mode='precision')]))
   self.assertEqual(len(chosen),3);self.assertEqual(chosen[0][1]['state'],'CA');self.assertEqual(chosen[0][1]['year'],2012)
   self.assertEqual(absent,[dict(pathogen='STEC',stratum='flagged_nonzero')])
 def test_plan_refuses_execution_and_partial_collection(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'plan';plan=mod.prepare(ROOT,dest,False);digest=mod.sha(dest/'plan.json')
   self.assertEqual(len(plan['tasks']),24);self.assertEqual(len({t['id'] for t in plan['tasks']}),24)
   self.assertTrue(all(t['cutoff']==2016 and t['model']=='shared' for t in plan['tasks']))
   self.assertTrue(all(t['command'][-3:]==[t['state'],str(t['year']),str(t['seed'])] for t in plan['tasks']))
   subprocess.check_call(['bash','-n',str(dest/'run.sh')])
   self.assertNotEqual(subprocess.call(['bash',str(dest/'run.sh')],env={'SGE_TASK_ID':'25'}),0)
   with patch.object(mod.subprocess,'call') as call:
    self.assertEqual(mod.worker(dest,plan['tasks'][0]['id'],digest),1);call.assert_not_called()
   self.assertEqual(mod.collect(dest,digest),1)
   self.assertFalse(json.loads((dest/'summary.json').read_text())['accepted'])
   self.assertTrue(Path(str(dest)+'.tar.gz').is_file())
 def test_verified_source_checks_hashes(self):
  with tempfile.TemporaryDirectory() as tmp:
   import shutil
   root=Path(tmp);(root/'scripts').mkdir();(root/'docs').mkdir()
   for n in mod.FILES:shutil.copyfile(str(ROOT/'scripts'/n),str(root/'scripts'/n))
   (root/'docs/classification_crosscheck.md').write_text('frozen protocol')
   origin=root/'output'/mod.SOURCE;origin.mkdir(parents=True);container=root/'foodnet-inla-fixed.sif';container.write_text('container')
   inputs={str(container):mod.sha(container)};tasks=[]
   for pathogen in mod.PATHOGENS:
    for kind,cutoff in (('hindcast',2016),('description',2019)):
     for model in ('shared','site_slopes'):
      for mode in (('inspect','precision') if kind=='hindcast' else ('inspect',)):
       name=pathogen+'_'+kind+'_'+model+'_'+mode;fit=root/(name+'.rds');fit.write_text('fit');support=root/(name+'.csv')
       self.write(support,[dict(state='CA',year=2012,cidt_classified=0,classification_denominator=100)])
       inputs[str(fit)]=mod.sha(fit);inputs[str(support)]=mod.sha(support)
       tasks.append(dict(id=name,pathogen=pathogen,kind=kind,cutoff=cutoff,model=model,mode=mode,fit=str(fit),support=str(support)))
       if mode=='inspect':
        work=origin/name;(work/'result').mkdir(parents=True)
        self.write(work/'result/row_diagnostics.csv',[dict(state='CA',year=2012,observed='TRUE',cpo_failure=1,cpo=.1)])
   (origin/'plan.json').write_text(json.dumps(dict(version='classification_saved_diagnostics_v1',verified=True,tasks=tasks,inputs=inputs)))
   digest=mod.sha(origin/'plan.json')
   for t in tasks:
    if t['mode']!='inspect':continue
    work=origin/t['id'];record=dict(task=t['id'],status='COMPLETE',exit_status=0,plan_sha256=digest,outputs={str(p.relative_to(work)):mod.sha(p) for p in work.rglob('*') if p.is_file()})
    (work/'task_status.json').write_text(json.dumps(record))
   with patch.object(mod.prior,'validate'):
    plan=mod.prepare(root,root/'prepared',True);self.assertEqual(len(plan['tasks']),6);self.assertEqual(len(plan['absent_strata']),18)
    mod.verify(root/'prepared',plan,mod.sha(root/'prepared/plan.json'))
    (origin/tasks[0]['id']/'result/row_diagnostics.csv').write_text('changed')
    with self.assertRaisesRegex(ValueError,'Source output changed'):mod.prepare(root,root/'other',True)
 def test_provenance(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp);source=dest/'source';source.write_text('fit');plan=dict(verified=True,inputs={str(source):mod.sha(source)})
   (dest/'plan.json').write_text(json.dumps(plan));digest=mod.sha(dest/'plan.json');mod.verify(dest,plan,digest);source.write_text('changed')
   with self.assertRaisesRegex(ValueError,'Changed input'):mod.verify(dest,plan,digest)
if __name__=='__main__':unittest.main()
