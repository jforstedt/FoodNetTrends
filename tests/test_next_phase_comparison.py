import csv
from pathlib import Path
import sys
import tempfile
import unittest
import math
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect_next_phase_batch import spline_comparisons

class ComparisonTests(unittest.TestCase):
    def test_pools_densities_before_log(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            def write(task,name,data):
                p=root/task/'result';p.mkdir(parents=True,exist_ok=True)
                with (p/name).open('w',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
            write('saved','seed_cells_INTERNAL.csv',[dict(fips='00001',state='AA',year='2012',seed=str(i),log_predictive_density=math.log(x)) for i,x in enumerate((.1,.2,.3,.4))])
            write('spline','heldout_cells_INTERNAL.csv',[dict(fips='00001',state='AA',year='2012',log_predictive_density=math.log(.5),lower95=0,upper95=3,observed=2)])
            tasks={'saved':dict(id='saved',kind='sampling',pathogen='TEST',origin=2011,model='iid_county_time'),
                   'spline':dict(id='spline',kind='spline',pathogen='TEST',origin=2011,variant='iid')}
            r=spline_comparisons(root,tasks)[0]
            self.assertAlmostEqual(r['rw1_pooled_log_score'],math.log(.25))
            self.assertAlmostEqual(r['spline_minus_rw1'],math.log(2))
            self.assertEqual(r['spline_95_coverage'],1)
            write('spline','heldout_cells_INTERNAL.csv',[dict(fips='00002',state='AA',year='2012',log_predictive_density=0,lower95=0,upper95=3,observed=2)])
            with self.assertRaises(ValueError):spline_comparisons(root,tasks)

if __name__=='__main__':unittest.main()
