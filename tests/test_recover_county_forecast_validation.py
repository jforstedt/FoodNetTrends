import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('recovery', str(Path(__file__).resolve().parents[1] / 'scripts/recover_county_forecast_validation.py'))
m = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(m)


class RecoveryTests(unittest.TestCase):
    def fixture(self, base):
        old = base / 'old'; old.mkdir(); (old / 'scripts').mkdir(); (old / 'tests').mkdir()
        for name in ('run_county_forecast_validation.py', 'county_forecast_artifacts.py', 'gate.py', 'collect_county_forecast_validation.py'):
            (old / 'scripts' / name).write_text('def validate_task_outputs(work, task):\n assert (work / "result/data.csv").is_file()\n')
        container = base / 'container.sif'; container.write_text('unchanged')
        fingerprints = {str(p):m.sha(p) for p in (old / 'scripts').iterdir()}; fingerprints[str(container)] = m.sha(container)
        tasks = [dict(id='done',kind='calibration',command=['Rscript',str(old / 'scripts/gate.py'),str(old / 'done/result')]), dict(id='missing',kind='horizon',command=[]), dict(id='forecast',kind='forecast',command=[])]
        plan = dict(inputs_verified=True,fingerprints=fingerprints,tasks=tasks,calibration_collect_command=['python3',str(old / 'scripts/gate.py'),str(old)])
        (old / 'manifest.json').write_text(json.dumps(plan)); (old / 'submission.json').write_text('{"screen":"123"}')
        result = old / 'done/result'; result.mkdir(parents=True); (result / 'data.csv').write_text('a,b\n1,2\n'); (result / 'fit.rds').write_text('do not copy')
        status = dict(status='COMPLETE',exit_status=0,task_sha256=m.identity(tasks[0],fingerprints),outputs={'result/data.csv':m.sha(result / 'data.csv')})
        (old / 'done/task_status.json').write_text(json.dumps(status))
        return old,plan

    def test_reuses_only_valid_outputs_and_rebases_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            old,plan=self.fixture(Path(tmp)); dest=Path(tmp)/'new'
            recovery=m.prepare(old,dest,verify_jobs=False)
            self.assertEqual(recovery['reused'],['done']); self.assertEqual(recovery['missing_screen'],['missing'])
            self.assertEqual(recovery['missing_forecast'],['forecast'])
            self.assertFalse((dest/'done/result/fit.rds').exists()); self.assertTrue((old/'done/result/fit.rds').exists())
            new=json.loads((dest/'manifest.json').read_text()); record=json.loads((dest/'done/task_status.json').read_text())
            self.assertEqual(new['tasks'][0]['command'][-1],str(dest/'done/result'))
            self.assertEqual(record['task_sha256'],m.identity(new['tasks'][0],new['fingerprints']))
            self.assertEqual((dest/'scripts/gate.py').read_bytes(),(old/'scripts/gate.py').read_bytes())
            self.assertTrue((dest/'recovery_provenance/done.json').exists())
            subprocess.check_call(['bash','-n',str(dest/'screen.sh')])
            self.assertNotIn('-tc',(dest/'screen.sh').read_text())

    def test_new_checkpoint_hash_is_preserved_and_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            old,_=self.fixture(Path(tmp));status=old/'done/task_status.json'
            r=json.loads(status.read_text());r['checkpoint_sha256']={'result/fit.rds':m.sha(old/'done/result/fit.rds')};status.write_text(json.dumps(r))
            dest=Path(tmp)/'new';m.prepare(old,dest,False)
            self.assertEqual((dest/'done/result/fit.rds').read_bytes(),(old/'done/result/fit.rds').read_bytes())
            self.assertEqual(json.loads((dest/'done/task_status.json').read_text())['checkpoint_sha256'],r['checkpoint_sha256'])
            (old/'done/result/fit.rds').write_text('changed checkpoint')
            with self.assertRaisesRegex(ValueError,'checkpoint'):m.prepare(old,Path(tmp)/'bad',False)

    def test_changed_complete_output_and_changed_source_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            old,_=self.fixture(Path(tmp)); (old/'done/result/data.csv').write_text('changed')
            with self.assertRaisesRegex(ValueError,'Changed completed artifact'):m.prepare(old,Path(tmp)/'new',False)
            self.assertFalse((Path(tmp)/'new').exists())
        with tempfile.TemporaryDirectory() as tmp:
            old,_=self.fixture(Path(tmp)); (old/'scripts/gate.py').write_text('changed')
            with self.assertRaisesRegex(ValueError,'Changed original'):m.prepare(old,Path(tmp)/'new',False)

    def test_only_explicit_scheduler_absence_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            old,_=self.fixture(Path(tmp))
            for code,out in ((0,'job exists'),(1,'permission denied'),(1,'Following jobs do not exist: 124')):
                with mock.patch.object(m.subprocess,'run',side_effect=[subprocess.CompletedProcess([],0,'<job_info/>',''),subprocess.CompletedProcess([],code,out,'')]):
                    with self.assertRaises(ValueError):m.require_finished(old)
            with mock.patch.object(m.subprocess,'run',side_effect=[subprocess.CompletedProcess([],0,'<job_info/>',''),subprocess.CompletedProcess([],1,'','Following jobs do not exist or permissions are not sufficient: \n123\n')]):
                self.assertEqual(m.require_finished(old),{'screen':'123'})

    def test_live_inventory_blocks_ambiguous_absence(self):
        with tempfile.TemporaryDirectory() as tmp:
            old,_=self.fixture(Path(tmp))
            responses=[subprocess.CompletedProcess([],0,'<job_info><JB_job_number>123</JB_job_number></job_info>',''), subprocess.CompletedProcess([],1,'','Following jobs do not exist or permissions are not sufficient: 123')]
            with mock.patch.object(m.subprocess,'run',side_effect=responses):
                with self.assertRaises(ValueError):m.require_finished(old)

    def test_completed_forecast_requires_original_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            old,plan=self.fixture(Path(tmp)); plan['tasks'][0]['kind']='forecast'
            (old/'manifest.json').write_text(json.dumps(plan))
            status=json.loads((old/'done/task_status.json').read_text()); status['task_sha256']=m.identity(plan['tasks'][0],plan['fingerprints'])
            (old/'done/task_status.json').write_text(json.dumps(status))
            (old/'gate.json').write_text(json.dumps(dict(status='REVIEW_REQUIRED',manifest_sha256=m.sha(old/'manifest.json'))))
            with self.assertRaisesRegex(ValueError,'valid original gate'):m.prepare(old,Path(tmp)/'new',False)

    def test_existing_recovery_claim_blocks_before_preparation(self):
        with tempfile.TemporaryDirectory() as tmp:
            old,_=self.fixture(Path(tmp)); (old/'recovery_submission.json').write_text('{}')
            with mock.patch('sys.argv',['recover',str(old)]), mock.patch.object(m,'prepare') as prepare, mock.patch.object(m,'submit') as submit:
                with self.assertRaises(SystemExit):m.main()
                prepare.assert_not_called(); submit.assert_not_called()

    def test_submission_dependencies_missing_only_no_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp); commands=[]
            def qsub(cmd,**kwargs):commands.append(cmd);return str(100+len(commands))
            with mock.patch.object(m.subprocess,'check_output',side_effect=qsub):m.submit(dest,dict(missing_screen=['a']*10,missing_forecast=['b']*54))
            self.assertEqual(len(commands),4)
            self.assertIn('1-10',commands[0]); self.assertIn('1-54',commands[2]); self.assertIn('102',commands[2])
            self.assertTrue(all('-tc' not in c for c in commands))
            self.assertIn('h_rt=04:00:00,h_rss=16384M,mem_free=16384M,h_vmem=32G',commands[0])

if __name__=='__main__':unittest.main()
