import ast
import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import launch_monthly_spline_factorial as m
ROOT=Path(__file__).resolve().parents[1]


class SplineFactorialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.dest=Path(self.tmp.name)/'run'

    def test_matrix_and_protected_windows(self):
        ts=m.matrix();self.assertEqual(len(ts),54);self.assertEqual(len({t['id'] for t in ts}),54)
        for p in m.f.PATHOGENS:
            self.assertEqual({(t['cutoff'],t['seasonal']) for t in ts if t['pathogen']==p},{(c,s) for c in m.f.origins(p) for s in (False,True)})
        self.assertTrue(all(t['cutoff']+3<=t['end_year'] for t in ts))

    def test_basis_source_and_prediction_rows_bound(self):
        root=Path(self.tmp.name)/'repo';root.mkdir();(root/'scripts').mkdir();(root/'analysis_configs').mkdir()
        shutil.copytree(str(ROOT/'analysis_configs/monthly_spline_basis'),str(root/'analysis_configs/monthly_spline_basis'))
        spec=json.loads((root/'analysis_configs/monthly_spline_basis/manifest.json').read_text())
        for n in spec['sources']:shutil.copyfile(str(ROOT/n),str(root/n))
        m.verify_basis(root)
        path=root/'analysis_configs/monthly_spline_basis/2011.csv';path.write_text(path.read_text().replace('24048','24049',1))
        with self.assertRaisesRegex(ValueError,'Changed bound'):m.verify_basis(root)
        shutil.copyfile(str(ROOT/'analysis_configs/monthly_spline_basis/2011.csv'),str(path))
        path=root/'scripts/monthly_spline_combination.R';path.write_text(path.read_text()+'\n# changed\n')
        with self.assertRaisesRegex(ValueError,'Changed bound'):m.verify_basis(root)

    def test_preparation_and_unverified_worker(self):
        plan=m.prepare(ROOT,self.dest,False)
        self.assertEqual(len(plan['tasks']),54);self.assertFalse(plan['verified'])
        self.assertEqual(len({t['seed'] for t in plan['tasks']}),54)
        for n in ('run.sh','collect.sh'):subprocess.check_call(['bash','-n',str(self.dest/n)])
        with patch.object(m.subprocess,'call') as execute:
            self.assertEqual(m.worker(self.dest,plan['tasks'][0]['id'],m.f.sha(self.dest/'plan.json')),1)
            execute.assert_not_called()

    def test_runtime_and_basis_copy_changes_rejected(self):
        plan=m.prepare(ROOT,self.dest,False);plan['verified']=True
        (self.dest/'plan.json').write_text(json.dumps(plan));digest=m.f.sha(self.dest/'plan.json')
        m.verify(self.dest,plan,digest)
        path=self.dest/'basis/2011.csv';path.write_text(path.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'Changed bound'):m.verify(self.dest,plan,digest)

    def test_verified_plan_reuses_all_controls_and_binds_runtime(self):
        root=Path(self.tmp.name)/'repo';root.mkdir()
        for folder in ('scripts','docs','analysis_configs'):(root/folder).symlink_to(ROOT/folder,target_is_directory=True)
        (root/'foodnet-inla-fixed.sif').write_text('synthetic container')
        base=root/'output'/m.SOURCE;base.mkdir(parents=True)
        ts=m.f.matrix();source=dict(tasks=[],references=[],inputs={},provenance={})
        runtime=root/'runtime';runtime.mkdir();candidate=runtime/'candidate.rds';candidate.write_text('candidate')
        audit=runtime/'audit';audit.mkdir();panel=audit/'county_panel_INTERNAL.rds';panel.write_text('panel')
        for t in ts:
            if t['reused']:source['references'].append(t)
            else:source['tasks'].append(dict(t,inputs={str(candidate):m.f.sha(candidate),str(panel):m.f.sha(panel)},command=['Rscript','/snapshot/run_monthly_factorial.R',str(candidate),str(audit)]))
        (base/'plan.json').write_text(json.dumps(source))
        (base/'summary.json').write_text(json.dumps(dict(complete=108,expected=108,issues=[],tasks=[dict(status='COMPLETE') for t in ts])))
        reports=root/'reports';reports.mkdir()
        for n in ('stream_scores.csv','aggregate_tails.csv','settings.csv'):(reports/n).write_text('synthetic\n')
        ref=dict(work=str(reports),truth_sha256='same',inputs={str(reports/n):m.f.sha(reports/n) for n in ('stream_scores.csv','aggregate_tails.csv','settings.csv')})
        with patch.object(m.f,'verify'),patch.object(m,'control',return_value=ref):plan=m.prepare(root,self.dest,True)
        self.assertEqual(len(plan['references']),108);self.assertEqual(len(plan['tasks']),54)
        self.assertTrue(all(t['reused'] for t in plan['references']))
        t=plan['tasks'][0];self.assertIn(str(candidate),t['command']);self.assertIn(str(audit),t['command'])
        m.verify(self.dest,plan,m.f.sha(self.dest/'plan.json'),t)
        candidate.write_text('changed')
        with self.assertRaisesRegex(ValueError,'Changed bound'):m.verify(self.dest,plan,m.f.sha(self.dest/'plan.json'),t)

    def test_contrasts_against_both_controls_and_missing_arms(self):
        scores=[]
        for state in m.f.STATES:
            for model,season,value in [('rw1',False,-10),('rw1',True,-7),('ar1',False,-8),('ar1',True,-6),('spline',False,-9),('spline',True,-3)]:
                scores.append(dict(pathogen='STEC',cutoff=2011,state=state,year=2012,stream=0,temporal=model,seasonal=season,mean_log_score=value))
        site,equal=m.contrasts(scores);self.assertEqual(len(site),20);self.assertEqual(len(equal),2)
        by={r['reference']:r for r in equal}
        self.assertEqual(by['rw1']['interaction'],3);self.assertEqual(by['ar1']['interaction'],4)
        self.assertEqual(by['ar1']['spline_minus_reference_nonseasonal'],-1)
        self.assertEqual(by['ar1']['spline_minus_reference_seasonal'],3)
        self.assertEqual(len(m.contrasts(scores[:-1])[1]),0)
        with self.assertRaisesRegex(ValueError,'Duplicate'):m.contrasts(scores+[scores[0]])

    def test_partial_archive_preserves_failures(self):
        m.prepare(ROOT,self.dest,False)
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(m.collect(self.dest,m.f.sha(self.dest/'plan.json')),1)
        summary=json.loads((self.dest/'summary.json').read_text())
        self.assertEqual(summary['complete'],0);self.assertEqual(summary['expected'],162)
        self.assertTrue(Path(str(self.dest)+'.tar.gz').is_file())

    def test_corruption_suppresses_contrasts_and_removes_stale_files(self):
        plan=m.prepare(ROOT,self.dest,False);plan.update(verified=True,tasks=[],references=[],provenance={})
        for model in ('rw1','ar1','spline'):
            for season in (False,True):
                name=m.f.task_id('STEC',2011,model,season);out=self.dest/'references'/name;out.mkdir(parents=True)
                for filename,text in [('stream_scores.csv','state,year,stream,mean_log_score\nCA,2012,0,-3\n'),('aggregate_tails.csv','state,year,stream\nCA,2012,0\n'),('settings.csv','setting\nsynthetic\n')]:
                    path=out/filename;path.write_text(text);plan['inputs'][str(path)]=m.f.sha(path)
                plan['references'].append(dict(id=name,pathogen='STEC',cutoff=2011,temporal=model,seasonal=season,reused=True,reference=dict(inputs={},truth_sha256='same')))
        (self.dest/'plan.json').write_text(json.dumps(plan));digest=m.f.sha(self.dest/'plan.json')
        (out/'stream_scores.csv').write_text('state,year,stream,mean_log_score\nCA,2012,0,100\n')
        (self.dest/'spline_equal_site_contrasts.csv').write_text('stale')
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(m.collect(self.dest,digest),1)
        self.assertFalse((self.dest/'spline_equal_site_contrasts.csv').exists())
        self.assertTrue(json.loads((self.dest/'summary.json').read_text())['issues'])
        with patch.object(m,'verify'),contextlib.redirect_stdout(io.StringIO()):m.collect(self.dest,digest)
        self.assertEqual(json.loads((self.dest/'summary.json').read_text())['tasks'][-1]['status'],'FAILED_OR_MISSING')

    def test_python36(self):
        ast.parse((ROOT/'scripts/launch_monthly_spline_factorial.py').read_text(),feature_version=(3,6))


if __name__=='__main__':unittest.main()
