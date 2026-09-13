"""Final collection must recheck execution provenance, including revoked gates."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect_county_forecast_validation import collect
from run_county_forecast_validation import sha

class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'run';self.root.mkdir()
        self.source=self.root/'source.R';self.source.write_text('# frozen source\n')
        self.task=dict(id='reference',kind='reference')
        self.plan=dict(tasks=[self.task],inputs_verified=True,fingerprints={str(self.source):sha(self.source)})
        self.work=self.root/'reference';self.work.mkdir();(self.work/'result.txt').write_text('pass\n')
        self.record=dict(status='COMPLETE',exit_status=0,outputs={'result.txt':sha(self.work/'result.txt')})
        self.publish()
    def tearDown(self):self.temp.cleanup()
    def publish(self):
        self.record['task_sha256']=hashlib.sha256(json.dumps(dict(task=self.task,fingerprints=self.plan['fingerprints']),sort_keys=True).encode()).hexdigest()
        (self.root/'manifest.json').write_text(json.dumps(self.plan))
        (self.work/'task_status.json').write_text(json.dumps(self.record))
    def run_collect(self):
        with contextlib.redirect_stdout(io.StringIO()),patch('collect_county_forecast_validation.validate_task_outputs'):
            code=collect(self.root)
        self.assertTrue(Path(str(self.root)+'.tar.gz').is_file())
        return code,json.loads((self.root/'summary.json').read_text())
    def test_valid_provenance(self):
        code,summary=self.run_collect();self.assertEqual(code,0);self.assertTrue(summary['execution_complete'])
    def test_empty_inventory_is_failure_with_archive(self):
        self.plan['tasks']=[];self.publish();code,summary=self.run_collect();self.assertEqual(code,1);self.assertFalse(summary['execution_complete'])
    def test_changed_task_identity(self):
        self.plan['tasks'][0]['command']=['different'];(self.root/'manifest.json').write_text(json.dumps(self.plan))
        code,summary=self.run_collect();self.assertEqual(code,1);self.assertIn('identity',summary['tasks'][0]['reason'])
    def test_changed_shared_source(self):
        self.source.write_text('changed');code,summary=self.run_collect();self.assertEqual(code,1);self.assertIn('fingerprint',summary['tasks'][0]['reason'])
    def test_unverified_plan(self):
        self.plan['inputs_verified']=False;self.publish();code,summary=self.run_collect();self.assertEqual(code,1);self.assertFalse(summary['execution_complete'])
    def test_revoked_forecast_gate(self):
        self.task['kind']='forecast';self.publish()
        (self.root/'gate.json').write_text(json.dumps(dict(status='FAIL',manifest_sha256=sha(self.root/'manifest.json'))))
        code,summary=self.run_collect();self.assertEqual(code,1);self.assertIn('gate',summary['tasks'][0]['reason'])
    def test_unreadable_status_retains_archive(self):
        (self.work/'task_status.json').write_text('{broken');code,summary=self.run_collect();self.assertEqual(code,1);self.assertEqual(summary['tasks'][0]['status'],'INVALID_ARTIFACTS')

if __name__=='__main__':unittest.main()
