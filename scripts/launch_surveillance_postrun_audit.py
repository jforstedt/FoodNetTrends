#!/usr/bin/env python3
"""Submit one parallel saved-result audit; never fit models or modify the source run."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

SOURCES=('audit_saved_state_fit.R','audit_listeria_state_inputs.py','collect_surveillance_refits.py','run_surveillance_postrun_audit.py')

def latest(root):
    candidates=sorted(p for p in (root/'output').glob('surveillance_refits_*')
                      if re.fullmatch(r'surveillance_refits_\d{8}_\d{6}_\d{6}',p.name) and (p/'manifest.json').is_file())
    if not candidates:raise ValueError('No surveillance refit run found; supply --source')
    return candidates[-1]

def prepare(root,source,dest,workers=4):
    source=Path(source).resolve();manifest=json.loads((source/'manifest.json').read_text())
    if not manifest.get('jobs'):raise ValueError('Source manifest has no fit jobs')
    if workers<1 or workers>8:raise ValueError('workers must be between 1 and 8')
    for job in manifest['jobs']:
        if not (source/job['task']/'exit_status.txt').is_file():
            raise ValueError('Fit task has no exit status yet: '+job['task']+'. Run the audit after the fit array finishes.')
    dest.mkdir(parents=True,exist_ok=False);scripts=dest/'scripts';scripts.mkdir();hashes={}
    for n in SOURCES:
        f=root/'scripts'/n;shutil.copyfile(str(f),str(scripts/n));hashes[n]=hashlib.sha256(f.read_bytes()).hexdigest()
    shutil.copyfile(str(source/'manifest.json'),str(dest/'source_manifest.json'))
    info=dict(source=str(source),workers=workers,container=str(root/'foodnet.sif'),source_sha256=hashes,
              mode='Read-only saved-fit/input/artifact audit; no sampling or dashboard replacement')
    (dest/'audit_plan.json').write_text(json.dumps(info,indent=2)+'\n')
    command=['python3',str(scripts/'run_surveillance_postrun_audit.py'),str(dest)]
    (dest/'run.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+' '.join(shlex.quote(v) for v in command)+'\n')
    return ['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_saved_audit','-pe','smp',str(workers),
            '-l','h_rt=04:00:00,h_rss=16384M,mem_free=16384M,h_vmem=32G','-j','y','-o',str(dest/'audit.log'),str(dest/'run.sh')]

def main():
    root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path);p.add_argument('--workers',type=int,default=4);p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    try:source=a.source.resolve() if a.source else latest(root)
    except ValueError as e:p.error(str(e))
    if not a.prepare_only:
        for n in ('qsub','singularity'):
            if not shutil.which(n):p.error('Load module for '+n)
        if not (root/'foodnet.sif').is_file():p.error('Missing foodnet.sif')
    dest=root/'output'/('surveillance_postrun_audit_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    try:command=prepare(root,source,dest,a.workers)
    except (OSError,ValueError,KeyError) as e:p.error(str(e))
    print('Source run: '+str(source)+'\nAudit output: '+str(dest),flush=True)
    if a.prepare_only:return
    job=subprocess.check_output(command,universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(job=job))+'\n')
    print('Audit job: '+job+'\nLog: '+str(dest/'audit.log')+'\nArchive: '+str(dest)+'.tar.gz')
if __name__=='__main__':main()
