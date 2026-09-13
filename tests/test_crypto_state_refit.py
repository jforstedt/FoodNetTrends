import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(n):
 s=importlib.util.spec_from_file_location(n,ROOT/'scripts'/(n+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class StateRefitTest(unittest.TestCase):
 def test_scope_snapshot_and_coverage_gate(self):
  with tempfile.TemporaryDirectory() as t:
   dest=Path(t)/'space path';m=load('launch_crypto_state_refit');cmd=m.prepare(ROOT,dest,Path('/data'))
   subprocess.check_call(['bash','-n',str(dest/'run.sh')])
   c=json.loads((dest/'manifest.json').read_text())['command']
   for flag,value in [('--pathogen','CRYPTOSPORIDIUM'),('--baseline_start','2015'),('--baseline_end','2017'),('--parasite_end_year','2017'),('--chains','6'),('--iterations','10001')]:self.assertEqual(c[c.index(flag)+1],value)
   self.assertEqual((dest/'scripts/functions.R').read_bytes(),(ROOT/'bin/functions.R').read_bytes())
   self.assertNotIn('nextflow',c)
   self.assertEqual(c[c.index('--env')+1], 'OPENBLAS_NUM_THREADS=2,OMP_NUM_THREADS=2,MKL_NUM_THREADS=2')
   prefix=dest/'spline_results/CRYPTOSPORIDIUM_combined'
   for suffix in ('_IRCatch.csv','_IRSite.csv','_EstIRRCatch_2015_2017.csv'):Path(str(prefix)+suffix).write_text('year,value\n2015,1\n2016,1\n2017,1\n')
   for suffix in ('_analysis_settings.csv','_convergence_diagnostics.csv','_brm.Rds'):Path(str(prefix)+suffix).write_text('placeholder')
   (dest/'fit_exit_status.txt').write_text('0\n');collector=load('collect_crypto_state_refit')
   self.assertEqual(collector.collect(dest),0)
   with tarfile.open(str(dest)+'.tar.gz') as a:self.assertFalse(any(n.lower().endswith('.rds') for n in a.getnames()))
   Path(str(prefix)+'_IRCatch.csv').write_text('year,value\n2018,0\n')
   self.assertEqual(collector.collect(dest),1)
if __name__=='__main__':unittest.main()
