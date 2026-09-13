import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
A=load('audit_listeria_state_inputs');L=load('launch_surveillance_postrun_audit')
def write(path,rows):
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
class PostrunTests(unittest.TestCase):
 def test_listeria_exact_scope_and_unverified_rejection(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);source=root/'source';source.mkdir();proof=root/'audit';(proof/'task_01').mkdir(parents=True)
   clean=root/'clean.csv';base=dict(pathogen='LISTERIA',year='2018',state='CA',county='ALAMEDA',travelint='NO',cxcidt='CX+',cste='YES')
   job=dict(task='task_01',prefix='LISTERIA_combined',settings=dict(pathogen='LISTERIA',subgroup='combined',travel='NO,UNKNOWN,YES',cidt='CIDT+,CX+,PARASITIC',colorado_coverage='historical'),command=['Rscript','--cleanFile',str(clean)])
   (source/'manifest.json').write_text(json.dumps(dict(jobs=[job])))
   evidence=dict(eligibility_status='PASS',expected_keys=[dict(year=2018,state='CA')],model_data=[dict(year=2018,state='CA',count=1,population=100)])
   (proof/'task_01/saved_fit_validation.json').write_text(json.dumps(evidence))
   write(clean,[base,dict(base,year='2025',cste='NO'),dict(base,pathogen='SALMONELLA',cste='NO'),dict(base,county='UNKNOWN',cste='NO')])
   result=A.audit(source,proof,root/'ok.json');self.assertEqual(result['status'],'PASS');self.assertEqual(result['results'][0]['verified_records'],1)
   write(clean,[base,dict(base,cste='NO')]);self.assertEqual(A.audit(source,proof,root/'excluded.json')['status'],'PASS')
   evidence['model_data'][0]['count']=2;(proof/'task_01/saved_fit_validation.json').write_text(json.dumps(evidence))
   result=A.audit(source,proof,root/'bad.json');self.assertEqual(result['status'],'REVIEW_REQUIRED');self.assertEqual(result['results'][0]['unverified'][0]['records'],1)
   base.pop('cste');write(clean,[base]);result=A.audit(source,proof,root/'missing.json');self.assertEqual(result['status'],'REVIEW_REQUIRED');self.assertIn('cste',str(result['results'][0]['issues']))
 def test_no_fitting_no_source_mutation_and_incomplete_run_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);source=root/'source';source.mkdir();(source/'task_01').mkdir()
   (source/'manifest.json').write_text(json.dumps(dict(jobs=[dict(task='task_01')])))
   with self.assertRaisesRegex(ValueError,'no exit status'):L.prepare(ROOT,source,root/'notyet')
   (source/'task_01/exit_status.txt').write_text('0\n');before={str(p.relative_to(source)):p.read_bytes() for p in source.rglob('*') if p.is_file()}
   dest=root/'audit space';cmd=L.prepare(ROOT,source,dest,4)
   self.assertEqual(cmd[cmd.index('-pe')+2],'4');self.assertNotIn('-t',cmd)
   subprocess.check_call(['bash','-n',str(dest/'run.sh')])
   self.assertEqual(before,{str(p.relative_to(source)):p.read_bytes() for p in source.rglob('*') if p.is_file()})
   plan=json.loads((dest/'audit_plan.json').read_text());self.assertEqual(set(plan['source_sha256']),set(L.SOURCES))
   worker=(dest/'scripts/run_surveillance_postrun_audit.py').read_text();self.assertNotIn('nextflow',worker);self.assertNotIn('trendy.R',worker)
   self.assertIn('OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1',worker);self.assertIn("':ro'",worker)
if __name__=='__main__':unittest.main()
