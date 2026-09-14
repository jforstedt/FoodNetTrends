import sys,unittest,copy,io,csv
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import review_monthly_spatial_results as r
class SpatialReviewTests(unittest.TestCase):
 def metric(self):return dict(observed=4.,mean_expected=5.,median_expected=4.,p975_expected=8.,max_expected=10.,top_one_percent_mean_share=.1,lower95=1.,median_predictive=4.,upper95=9.,prob_above_twice_observed=.2)
 def pair(self):
  scores=[];tails=[]
  for mode in ['iid','bym2']:
   d=dict(pathogen='LISTERIA',cutoff=2011,temporal='ar1',seasonal=True,state='CA',year=2012,stream=0,spatial=mode)
   scores.append(dict(d,mean_log_score=-1 if mode=='bym2' else -2));tails.append(dict(d,**self.metric()))
  return scores,tails
 def test_matrix(self):
  self.assertEqual(len(r.matrix()),324);self.assertEqual(sum(x['reused'] for x in r.matrix().values()),162)
 def test_pair_calibration(self):
  scores,tails=self.pair();z=r.paired(scores,tails)[0];self.assertEqual(z['score_gain'],1);self.assertEqual(z['iid_covered'],1);self.assertEqual(z['bym2_width'],8);self.assertEqual(z['bym2_abs_error'],1)
 def test_duplicate_or_changed_truth(self):
  scores,tails=self.pair()
  with self.assertRaises(ValueError):r.paired(scores+scores[:1],tails)
  with self.assertRaises(ValueError):r.paired(scores,tails+tails[:1])
  tails[0]['observed']=3
  with self.assertRaises(ValueError):r.paired(scores,tails)
 def test_range_rejections(self):
  r.validate_metric(self.metric(),True)
  for key,val in [('observed',.5),('mean_expected',-1),('lower95',10),('top_one_percent_mean_share',1.1),('max_expected',float('nan'))]:
   row=self.metric();row[key]=val
   with self.subTest(key=key),self.assertRaises(ValueError):r.validate_metric(row,True)
  for score,mcse in [(1,0),(-1,-1),(-1,float('inf'))]:
   with self.assertRaises(ValueError):r.validate_metric(dict(mean_log_score=score,max_cell_density_relative_mcse=mcse),False)
 def test_settings_metadata(self):
  task=dict(cutoff=2011,seasonal=True,spatial='iid',seed=12)
  row=dict(cutoff='2011',streams='4',draws_per_stream='2000',seasonal='TRUE',coverage_certified='FALSE',refitted='FALSE',base_seed='12')
  class Fake:
   files={}
   def read(self,name):
    out=io.StringIO();w=csv.DictWriter(out,fieldnames=list(row));w.writeheader();w.writerow(row);return out.getvalue().encode()
  a=Fake();r.validate_settings(a,task,'result')
  for field in ['coverage_certified','refitted']:
   row[field]='TRUE'
   with self.assertRaises(ValueError):r.validate_settings(a,task,'result')
   row[field]='FALSE'
  a.files={'result/rng_protocol.csv':True}
  with self.assertRaises(ValueError):r.validate_settings(a,task,'result')
 def test_changed_model_recovery_rejected(self):
  class Fake:
   def json(self,name):return dict(version='monthly_spatial_recovery_v1',model_changed=True,quality_gate_relaxed=False)
   def close(self):pass
  with patch.object(r,'Archive',return_value=Fake()),self.assertRaises(ValueError):r.add_recovery('unused',None,None,None,[],[])
 def restart_numerics(self):
  return dict(initial_ok='TRUE',initial_mode_status='0',restart_ok='TRUE',restart_mode_status='0',fitting_threads='1:1',strategy='INLA_inla.rerun_once',model_changed='FALSE',quality_gate_relaxed='FALSE')
 def test_restart_initial_success_not_cure(self):
  row=self.restart_numerics();z=r.validate_restart_numerics([row]);self.assertTrue(z['initial_already_passed']);self.assertFalse(z['restart_proved_cure'])
  row['initial_mode_status']='2';self.assertFalse(r.validate_restart_numerics([row])['initial_already_passed'])
 def test_restart_numerical_failures_rejected(self):
  for key,val in [('restart_mode_status','2'),('restart_ok','FALSE'),('initial_ok','FALSE'),('model_changed','TRUE'),('quality_gate_relaxed','TRUE'),('strategy','retry_forever'),('fitting_threads','4:1')]:
   row=self.restart_numerics();row[key]=val
   with self.subTest(key=key),self.assertRaises(ValueError):r.validate_restart_numerics([row])
  with self.assertRaises(ValueError):r.validate_restart_numerics([])
 def test_restart_needs_previous_recovery(self):
  with self.assertRaisesRegex(ValueError,'preceding recovery'):r.add_restart('unused',None,None,None,None,[],[])
 def test_restart_changed_protocol_rejected(self):
  class Fake:
   def json(self,name):return dict(version='shigella_numerical_restart_v1',model_changed=True)
   def close(self):pass
  with patch.object(r,'Archive',return_value=Fake()),self.assertRaisesRegex(ValueError,'restart protocol'):r.add_restart('new','previous',None,None,None,[],[])
 def test_restart_wrong_original_lineage_rejected(self):
  name='SHIGELLA_2011_ar1_seasonal_bym2';lis='LISTERIA_2011_ar1_seasonal_bym2'
  rp=dict(version='shigella_numerical_restart_v1',model_changed=False,quality_gate_relaxed=False,numerical_strategy='INLA_inla.rerun_once',fitting_threads='1:1',reused_complete=323,tasks=[dict(id=name)],source_plan_sha256='wrong')
  rs=dict(issues=[],complete=1,expected=1,source_complete=323,execution_complete=True,tasks=[dict(task=name,status='COMPLETE')])
  pp=dict(version='monthly_spatial_recovery_v1',model_changed=False,quality_gate_relaxed=False)
  ps=dict(issues=[],complete=1,tasks=[dict(task=lis,status='COMPLETE'),dict(task=name,status='FAILED_OR_MISSING')])
  class Fake:
   def __init__(self,p,s):self.p=p;self.s=s
   def json(self,n):return self.p if n=='plan.json' else self.s
   def read(self,n):return b'original'
   def close(self):pass
  with patch.object(r,'Archive',side_effect=[Fake(rp,rs),Fake(pp,ps)]),self.assertRaisesRegex(ValueError,'original lineage'):r.add_restart('new','previous',Fake({},{}),None,None,[],[])
 def test_restart_missing_or_altered_previous_binding(self):
  class Fake:
   def read(self,n):return b'evidence'
  p=dict(successful_recovery='/old',inputs={})
  with self.assertRaisesRegex(ValueError,'Missing bound'):r.verify_restart_previous_inputs(Fake(),p)
  p['inputs']['/old/plan.json']='wrong'
  with self.assertRaisesRegex(ValueError,'Changed bound'):r.verify_restart_previous_inputs(Fake(),p)
 def test_restart_cannot_replace_success(self):
  name='SHIGELLA_2011_ar1_seasonal_bym2';lis=dict(task='LISTERIA_2011_ar1_seasonal_bym2',spatial='bym2');summary=dict(tasks=[dict(task=name,status='FAILED')])
  r.ensure_restart_slot([lis],summary)
  with self.assertRaises(ValueError):r.ensure_restart_slot([lis,dict(task=name,spatial='bym2')],summary)
  with self.assertRaises(ValueError):r.ensure_restart_slot([],summary)
  summary['tasks'][0]['status']='COMPLETE'
  with self.assertRaises(ValueError):r.ensure_restart_slot([lis],summary)
 def block(self):
  row=r.paired(*self.pair())[0];return [dict(row,state=state,year=y,stream=k) for state in r.base.STATES for y in range(2012,2015) for k in range(5)]
 def test_partial_origin_is_labelled(self):
  result=r.summaries(self.block())[0];self.assertEqual(result['origins'],1);self.assertFalse(result['complete_three_origins']);self.assertEqual(result['stream_gain_min'],1)
 def test_incomplete_duplicate_streams_rejected(self):
  rows=self.block()
  with self.assertRaises(ValueError):r.summaries(rows[:-1])
  with self.assertRaises(ValueError):r.summaries(rows[:-1]+rows[:1])
  with self.assertRaises(ValueError):r.summaries([dict(x,cutoff=2008,year=x['year']-3) for x in rows])
if __name__=='__main__':unittest.main()
