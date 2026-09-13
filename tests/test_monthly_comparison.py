import ast
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import launch_monthly_comparison as m
ROOT=Path(__file__).resolve().parents[1]
class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.dest=Path(self.tmp.name)/'plan'
    def test_pairing_and_dispatch(self):
        p=m.prepare(ROOT,self.dest,False);self.assertEqual(len(p['tasks']),12)
        for a,b in zip(p['tasks'][::2],p['tasks'][1::2]):
            self.assertEqual(a['pathogen'],b['pathogen']);self.assertEqual(a['cutoff'],b['cutoff'])
            self.assertFalse(a['seasonal']);self.assertTrue(b['seasonal']);self.assertEqual(a['command'][11:14],b['command'][11:14])
        self.assertEqual(len({t['seed'] for t in p['tasks']}),12)
        for script in ('run.sh','collect.sh'):subprocess.check_call(['bash','-n',str(self.dest/script)])
        r=subprocess.run(['bash',str(self.dest/'run.sh')],env={'SGE_TASK_ID':'undefined'},stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.assertEqual(r.returncode,2)
        self.assertNotIn('SGE_TASK_ID',(self.dest/'collect.sh').read_text())
    def test_unverified_and_changed_plans_block(self):
        p=m.prepare(ROOT,self.dest,False)
        with self.assertRaises(ValueError):m.verify(self.dest,p,m.sha(self.dest/'plan.json'))
        p['verified']=True;(self.dest/'plan.json').write_text(json.dumps(p));h=m.sha(self.dest/'plan.json')
        m.verify(self.dest,p,h)
        (self.dest/'scripts/monthly_seasonal_model.R').write_text('altered')
        with self.assertRaisesRegex(ValueError,'Changed input'):m.verify(self.dest,p,h)
        with self.assertRaises(ValueError):m.verify(self.dest,p,'wrong')
    def test_missing_tasks_archive_failure(self):
        m.prepare(ROOT,self.dest,False)
        self.assertEqual(m.collect(self.dest,m.sha(self.dest/'plan.json')),1)
        self.assertTrue(Path(str(self.dest)+'.tar.gz').is_file())
    def test_result_numerical_and_identity_gates(self):
        work=Path(self.tmp.name)/'task';out=work/'result';out.mkdir(parents=True)
        (work/'task.log').write_text('')
        (out/'status.txt').write_text('EXPLORATORY_FIT_COMPLETE')
        def write(name,rs):
            with (out/name).open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
        write('readiness.csv',[dict(coverage='EXPLORATORY_ASSUMED_CONTINUOUS',coverage_certified='FALSE',cutoff=2011,seasonal='FALSE',heldout_cells=17496,draws=1000)])
        for name in ('fit_INTERNAL.rds','draws_INTERNAL.rds','county_month_predictions.csv','site_month_predictions.csv','site_year_predictions.csv','catchment_month_predictions.csv','catchment_year_predictions.csv','hyperparameters.csv'):(out/name).write_text('fixture')
        metrics=[dict(state=s,horizon_year=h,log_score=-1,log_score_stream_difference=0,interval_score95=1,coverage95=1,coverage50=.5,absolute_error=1) for s in ('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN') for h in (1,2,3)]
        write('site_horizon_metrics.csv',metrics);task=dict(cutoff=2011,seasonal=False)
        m.validate_result(work,task)
        (work/'task.log').write_text("vb.correction' is aborted")
        with self.assertRaisesRegex(ValueError,'numerical'):m.validate_result(work,task)
        (work/'task.log').write_text('');metrics[0]['log_score']='nan';write('site_horizon_metrics.csv',metrics)
        with self.assertRaisesRegex(ValueError,'Nonfinite'):m.validate_result(work,task)
    def test_python36(self):ast.parse((ROOT/'scripts/launch_monthly_comparison.py').read_text(),feature_version=(3,6))
if __name__=='__main__':unittest.main()
