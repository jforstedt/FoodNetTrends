import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from monthly_diagnostic_view import derive
class DiagnosticTests(unittest.TestCase):
 def fixture(self):
  common=dict(pathogen='TEST',state='AA',year='2013');dates=[dict(common,records='10')]
  codes=[dict(common,field=f,code=c,records=str(n)) for f,c,n in [('cxcidt','CX+',8),('cxcidt','CIDT+',2),('culturestatus','CX+',5),('culturestatus','CX+CIDT+',3),('culturestatus','CXNTCIDT+',2),('pcrclinic','<BLANK>',4),('pcrclinic','NOT TESTED',3),('pcrclinic','UNKNOWN',1),('pcrclinic','STX1',2)]]
  cross=[dict(common,field='culturestatus',category=c,result_code=code,records=str(n)) for c,code,n in [('CX+','CX+',5),('CX+','CX+CIDT+',3),('CIDT+','CXNTCIDT+',2)]]
  return codes,dates,cross
 def test_preserves_literal_categories(self):
  x=derive(*self.fixture());self.assertEqual(len(x['codes']),9);self.assertEqual(x['crosswalk'][1][3:5],['CX+','CX+CIDT+']);self.assertEqual(x['universe'],'RAW_RECORDS_NOT_MODEL_ELIGIBILITY')
 def test_rejects_wrong_denominator(self):
  c,d,x=self.fixture();d[0]['records']='11'
  with self.assertRaisesRegex(ValueError,'reconcile'):derive(c,d,x)
 def test_rejects_duplicate_and_crosswalk_mismatch(self):
  c,d,x=self.fixture()
  with self.assertRaisesRegex(ValueError,'Duplicate'):derive(c+[c[0]],d,x)
  x[0]['records']='4'
  with self.assertRaisesRegex(ValueError,'Crosswalk'):derive(c,d,x)
if __name__=='__main__':unittest.main()
