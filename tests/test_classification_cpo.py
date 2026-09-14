import ast,csv,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import launch_classification_cpo as mod
class CpoTests(unittest.TestCase):
 def write(self,path,data):
  with path.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 def fixture(self,work):
  out=work/'result';out.mkdir()
  task=dict(cutoff=2016,model='shared',requested=1,flags=str(work/'flags.csv'))
  flags=[dict(state=s,year=y,observed='TRUE' if y<=2016 else 'FALSE',cpo_failure=int(s=='CA' and y==2012),cpo=.2,pit=.4) for s in mod.STATES for y in range(2012,2020)]
  self.write(Path(task['flags']),flags)
  d=[dict(state=r['state'],year=r['year'],observed=r['observed'],requested='TRUE' if r['cpo_failure'] else 'FALSE',before_failure=r['cpo_failure'],after_failure=0,before_cpo=.2,after_cpo=.3 if r['cpo_failure'] else .2,before_pit=.4,after_pit=.5 if r['cpo_failure'] else .4) for r in flags]
  self.write(out/'comparison.csv',d)
  self.write(out/'identity.csv',[dict(cutoff=2016,model='shared',rows=80,requested=1,original_preserved='TRUE',scientific_model_changed='FALSE',accepted='FALSE')])
  self.write(out/'summary.csv',[dict(requested=1,remaining_flagged=0,invalid_requested=0,resolved=1)])
  (out/'status.txt').write_text('CPO_RECOMPUTATION_COMPLETE');(out/'repaired_INTERNAL.rds').write_text('saved')
  return task
 def test_python36(self):ast.parse((ROOT/'scripts/launch_classification_cpo.py').read_text(),feature_version=(3,6))
 def test_masks_and_original(self):
  with tempfile.TemporaryDirectory() as tmp:
   work=Path(tmp);t=self.fixture(work);self.assertEqual(mod.validate(work,t)['resolved'],1)
   p=work/'result/comparison.csv';d=mod.rows(p);d[0]['before_cpo']=.1;self.write(p,d)
   with self.assertRaisesRegex(ValueError,'Original'):mod.validate(work,t)
   d[0]['before_cpo']=.2;d[0]['requested']='FALSE';self.write(p,d)
   with self.assertRaisesRegex(ValueError,'mask'):mod.validate(work,t)
 def test_unresolved_is_finding(self):
  with tempfile.TemporaryDirectory() as tmp:
   work=Path(tmp);t=self.fixture(work);p=work/'result/comparison.csv';d=mod.rows(p);d[0]['after_cpo']='NA';self.write(p,d)
   self.write(work/'result/summary.csv',[dict(requested=1,remaining_flagged=0,invalid_requested=1,resolved=0)])
   self.assertEqual(mod.validate(work,t)['resolved'],0)
 def test_selection_ignores_unobserved(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);w=root/'one';w.mkdir();t=self.fixture(w);(w/'result/row_diagnostics.csv').write_text((w/'flags.csv').read_text())
   tasks=[dict(id='one',mode='inspect'),dict(id='other',mode='precision')]
   with patch.object(mod.prior,'validate'):
    self.assertEqual(mod.selected(dict(tasks=tasks,_origin=str(root)))[0][1],1)
    p=w/'result/row_diagnostics.csv';d=mod.rows(p);d[0]['observed']='FALSE';self.write(p,d)
    self.assertEqual(mod.selected(dict(tasks=tasks,_origin=str(root))),[])
 def test_frozen_plan_and_partial_archive(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'plan';p=mod.prepare(ROOT,dest,False)
   self.assertEqual(len(p['tasks']),13)
   self.assertEqual(len({t['id'] for t in p['tasks']}),13)
   self.assertTrue(all(t['command'][-1]==t['model'] for t in p['tasks']))
   subprocess.check_call(['bash','-n',str(dest/'run.sh')])
   self.assertNotEqual(subprocess.call(['bash',str(dest/'run.sh')],env={'SGE_TASK_ID':'14'}),0)
   with self.assertRaises(ValueError):mod.verify(dest,p,mod.sha(dest/'plan.json'))
   with patch.object(mod.subprocess,'call') as call:
    self.assertEqual(mod.worker(dest,p['tasks'][0]['id'],mod.sha(dest/'plan.json')),1);call.assert_not_called()
   self.assertEqual(mod.collect(dest,mod.sha(dest/'plan.json')),1)
   summary=json.loads((dest/'summary.json').read_text());self.assertFalse(summary['diagnostics_resolved']);self.assertEqual(summary['complete'],0)
   self.assertTrue(Path(str(dest)+'.tar.gz').is_file())
 def test_verified_source_selection_and_changed_output(self):
  with tempfile.TemporaryDirectory() as tmp:
   import shutil
   root=Path(tmp);(root/'scripts').mkdir();(root/'docs').mkdir()
   for name in mod.FILES:shutil.copyfile(str(ROOT/'scripts'/name),str(root/'scripts'/name))
   shutil.copyfile(str(ROOT/'docs/classification_cpo_repair.md'),str(root/'docs/classification_cpo_repair.md'))
   origin=root/'output'/mod.SOURCE;origin.mkdir(parents=True)
   container=root/'foodnet-inla-fixed.sif';container.write_text('container');inputs={str(container):mod.sha(container)};tasks=[]
   for pathogen in mod.PATHOGENS:
    for kind,cutoff in (('hindcast',2016),('description',2019)):
     for model in ('shared','site_slopes'):
      for mode in (('inspect','precision') if kind=='hindcast' else ('inspect',)):
       name=pathogen+'_'+kind+'_'+model+'_'+mode
       fit=root/(name+'.rds');fit.write_text('fit');support=root/(name+'.csv');support.write_text('support')
       inputs[str(fit)]=mod.sha(fit);inputs[str(support)]=mod.sha(support)
       t=dict(id=name,pathogen=pathogen,kind=kind,cutoff=cutoff,model=model,mode=mode,fit=str(fit),support=str(support));tasks.append(t)
       if mode=='inspect':
        work=origin/name;work.mkdir();self.fixture(work)
        flagfile=work/'result/row_diagnostics.csv';flagfile.write_text((work/'flags.csv').read_text())
   old=dict(version='classification_saved_diagnostics_v1',verified=True,tasks=tasks,inputs=inputs)
   (origin/'plan.json').write_text(json.dumps(old));digest=mod.sha(origin/'plan.json')
   for t in tasks:
    if t['mode']!='inspect':continue
    work=origin/t['id'];record=dict(task=t['id'],status='COMPLETE',exit_status=0,plan_sha256=digest,outputs={str(p.relative_to(work)):mod.sha(p) for p in work.rglob('*') if p.is_file()})
    (work/'task_status.json').write_text(json.dumps(record))
   with patch.object(mod.prior,'validate'):
    plan=mod.prepare(root,root/'prepared',True)
    self.assertEqual(len(plan['tasks']),24)
    mod.verify(root/'prepared',plan,mod.sha(root/'prepared/plan.json'))
    first=origin/tasks[0]['id']/'result/row_diagnostics.csv';first.write_text('changed')
    with self.assertRaisesRegex(ValueError,'Source output changed'):mod.prepare(root,root/'other',True)
 def test_provenance_change_blocks_execution(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp);source=dest/'source';source.write_text('fit');plan=dict(verified=True,inputs={str(source):mod.sha(source)})
   (dest/'plan.json').write_text(json.dumps(plan));digest=mod.sha(dest/'plan.json');mod.verify(dest,plan,digest)
   source.write_text('different')
   with self.assertRaisesRegex(ValueError,'Changed input'):mod.verify(dest,plan,digest)
if __name__=='__main__':unittest.main()
