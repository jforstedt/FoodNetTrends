import ast
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import launch_monthly_spatial_factorial as m
ROOT=Path(__file__).resolve().parents[1]
F=m.s.f

class SpatialFactorialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.dest=Path(self.tmp.name)/'run'

    def test_complete_grid_and_windows(self):
        ts=m.matrix();self.assertEqual(len(ts),162);self.assertEqual(len({t['id'] for t in ts}),162)
        for p in F.PATHOGENS:
            self.assertEqual({(t['cutoff'],t['temporal'],t['seasonal']) for t in ts if t['pathogen']==p},{(c,x,s) for c in F.origins(p) for x in ('rw1','ar1','spline') for s in (False,True)})
        self.assertTrue(all(t['cutoff']+3<=t['end_year'] for t in ts))
        self.assertEqual({t['cutoff'] for t in ts if t['pathogen']=='CRYPTOSPORIDIUM'},{2011,2013,2014})

    def test_prepare_unverified_and_graph_tamper(self):
        plan=m.prepare(ROOT,self.dest,False)
        self.assertEqual(len(plan['tasks']),162);self.assertFalse(plan['verified'])
        self.assertEqual(len({t['seed'] for t in plan['tasks']}),162)
        for n in ('run.sh','collect.sh'):subprocess.check_call(['bash','-n',str(self.dest/n)])
        for t in plan['tasks']:
            cmd=t['command'];j=next(j for j,v in enumerate(cmd) if v.endswith('/run_monthly_spatial_factorial.R'))
            self.assertEqual(len(cmd[j+1:]),11)
        with patch.object(m.subprocess,'call') as run:
            self.assertEqual(m.worker(self.dest,plan['tasks'][0]['id'],F.sha(self.dest/'plan.json')),1);run.assert_not_called()
        plan['verified']=True;(self.dest/'plan.json').write_text(json.dumps(plan));digest=F.sha(self.dest/'plan.json')
        m.verify(self.dest,plan,digest)
        path=self.dest/'graph/edges.csv';path.write_text(path.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'Changed bound'):m.verify(self.dest,plan,digest)

    def test_verified_source_pointers_and_controls(self):
        root=Path(self.tmp.name)/'repo';root.mkdir()
        for folder in ('scripts','docs','analysis_configs'):(root/folder).symlink_to(ROOT/folder,target_is_directory=True)
        (root/'foodnet-inla-fixed.sif').write_text('synthetic container')
        base=root/'output'/m.SOURCE;base.mkdir(parents=True)
        runtime=root/'runtime';runtime.mkdir();candidate=runtime/'candidate.rds';candidate.write_text('candidate')
        audit=runtime/'audit';audit.mkdir();panel=audit/'county_panel_INTERNAL.rds';panel.write_text('panel')
        source=dict(tasks=[],references=[],inputs={},provenance={})
        for t in m.matrix():
            t=dict(t,id=F.task_id(t['pathogen'],t['cutoff'],t['temporal'],t['seasonal']))
            if t['temporal']=='spline':source['tasks'].append(dict(t,inputs={str(candidate):F.sha(candidate),str(panel):F.sha(panel)},command=['Rscript','/snapshot/run_monthly_spline_factorial.R',str(candidate),str(audit)]))
            else:source['references'].append(dict(t,reused=True))
        (base/'plan.json').write_text(json.dumps(source));(base/'summary.json').write_text(json.dumps(dict(complete=162,issues=[])))
        reports=root/'reports';reports.mkdir()
        for n in ('stream_scores.csv','aggregate_tails.csv','settings.csv'):(reports/n).write_text('synthetic\n')
        ref=dict(work=str(reports),truth_sha256='same',inputs={str(reports/n):F.sha(reports/n) for n in ('stream_scores.csv','aggregate_tails.csv','settings.csv')})
        with patch.object(m.s,'verify'),patch.object(m,'load_control',return_value=ref):plan=m.prepare(root,self.dest,True)
        self.assertEqual(len(plan['references']),162);self.assertEqual(len(plan['tasks']),162)
        self.assertTrue(all(t['reused'] and t['spatial']=='iid' for t in plan['references']))
        self.assertTrue(all(str(candidate) in t['command'] and str(audit) in t['command'] for t in plan['tasks']))
        m.verify(self.dest,plan,F.sha(self.dest/'plan.json'),plan['tasks'][0])
        candidate.write_text('changed')
        with self.assertRaisesRegex(ValueError,'Changed bound'):m.verify(self.dest,plan,F.sha(self.dest/'plan.json'),plan['tasks'][0])

    def test_contrasts_three_way_missing_duplicate(self):
        scores=[]
        for state in F.STATES:
            for spatial in ('iid','bym2'):
                for model,season,val in [('rw1',False,-10),('rw1',True,-7),('ar1',False,-8),('ar1',True,-6),('spline',False,-9),('spline',True,-3)]:
                    gain=0 if spatial=='iid' else (5 if model=='spline' and season else 1)
                    scores.append(dict(pathogen='STEC',cutoff=2011,state=state,year=2012,stream=0,temporal=model,seasonal=season,spatial=spatial,mean_log_score=val+gain))
        sp,tp,three=m.contrasts(scores)
        self.assertEqual(len(sp),60);self.assertEqual(len(tp),40);self.assertEqual(len(three),20)
        self.assertTrue(all(r['spatial_temporal_seasonal_interaction']==4 for r in three))
        self.assertEqual(len(m.equal_sites(three,('spatial_temporal_seasonal_interaction',))),2)
        direct,dt=m.ar1_rw1_contrasts(scores)
        self.assertEqual(len(direct),20);self.assertEqual(len(dt),10)
        self.assertTrue(all(r['interaction']==-1 for r in direct))
        self.assertTrue(all(r['spatial_ar1_rw1_seasonal_interaction']==0 for r in dt))
        asymmetric=[dict(r,mean_log_score=float(r['mean_log_score'])+(2 if r['spatial']=='bym2' and r['temporal']=='ar1' and r['seasonal'] else 0)) for r in scores]
        self.assertTrue(all(r['spatial_ar1_rw1_seasonal_interaction']==2 for r in m.ar1_rw1_contrasts(asymmetric)[1]))
        self.assertEqual(len(m.equal_sites(m.ar1_rw1_contrasts(asymmetric)[1],('spatial_ar1_rw1_seasonal_interaction',))),1)
        missing=m.contrasts(scores[:-1]);self.assertEqual(len(m.equal_sites(missing[2],('spatial_temporal_seasonal_interaction',))),0)
        with self.assertRaisesRegex(ValueError,'Duplicate'):m.contrasts(scores+[scores[0]])

    def test_partial_and_corruption_no_contrasts(self):
        plan=m.prepare(ROOT,self.dest,False)
        (self.dest/'three_way_equal_site_contrasts.csv').write_text('stale')
        with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(m.collect(self.dest,F.sha(self.dest/'plan.json')),1)
        summary=json.loads((self.dest/'summary.json').read_text());self.assertEqual(summary['complete'],0);self.assertEqual(summary['expected'],324)
        self.assertTrue(summary['issues']);self.assertFalse((self.dest/'three_way_equal_site_contrasts.csv').exists())
        self.assertTrue(Path(str(self.dest)+'.tar.gz').is_file())

    def test_reused_copy_hash_rechecked(self):
        self.dest.mkdir();out=self.dest/'references'/'example';out.mkdir(parents=True)
        inputs={}
        for n in ('stream_scores.csv','aggregate_tails.csv','settings.csv'):
            p=out/n;p.write_text('original');inputs[str(p)]=F.sha(p)
        task=dict(id='example',reused=True,reference=dict(inputs={},truth_sha256='same'))
        self.assertEqual(m.load_control(self.dest,dict(inputs=inputs),task)['truth_sha256'],'same')
        (out/'stream_scores.csv').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'Changed bound'):m.load_control(self.dest,dict(inputs=inputs),task)

    def test_python36(self):
        ast.parse((ROOT/'scripts/launch_monthly_spatial_factorial.py').read_text(),feature_version=(3,6))

if __name__=='__main__':unittest.main()
