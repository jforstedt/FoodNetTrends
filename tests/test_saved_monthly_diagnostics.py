import ast
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import launch_saved_monthly_diagnostics as m
ROOT=Path(__file__).resolve().parents[1]
class SavedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.dest=Path(self.tmp.name)/'plan'
    def test_plan_and_seed_isolation(self):
        p=m.prepare(ROOT,self.dest,False);self.assertEqual(len(p['tasks']),12);self.assertFalse(p['refitted'])
        seeds=[]
        for t in p['tasks']:
            self.assertIn('fit_INTERNAL.rds',t['command'][11]);self.assertEqual(t['command'][14],'TRUE' if t['seasonal'] else 'FALSE')
            for s in range(4):
                for start in range(1,2001,100):seeds.extend((t['seed']+s*50000+start,t['seed']+s*50000+10000+start))
        self.assertEqual(len(seeds),len(set(seeds)))
        for n in ('run.sh','collect.sh'):subprocess.check_call(['bash','-n',str(self.dest/n)])
        rc=subprocess.run(['bash',str(self.dest/'run.sh')],env={'SGE_TASK_ID':'undefined'},stdout=subprocess.PIPE,stderr=subprocess.PIPE).returncode
        self.assertEqual(rc,2);self.assertNotIn('SGE_TASK_ID',(self.dest/'collect.sh').read_text())
    def test_fail_closed_and_partial_archive(self):
        p=m.prepare(ROOT,self.dest,False)
        with self.assertRaises(ValueError):m.verify(self.dest,p,m.sha(self.dest/'plan.json'))
        self.assertEqual(m.collect(self.dest,m.sha(self.dest/'plan.json')),1)
        self.assertTrue(Path(str(self.dest)+'.tar.gz').exists())
    def test_changed_checkpoint_blocks(self):
        p=m.prepare(ROOT,self.dest,False);f=self.dest/'checkpoint';f.write_text('original')
        p['tasks'][0]['inputs']={str(f):m.sha(f)};p['verified']=True;(self.dest/'plan.json').write_text(json.dumps(p));h=m.sha(self.dest/'plan.json')
        m.verify(self.dest,p,h,p['tasks'][0]);f.write_text('changed')
        with self.assertRaisesRegex(ValueError,'Changed saved input'):m.verify(self.dest,p,h,p['tasks'][0])
    def test_completion_domain_and_tail_checks(self):
        work=Path(self.tmp.name)/'result_test';out=work/'result';out.mkdir(parents=True)
        (out/'status.txt').write_text('SAVED_MONTHLY_DIAGNOSTICS_COMPLETE')
        def write(name,data):
            with (out/name).open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
        task=dict(cutoff=2011,seasonal=True,seed=10000000)
        write('settings.csv',[dict(cutoff=2011,seasonal='TRUE',base_seed=10000000,streams=4,draws_per_stream=2000,refitted='FALSE',coverage_certified='FALSE')])
        states=('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN')
        scores=[dict(state=s,year=y,stream=k,draws=8000 if k==0 else 2000,mean_log_score=-1,max_cell_density_relative_mcse=.1) for s in states for y in range(2012,2015) for k in range(5)]
        tails=[dict(state=s,year=y,stream=k,draws=8000 if k==0 else 2000,mean_expected=1,median_expected=1,p975_expected=2,max_expected=3,top_one_percent_mean_share=.2,lower95=0,upper95=4) for s in states+('ALL',) for y in range(2012,2015) for k in range(5)]
        write('stream_scores.csv',scores);write('aggregate_tails.csv',tails)
        for n in ('aggregate_draws_INTERNAL.rds','pooled_cell_scores.csv','shape_streams.csv','input_checksums.csv','latent_sd_by_site_year.csv'):(out/n).write_text('fixture')
        m.validate_result(work,task)
        tails[0]['top_one_percent_mean_share']=2;write('aggregate_tails.csv',tails)
        with self.assertRaisesRegex(ValueError,'tail share'):m.validate_result(work,task)
        tails[0]['top_one_percent_mean_share']=.2;write('aggregate_tails.csv',tails[:-1])
        with self.assertRaisesRegex(ValueError,'domain'):m.validate_result(work,task)
    def test_no_fit_entrypoint_and_python36(self):
        s=(ROOT/'scripts/audit_saved_monthly.R').read_text();self.assertNotIn('INLA::inla(',s);self.assertNotIn('fit_monthly_model(',s)
        ast.parse((ROOT/'scripts/launch_saved_monthly_diagnostics.py').read_text(),feature_version=(3,6))
if __name__=='__main__':unittest.main()
