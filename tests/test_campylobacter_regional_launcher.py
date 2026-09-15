import csv
from pathlib import Path
import sys
import tempfile
import tarfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import launch_campylobacter_regional_audit as m


class Launcher(unittest.TestCase):
    def test_git_checkout_launch_snapshots_code_without_data_reads(self):
        import shutil
        repo=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for folder in ('scripts','docs','analysis_configs'):(root/folder).mkdir()
            for n in ('launch_campylobacter_regional_audit.py','regional_audit_runtime.py','audit_campylobacter_regional_history.R'):
                shutil.copyfile(repo/'scripts'/n,root/'scripts'/n)
            shutil.copyfile(repo/'docs/campylobacter_regional_audit_protocol.md',root/'docs/campylobacter_regional_audit_protocol.md')
            shutil.copyfile(repo/'analysis_configs/campylobacter_regional_audit_source.json',root/'analysis_configs/campylobacter_regional_audit_source.json')
            with patch.object(m.shutil,'which',return_value='/bin/tool'),patch.object(m.base,'submit',return_value='123'):
                dest=m.launch(root)
            m.package_check(dest/'bundle',m.base.sha(dest/'bundle/bundle.json'))
            # A fresh worker interpreter must not create extra files in its snapshot.
            import subprocess
            subprocess.run([sys.executable,'-E',str(dest/'bundle/launch_campylobacter_regional_audit.py'),'--help'],stdout=subprocess.DEVNULL,check=True)
            m.package_check(dest/'bundle',m.base.sha(dest/'bundle/bundle.json'))
            self.assertTrue(m.base.read(dest/'bundle/source_receipt.json')['derive_inputs'])
            self.assertFalse((dest/'plan.json').exists())
    def package(self,p):
        p.mkdir()
        for name in m.MEMBERS:(p/name).write_text('{}')
        m.base.write(p/'bundle.json',dict(version=m.VERSION,files={n:m.base.sha(p/n) for n in m.MEMBERS}))
        return m.base.sha(p/'bundle.json')
    def test_package_binds_exact_members_and_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bundle';h=self.package(p);m.package_check(p,h)
            (p/'source_receipt.json').write_text('changed')
            with self.assertRaises(ValueError):m.package_check(p,h)
    def test_extra_bundle_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bundle';h=self.package(p);(p/'private.csv').write_text('unexpected')
            with self.assertRaisesRegex(ValueError,'members'):m.package_check(p,h)
    def test_visible_job_before_source_reads(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);bundle=root/'input';self.package(bundle)
            with patch.object(m.shutil,'which',return_value='/bin/tool'),patch.object(m.base,'submit',return_value='123') as submit:
                dest=m.launch(root,bundle)
            self.assertEqual(submit.call_count,1);self.assertEqual(submit.call_args.args[3],(2,'h_rt=08:00:00,h_rss=16384M,mem_free=16384M,h_vmem=24G'))
            self.assertFalse((dest/'plan.json').exists());self.assertTrue((dest/'run.sh').is_file())
    def test_bad_bootstrap_archives_failure_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'run';dest.mkdir();m.base.write(dest/'bootstrap.json',{})
            self.assertEqual(m.run(dest,'not_the_hash'),1)
            self.assertEqual(m.base.read(dest/'summary.json')['status'],'FAILED')
            self.assertFalse(m.base.read(dest/'summary.json')['models_fitted'])
            with tarfile.open(str(dest)+'.tar.gz') as archive:self.assertIn('summary.json',archive.getnames())
    def test_status_only_cannot_pass(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'status.txt').write_text('CAMPYLOBACTER_REGIONAL_HISTORY_COMPLETE')
            with self.assertRaisesRegex(ValueError,'Missing'):m.validate(p)
    def test_domains_and_arithmetic(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);states=['CA','CO','CT','GA','MD','MN','NM','NY','OR','TN']
            def writecsv(name,rows):
                with (p/name).open('w') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            month=[dict(state=s,year=y,month=mo,count=1,person_years=10,record_rate_per_100000_person_years=10000) for s in states for y in range(2004,2020) for mo in range(1,13)]
            year=[dict(state=s,year=y,count=12,person_years=120,record_rate_per_100000_person_years=10000) for s in states for y in range(2004,2020)]
            origins=[dict(r,cutoff=c) for r in year for c in (2011,2013,2016)]
            domain=[dict(state=r['state'],year=r['year'],counties=1,zero_record_counties=0,all_zero_month_counties=0) for r in year]
            for name,rows in [('state_month_history.csv',month),('state_year_history.csv',year),('state_year_origin_history.csv',origins),('county_domain_summary.csv',domain),('input_checksums.csv',[dict(file='source',md5='x')])]:writecsv(name,rows)
            (p/'status.txt').write_text('CAMPYLOBACTER_REGIONAL_HISTORY_COMPLETE')
            m.base.write(p/'audit_metadata.json',dict(version='campylobacter_regional_history_v1',models_fitted=False,refitted=False,pathogen='CAMPYLOBACTER',years=list(range(2004,2020)),states=states))
            m.validate(p)
            month[0]['count']=2;month[0]['record_rate_per_100000_person_years']=20000;writecsv('state_month_history.csv',month)
            with self.assertRaisesRegex(ValueError,'Month/year'):m.validate(p)

    def test_archive_excludes_internal(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'run';(p/'reports').mkdir(parents=True)
            (p/'reports/county_year_INTERNAL.csv').write_text('private');(p/'reports/state_year_history.csv').write_text('state')
            m.base.archive(p)
            with tarfile.open(str(p)+'.tar.gz') as a:
                self.assertNotIn('reports/county_year_INTERNAL.csv',a.getnames());self.assertIn('reports/state_year_history.csv',a.getnames())

if __name__=='__main__':unittest.main()
