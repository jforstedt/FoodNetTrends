import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import recover_monthly_shigella as r
ROOT=Path(__file__).resolve().parents[1]
class RecoveryTests(unittest.TestCase):
 def test_six_only_reuses_candidate(self):
  with tempfile.TemporaryDirectory() as tmp:
   origin=Path(tmp)/'old';origin.mkdir();dest=Path(tmp)/'new';tasks=[]
   for cutoff in (2011,2013,2016):
    for model in ('rw1','ar1'):
     name='SHIGELLA_%s_%s'%(cutoff,model);(origin/name).mkdir()
     tasks.append(dict(id=name,pathogen='SHIGELLA',cutoff=cutoff,temporal=model,command=[str(origin/'scripts/run_monthly_expansion.R'),str(origin/'SHIGELLA/result/candidate_monthly_INTERNAL.rds'),str(origin/name/'result')]))
   old=dict(tasks=tasks,inputs={},verified=True,preparation_sha256='prep');(origin/'expansion.json').write_text(json.dumps(old))
   for t in tasks:(origin/t['id']/'task_status.json').write_text(json.dumps(dict(status='BLOCKED',reason='Month-definition disagreements require review',plan_sha256=r.m.sha(origin/'expansion.json'))))
   with patch.object(r,'SOURCE',str(origin)),patch.object(r.m,'verify'),patch.object(r.m,'gate'):
    plan=r.prepare(ROOT,dest)
   self.assertEqual(len(plan['tasks']),6)
   for t in plan['tasks']:
    self.assertEqual(t['command'][0],str(dest/'scripts/run_monthly_expansion.R'))
    self.assertEqual(t['command'][1],str(origin/'SHIGELLA/result/candidate_monthly_INTERNAL.rds'))
    self.assertEqual(t['command'][2],str(dest/t['id']/'result'))
   for n in ('fit.sh','finish.sh'):subprocess.check_call(['bash','-n',str(dest/n)])
   self.assertFalse((dest/'run.sh').exists())
   (origin/tasks[0]['id']/'task_status.json').write_text(json.dumps(dict(status='COMPLETE')))
   with patch.object(r,'SOURCE',str(origin)),patch.object(r.m,'verify'),patch.object(r.m,'gate'):
    with self.assertRaisesRegex(ValueError,'not the reviewed blocked'):r.prepare(ROOT,Path(tmp)/'again')
 def test_exception_is_hash_bound(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp);work=dest/'SHIGELLA';work.mkdir()
   (work/'task_status.json').write_text(json.dumps(dict(status='COMPLETE',exit_status=0,task='SHIGELLA',plan_sha256='prep',outputs={'result/candidate_monthly_INTERNAL.rds':'checkpoint'})))
   hashes={'candidate_monthly_INTERNAL.rds':'checkpoint','date_issues.csv':'bbeae4d38a0098ce763e24fe05fdba708b1a776ba3202f28f1863e0e80615546','source_month_comparison.csv':'bfd18daf5f5a88fd6bd60cd20fd5ada35b21f554b04f18176b76d235d0bc60f8','task_status.json':'2f92d7b5b7913ae9ba9b68add879b17b077fd91fd1269bee71a5440aac337c16'}
   plan=dict(preparation_sha256='prep',month_decision='SHIGELLA_SPECIMEN_20260913')
   def rows(p):return [{'unassigned_records':'0'}] if p.name=='annual_reconciliation.csv' else [{'month_disagreement':'2'}]
   with patch.object(r.m.prep,'validate_result'),patch.object(r.m,'rows',side_effect=rows),patch.object(r.m,'sha',side_effect=lambda p:hashes[p.name]):
    r.m.gate(dest,plan,'SHIGELLA')
    hashes['date_issues.csv']='changed'
    with self.assertRaisesRegex(ValueError,'Month-definition'):r.m.gate(dest,plan,'SHIGELLA')
 def test_python36(self):ast.parse((ROOT/'scripts/recover_monthly_shigella.py').read_text(),feature_version=(3,6))
if __name__=='__main__':unittest.main()
