import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import review_broader_combinations as r


def raw(obj):return json.dumps(obj).encode()
def archive(files,manifest):
    files=dict(files);files[manifest]=raw({n:hashlib.sha256(v).hexdigest() for n,v in files.items()})
    out=io.BytesIO()
    with tarfile.open(fileobj=out,mode='w:gz') as tar:
        for name,value in files.items():
            entry=tarfile.TarInfo(name);entry.size=len(value);tar.addfile(entry,io.BytesIO(value))
    return out.getvalue()
def fixture(branch,duplicate=False):
    files={};tasks=[];results=[]
    script={'spatial':'launch_monthly_spatial_factorial.py','classification':'launch_classification_monthly_preparation.py','inspection':'launch_monthly_spline_inspection.py'}[branch]
    files['scripts/'+script]=b'# synthetic snapshot\n'
    for name,fields in r.identities(branch).items():
        tasks.append(dict(id=name,reused=branch=='spatial' and fields['spatial']=='iid',**fields));results.append(dict(task=name,status='COMPLETE'))
    plan=dict(version={'spatial':'monthly_spatial_factorial_v1','classification':'classification_monthly_preparation_v1','inspection':'monthly_spline_inspection_v1'}[branch],verified=True,tasks=tasks,inputs={'/snapshot/scripts/'+script:hashlib.sha256(files['scripts/'+script]).hexdigest()})
    files['plan.json']=raw(plan);digest=hashlib.sha256(files['plan.json']).hexdigest()
    for t in tasks:
        if t['reused']:continue
        files[t['id']+'/result/status.txt']=b'synthetic'
        files[t['id']+'/task_status.json']=raw(dict(task=t['id'],status='COMPLETE',exit_status=0,plan_sha256=digest,outputs={'result/status.txt':hashlib.sha256(b'synthetic').hexdigest()}))
    if duplicate:results[-1]=results[0]
    summary=dict(tasks=results,issues=[],complete=len(results),execution_complete=True)
    files['summary.json']=raw(summary)
    return files,summary

class ReviewTests(unittest.TestCase):
    def bundle(self,duplicate=False):
        files={};summaries={}
        for branch in ('spatial','classification','inspection'):
            f,s=fixture(branch,duplicate and branch=='spatial');files[branch+'.tar.gz']=archive(f,'report_sha256.json');summaries[branch]=dict(summary=s)
        files['summary.json']=raw(dict(branches=summaries,issues=[],execution_complete=True))
        return archive(files,'archive_sha256.json')
    def test_full_three_branch_intake(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'run.tar.gz').write_bytes(self.bundle());result=r.review(p/'run.tar.gz',p/'review')
            self.assertTrue(result['execution_complete']);self.assertFalse(result['scientific_acceptance'])
            self.assertEqual([result['branches'][k]['complete'] for k in ('spatial','classification','inspection')],[324,6,54])
            with self.assertRaises(ValueError):r.review(p/'run.tar.gz',p/'review')
    def test_duplicate_identity_rejected_before_export(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'run.tar.gz').write_bytes(self.bundle(True))
            with self.assertRaisesRegex(ValueError,'summary task identities'):r.review(p/'run.tar.gz',p/'review')
            self.assertFalse((p/'review').exists())
    def test_rehashed_task_tampering_still_rejected(self):
        files,_=fixture('inspection');name=next(n for n in files if n.endswith('/result/status.txt'));files[name]=b'changed'
        a=r.Archive(archive(files,'report_sha256.json'),'report_sha256.json')
        try:
            with self.assertRaisesRegex(ValueError,'Changed task output'):r.inspect_branch('inspection',a)
        finally:a.close()
    def test_rehashed_snapshot_tampering_still_rejected(self):
        files,_=fixture('classification');files['scripts/launch_classification_monthly_preparation.py']=b'changed'
        a=r.Archive(archive(files,'report_sha256.json'),'report_sha256.json')
        try:
            with self.assertRaisesRegex(ValueError,'Changed frozen input'):r.inspect_branch('classification',a)
        finally:a.close()
    def test_traversal_and_duplicate_json_rejected(self):
        with self.assertRaises(ValueError):r.Archive(archive({'../escape':b'x'},'report_sha256.json'),'report_sha256.json')
        with self.assertRaises(ValueError):r.decode(b'{"a":1,"a":2}')
    def test_missing_branch_is_explicit_partial(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);files={'summary.json':raw(dict(branches={},issues=['preparation failed'],execution_complete=False))}
            (p/'partial.tar.gz').write_bytes(archive(files,'archive_sha256.json'))
            result=r.review(p/'partial.tar.gz',p/'review');self.assertFalse(result['execution_complete']);self.assertEqual(len(result['branches']),3)

if __name__=='__main__':unittest.main()
