import ast
import csv
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import launch_monthly_spline_inspection as m

class InspectionTest(unittest.TestCase):
    def prepare(self,path):return m.prepare(ROOT,path,False)
    def test_matrix_unverified_worker(self):
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/'run';p=self.prepare(dest);self.assertEqual(len(p['tasks']),54)
            with patch.object(m.subprocess,'call') as call:
                self.assertEqual(m.worker(dest,p['tasks'][0]['id'],m.source.f.sha(dest/'plan.json')),1);call.assert_not_called()
    def fixture(self,out,t):
        out.mkdir(parents=True)
        def write(n,data):
            with (out/n).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
        data=[]
        for state in m.source.f.STATES:
            for y in range(2004,t['cutoff']+4):
                for mo in range(1,13):data.append(dict(state=state,year=y,month=mo,in_training='TRUE' if y<=t['cutoff'] else 'FALSE',observed=2,person_years=100,mean_log_linear=.1,mean_log_nonlinear=.2,mean_log_temporal=.3,linear_change_from_origin=0,nonlinear_change_from_origin=0,temporal_change_from_origin=0))
        write('state_month_components.csv',data);write('december_temporal_changes.csv',[r for r in data if r['year']>t['cutoff'] and r['month']==12])
        write('state_coefficients.csv',[dict(state=s,component='linear' if i==0 else 'nonlinear',basis_column=i,posterior_mean=.1) for s in m.source.f.STATES for i in range(5)])
        write('settings.csv',[dict(cutoff=t['cutoff'],seasonal='TRUE' if t['seasonal'] else 'FALSE',refitted='FALSE',resampled='FALSE',joint_intervals='FALSE')])
        write('input_checksums.csv',[dict(path='fit',md5='a'*32),dict(path='truth',md5='b'*32)])
        (out/'status.txt').write_text('SAVED_SPLINE_COMPONENT_INSPECTION_COMPLETE\n')
    def test_integrity_partial_portable_archive(self):
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/'run';p=self.prepare(dest);p['verified']=True;(dest/'plan.json').write_text(json.dumps(p));digest=m.source.f.sha(dest/'plan.json');t=p['tasks'][0];work=dest/t['id'];self.fixture(work/'result',t)
            m.validate_result(work,t)
            record=dict(task=t['id'],status='COMPLETE',exit_status=0,plan_sha256=digest,outputs={str(f.relative_to(work)):m.source.f.sha(f) for f in work.rglob('*') if f.is_file()});(work/'task_status.json').write_text(json.dumps(record))
            (dest/'secret_INTERNAL.rds').write_text('private');self.assertEqual(m.collect(dest,digest),1);self.assertEqual(json.loads((dest/'summary.json').read_text())['complete'],1)
            with tarfile.open(str(dest)+'.tar.gz') as tar:
                self.assertFalse(any('_INTERNAL' in n for n in tar.getnames()));manifest=json.load(tar.extractfile('report_sha256.json'))
                import hashlib
                for name,h in manifest.items():self.assertEqual(hashlib.sha256(tar.extractfile(name).read()).hexdigest(),h)
            (work/'result/state_coefficients.csv').write_text('broken');self.assertEqual(m.collect(dest,digest),1);self.assertEqual(json.loads((dest/'summary.json').read_text())['complete'],0)
    def test_wrong_settings_and_incomplete_components(self):
        with tempfile.TemporaryDirectory() as td:
            work=Path(td);t=m.source.matrix()[0];self.fixture(work/'result',t)
            with self.assertRaises(ValueError):m.validate_result(work,dict(t,seasonal=not t['seasonal']))
            path=work/'result/state_month_components.csv';s=path.read_text().splitlines();path.write_text('\n'.join(s[:-1])+'\n')
            with self.assertRaisesRegex(ValueError,'Incomplete'):m.validate_result(work,t)
    def test_python36(self):ast.parse((ROOT/'scripts/launch_monthly_spline_inspection.py').read_text(),feature_version=(3,6))
if __name__=='__main__':unittest.main()
