import csv
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
import shutil
import subprocess
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import launch_campylobacter_cx_comparison as m

class Launcher(unittest.TestCase):
    def test_six_matched_tasks_with_disjoint_seeds(self):
        tasks=m.matrix();self.assertEqual(len(tasks),6);self.assertEqual(len({t['seed'] for t in tasks}),6)
        self.assertEqual({(t['cutoff'],t['local_seasonality']) for t in tasks},{(c,l) for c in (2011,2013,2016) for l in (False,True)})
        self.assertTrue(all(t['target']=='CX+' and not t['weather'] and not t['age'] and t['temporal']=='rw1' for t in tasks))
    def test_visible_preparation_only_and_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for sub in ('scripts','docs','analysis_configs'):(root/sub).mkdir()
            repo=Path(__file__).resolve().parents[1]
            for name in m.SCRIPTS:shutil.copyfile(repo/'scripts'/name,root/'scripts'/name)
            (root/'docs/campylobacter_diagnostic_era_protocol.md').write_text('protocol')
            (root/'analysis_configs/campylobacter_regional_audit_source.json').write_text('{}')
            with patch.object(m.shutil,'which',return_value='/bin/tool'),patch.object(m.base,'submit',return_value='123') as submit:out=m.launch(root)
            self.assertEqual(submit.call_count,1);self.assertEqual(submit.call_args.args[1],'foodnet_cx_prepare')
            self.assertFalse((out/'plan.json').exists());m.package_check(out/'bundle',m.base.sha(out/'bundle/bundle.json'))
            subprocess.run([sys.executable,'-E',str(out/'bundle/launch_campylobacter_cx_comparison.py'),'--help'],stdout=subprocess.DEVNULL,check=True)
            m.package_check(out/'bundle',m.base.sha(out/'bundle/bundle.json'))
            (out/'bundle/unexpected.pyc').write_text('bad')
            with self.assertRaisesRegex(ValueError,'members'):m.package_check(out/'bundle',m.base.sha(out/'bundle/bundle.json'))
    def test_root_status_required(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);(out/'reports').mkdir();(out/'reports/status.txt').write_text('CX_MODEL_COMPLETE')
            with self.assertRaises(OSError):m.validate(out,m.matrix()[0])
    def test_internal_replay_excluded_from_portable_archive(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'run';(out/'preparation/replay_INTERNAL').mkdir(parents=True)
            (out/'preparation/replay_INTERNAL/counts.csv').write_text('private');(out/'preparation/state_year_target_counts.csv').write_text('state')
            m.base.archive(out)
            with tarfile.open(str(out)+'.tar.gz') as a:
                self.assertNotIn('preparation/replay_INTERNAL/counts.csv',a.getnames());self.assertIn('preparation/state_year_target_counts.csv',a.getnames())
    def fixture(self,out,t):
        (out/'reports').mkdir();r=out/'reports'
        for p in (out/'status.txt',r/'status.txt'):p.write_text('CX_MODEL_COMPLETE')
        for p in (out/'fit_INTERNAL.rds',out/'truth_INTERNAL.csv',r/'pooled_cell_scores_INTERNAL.csv'):p.write_text('internal')
        m.base.write(r/'cx_model_metadata.json',dict(version='campylobacter_cx_model_v1',streams=4,draws_per_stream=1000,weather=False,age=False,task_id=t['task_id'],cutoff=t['cutoff'],local_seasonality=t['local_seasonality'],seed=t['seed'],target='recorded_CX_positive',scientific_acceptance=False,refitted=t['cutoff']!=2011))
        def csvwrite(name,rows):
            with (r/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        rows=[];tails=[]
        for state in sorted(m.STATES|{'ALL'}):
            for year in range(t['cutoff']+1,t['cutoff']+4):
                for stream in range(5):
                    common=dict(state=state,year=year,stream=stream,draws=4000 if stream==0 else 1000)
                    if state!='ALL':rows.append(dict(common,mean_log_score=-1,max_cell_density_relative_mcse=.01))
                    f=10 if state=='ALL' else 1;tails.append(dict(common,observed=f,mean_expected=f,median_expected=f,p975_expected=2*f,max_expected=3*f,lower95=0,median_predictive=f,upper95=3*f,top_one_percent_mean_share=.01,prob_above_twice_observed=.1))
        csvwrite('stream_scores.csv',rows);csvwrite('aggregate_tails.csv',tails)
        csvwrite('settings.csv',[dict(draws_per_stream=1000,base_seed=t['seed'],streams=4)])
        csvwrite('rng_protocol.csv',[dict(protocol='explicit_config_v2',base_seed=t['seed'],stream_stride=50000,batch_size=100,r_configuration_seed_offset=20000,predictive_seed_offset=10000,inla_version='26.8.7')])
    def test_valid_refit_and_reuse_domains(self):
        for t in (m.matrix()[0],m.matrix()[2]):
            with tempfile.TemporaryDirectory() as d:self.fixture(Path(d),t);m.validate(Path(d),t)
    def test_nonfinite_metric_and_rng_seed_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);t=m.matrix()[2];self.fixture(out,t)
            p=out/'reports/rng_protocol.csv';text=p.read_text();p.write_text(text.replace(str(t['seed']),'123'))
            with self.assertRaisesRegex(ValueError,'RNG'):m.validate(out,t)
            p.write_text(text);p=out/'reports/stream_scores.csv';p.write_text(p.read_text().replace('-1','nan',1))
            with self.assertRaisesRegex(ValueError,'Nonfinite'):m.validate(out,t)
    def test_missing_workers_still_archive_failed_summary(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'run';dest.mkdir();tasks=[]
            for t in m.matrix():
                t['output']=str(dest/t['task_id']/'result');tasks.append(dict(task=t))
            m.base.write(dest/'plan.json',dict(tasks=tasks))
            with patch.object(m,'verify'):code=m.collect(dest,'digest')
            self.assertEqual(code,1);s=m.base.read(dest/'summary.json');self.assertEqual(s['complete'],0);self.assertEqual(s['expected'],6);self.assertEqual(s['new_fits'],4);self.assertEqual(s['rescored_saved_fits'],2);self.assertFalse(s['scientific_acceptance'])
            self.assertTrue(Path(str(dest)+'.tar.gz').is_file())

    def test_wrong_refitted_identity_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);t=m.matrix()[0];self.fixture(out,t);p=out/'reports/cx_model_metadata.json';j=m.base.read(p);j['refitted']=True;m.base.write(p,j)
            with self.assertRaisesRegex(ValueError,'target/status'):m.validate(out,t)

if __name__=='__main__':unittest.main()
