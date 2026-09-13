import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_next_phase_task import execution_identity,execution_provenance,verify_checkpoints,run,sha
from collect_next_phase_batch import collect

class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'run';self.root.mkdir()
        self.task=dict(id='test',kind='definitions',commands=[[sys.executable,'-c',"from pathlib import Path;p=Path('test/result');p.mkdir();(p/'status.txt').write_text('done');(p/'fit_INTERNAL.rds').write_bytes(b'checkpoint')"]])
        self.plan=dict(tasks=[self.task],verified=True,fingerprints={})
        (self.root/'plan.json').write_text(json.dumps(self.plan))
    def tearDown(self):self.temp.cleanup()
    def execute(self):
        with patch('run_next_phase_task.validate'):self.assertEqual(run(self.root,'test'),0)
        return json.loads((self.root/'test/task_status.json').read_text())
    def test_new_worker_records_identity_and_checkpoint(self):
        r=self.execute();self.assertTrue(execution_provenance(self.root,self.plan,self.task,r)['identity_verified'])
        self.assertEqual(set(r['checkpoint_sha256']),{'result/fit_INTERNAL.rds'})
        self.assertTrue(verify_checkpoints(self.root/'test',r))
        self.assertNotIn('result/fit_INTERNAL.rds',r['outputs'])
        (self.root/'test/result/fit_INTERNAL.rds').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'Checkpoint'):verify_checkpoints(self.root/'test',r)
    def test_changed_command_rejected(self):
        r=self.execute();self.task['commands']=[['different']]
        with self.assertRaisesRegex(ValueError,'identity'):execution_provenance(self.root,self.plan,self.task,r)
    def test_legacy_explicit_not_invented(self):
        p=execution_provenance(self.root,self.plan,self.task,dict(status='COMPLETE'))
        self.assertFalse(p['identity_verified']);self.assertEqual(p['provenance_status'],'LEGACY_IDENTITY_UNVERIFIED')
    def test_exact_recovered_identity(self):
        r=self.execute();dest=self.root.parent/'recovery';shutil.copytree(str(self.root),str(dest))
        new=dict(self.plan,recovery=dict(source=str(self.root),source_plan_sha256=sha(self.root/'plan.json')))
        (dest/'plan.json').write_text(json.dumps(new))
        self.assertEqual(execution_provenance(dest,new,self.task,r)['provenance_status'],'RECOVERED_EXECUTION_IDENTITY_VERIFIED')
        changed=dict(self.task,commands=[['different']])
        with self.assertRaises(ValueError):execution_provenance(dest,new,changed,r)
    def test_collection_legacy_warning_and_unverified_guard(self):
        r=self.execute();r.pop('task_sha256');r.pop('plan_sha256');(self.root/'test/task_status.json').write_text(json.dumps(r))
        with patch('collect_next_phase_batch.validate'),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(collect(self.root),0)
        summary=json.loads((self.root/'summary.json').read_text());self.assertFalse(summary['tasks'][0]['identity_verified'])
        self.plan['verified']=False;(self.root/'plan.json').write_text(json.dumps(self.plan))
        with patch('collect_next_phase_batch.validate'),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(collect(self.root),1)

if __name__=='__main__':unittest.main()
