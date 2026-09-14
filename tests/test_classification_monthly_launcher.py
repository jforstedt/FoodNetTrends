import ast
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import launch_classification_monthly_preparation as m

class LauncherTest(unittest.TestCase):
    def root(self,base):
        root=base/'root';root.mkdir();(root/'scripts').symlink_to(ROOT/'scripts',target_is_directory=True);(root/'docs').symlink_to(ROOT/'docs',target_is_directory=True);return root
    def test_unverified_matrix_and_worker_refusal(self):
        with tempfile.TemporaryDirectory() as td:
            root=self.root(Path(td));dest=root/'run';plan=m.prepare(root,dest,False)
            self.assertEqual(len(plan['tasks']),6)
            for t in plan['tasks']:
                self.assertEqual(t['command'][-2],t['id']);self.assertTrue(t['command'][-1].endswith('/result/support.csv'))
            with patch.object(m.subprocess,'call') as run:
                self.assertEqual(m.worker(dest,'SALMONELLA',m.sha(dest/'plan.json')),1);run.assert_not_called()
            self.assertIn('Unverified',(dest/'SALMONELLA/task_status.json').read_text())
    def test_mock_verified_source_contract_and_changed_support(self):
        with tempfile.TemporaryDirectory() as td:
            root=self.root(Path(td));origin=root/'output'/m.SOURCE;origin.mkdir(parents=True)
            (origin/'plan.json').write_text(json.dumps(dict(verified=True,models_fitted=False)));digest=m.sha(origin/'plan.json')
            for name in m.PATHOGENS:
                work=origin/name;(work/'result').mkdir(parents=True);support=work/'result/support.csv';support.write_text('state,year\n')
                (work/'task_status.json').write_text(json.dumps(dict(task=name,status='COMPLETE',exit_status=0,plan_sha256=digest,outputs={'result/support.csv':m.sha(support)})))
            original=m.monthly.prepare
            def mock_monthly(root,dest,raw,clean,mapping,verified,pathogens):
                result=original(root,dest,raw,clean,mapping,False,pathogens);result['verified']=True;return result
            with patch.object(m.monthly,'prepare',side_effect=mock_monthly),patch.object(m.eligible,'validate_result',return_value=True):plan=m.prepare(root,root/'run',True)
            dest=root/'run';h=m.sha(dest/'plan.json');m.verify(dest,plan,h)
            (origin/'SALMONELLA/result/support.csv').write_text('altered')
            with self.assertRaisesRegex(ValueError,'Changed'):m.verify(dest,plan,h)
            self.assertEqual(m.collect(dest,h),1)
            self.assertFalse(json.loads((dest/'summary.json').read_text())['execution_complete'])
    def test_bad_annual_plan_blocks_preparation(self):
        with tempfile.TemporaryDirectory() as td:
            root=self.root(Path(td));origin=root/'output'/m.SOURCE;origin.mkdir(parents=True);(origin/'plan.json').write_text(json.dumps(dict(verified=False,models_fitted=False)))
            original=m.monthly.prepare
            def mock(*args):
                result=original(*args[:-2],False,args[-1]);result['verified']=True;return result
            with patch.object(m.monthly,'prepare',side_effect=mock):
                with self.assertRaisesRegex(ValueError,'Unsupported eligible'):m.prepare(root,root/'run',True)
    def test_partial_archive_excludes_private(self):
        with tempfile.TemporaryDirectory() as td:
            root=self.root(Path(td));dest=root/'run';m.prepare(root,dest,False);(dest/'private_INTERNAL.csv').write_text('private');(dest/'fit_INTERNAL.rds').write_text('private')
            self.assertEqual(m.collect(dest,m.sha(dest/'plan.json')),1)
            with tarfile.open(str(dest)+'.tar.gz') as arc:self.assertFalse(any('_INTERNAL' in n for n in arc.getnames()))
    def test_python36_syntax(self):
        ast.parse((ROOT/'scripts/launch_classification_monthly_preparation.py').read_text(),feature_version=(3,6))

if __name__=='__main__':unittest.main()
