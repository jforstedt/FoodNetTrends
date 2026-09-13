import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('calibration',Path(__file__).resolve().parents[1]/'scripts/collect_county_forecast_calibration.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class CalibrationCollection(unittest.TestCase):
    def fixture(self,root,replicates,coverage=1):
        for d in module.DENSITIES:
            for v in module.VARIANTS:
                for r in range(1,replicates+1):
                    out=Path(root)/('calibration_{}_{}_{:03d}'.format(d,v,r))/'result';out.mkdir(parents=True)
                    (out/'task_summary.json').write_text(json.dumps(dict(status='TASK_COMPLETE',density=d,variant=v,replicate=r,draws=1000,specification={'version':'county-forecast-calibration-v1'})))
                    with (out/'metrics.csv').open('w') as h:
                        writer=csv.DictWriter(h,fieldnames=['density','variant','replicate','method','horizon','unit','coverage','mean_width']);writer.writeheader()
                        for m in module.METHODS:
                            for horizon in (1,2,3):
                                for u in module.UNITS:
                                    writer.writerow(dict(density=d,variant=v,replicate=r,method=m,horizon=horizon,unit=u,coverage=coverage,mean_width=1))
    def test_complete_screen_keeps_scientific_review(self):
        with tempfile.TemporaryDirectory() as root:
            self.fixture(root,20)
            out=module.collect(root,20)
            self.assertEqual(out['status'],'NUMERICAL_SCREEN_PASS')
            self.assertEqual(out['scientific_status'],'REVIEW_REQUIRED')
            self.assertEqual(out['completed_tasks'],80)
            self.assertLess(out['metrics'][0]['coverage_lower95_bound'],1)
    def test_undercoverage_and_insufficient_replicates_block(self):
        for reps,coverage in ((20,.7),(1,1)):
            with tempfile.TemporaryDirectory() as root:
                self.fixture(root,reps,coverage)
                self.assertEqual(module.collect(root,reps)['status'],'REVIEW_REQUIRED')
    def test_missing_or_duplicate_metric_blocks(self):
        with tempfile.TemporaryDirectory() as root:
            self.fixture(root,20)
            p=next(Path(root).rglob('metrics.csv'));p.write_text(p.read_text().splitlines()[0]+'\n')
            self.assertEqual(module.collect(root,20)['status'],'REVIEW_REQUIRED')
    def test_missing_task_blocks(self):
        with tempfile.TemporaryDirectory() as root:
            self.fixture(root,1)
            self.assertEqual(module.collect(root,20)['status'],'REVIEW_REQUIRED')

if __name__=='__main__':unittest.main()
