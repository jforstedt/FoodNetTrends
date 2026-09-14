#!/usr/bin/env python3
"""Recover six Shigella fits under the reviewed specimen-month convention."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import launch_monthly_expansion as m
SOURCE='monthly_expansion_20260913_223222_865377'

def prepare(root,dest):
 root=Path(root).resolve();dest=Path(dest).resolve();origin=root/'output'/SOURCE
 old=json.loads((origin/'expansion.json').read_text());m.verify(origin,old,m.sha(origin/'expansion.json'))
 tasks=[dict(t) for t in old['tasks'] if t['pathogen']=='SHIGELLA']
 if len(tasks)!=6 or {(t['cutoff'],t['temporal']) for t in tasks}!={(c,v) for c in (2011,2013,2016) for v in ('rw1','ar1')}:raise ValueError('Unexpected recovery scope')
 for t in tasks:
  r=json.loads((origin/t['id']/'task_status.json').read_text())
  if r.get('status')!='BLOCKED' or r.get('reason')!='Month-definition disagreements require review' or r.get('plan_sha256')!=m.sha(origin/'expansion.json'):raise ValueError('Recovery task is not the reviewed blocked attempt')
 plan=dict(old,preparation_root=str(origin),month_decision='SHIGELLA_SPECIMEN_20260913',tasks=tasks,maximum_fits=6)
 m.gate(dest,plan,'SHIGELLA')
 dest.mkdir(parents=True,exist_ok=False);(dest/'scripts').mkdir()
 for n in set(m.FILES+m.prep.FILES+('recover_monthly_shigella.py',)):
  shutil.copyfile(str(root/'scripts'/n),str(dest/'scripts'/n))
 proof=dest/'monthly_shigella_recovery.md';shutil.copyfile(str(root/'docs/monthly_shigella_recovery.md'),str(proof))
 plan['inputs']=dict(old['inputs'])
 plan['inputs'].update({str(p):m.sha(p) for p in (dest/'scripts').iterdir()});plan['inputs'][str(proof)]=m.sha(proof)
 plan['inputs'][str(origin/'expansion.json')]=m.sha(origin/'expansion.json')
 for t in tasks:
  t['command']=[str(dest/'scripts/run_monthly_expansion.R') if x==str(origin/'scripts/run_monthly_expansion.R') else str(dest/t['id']/'result') if x==str(origin/t['id']/'result') else x for x in t['command']]
 (dest/'expansion.json').write_text(json.dumps(plan,indent=2)+'\n');digest=m.sha(dest/'expansion.json');q=shlex.quote
 base='python3 '+q(str(dest/'scripts/launch_monthly_expansion.py'))
 shell='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-undefined}" in\n'
 for i,t in enumerate(tasks,1):shell+=str(i)+') task='+t['id']+';;\n'
 shell+='*) exit 2;;\nesac\nexec '+base+' --worker '+q(str(dest))+' --task "$task" --digest '+digest+'\n'
 (dest/'fit.sh').write_text(shell);(dest/'finish.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+base+' --collect '+q(str(dest))+' --digest '+digest+'\n')
 return plan

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
 root=Path(__file__).resolve().parents[1];dest=root/'output'/('monthly_shigella_recovery_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
 if not a.prepare_only and any(not shutil.which(t) for t in ('qsub','singularity')):p.error('Load singularity on an SGE host')
 try:prepare(root,dest)
 except (OSError,ValueError,KeyError) as e:p.error(str(e))
 print('Output: '+str(dest),flush=True)
 if a.prepare_only:return 0
 base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y','-o',str(dest)]
 job=subprocess.check_output(base+['-N','foodnet_shigella','-t','1-6','-pe','smp','4','-l','h_rt=48:00:00,h_rss=53248M,mem_free=53248M,h_vmem=68G',str(dest/'fit.sh')],universal_newlines=True).strip()
 (dest/'submission.json').write_text(json.dumps(dict(array=job))+'\n');print('Fit array: '+job,flush=True)
 match=re.match(r'^(\d+)(?:[.\s]|$)',job)
 if not match:raise ValueError('Unexpected job response; inspect queue before retry')
 col=subprocess.check_output(base+['-N','foodnet_shigella_collect','-hold_jid',match.group(1),'-pe','smp','1','-l','h_rt=04:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G',str(dest/'finish.sh')],universal_newlines=True).strip()
 (dest/'submission.json').write_text(json.dumps(dict(array=job,collector=col))+'\n');print('Collector: '+col+'\nArchive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
