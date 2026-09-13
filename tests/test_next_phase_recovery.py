import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from launch_next_phase_batch import prepare,write_scripts,submit
from recover_next_phase_batch import prepare_recovery
from run_next_phase_task import sha

class RecoveryTests(unittest.TestCase):
    def test_actual_shell_dispatch_with_sge_undefined(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);(d/'scripts').mkdir()
            (d/'scripts/run_next_phase_task.py').write_text('import pathlib,sys\npathlib.Path(sys.argv[1],"called.txt").write_text(sys.argv[2])\n')
            write_scripts(d,{'basis':['basis'],'spline':['one','two']})
            env=dict(os.environ,SGE_TASK_ID='undefined')
            r=subprocess.run(['bash',str(d/'basis.sh')],env=env)
            self.assertEqual(r.returncode,0);self.assertEqual((d/'called.txt').read_text(),'basis')
            r=subprocess.run(['bash',str(d/'spline.sh')],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertEqual(r.returncode,2)
            env['SGE_TASK_ID']='2';r=subprocess.run(['bash',str(d/'spline.sh')],env=env)
            self.assertEqual(r.returncode,0);self.assertEqual((d/'called.txt').read_text(),'two')

    def test_recovery_submission_keeps_gate_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls=[]
            def qsub(cmd,**kwargs):
                calls.append(cmd);return str(100+len(calls))+'\n'
            groups={'definitions':['definitions'],'cyclospora_serial':['cyclospora_threads_1'],
                    'cyclospora_parallel':['cyclospora_threads_8'],'basis':['basis'],'gate':['gate'],
                    'spline':['spline_'+str(i) for i in range(12)]}
            with patch('launch_next_phase_batch.subprocess.check_output',side_effect=qsub),contextlib.redirect_stdout(io.StringIO()):
                submit(Path(tmp),groups)
            self.assertEqual(len(calls),7)
            self.assertTrue(all('foodnet_phase_sampling' not in c for c in calls))
            self.assertEqual(calls[4][calls[4].index('-hold_jid')+1],'104')
            self.assertEqual(calls[5][calls[5].index('-hold_jid')+1],'105')
            self.assertEqual(calls[6][calls[6].index('-hold_jid')+1],'101,102,103,104,105,106')

    def test_recovery_copies_53_and_submits_no_sampling(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);old=base/'old';new=base/'new'
            plan,_=prepare(ROOT,old,base/'earlier',base/'raw',verified=False)
            plan['verified']=True;(old/'plan.json').write_text(json.dumps(plan))
            summary=[]
            for task in plan['tasks']:
                complete=task['kind']=='sampling'
                summary.append(dict(task=task['id'],status='COMPLETE' if complete else 'FAILED'))
                if complete:
                    work=old/task['id'];work.mkdir();(work/'result').mkdir();artifact=work/'result/example.csv';artifact.write_text('synthetic\n')
                    (work/'task_status.json').write_text(json.dumps(dict(status='COMPLETE',exit_status=0,outputs={'result/example.csv':sha(artifact)})))
            (old/'summary.json').write_text(json.dumps(dict(tasks=summary)))
            with patch('recover_next_phase_batch.validate') as validator:
                groups=prepare_recovery(old,new)
                self.assertEqual(validator.call_count,53)
            self.assertNotIn('sampling',groups);self.assertEqual(sum(map(len,groups.values())),17)
            restored=json.loads((new/'plan.json').read_text())
            self.assertEqual(len(restored['tasks']),70)
            for before,after in zip(plan['tasks'],restored['tasks']):
                self.assertEqual(json.dumps(after['commands']).replace(str(new),str(old)),json.dumps(before['commands']))
            for p,h in restored['fingerprints'].items():self.assertEqual(sha(p),h)
            first=next(t for t in plan['tasks'] if t['kind']=='sampling')
            (old/first['id']/'result/example.csv').write_text('tampered\n')
            with patch('recover_next_phase_batch.validate'),self.assertRaisesRegex(ValueError,'Changed source/input'):
                prepare_recovery(old,base/'bad')

if __name__=='__main__':unittest.main()
