import importlib.util
import csv
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(n):
 s=importlib.util.spec_from_file_location(n,ROOT/'scripts'/(n+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class CorrectionTest(unittest.TestCase):
 def test_scope_and_existing_state_csv(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);state=b/'state';state.mkdir()
   (state/'CRYPTOSPORIDIUM_IRCatch.csv').write_text('year,rate\n2017,1\n2018,0\n')
   before=(state/'CRYPTOSPORIDIUM_IRCatch.csv').read_bytes()
   load('audit_crypto_state_outputs').audit(state,b/'audit')
   r=json.loads((b/'audit/state_output_audit.json').read_text())
   self.assertEqual(r[0]['post_surveillance_years'],[2018]);self.assertEqual(before,(state/'CRYPTOSPORIDIUM_IRCatch.csv').read_bytes())
   dest=b/'with spaces';load('launch_crypto_correction').prepare(ROOT,dest,state)
   for n in ('prepare','run','collect'):subprocess.check_call(['bash','-n',str(dest/(n+'.sh'))])
   plan=json.loads((dest/'manifest.json').read_text());self.assertEqual(plan['forecast_test'],[2015,2017]);self.assertEqual(len(plan['tasks']),4)
if __name__=='__main__':unittest.main()
