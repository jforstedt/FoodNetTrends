import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import finalize_accepted_state_dashboard as m
ROOT=Path(__file__).resolve().parents[1]
class DashboardTests(unittest.TestCase):
 def test_seven_sources_copy_and_provenance(self):
  with tempfile.TemporaryDirectory() as tmp:
   base=Path(tmp);selected={}
   for k in m.EXPECTED:
    w=base/k;(w/'spline_results').mkdir(parents=True)
    for suffix in ['_IRCatch.csv','_IRSite.csv','_analysis_settings.csv']:(w/'spline_results'/(k+suffix)).write_text('year\n2024\n')
    (w/'spline_results'/(k+'_brm.Rds')).write_bytes(b'checkpoint')
    proof=w/'proof.json';proof.write_text('{}')
    selected[k]=(w,proof,dict(first_year=2000,last_year=2024,settings=dict(baseline_start='2019',baseline_end='2019')))
   dest=base/'new dashboard'
   with patch.object(m,'selection',return_value=selected),patch.object(m,'validate_proof',return_value={}),patch.object(m,'validate_outputs') as validate:
    m.prepare(ROOT,base/'audit',base/'refits',dest)
    self.assertEqual(validate.call_count,7)
   self.assertEqual(len(list((dest/'spline_results').glob('*.csv'))),21)
   self.assertFalse(list(dest.rglob('*.Rds')))
   subprocess.check_call(['bash','-n',str(dest/'run.sh')])
   data=dict(analyses={k:dict(status='success',ircatch=[dict(year=2024)],irsite=[dict(year=2024)]) for k in selected})
   (dest/'dashboard.html').write_text('<html><body><script>window.DASHBOARD_DATA = '+json.dumps(data)+';</script></body></html>')
   subprocess.check_call([sys.executable,str(dest/'finish.py')])
   self.assertTrue(Path(str(dest)+'.tar.gz').exists())
   self.assertTrue(json.loads((dest/'completion.json').read_text())['validated_tables_unchanged'])
   file=next((dest/'spline_results').glob('*.csv'));file.write_text('tampered')
   self.assertNotEqual(subprocess.run([sys.executable,str(dest/'finish.py')],stdout=subprocess.PIPE,stderr=subprocess.PIPE).returncode,0)
if __name__=='__main__':unittest.main()
