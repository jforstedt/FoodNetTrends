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
import launch_monthly_preparation as m

class MonthlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def write(self,out,name,rows):
        with (out/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    def fixture(self):
        work=self.root/'SALMONELLA';out=work/'result';out.mkdir(parents=True)
        (out/'status.txt').write_text('MONTHLY_PREPARATION_COMPLETE\n')
        (out/'candidate_monthly_INTERNAL.rds').write_bytes(b'fixture')
        calendar=[];monthly=[];annual=[]
        for state in ('CA','CO','CT','GA','MD','MN','NM','NY','OR','TN'):
            for year in range(2004,2020):
                annual.append(dict(state=state,year=year,annual_records=13,assigned_records=12,unassigned_records=1,population=120,candidate_person_years=120))
                for month in range(1,13):
                    calendar.append(dict(state=state,year=year,month=month,observation_status='UNVERIFIED',observed_days='',evidence_reference=''))
                    monthly.append(dict(state=state,year=year,month=month,record_count=1,candidate_person_years=10,observation_status='UNVERIFIED',modeled_count=''))
        self.write(out,'calendar_template.csv',calendar);self.write(out,'state_month_records.csv',monthly);self.write(out,'annual_reconciliation.csv',annual)
        self.write(out,'readiness.csv',[dict(pathogen='SALMONELLA',status='REVIEW_REQUIRED',monthly_observation_verified='FALSE',candidate_rows=93312,raw_clean_strata_match='TRUE',individual_linkage_validated='FALSE')])
        self.write(out,'source_month_comparison.csv',[dict(state=r['state'],year=r['year'],month=r['month'],specimen_month_records=1,source_month_records=1,difference=0) for r in monthly])
        self.write(out,'date_issues.csv',[dict(unassigned_records=160)])
        self.write(out,'input_checksums.csv',[dict(file='fixture',md5='fixture')])
        return work,monthly,annual,calendar
    def test_valid_inventory(self):
        work,*_=self.fixture();self.assertTrue(m.validate_result(work))
    def test_rejects_model_counts(self):
        work,rows,*_=self.fixture();rows[0]['modeled_count']=0;self.write(work/'result','state_month_records.csv',rows)
        with self.assertRaisesRegex(ValueError,'modeled counts'):m.validate_result(work)
    def test_rejects_missing_month(self):
        work,rows,*_=self.fixture();self.write(work/'result','state_month_records.csv',rows[:-1])
        with self.assertRaisesRegex(ValueError,'domain'):m.validate_result(work)
    def test_rejects_count_mismatch(self):
        work,rows,*_=self.fixture();rows[0]['record_count']=2;self.write(work/'result','state_month_records.csv',rows)
        with self.assertRaisesRegex(ValueError,'counts'):m.validate_result(work)
    def test_rejects_exposure_mismatch(self):
        work,rows,*_=self.fixture();rows[0]['candidate_person_years']=11;self.write(work/'result','state_month_records.csv',rows)
        with self.assertRaisesRegex(ValueError,'exposure'):m.validate_result(work)
    def test_preparation_interface_and_shell(self):
        dest=self.root/'plan';plan=m.prepare(ROOT,dest,'raw','clean','mapping',verified=False)
        self.assertEqual(len(plan['tasks']),2)
        for task in plan['tasks']:
            self.assertEqual(task['command'][-2:], [str(dest/task['id']/'result'),task['id']])
        for name in ('run.sh','collect.sh'):
            subprocess.check_call(['bash','-n',str(dest/name)])
        r=subprocess.run(['bash',str(dest/'run.sh')],env={'SGE_TASK_ID':'undefined'},stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.assertEqual(r.returncode,2)
        with self.assertRaisesRegex(ValueError,'Unverified'):m.verify(dest,plan,m.sha(dest/'plan.json'))
        with self.assertRaisesRegex(ValueError,'Plan changed'):m.verify(dest,plan,'wrong')
    def test_partial_collection_fails_and_archives(self):
        dest=self.root/'plan';m.prepare(ROOT,dest,'raw','clean','mapping',verified=False)
        self.assertEqual(m.collect(dest,m.sha(dest/'plan.json')),1)
        self.assertTrue(Path(str(dest)+'.tar.gz').exists())
        self.assertFalse(json.loads((dest/'summary.json').read_text())['execution_complete'])
    def test_single_pathogen_dispatch(self):
        dest=self.root/'single';plan=m.prepare(ROOT,dest,'raw','clean','mapping',verified=False,pathogens=('SALMONELLA',))
        self.assertEqual([t['id'] for t in plan['tasks']],['SALMONELLA'])
        self.assertNotIn('2) task=',(dest/'run.sh').read_text())
        with self.assertRaisesRegex(ValueError,'Invalid pathogen'):m.prepare(ROOT,self.root/'bad','raw','clean','mapping',False,())
    def test_rejects_inconsistent_comparison(self):
        work,*_=self.fixture()
        path=work/'result/source_month_comparison.csv'
        with path.open() as f:rows=list(csv.DictReader(f))
        rows[0]['difference']='1';self.write(work/'result',path.name,rows)
        with self.assertRaisesRegex(ValueError,'comparison counts'):m.validate_result(work)
    def test_python36_syntax(self):
        ast.parse((ROOT/'scripts/launch_monthly_preparation.py').read_text(),feature_version=(3,6))

if __name__=='__main__':unittest.main()
