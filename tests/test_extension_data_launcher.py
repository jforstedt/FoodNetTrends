import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import launch_extension_data_audit as launch
import run_extension_data_audit as worker
import collect_extension_data_audit as collector

class ExtensionDataTests(unittest.TestCase):
    def test_parallel_matrix_and_unverified_cannot_execute(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'audit';plan=launch.prepare(ROOT,dest,Path(tmp),Path(tmp)/'clean.csv',False)
            self.assertEqual(len(plan['tasks']),11);self.assertEqual(sum(t['kind']=='counts' for t in plan['tasks']),9)
            self.assertFalse(plan['models_fitted']);self.assertFalse(plan['verified'])
            for p in dest.glob('*.sh'):subprocess.check_call(['bash','-n',str(p)])
            self.assertEqual(worker.run(dest,'diagnostics'),1)
            record=json.loads((dest/'diagnostics/task_status.json').read_text());self.assertIn('Prepare-only',record['reason'])
            self.assertEqual(collector.collect(dest),1);self.assertTrue(Path(str(dest)+'.tar.gz').exists())
    def test_report_manifest_requires_tables_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);(out/'status.txt').write_text('EXTENSION_DATA_AUDIT_COMPLETE\n')
            names=['fields.csv','categories.csv','readiness.csv']
            lines=['file,source_rows,source_columns,md5']
            for name in names:
                (out/name).write_text('value\nx\n');lines.append('%s,1,1,%s'%(name,worker.sha(out/name,'md5')))
            (out/'report_manifest.csv').write_text('\n'.join(lines)+'\n')
            self.assertEqual(worker.validate_reports(out,'diagnostics'),3)
            (out/'categories.csv').write_text('value\ny\n')
            with self.assertRaisesRegex(ValueError,'checksum'):worker.validate_reports(out,'diagnostics')

if __name__=='__main__':unittest.main()
