import json,sys,tempfile,unittest,tarfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import launch_spatial_residual_audit as a
class Tests(unittest.TestCase):
 def test_bootstrap_pins_digest_and_frozen_sources(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'scripts').mkdir();g=r/'analysis_configs/county_pilot';g.mkdir(parents=True)
   for n in ('counties.csv','edges.csv','provenance.json'):(g/n).write_text('graph')
   for n in ('launch_spatial_residual_audit.py','audit_spatial_residuals.R','sample.R'):(r/'scripts'/n).write_text('current')
   old=r/'output'/a.SOURCE/'spatial/scripts';old.mkdir(parents=True);(old/'sample.R').write_text('frozen')
   with patch.object(a.spatial,'FILES',('sample.R',)):a.bootstrap(r,r/'new')
   self.assertEqual((r/'new/scripts/sample.R').read_text(),'frozen')
   self.assertIn('--digest '+a.sha(r/'new/bootstrap.json'),(r/'new/prepare.sh').read_text())
   with self.assertRaisesRegex(ValueError,'Bootstrap'):a.prepare(r/'new','wrong')
 def test_changed_graph_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);(d/'graph').mkdir();old={'inputs':{}}
   for n in ('counties.csv','edges.csv','provenance.json'):
    f=d/'graph'/n;f.write_text('original');old['inputs'][str(Path('/original/graph')/n)]=a.sha(f)
   a.verify_graph_snapshot(d,old,Path('/original'))
   (d/'graph/edges.csv').write_text('different')
   with self.assertRaisesRegex(ValueError,'Graph differs'):a.verify_graph_snapshot(d,old,Path('/original'))
 def test_private_results_and_container_not_archived(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);(d/'county_month_residuals_INTERNAL.csv').write_text('private');(d/'runtime.sif').write_text('binary');(d/'state_year_residuals.csv').write_text('aggregate')
   a.archive(d)
   with tarfile.open(str(d)+'.tar.gz') as arc:self.assertEqual(set(arc.getnames()),{'state_year_residuals.csv','report_sha256.json'})
   Path(str(d)+'.tar.gz').unlink()
 def test_unsafe_output_paths_fail_closed(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);p={'tasks':[{'id':'X'}],'container':str(d/'runtime.sif'),'container_sha256':'hash'};a.write(d/'plan.json',p);(d/'X').mkdir()
   a.write(d/'X/task_status.json',dict(task='X',status='COMPLETE',exit_status=0,plan_sha256='digest',outputs={'../escape.csv':'hash'}))
   with patch.object(a,'verify'),patch.object(a,'sha',return_value='hash'),patch.object(a,'archive'):
    self.assertEqual(a.collect(d,'digest'),1)
   self.assertIn('Unsafe',json.loads((d/'summary.json').read_text())['tasks'][0]['reason'])
 def test_container_rehashed_at_collection(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);a.write(d/'plan.json',dict(tasks=[],container='unused',container_sha256='expected'))
   with patch.object(a,'verify'),patch.object(a,'sha',return_value='changed'),patch.object(a,'archive'):self.assertEqual(a.collect(d,'digest'),1)
   self.assertIn('hash changed',json.loads((d/'summary.json').read_text())['issues'][0])
 def test_saved_fit_payload_is_deferred(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);(d/'fit_INTERNAL.rds').write_bytes(b'not read in preparation');(d/'settings.csv').write_text('metadata')
   true_sha=a.sha;record=dict(outputs={'fit_INTERNAL.rds':'deferred-hash','settings.csv':true_sha(d/'settings.csv')})
   def limited(path):
    if str(path).endswith('fit_INTERNAL.rds'):raise AssertionError('Preparation read fit bytes')
    return true_sha(path)
   with patch.object(a,'sha',side_effect=limited):bound=a.bind_saved_outputs(d,record)
   self.assertEqual(bound[str(d/'fit_INTERNAL.rds')],'deferred-hash')
 def test_worker_rejects_changed_fit_before_execution(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);fit=d/'fit.rds';fit.write_text('changed')
   a.write(d/'plan.json',dict(tasks=[dict(id='task',inputs={str(fit):'wrong'},command=['must-not-run'])]))
   with patch.object(a,'verify'),patch.object(a.subprocess,'call') as run:
    self.assertEqual(a.worker(d,1,'digest'),1);run.assert_not_called()
   self.assertEqual(json.loads((d/'task/task_status.json').read_text())['status'],'FAILED')
 def test_conflicting_historical_hash_rejected(self):
  self.assertEqual(a.merge_bindings({'x':'a'},{'x':'a','y':'b'}),{'x':'a','y':'b'})
  with self.assertRaisesRegex(ValueError,'Conflicting'):a.merge_bindings({'x':'a'},{'x':'b'})
if __name__=='__main__':unittest.main()
