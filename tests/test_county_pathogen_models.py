import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def module(name):
    s=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'))
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class ModelsTest(unittest.TestCase):
    def test_workflow_and_failed_collection(self):
        m=module('launch_county_pathogen_models');c=module('collect_county_pathogen_models')
        with tempfile.TemporaryDirectory() as t:
            dest=Path(t)/'with spaces'
            m.prepare(ROOT,Path('/audit'),dest,Path('/raw'),Path('/clean'),Path('/mapping'))
            for name in ('fit','reconcile','collect'):subprocess.check_call(['bash','-n',str(dest/(name+'.sh'))])
            self.assertEqual((dest/'fit.sh').read_text().count('Rscript'),16)
            self.assertEqual((dest/'reconcile.sh').read_text().count('Rscript'),8)
            self.assertNotIn('SALMONELLA', (dest/'fit.sh').read_text())
            (dest/'fit_INTERNAL.rds').write_bytes(b'secret checkpoint')
            self.assertEqual(c.collect(dest),1)
            with tarfile.open(str(dest)+'.tar.gz') as archive:self.assertNotIn('fit_INTERNAL.rds',archive.getnames())
if __name__=='__main__':unittest.main()
