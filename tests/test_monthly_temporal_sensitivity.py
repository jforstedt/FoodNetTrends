import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import launch_monthly_temporal_sensitivity as m
ROOT=Path(__file__).resolve().parents[1]
class SensitivityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.dest=Path(self.tmp.name)/'plan'
    def test_six_new_fits_and_reused_reference(self):
        p=m.prepare(ROOT,self.dest,False)
        self.assertEqual(len(p['tasks']),6);self.assertEqual(p['new_fits'],6);self.assertEqual(p['reference_fits_reused'],6)
        self.assertEqual(p['trend_sd_upper'],.25);self.assertEqual(p['reference_trend_sd_upper'],.5)
        self.assertTrue(all(t['seasonal'] for t in p['tasks']));self.assertEqual(len({t['seed'] for t in p['tasks']}),6)
        for t in p['tasks']:
            self.assertIn('run_monthly_temporal_sensitivity.R',t['command'][10]);self.assertIn(m.BASELINE,t['baseline'])
        for n in ('run.sh','collect.sh'):subprocess.check_call(['bash','-n',str(self.dest/n)])
        rc=subprocess.run(['bash',str(self.dest/'run.sh')],env={'SGE_TASK_ID':'undefined'},stdout=subprocess.PIPE,stderr=subprocess.PIPE).returncode
        self.assertEqual(rc,2)
    def test_unverified_or_altered_blocks(self):
        p=m.prepare(ROOT,self.dest,False)
        with self.assertRaises(ValueError):m.verify(self.dest,p,m.sha(self.dest/'plan.json'))
        p['verified']=True;(self.dest/'plan.json').write_text(json.dumps(p));h=m.sha(self.dest/'plan.json');m.verify(self.dest,p,h)
        f=self.dest/'scripts/monthly_seasonal_model.R';f.write_text('changed')
        with self.assertRaisesRegex(ValueError,'Changed sensitivity input'):m.verify(self.dest,p,h)
    def test_partial_archive_failure(self):
        m.prepare(ROOT,self.dest,False);self.assertEqual(m.collect(self.dest,m.sha(self.dest/'plan.json')),1)
        self.assertTrue(Path(str(self.dest)+'.tar.gz').exists())
    def test_python36(self):ast.parse((ROOT/'scripts/launch_monthly_temporal_sensitivity.py').read_text(),feature_version=(3,6))
if __name__=='__main__':unittest.main()
