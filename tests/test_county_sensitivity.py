import importlib.util
from pathlib import Path
import subprocess
import tempfile
import tarfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,str(ROOT/'scripts'/ (name+'.py')));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
launcher=load('launch_county_sensitivity');collector=load('collect_county_sensitivity')
class SensitivityTests(unittest.TestCase):
 def test_array_and_archive(self):
  with tempfile.TemporaryDirectory() as td:
   dest=Path(td)/'sensitivity'
   command=launcher.prepare(ROOT,Path('/audit'),Path('/baseline'),Path('/diagnostics'),Path('/image'),dest)
   self.assertIn('1-4',command);self.assertNotIn('-tc',command);self.assertEqual(command[command.index('-pe')+2],'8')
   for script in ('fit.sh','collect.sh'):subprocess.check_call(['bash','-n',str(dest/script)])
   self.assertIn('/baseline:/baseline:ro',(dest/'fit.sh').read_text())
   for n in launcher.NAMES:
    report=dest/n/'reports';report.mkdir(parents=True)
    (report/'status.txt').write_text('SENSITIVITY_FIT_COMPLETE\n');(report/'exit_status.txt').write_text('0\n')
    (dest/n/'fit_INTERNAL.rds').write_text('private checkpoint')
   self.assertEqual(collector.collect(dest,0),0)
   with tarfile.open(str(dest)+'.tar.gz') as t:self.assertFalse(any('fit_INTERNAL' in n for n in t.getnames()))
   (dest/launcher.NAMES[0]/'reports/exit_status.txt').write_text('1')
   self.assertEqual(collector.collect(dest,0),1)
if __name__=='__main__':unittest.main()
