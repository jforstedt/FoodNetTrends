import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from launch_next_phase_batch import prepare,FILES
from run_next_phase_task import run,validate,sha,prerequisite


def csvfile(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


class NextPhaseBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.dest=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_prepare_only_snapshots_and_dependencies(self):
        out=self.dest/'prepared'
        plan,groups=prepare(ROOT,out,self.dest/'source',self.dest/'raw.sas7bdat',verified=False)
        self.assertFalse(plan['verified']);self.assertEqual(len(groups['sampling']),53);self.assertEqual(len(groups['spline']),12)
        self.assertEqual(len(plan['tasks']),70)
        for p,h in plan['fingerprints'].items():self.assertEqual(sha(p),h)
        self.assertTrue((out/'scripts/diagnose_saved_county_pilot.R').is_file())
        for task in plan['tasks']:
            if task['kind']=='sampling':
                self.assertEqual(task['commands'][0][-1],task['model'])
                self.assertIn('audit_saved_forecast_sampling.R',' '.join(task['commands'][0]))
                self.assertNotIn('requires',task)
            if task['kind']=='spline':self.assertEqual(task['requires'],['basis','gate'])
        for name in list(groups)+['collect']:
            subprocess.check_call(['bash','-n',str(out/(name+'.sh'))])
    def test_unverified_plan_cannot_execute(self):
        marker=self.dest/'should_not_exist'
        task=dict(id='blocked',kind='definitions',commands=[[sys.executable,'-c','open(%r,"w").write("bad")'%str(marker)]])
        (self.dest/'plan.json').write_text(json.dumps(dict(verified=False,fingerprints={},tasks=[task])))
        self.assertEqual(run(self.dest,'blocked'),1);self.assertFalse(marker.exists())
        self.assertEqual(json.loads((self.dest/'blocked/task_status.json').read_text())['status'],'FAILED')
    def test_failed_gate_blocks_before_command(self):
        marker=self.dest/'should_not_exist'
        task=dict(id='spline',kind='spline',requires=['gate'],commands=[[sys.executable,'-c','open(%r,"w").write("bad")'%str(marker)]])
        gate=dict(id='gate',kind='gate');(self.dest/'gate').mkdir()
        (self.dest/'gate/task_status.json').write_text(json.dumps(dict(status='FAILED',exit_status=1)))
        (self.dest/'plan.json').write_text(json.dumps(dict(verified=True,fingerprints={},tasks=[gate,task])))
        self.assertEqual(run(self.dest,'spline'),1);self.assertFalse(marker.exists())
    def gate_fixture(self):
        out=self.dest/'gate/result';out.mkdir(parents=True)
        (out/'status.txt').write_text('SPLINE_NUMERICAL_GATE_PASS\n')
        csvfile(out/'spline_gate_checks.csv',[dict(model=m,status='PASS',standardized_mean_change=.001,relative_sd_change=.001,heldout_mask_change=.001) for m in ('iid','spatial')])
        csvfile(out/'spline_gaussian_reference.csv',[dict(status='PASS',mean_error=.000001,sd_error=.000001)])
        return out,dict(id='gate',kind='gate')
    def test_gate_requires_real_numerical_evidence(self):
        out,task=self.gate_fixture();self.assertTrue(validate(self.dest,task))
        csvfile(out/'spline_gaussian_reference.csv',[dict(status='PASS',mean_error='nan',sd_error=.000001)])
        with self.assertRaises(ValueError):validate(self.dest,task)
        (out/'spline_gaussian_reference.csv').unlink()
        with self.assertRaises(ValueError):validate(self.dest,task)
    def test_gate_fingerprint_revocation(self):
        out,task=self.gate_fixture();work=out.parent
        record=dict(status='COMPLETE',exit_status=0,outputs={str(p.relative_to(work)):sha(p) for p in out.iterdir()})
        (work/'task_status.json').write_text(json.dumps(record));plan=dict(tasks=[task])
        prerequisite(self.dest,plan,'gate')
        (out/'status.txt').write_text('SPLINE_NUMERICAL_GATE_PASS\nchanged\n')
        with self.assertRaises(ValueError):prerequisite(self.dest,plan,'gate')
    def test_sampling_grid_and_nonfinite_rejected(self):
        audit=self.dest/'audit';nodes=[dict(fips='%05d'%i,state='S%d'%(i%10)) for i in range(486)]
        csvfile(audit/'reports/graph_nodes.csv',nodes)
        task=dict(id='sampling',kind='sampling',origin=2011,model='iid_county_time',source=dict(audit=str(audit)))
        out=self.dest/'sampling/result';out.mkdir(parents=True);(out/'status.txt').write_text('SAVED_FORECAST_SAMPLING_COMPLETE\n')
        for n in ('inputs.csv','cell_stability_INTERNAL.csv'):(out/n).write_text('placeholder\n')
        seeds=['91001','191003','291007','391009']
        csvfile(out/'settings.csv',[dict(origin=2011,horizon=3,draws_per_seed=4000,refitted='FALSE',model=task['model'],seeds=';'.join(seeds))])
        cells=[dict(fips=n['fips'],state=n['state'],year=y,seed=s,log_predictive_density=-2,density_relative_mcse=.01) for n in nodes for y in (2012,2013,2014) for s in seeds]
        csvfile(out/'seed_cells_INTERNAL.csv',cells)
        scores=[dict(seed=s,state=st,year=y,cells=sum(n['state']==st for n in nodes),sum_log_predictive_density=-2*sum(n['state']==st for n in nodes)) for s in seeds for st in sorted({n['state'] for n in nodes}) for y in (2012,2013,2014)]
        csvfile(out/'seed_state_year_scores.csv',scores);self.assertTrue(validate(self.dest,task))
        cells[0]['log_predictive_density']='nan';csvfile(out/'seed_cells_INTERNAL.csv',cells)
        with self.assertRaises(ValueError):validate(self.dest,task)
        cells[0]['log_predictive_density']=-2;cells[0]['year']=2015;csvfile(out/'seed_cells_INTERNAL.csv',cells)
        with self.assertRaises(ValueError):validate(self.dest,task)

if __name__=='__main__':unittest.main()
