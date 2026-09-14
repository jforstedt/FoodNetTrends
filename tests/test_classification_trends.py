import ast
import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import launch_classification_trends as mod

class ClassificationTests(unittest.TestCase):
 def test_python36(self):
  ast.parse((ROOT/'scripts/launch_classification_trends.py').read_text(),feature_version=(3,6))
 def test_frozen_array_and_unverified_block(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'plan';p=mod.prepare(ROOT,dest,False)
   self.assertEqual(len(p['tasks']),24)
   self.assertEqual(len({t['seed'] for t in p['tasks']}),24)
   for pathogen in mod.PATHOGENS:
    tasks=[t for t in p['tasks'] if t['pathogen']==pathogen]
    self.assertEqual({(t['cutoff'],t['model']) for t in tasks},{(y,m) for y in (2016,2019) for m in ('shared','site_slopes')})
   subprocess.check_call(['bash','-n',str(dest/'run.sh')])
   self.assertNotEqual(subprocess.call(['bash',str(dest/'run.sh')],env={'SGE_TASK_ID':'25'}),0)
   with self.assertRaises(ValueError):mod.verify(dest,p,mod.sha(dest/'plan.json'))
 def fixture(self,work):
  out=work/'result';out.mkdir();(out/'status.txt').write_text('CLASSIFICATION_FIT_COMPLETE');(out/'warnings.txt').write_text('');(out/'fit_INTERNAL.rds').touch()
  def write(name,data):
   with (out/name).open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
  write('numerical.csv',[dict(fit_ok='TRUE',mode_status=0,waic=100,cpo_failures=0)])
  write('settings.csv',[dict(cutoff=2016,model='shared',seed=1,streams=4,draws_per_stream=500,classification_target='TRUE',incidence_adjustment='FALSE',independent_validation='FALSE')])
  domain=[(s,y) for s in ('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN') for y in range(2012,2020)]
  write('predictions.csv',[dict(state=s,year=y,observed_cidt=2,trials=10,observed_share=.2,mean_probability=.2,lower_probability=.1,median_probability=.2,upper_probability=.4,lower_predictive=0,median_predictive=2,upper_predictive=6,evaluation='CONDITIONAL_HINDCAST' if y>2016 else 'IN_SAMPLE_DESCRIPTION') for s,y in domain])
  write('scoring_input.csv',[dict(state=s,year=y,cidt_classified=2,trials=10) for s,y in domain])
  write('support.csv',[dict(state=s,year=y,cidt_classified=2,classification_denominator=10) for s,y in domain])
  write('annual.csv',[dict(year=y,trials=100,observed_cidt=20,mean_predicted_cidt=20,lower_predictive=10,median_predictive=20,upper_predictive=30) for y in range(2012,2020)])
  write('stream_scores.csv',[dict(state=s,year=y,stream=k,draws=2000 if k==0 else 500,log_score=-2,density_relative_mcse=.01) for s,y in domain for k in range(5)])
  return dict(cutoff=2016,model='shared',seed=1,command=[str(out/'support.csv'),'out','2016','shared','1'])
 def test_validator_rejects_changed_outcomes_and_scores(self):
  with tempfile.TemporaryDirectory() as tmp:
   work=Path(tmp);task=self.fixture(work);mod.validate(work,task)
   p=work/'result/support.csv';old=p.read_text();p.write_text(old.replace(',2,10',',3,10'))
   with self.assertRaisesRegex(ValueError,'Source outcome'):mod.validate(work,task)
   p.write_text(old)
   p=work/'result/stream_scores.csv';p.write_text(p.read_text().replace('0.01','nan'))
   with self.assertRaisesRegex(ValueError,'sampling diagnostic'):mod.validate(work,task)
 def test_partial_archive_records_failure(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'plan';mod.prepare(ROOT,dest,False)
   self.assertEqual(mod.collect(dest,mod.sha(dest/'plan.json')),1)
   s=json.loads((dest/'summary.json').read_text());self.assertEqual(s['complete'],0);self.assertFalse(s['accepted'])
   self.assertTrue(Path(str(dest)+'.tar.gz').is_file())

if __name__=='__main__':unittest.main()
