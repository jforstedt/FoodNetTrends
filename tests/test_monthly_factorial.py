import ast
import contextlib
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import launch_monthly_factorial as m
ROOT=Path(__file__).resolve().parents[1]

class MonthlyFactorialTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.dest=Path(self.tmp.name)/'run'
 def test_matrix_complete_without_unnecessary_refits(self):
  cells=m.matrix();self.assertEqual(len(cells),108);self.assertEqual(len({t['id'] for t in cells}),108)
  self.assertEqual(sum(t['reused'] for t in cells),60)
  for p in m.PATHOGENS:
   self.assertEqual({(t['cutoff'],t['temporal'],t['seasonal']) for t in cells if t['pathogen']==p},{(c,x,s) for c in m.origins(p) for x in ('rw1','ar1') for s in (False,True)})
  new=[t for t in cells if not t['reused']]
  self.assertTrue(all(not t['seasonal'] for t in new));self.assertEqual(sum(t['temporal']=='ar1' for t in new),27)
  self.assertTrue(all(t['cutoff']+3<=t['end_year'] for t in cells))
 def test_sources_exact(self):
  cells={t['id']:t for t in m.matrix()}
  base,name,pn=m.reference_location(ROOT,cells['SALMONELLA_2011_ar1_seasonal'])
  self.assertEqual(base.name,m.AR1);self.assertEqual(name,'SALMONELLA_2011_seasonal')
  base,name,pn=m.reference_location(ROOT,cells['SHIGELLA_2013_rw1_seasonal'])
  self.assertEqual(base.name,m.SHIGELLA);self.assertEqual(name,'SHIGELLA_2013_rw1');self.assertEqual(pn,'expansion.json')
  base,name,pn=m.reference_location(ROOT,cells['CAMPYLOBACTER_2016_rw1_nonseasonal'])
  self.assertEqual(base.name,m.BASE);self.assertEqual(name,'CAMPYLOBACTER_2016_reference')
 def test_plan_identity_shell_and_unverified_worker(self):
  plan=m.prepare(ROOT,self.dest,False);self.assertEqual(len(plan['tasks']),48);self.assertEqual(len(plan['references']),60)
  self.assertEqual(len({t['seed'] for t in plan['tasks']}),48)
  for name in ('run.sh','collect.sh'):subprocess.check_call(['bash','-n',str(self.dest/name)])
  with self.assertRaises(ValueError):m.verify(self.dest,plan,m.sha(self.dest/'plan.json'))
  with patch.object(m.subprocess,'call') as execute:
   self.assertEqual(m.worker(self.dest,plan['tasks'][0]['id'],m.sha(self.dest/'plan.json')),1);execute.assert_not_called()
 def test_changed_plan_and_runtime_bound(self):
  plan=m.prepare(ROOT,self.dest,False);plan['verified']=True
  (self.dest/'plan.json').write_text(json.dumps(plan));digest=m.sha(self.dest/'plan.json');m.verify(self.dest,plan,digest)
  path=Path(self.tmp.name)/'runtime';path.write_text('old');task=dict(inputs={str(path):m.sha(path)})
  path.write_text('new')
  with self.assertRaisesRegex(ValueError,'Changed bound'):m.verify(self.dest,plan,digest,task)
  (self.dest/'plan.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'changed factorial'):m.verify(self.dest,plan,digest)
 def truth(self,path,extra=False,change=False):
  with path.open('w',newline='') as f:
   fields=['fips','state','year','month','observed']+(['other'] if extra else []);w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
   for county in reversed(range(486)) if extra else range(486):
    for year in range(2012,2015):
     for month in range(1,13):
      r=dict(fips=str(1000+county).zfill(5) if extra else str(1000+county),state=m.STATES[county%10],year=year,month=month,observed=county%4+int(change and county==0 and year==2012 and month==1))
      if extra:r['other']='unused'
      w.writerow(r)
 def test_truth_canonical_equal_and_difference(self):
  a=Path(self.tmp.name)/'a.csv';b=Path(self.tmp.name)/'b.csv';self.truth(a);self.truth(b,True)
  self.assertEqual(m.truth_identity(a,2011),m.truth_identity(b,2011));self.truth(b,True,True)
  self.assertNotEqual(m.truth_identity(a,2011),m.truth_identity(b,2011))
  a.write_text('fips,state,year,month,observed\n01001,CA,2012,1,0\n')
  with self.assertRaisesRegex(ValueError,'Incomplete'):m.truth_identity(a,2011)
 def test_complete_factorial_contrasts_and_missing_arm(self):
  scores=[]
  for stream in range(5):
   for state in m.STATES:
    for temporal,seasonal,value in [('rw1',False,-10),('ar1',False,-8),('rw1',True,-7),('ar1',True,-3)]:
     scores.append(dict(pathogen='STEC',cutoff=2011,state=state,year=2012,stream=stream,temporal=temporal,seasonal=seasonal,mean_log_score=value))
  paired,equal=m.contrasts(scores);self.assertEqual(len(paired),50);self.assertEqual(len(equal),5)
  self.assertTrue(all(r['interaction']==2 and r['seasonality_under_ar1']==5 and r['ar1_minus_rw1_seasonal']==4 for r in paired))
  paired,equal=m.contrasts(scores[:-1]);self.assertEqual(len(paired),49);self.assertEqual(len(equal),4)
  with self.assertRaisesRegex(ValueError,'Duplicate'):m.contrasts(scores+[scores[0]])
 def test_hash_failure_blocks_reused_output(self):
  work=Path(self.tmp.name);path=work/'report.csv';path.write_text('old');record=dict(outputs={'report.csv':m.sha(path)})
  path.write_text('new')
  with self.assertRaisesRegex(ValueError,'Changed bound'):m.bind_record(work,record)
 def test_partial_collection_archives_failure(self):
  m.prepare(ROOT,self.dest,False)
  with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(m.collect(self.dest,m.sha(self.dest/'plan.json')),1)
  self.assertTrue(Path(str(self.dest)+'.tar.gz').is_file());self.assertEqual(json.loads((self.dest/'summary.json').read_text())['complete'],0)
 def test_corrupted_copy_blocks_contrasts_and_removes_stale_outputs(self):
  plan=m.prepare(ROOT,self.dest,False);plan.update(verified=True,tasks=[],references=[],provenance={})
  copies=[]
  for temporal,seasonal,value in [('rw1',False,-10),('ar1',False,-8),('rw1',True,-7),('ar1',True,-3)]:
   name=m.task_id('STEC',2011,temporal,seasonal);out=self.dest/'references'/name;out.mkdir(parents=True)
   for filename,content in [('stream_scores.csv','state,year,stream,mean_log_score\nCA,2012,0,%s\n'%value),('aggregate_tails.csv','state,year,stream\nCA,2012,0\n'),('settings.csv','setting\nsynthetic\n')]:
    path=out/filename;path.write_text(content);plan['inputs'][str(path)]=m.sha(path)
   copies.append(out/'stream_scores.csv')
   plan['references'].append(dict(id=name,pathogen='STEC',cutoff=2011,temporal=temporal,seasonal=seasonal,reused=True,reference=dict(inputs={},truth_sha256='same')))
  (self.dest/'plan.json').write_text(json.dumps(plan));digest=m.sha(self.dest/'plan.json')
  copies[-1].write_text('state,year,stream,mean_log_score\nCA,2012,0,100\n')
  for name in ('factorial_site_contrasts.csv','factorial_equal_site_contrasts.csv'):(self.dest/name).write_text('stale')
  with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(m.collect(self.dest,digest),1)
  summary=json.loads((self.dest/'summary.json').read_text());self.assertTrue(summary['issues'])
  self.assertEqual(summary['tasks'][-1]['status'],'FAILED_OR_MISSING')
  self.assertFalse((self.dest/'factorial_site_contrasts.csv').exists());self.assertFalse((self.dest/'factorial_equal_site_contrasts.csv').exists())
  self.assertNotIn('100', (self.dest/'all_stream_scores.csv').read_text())
  # Even if the global verification is bypassed, each copied report is checked.
  with patch.object(m,'verify'),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(m.collect(self.dest,digest),1)
  self.assertEqual(json.loads((self.dest/'summary.json').read_text())['tasks'][-1]['status'],'FAILED_OR_MISSING')
  self.assertFalse((self.dest/'factorial_site_contrasts.csv').exists())
 def test_python36_and_no_cap(self):
  source=(ROOT/'scripts/launch_monthly_factorial.py').read_text();ast.parse(source,feature_version=(3,6));self.assertNotIn("'-tc'",source)
  self.assertIn("'48:00:00',53248,68,'1-48'",source)
if __name__=='__main__':unittest.main()
