import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import package_monthly_exploratory_release as m
class PackageTests(unittest.TestCase):
 def test_integrity_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);dec=root/'dec.json';dec.write_text('{}');dest=root/'release'
   payload=dict(assessments={'TEST':dict(candidate=None,limitation='Synthetic test only')},provenance=[])
   with patch.object(m.review,'build',return_value=payload):archive=m.package([],dec,None,dest)
   self.assertTrue(m.verify_zip(archive));self.assertFalse(json.loads((dest/'provenance.json').read_text())['accepted'])
   with self.assertRaisesRegex(ValueError,'existing'):m.package([],dec,None,dest)
   with zipfile.ZipFile(archive) as z:contents={n:z.read(n) for n in z.namelist()}
   contents['dashboard.html']=b'changed'
   bad=root/'bad.zip'
   with zipfile.ZipFile(bad,'w') as z:
    for n,b in contents.items():z.writestr(n,b)
   with self.assertRaisesRegex(ValueError,'integrity'):m.verify_zip(bad)
 def test_validation_failure_creates_no_package(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp)/'release';dec=Path(tmp)/'decision.json';dec.write_text('{}')
   with patch.object(m.review,'build',side_effect=ValueError('bad source')):
    with self.assertRaises(ValueError):m.package([],dec,None,dest)
   self.assertFalse(dest.exists());self.assertFalse(Path(str(dest)+'.zip').exists())
if __name__=='__main__':unittest.main()
