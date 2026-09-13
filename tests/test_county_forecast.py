import contextlib
import csv
import importlib.util
import io
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,str(ROOT/'scripts'/(name+'.py')));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
launcher=load('launch_county_forecast');collector=load('collect_county_forecast')
class ForecastTests(unittest.TestCase):
 def test_launch_and_compare(self):
  with tempfile.TemporaryDirectory() as td:
   dest=Path(td)/'forecast';command=launcher.prepare(ROOT,Path('/audit'),Path('/container'),dest)
   self.assertIn('1-4',command);self.assertNotIn('-tc',command)
   self.assertEqual(command[command.index('-pe')+2],'8')
   for name in ('fit.sh','collect.sh'):subprocess.check_call(['bash','-n',str(dest/name)])
   for name in launcher.NAMES:
    r=dest/name/'reports';r.mkdir(parents=True)
    (r/'status.txt').write_text('FORECAST_CHECK_COMPLETE\n');(r/'exit_status.txt').write_text('0\n')
    collector.write_csv(r/'split.csv',[dict(train_start=2004,train_end=2016,test_start=2017,test_end=2019,training_cells=2,heldout_cells=2,draws=4000,heldout_counts_masked=True)])
    collector.write_csv(r/'panel_checksum.csv',[dict(md5='identical')])
    rows=[dict(fips='00001',state='AA',year=2017+i,population=100,observed=i,training_cases_band='01 zero',log_predictive_density=-2+(1 if name.endswith('time') else 0),zero_brier=.1) for i in range(2)]
    collector.write_csv(r/'heldout_cells_INTERNAL.csv',rows)
    collector.write_csv(r/'heldout_scores_INTERNAL.csv',[dict(grouping='overall',group='all',cells=2,sum_log_predictive_density=-4)])
    (dest/name/'fit_INTERNAL.rds').write_text('private fit')
   with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(collector.collect(dest),0)
   table=collector.read_csv(dest/'paired_forecast_comparison_INTERNAL.csv')
   target=next(r for r in table if r['reference']=='spatial_baseline' and r['candidate']=='spatial_county_time' and r['grouping']=='overall')
   self.assertEqual(float(target['log_score_gain']),2)
   with tarfile.open(str(dest)+'.tar.gz') as t:self.assertFalse(any('fit_INTERNAL' in n for n in t.getnames()))
   bad=dest/'iid_baseline/reports/heldout_cells_INTERNAL.csv';rows=collector.read_csv(bad);rows[0]['observed']='99';collector.write_csv(bad,rows)
   with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(collector.collect(dest),1)
if __name__=='__main__':unittest.main()
