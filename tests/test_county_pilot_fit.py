import importlib.util,json,os,subprocess,tarfile,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def load(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'))
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
launch=load('launch_county_pilot_fit');collector=load('collect_county_pilot_fit')
with tempfile.TemporaryDirectory(prefix="pilot fit ' ") as tmp:
 base=Path(tmp);dest=base/'run'
 cmd=launch.prepare(ROOT,base/'audit',base/'image.sif',dest)
 assert cmd[cmd.index('-t')+1]=='1-2' and '-tc' not in cmd
 assert cmd[cmd.index('-pe')+1:cmd.index('-pe')+3]==['smp','4']
 b=base/'bin';b.mkdir();tool=b/'singularity'
 tool.write_text('#!/bin/bash\necho simulated execution failure\nexit 7\n');tool.chmod(0o755)
 for task in ('1','2'):
  r=subprocess.run(['bash',str(dest/'fit.sh')],env=dict(os.environ,PATH=str(b)+':'+os.environ['PATH'],SGE_TASK_ID=task),stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
  assert r.returncode==7,r.stderr
 assert collector.collect(dest)==1
 for v in ('spatial','iid'):
  (dest/v/'fit_INTERNAL.rds').write_text('private checkpoint')
  report=dest/v/'reports';(report/'status.txt').write_text('EXPLORATORY_FIT_COMPLETE\n');(report/'exit_status.txt').write_text('0\n')
 assert collector.collect(dest)==0
 with tarfile.open(str(dest)+'.tar.gz') as t:
  assert not any('fit_INTERNAL' in n for n in t.getnames())
  assert t.extractfile('spatial/reports/job.log').read().startswith(b'simulated')
 assert not (base/'audit').exists()
print('PASS concurrent array setup, failure diagnostics, collector status, private checkpoint exclusion')
