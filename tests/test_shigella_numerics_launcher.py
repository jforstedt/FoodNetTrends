import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import recover_shigella_numerics as r

class Tests(unittest.TestCase):
 def test_target(self):
  self.assertEqual(r.TARGETS,{'SHIGELLA_2011_ar1_seasonal_bym2'})
 def test_verified_single_target(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);p={'version':'shigella_numerical_restart_v1','tasks':[{'id':next(iter(r.TARGETS))}],'model_changed':False,'quality_gate_relaxed':False,'inputs':{}}
   r.write(d/'plan.json',p)
   r.verify(d,p,r.sha(d/'plan.json'))
   p['quality_gate_relaxed']=True;r.write(d/'plan.json',p)
   with self.assertRaises(ValueError):r.verify(d,p,r.sha(d/'plan.json'))
 def test_no_private_archives(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);p={'tasks':[{'id':next(iter(r.TARGETS))}]};r.write(d/'plan.json',p)
   (d/'initial_optimizer_fit_INTERNAL.rds').write_bytes(b'private')
   with patch.object(r,'verify',side_effect=ValueError('bad')):
    self.assertEqual(r.collect(d,'x'),1)
   import tarfile
   with tarfile.open(str(d)+'.tar.gz') as a:self.assertFalse(any('_INTERNAL' in n for n in a.getnames()))
   Path(str(d)+'.tar.gz').unlink()
 def test_one_job_same_resources(self):
  calls=[]
  with tempfile.TemporaryDirectory() as td,patch.object(r,'prepare'),patch.object(r.subprocess,'check_output',side_effect=lambda argv,**kw:(calls.append(argv) or str(100+len(calls)))):
   r.launch(Path(td),Path(td))
  self.assertEqual(calls[0][calls[0].index('-t')+1],'1-1')
  self.assertEqual(calls[0][calls[0].index('-pe')+2],'1')
  self.assertEqual(calls[1][calls[1].index('-hold_jid')+1],'101')
if __name__=='__main__':unittest.main()
