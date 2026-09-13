import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('launcher', ROOT/'scripts/launch_county_pathogen_audit.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class LauncherTest(unittest.TestCase):
    def test_snapshot_and_archive(self):
        with tempfile.TemporaryDirectory() as t:
            dest = Path(t)/'output with spaces'
            cmd = m.prepare(ROOT, dest, Path('/clean data.csv'), Path('/b.sas'), Path('/p.sas'))
            subprocess.check_call(['bash', '-n', str(dest/'run.sh')])
            self.assertIn('--exclude=county_panel_INTERNAL.rds', (dest/'run.sh').read_text())
            self.assertEqual(cmd[cmd.index('-pe')+2], '4')
            self.assertEqual((dest/'classification.R').read_bytes(), (ROOT/'bin/classification.R').read_bytes())
            self.assertNotIn('fit_county', (dest/'run.sh').read_text())

if __name__ == '__main__': unittest.main()
