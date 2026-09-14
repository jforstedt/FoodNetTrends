import ast,csv,json
from pathlib import Path
import sys,tempfile,unittest,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import launch_eligible_diagnostics as m
ROOT=Path(__file__).resolve().parents[1]
class EligibleTests(unittest.TestCase):
 def test_plan_nine_no_fits(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'plan';p=m.prepare(ROOT,dest,'clean',False)
   self.assertEqual(len(p['tasks']),9);self.assertFalse(p['models_fitted'])
   for n in ('run.sh','collect.sh'):subprocess.check_call(['bash','-n',str(dest/n)])
   with self.assertRaisesRegex(ValueError,'Unverified'):m.verify(dest,p,m.sha(dest/'plan.json'))
 def test_reconciled_reports_and_tampering(self):
  with tempfile.TemporaryDirectory() as tmp:
   work=Path(tmp)/'CRYPTOSPORIDIUM';out=work/'result';out.mkdir(parents=True)
   def write(n,rr):
    with (out/n).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
   annual=[dict(state=s,year=y,eligible_records=2,population=1000) for s in ('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN') for y in range(2004,2018)]
   support=[dict(r,cx_classified=0,cidt_classified=0,parasitic_classified=2,classification_denominator=0,cidt_classification_share='') for r in annual]
   categories=[dict(state=r['state'],year=r['year'],category=c,records=2 if c=='PARASITIC' else 0) for r in annual for c in ('CX+','CIDT+','PARASITIC')]
   write('annual.csv',annual);write('support.csv',support);write('categories.csv',categories)
   write('readiness.csv',[dict(pathogen='CRYPTOSPORIDIUM',end_year=2017,counts_reconciled='TRUE',model_fitted='FALSE',coverage_certified='FALSE',selected_records=280)])
   write('flow.csv',[dict(records=n) for n in (282,2,280)]);write('input_checksums.csv',[dict(file='synthetic',md5='test')]);(out/'status.txt').write_text('ELIGIBLE_DIAGNOSTICS_COMPLETE')
   self.assertTrue(m.validate_result(work));support[0]['cidt_classification_share']='0';write('support.csv',support)
   with self.assertRaisesRegex(ValueError,'missing'):m.validate_result(work)
 def test_partial_collection(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'plan';m.prepare(ROOT,dest,'clean',False)
   self.assertEqual(m.collect(dest,m.sha(dest/'plan.json')),1)
   self.assertTrue(Path(str(dest)+'.tar.gz').exists())
 def test_python36(self):ast.parse((ROOT/'scripts/launch_eligible_diagnostics.py').read_text(),feature_version=(3,6))
if __name__=='__main__':unittest.main()
