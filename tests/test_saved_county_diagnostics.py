import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('launcher', str(ROOT / 'scripts/launch_saved_county_diagnostics.py'))
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def test_readonly_inputs_and_no_fit_command(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / 'saved checks'
            command = launcher.prepare(ROOT, Path('/saved fits'), Path('/audit'), Path('/image.sif'), dest)
            script = (dest / 'run.sh').read_text()
            self.assertIn('/saved fits:/saved fits:ro', script)
            self.assertIn('/audit:/audit:ro', script)
            self.assertNotIn('fit_county_pilot.R', script)
            self.assertNotIn('nextflow', script)
            self.assertIn('diagnose_saved_county_pilot.R', script)
            self.assertNotIn('-t', command)
            subprocess.check_call(['bash', '-n', str(dest / 'run.sh')])
            with self.assertRaises(FileExistsError):
                launcher.prepare(ROOT, Path('/fits'), Path('/audit'), Path('/image'), dest)


if __name__ == '__main__':
    unittest.main()
