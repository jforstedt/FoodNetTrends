import hashlib,json,sys,tempfile,unittest,subprocess,shutil
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import recover_monthly_spatial as r
ROOT=Path(__file__).resolve().parents[1]

class RecoveryTests(unittest.TestCase):
 def source(self,root):
  (root/'scripts').mkdir();origin=root/'output'/r.SOURCE/'spatial';(origin/'scripts').mkdir(parents=True)
  for n in ('recover_monthly_spatial.py','run_monthly_spatial_recovery.R'):shutil.copyfile(str(ROOT/'scripts'/n),str(root/'scripts'/n))
  (origin/'scripts/run_monthly_spatial_factorial.R').write_text('# frozen\n')
  tasks=[];refs=[]
  for n in sorted(r.TARGETS):
   t=dict(id=n,pathogen=n.split('_')[0],cutoff=2011,temporal='ar1',seasonal=True,inputs={},command=['Rscript',str(origin/'scripts/run_monthly_spatial_factorial.R'),'candidate','audit','2011',str(origin/n/'result'),'123','ar1','TRUE','2019','basis','nodes','edges'])
   tasks.append(t);refs.append(dict(pathogen=t['pathogen'],cutoff=2011,temporal='ar1',seasonal=True,reference=dict(inputs={},truth_sha256='truth')))
  old=dict(inputs={},tasks=tasks,references=refs);r.write(origin/'plan.json',old)
  for t in tasks:
   (origin/t['id']).mkdir();r.write(origin/t['id']/'task_status.json',dict(task=t['id'],status='FAILED',plan_sha256=r.sha(origin/'plan.json')));(origin/t['id']/'task.log').write_text('failure')
  expected={t['id'] for t in r.spatial.matrix()}|{t['id'][:-5] for t in r.spatial.matrix()}
  r.write(origin/'summary.json',dict(complete=322,issues=[],tasks=[dict(task=n,status='FAILED' if n in r.TARGETS else 'COMPLETE') for n in sorted(expected)]))
  return origin,old
 def prepared(self,root):
  origin,old=self.source(root);dest=root/'recovery'
  with patch.object(r.spatial,'verify'):plan=r.prepare(root,dest)
  return origin,old,dest,plan
 def test_only_two_commands_changed_and_sources_preserved(self):
  with tempfile.TemporaryDirectory() as td:
   origin,old,dest,plan=self.prepared(Path(td));self.assertEqual(len(plan['tasks']),2)
   for before,after in zip(old['tasks'],plan['tasks']):
    changes=[i for i,(a,b) in enumerate(zip(before['command'],after['command'])) if a!=b]
    self.assertEqual(changes,[1,5]);self.assertEqual(before['inputs'],after['inputs'])
   self.assertEqual(json.loads((origin/'plan.json').read_text()),old)
   for name in ('run.sh','collect.sh'):subprocess.check_call(['bash','-n',str(dest/name)])
   r.verify(dest,plan,r.sha(dest/'plan.json'))
 def test_changed_frozen_input_blocks(self):
  with tempfile.TemporaryDirectory() as td:
   origin,old,dest,plan=self.prepared(Path(td));(origin/'summary.json').write_text('{}')
   with self.assertRaises(ValueError):r.verify(dest,plan,r.sha(dest/'plan.json'))
 def test_wrong_failure_scope_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);origin,_=self.source(root);r.write(origin/'summary.json',dict(complete=321,issues=[],tasks=[]))
   with patch.object(r.spatial,'verify'),self.assertRaises(ValueError):r.prepare(root,root/'recovery')
   self.assertFalse((root/'recovery').exists())
 def test_existing_destination_refused(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);origin,_=self.source(root);dest=root/'recovery';dest.mkdir()
   with patch.object(r.spatial,'verify'),self.assertRaises(FileExistsError):r.prepare(root,dest)
 def test_failed_numerics_never_accepted(self):
  with tempfile.TemporaryDirectory() as td:
   origin,old,dest,plan=self.prepared(Path(td));name=plan['tasks'][0]['id']
   with patch.object(r.subprocess,'call',return_value=1),patch.object(r.spatial,'validate') as validate:
    self.assertEqual(r.worker(dest,name,r.sha(dest/'plan.json')),1);validate.assert_not_called()
   self.assertEqual(json.loads((dest/name/'task_status.json').read_text())['status'],'FAILED')
 def test_wrapper_single_thread_retains_quality_gate(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);shutil.copyfile(str(ROOT/'scripts/run_monthly_spatial_recovery.R'),str(d/'retry.R'))
   (d/'run_monthly_spatial_factorial.R').write_text("fit_monthly_spatial_combination<-function(...,threads) {stopifnot(threads==1L);list(ok=TRUE,mode=list(mode.status=0))}\nrun_monthly_spatial_factorial<-function(...) {fit<-fit_monthly_spatial_combination(threads=4L);stopifnot(isTRUE(fit$ok),fit$mode$mode.status==0)}\n")
   subprocess.check_call(['Rscript',str(d/'retry.R'),'candidate','audit','2011',str(d/'result'),'123','ar1','TRUE','2019','basis','nodes','edges'])
   self.assertIn('single_thread_same_model',(d/'recovery_numerics.csv').read_text())
if __name__=='__main__':unittest.main()
