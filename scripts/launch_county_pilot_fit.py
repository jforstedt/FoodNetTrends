#!/usr/bin/env python3
"""Submit spatial and IID exploratory county fits concurrently; collect reports."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess


def prepare(root, audit, container, dest):
    for path in (root,audit,dest):
        if any(c in str(path) for c in ('\n','\r',':',',')):
            raise ValueError('Paths cannot contain newlines, colons or commas')
    dest.mkdir(parents=True,exist_ok=False)
    source=root/'scripts/fit_county_pilot.R'
    shutil.copyfile(str(source),str(dest/source.name))
    manifest=dict(audit=str(audit),container=str(container),variants=['spatial','iid'],
        threads_per_job=4,script_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        purpose='Exploratory fits and prior checks, not validated dashboard output',
        posterior_draws=1000,posterior_skew_correction=False)
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    q=shlex.quote
    script='#!/bin/bash\nset -uo pipefail\ncase "${SGE_TASK_ID:-}" in 1) variant=spatial;; 2) variant=iid;; *) echo "Invalid array task" >&2; exit 2;; esac\n'
    script+='dest='+q(str(dest))+'\nstatus=0\n'
    command=['singularity','exec','--cleanenv','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/source.name),str(audit)]
    script+=' '.join(q(a) for a in command)+' "$dest/$variant" "$variant" 4 > "$dest/$variant.log" 2>&1 || status=$?\n'
    script+='mkdir -p "$dest/$variant/reports"\ncp "$dest/$variant.log" "$dest/$variant/reports/job.log" || { if [ "$status" -eq 0 ]; then status=1; fi; }\n'
    script+='printf "%s\\n" "$status" > "$dest/$variant/reports/exit_status.txt"\n'
    script+='if [ ! -f "$dest/$variant/reports/status.txt" ]; then printf "FAIL\\nR did not produce status\\n" > "$dest/$variant/reports/status.txt"; fi\n'
    script+='echo "$variant exit status: $status"\nexit "$status"\n'
    (dest/'fit.sh').write_text(script)
    shutil.copyfile(str(root/'scripts/collect_county_pilot_fit.py'),str(dest/'collect.py'))
    (dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\npython3 '+q(str(dest/'collect.py'))+' '+q(str(dest))+'\n')
    return ['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_county_fit','-t','1-2',
        '-pe','smp','4','-l','h_rt=04:00:00,h_rss=16384M,mem_free=16384M,h_vmem=32G',
        '-j','y','-o',str(dest),str(dest/'fit.sh')]


def main():
    root=Path(__file__).resolve().parent.parent
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit-dir',default=str(root/'output/county_pilot_audit_20260912_205807_702050'))
    p.add_argument('--container',default=str(root/'foodnet-inla-fixed.sif'))
    p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    audit=Path(a.audit_dir).resolve();container=Path(a.container).resolve()
    if not a.prepare_only:
        for tool in ('singularity','qsub'):
            if not shutil.which(tool):p.error('Load cluster modules: missing '+tool)
        for f in (container,audit/'county_panel_INTERNAL.rds',audit/'reports/status.txt'):
            if not f.is_file():p.error('Missing '+str(f))
        if (audit/'reports/status.txt').read_text().splitlines()[0]!='INPUT_AUDIT_PASS':p.error('Input audit must pass')
    dest=root/'output'/('county_pilot_fit_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    command=prepare(root,audit,container,dest)
    print('Output: '+str(dest),flush=True)
    if a.prepare_only:print('Prepared only; no jobs submitted.');return
    job=subprocess.check_output(command,universal_newlines=True).strip()
    if not re.match(r'^\d+(?:[.\s]|$)',job):raise RuntimeError('Unrecognized qsub response: '+job)
    number=re.match(r'^\d+',job).group()
    print('Fit array: '+job,flush=True)
    collector=subprocess.check_output(['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_fit_report',
        '-hold_jid',number,'-l','h_rt=00:30:00,h_vmem=4G','-j','y','-o',str(dest/'collection.log'),str(dest/'collect.sh')],universal_newlines=True).strip()
    print('Collection job: '+collector+'\nFinal log: '+str(dest/'collection.log')+'\nArchive: '+str(dest)+'.tar.gz')
if __name__=='__main__':main()
