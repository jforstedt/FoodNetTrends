import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect_extension_data_audit import collect
from run_extension_data_audit import sha

class IntegrityTests(unittest.TestCase):
    def test_false_completions_fail_with_archive(self):
        for error in ('nonzero','changed_input','unverified','empty'):
            with self.subTest(error=error),tempfile.TemporaryDirectory() as tmp:
                d=Path(tmp)/'run';d.mkdir();work=d/'audit';work.mkdir();out=work/'reports';out.mkdir()
                (out/'status.txt').write_text('EXTENSION_DATA_AUDIT_COMPLETE\n')
                manifest=['file,source_rows,source_columns,md5']
                for n in ('fields.csv','categories.csv','readiness.csv'):
                    (out/n).write_text('x\n1\n');manifest.append(n+',1,1,'+sha(out/n,'md5'))
                (out/'report_manifest.csv').write_text('\n'.join(manifest)+'\n')
                (work/'task_status.json').write_text(json.dumps(dict(status='COMPLETE',exit_status=140 if error=='nonzero' else 0)))
                source=d/'source.txt';source.write_text('source')
                plan=dict(verified=error!='unverified',tasks=[] if error=='empty' else [dict(id='audit',kind='diagnostics')],fingerprints={str(source):sha(source)})
                if error=='changed_input':source.write_text('changed')
                (d/'plan.json').write_text(json.dumps(plan))
                with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(collect(d),1)
                self.assertFalse(json.loads((d/'summary.json').read_text())['execution_complete'])
                self.assertTrue(Path(str(d)+'.tar.gz').is_file())
if __name__=='__main__':unittest.main()
