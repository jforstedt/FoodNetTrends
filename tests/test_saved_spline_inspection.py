import ast
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from launch_saved_spline_inspection import prepare,run,sha
ROOT=Path(__file__).resolve().parents[1]
class InspectionTests(unittest.TestCase):
    def test_unverified_cannot_execute_and_plan_is_pinned(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'run';p=prepare(ROOT,Path(temp)/'source',dest,False)
            self.assertEqual(len(p['tasks']),2);self.assertFalse(p['models_fitted']);self.assertFalse(p['posterior_sampling'])
            self.assertIn('--expected-plan-sha '+sha(dest/'plan.json'),(dest/'run.sh').read_text())
            self.assertNotIn('SGE_TASK_ID',(dest/'run.sh').read_text())
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(run(dest,sha(dest/'plan.json')),1)
            self.assertTrue(Path(str(dest)+'.tar.gz').exists())
    def test_changed_plan_rejected_before_process(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'run';p=prepare(ROOT,Path(temp)/'source',dest,False);digest=sha(dest/'plan.json')
            p['verified']=True;(dest/'plan.json').write_text(json.dumps(p))
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(run(dest,digest),1)
            self.assertIn('Plan changed',json.loads((dest/'summary.json').read_text())['issues'][0])
    def test_worker_archives_success_and_empty_marker_failure(self):
        for empty in (False,True):
            with self.subTest(empty=empty),tempfile.TemporaryDirectory() as temp:
                dest=Path(temp)/'run';plan=prepare(ROOT,Path(temp)/'source',dest,False)
                plan['verified']=True
                for task in plan['tasks']:
                    log=Path(temp)/(task['id']+'.log');log.write_text('original fit log')
                    task['log']=str(log);plan['inputs'][str(log)]=sha(log)
                (dest/'plan.json').write_text(json.dumps(plan))
                def process(cmd,**kwargs):
                    out=Path(cmd[-3]);out.mkdir(parents=True)
                    (out/'status.txt').write_text('' if empty else 'SAVED_SPLINE_INSPECTION_COMPLETE\n')
                    return SimpleNamespace(returncode=0)
                with patch('launch_saved_spline_inspection.subprocess.run',side_effect=process),contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(run(dest,sha(dest/'plan.json')),1 if empty else 0)
                summary=json.loads((dest/'summary.json').read_text())
                self.assertEqual(summary['execution_complete'],not empty)
                self.assertEqual(len(summary['tasks']),2)
                for name,digest in json.loads((dest/'report_sha256.json').read_text()).items():self.assertEqual(sha(dest/name),digest)
                self.assertTrue(Path(str(dest)+'.tar.gz').is_file())

    def test_python36_and_no_fitting_commands(self):
        ast.parse((ROOT/'scripts/launch_saved_spline_inspection.py').read_text(),feature_version=(3,6))
        r=(ROOT/'scripts/inspect_saved_spline.R').read_text()
        for call in ('inla.posterior.sample(', 'INLA::inla(', 'brm(', 'saveRDS('):self.assertNotIn(call,r)
if __name__=='__main__':unittest.main()
