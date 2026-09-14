import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import launch_monthly_expansion as m
ROOT=Path(__file__).resolve().parents[1]
class ExpansionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.dest=Path(self.tmp.name)/'run'
 def test_design_and_shell(self):
  plan=m.prepare(ROOT,self.dest,False)
  self.assertEqual(len(plan['tasks']),42);self.assertEqual(len({t['seed'] for t in plan['tasks']}),42)
  self.assertEqual(len(json.loads((self.dest/'plan.json').read_text())['tasks']),7)
  for t in plan['tasks']:
   self.assertNotIn(t['pathogen'],('SALMONELLA','CAMPYLOBACTER'))
   self.assertLessEqual(t['cutoff']+3,t['end_year'])
   self.assertEqual(t['end_year'],2017 if t['pathogen']=='CRYPTOSPORIDIUM' else 2019)
  for n in ('run.sh','fit.sh','finish.sh'):subprocess.check_call(['bash','-n',str(self.dest/n)])
  with self.assertRaises(ValueError):m.verify(self.dest,plan,m.sha(self.dest/'expansion.json'))
 def test_failed_preparation_blocks_without_R(self):
  p=m.prepare(ROOT,self.dest,False);t=p['tasks'][0]
  with patch.object(m,'verify'),patch.object(m.subprocess,'call') as run:
   self.assertEqual(m.worker(self.dest,t['id'],m.sha(self.dest/'expansion.json')),1);run.assert_not_called()
  self.assertEqual(json.loads((self.dest/t['id']/'task_status.json').read_text())['status'],'BLOCKED')
 def test_partial_archive(self):
  m.prepare(ROOT,self.dest,False)
  self.assertEqual(m.collect(self.dest,m.sha(self.dest/'expansion.json')),1)
  self.assertTrue(Path(str(self.dest)+'.tar.gz').is_file())
 def test_date_gate(self):
  plan=m.prepare(ROOT,self.dest,False);work=self.dest/'LISTERIA';out=work/'result';out.mkdir(parents=True)
  (out/'annual_reconciliation.csv').write_text('unassigned_records\n0\n')
  (out/'date_issues.csv').write_text('month_disagreement\n1\n')
  def record():
   (work/'task_status.json').write_text(json.dumps(dict(status='COMPLETE',exit_status=0,task='LISTERIA',plan_sha256=plan['preparation_sha256'],outputs={str(p.relative_to(work)):m.sha(p) for p in out.iterdir()})))
  record()
  with patch.object(m.prep,'validate_result'):
   with self.assertRaisesRegex(ValueError,'Month-definition'):m.gate(self.dest,plan,'LISTERIA')
   (out/'date_issues.csv').write_text('month_disagreement\n0\n');record();m.gate(self.dest,plan,'LISTERIA')
   (out/'annual_reconciliation.csv').write_text('unassigned_records\n1\n');record()
   with self.assertRaisesRegex(ValueError,'Unassigned'):m.gate(self.dest,plan,'LISTERIA')
 def test_python36(self):ast.parse((ROOT/'scripts/launch_monthly_expansion.py').read_text(),feature_version=(3,6))
if __name__=='__main__':unittest.main()
