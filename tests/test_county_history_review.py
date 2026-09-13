import importlib.util
from pathlib import Path
import tempfile
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('history',str(ROOT/'scripts/launch_county_history_review.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class HistoryTests(unittest.TestCase):
    def test_prepare(self):
        with tempfile.TemporaryDirectory() as td:
            audit=Path(td)/'audit';(audit/'reports').mkdir(parents=True)
            (audit/'reports/input_checksums.csv').write_text('file,md5\n/clean.csv,abc\n/pop.sas7bdat,xyz\n')
            dest=Path(td)/'history'
            c=m.prepare(ROOT,Path('/fits'),audit,Path('/foodnet.sif'),dest)
            s=(dest/'run.sh').read_text()
            self.assertIn('/clean.csv',s);self.assertIn('review_county_histories.R',s)
            self.assertIn('/fits:/fits:ro',s);self.assertNotIn('fit_INTERNAL.rds',s)
            self.assertEqual(c[c.index('-pe')+2],'4')
            subprocess.check_call(['bash','-n',str(dest/'run.sh')])
if __name__=='__main__':unittest.main()
