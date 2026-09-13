import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_county_forecast_validation as runner
from collect_county_forecast_validation import paired_scores
class ValidationTests(unittest.TestCase):
 def test_gate_blocks_command_and_hash_changes_reject(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);code=root/'source.txt';code.write_text('fixed')
   task=dict(id='forecast_001',kind='forecast',command=[sys.executable,'-c','raise Exception("must not execute")'])
   plan=dict(inputs_verified=True,tasks=[task],fingerprints={str(code):runner.sha(code)})
   m=root/'manifest.json';m.write_text(json.dumps(plan))
   (root/'gate.json').write_text(json.dumps(dict(status='REVIEW_REQUIRED',manifest_sha256=runner.sha(m))))
   self.assertEqual(runner.run(root,task['id']),2)
   self.assertEqual(json.loads((root/task['id']/'task_status.json').read_text())['status'],'BLOCKED_GATE')
   task['id']='changed';m.write_text(json.dumps(plan));code.write_text('changed')
   self.assertEqual(runner.run(root,'changed'),1)
 def test_paired_targets_and_no_false_independence(self):
  a=[dict(fips='00001',state='AA',year='2018',observed='1',population='100',log_predictive_density='-2')]
  b=[dict(a[0],log_predictive_density='-1')]
  self.assertEqual(paired_scores(a,b)[0]['log_score_gain'],1)
  with self.assertRaises(ValueError):paired_scores(a,[dict(b[0],population='101')])
  with self.assertRaises(ValueError):paired_scores(a,b+b)
if __name__=='__main__':unittest.main()
