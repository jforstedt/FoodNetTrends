import importlib.util
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import threading
import tarfile

spec=importlib.util.spec_from_file_location('bundle',Path(__file__).resolve().parents[1]/'scripts/launch_broader_combinations.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class BundleTests(unittest.TestCase):
    def test_parallel_and_dependencies(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);barrier=threading.Barrier(3); calls=[]
            def prepare(root,dest,spec,verified):
                barrier.wait(timeout=5);(dest/spec[0]).mkdir();return spec
            def submit(dest,name,script,*args,**kwargs):
                calls.append((name,kwargs));return str(len(calls))
            with patch.object(b,'prepare_branch',side_effect=prepare),patch.object(b,'submit',side_effect=submit):
                self.assertEqual(b.driver(d,d),0)
            self.assertEqual(len(calls),7)
            self.assertEqual(len(calls[-1][1]['holds']),6)
            self.assertEqual(sorted(c[1]['array'] for c in calls if 'array' in c[1]),[6,54,162])
            for i,(name,kw) in enumerate(calls):
                if name.endswith('_collect') and i<6:self.assertEqual(kw['holds'],[str(i)])
    def test_partial_failure_still_submits_other_branches(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            def prepare(root,dest,spec,verified):
                if spec[0]=='spatial':raise ValueError('missing control')
                (dest/spec[0]).mkdir()
            with patch.object(b,'prepare_branch',side_effect=prepare),patch.object(b,'submit',return_value='42') as sub:
                self.assertEqual(b.driver(d,d),1)
                self.assertEqual(sub.call_count,5)
            self.assertIn('missing control',(d/'submission.json').read_text())
    def test_failed_branch_collector_preserves_array_hold(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);calls=[]
            def prepare(root,dest,spec,verified):(dest/spec[0]).mkdir()
            def submit(dest,name,script,*args,**kwargs):
                calls.append((name,dict(kwargs)))
                if name=='foodnet_spatial_collect':raise ValueError('collector submission refused')
                return str(len(calls))
            with patch.object(b,'prepare_branch',side_effect=prepare),patch.object(b,'submit',side_effect=submit):
                self.assertEqual(b.driver(d,d),1)
            spatial_id=str(next(i for i,(name,_) in enumerate(calls,1) if name=='foodnet_spatial'))
            self.assertIn(spatial_id,calls[-1][1]['holds'])
            self.assertIn('collector submission refused',(d/'submission.json').read_text())

    def test_collector_success_and_missing_branch(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)/'bundle';d.mkdir();b.write(d/'submission.json',{'issues':[]})
            for name,*_ in b.BRANCHES:
                (d/name).mkdir();count={'spatial':324,'inspection':54,'classification':6}[name]
                b.write(d/name/'summary.json',{'complete':count,'execution_complete':True,'issues':[],'tasks':[{'status':'COMPLETE'} for _ in range(count)]})
                b.write(d/name/'report_sha256.json',{'summary.json':hashlib.sha256((d/name/'summary.json').read_bytes()).hexdigest()})
                with tarfile.open(str(d/name)+'.tar.gz','w:gz') as arc:
                    for filename in ('summary.json','report_sha256.json'):arc.add(str(d/name/filename),arcname=filename)
            self.assertEqual(b.collect(d),0)
            (d/'inspection.tar.gz').unlink()
            self.assertEqual(b.collect(d),1)
            self.assertFalse(json.loads((d/'summary.json').read_text())['execution_complete'])
    def test_empty_stale_and_tampered_archives_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td);summary=d/'summary.json';b.write(summary,{'tasks':[]})
            archive=d/'branch.tar.gz'
            with tarfile.open(str(archive),'w:gz'):pass
            with self.assertRaises(ValueError):b.verify_branch_archive(archive,summary)
            manifest=d/'report_sha256.json';b.write(manifest,{'summary.json':hashlib.sha256(summary.read_bytes()).hexdigest()})
            with tarfile.open(str(archive),'w:gz') as arc:
                arc.add(str(summary),arcname='summary.json');arc.add(str(manifest),arcname='report_sha256.json')
            self.assertEqual(b.verify_branch_archive(archive,summary),{'tasks':[]})
            b.write(summary,{'tasks':[{'status':'FAILED'}]})
            with self.assertRaisesRegex(ValueError,'summary differ'):b.verify_branch_archive(archive,summary)
            with tarfile.open(str(archive),'w:gz') as arc:
                arc.add(str(summary),arcname='summary.json');arc.add(str(manifest),arcname='report_sha256.json')
            with self.assertRaisesRegex(ValueError,'Changed branch archive member'):b.verify_branch_archive(archive,summary)

    def test_unrecognized_submission_preserved_without_retry(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            with patch.object(b.subprocess,'check_output',return_value='ambiguous') as sub:
                with self.assertRaises(ValueError):b.submit(d,'x',d/'run.sh',1,'01:00:00',1024,2)
                self.assertEqual(sub.call_count,1)
            self.assertIn('ambiguous',(d/'scheduler_responses.log').read_text())
if __name__=='__main__':unittest.main()
