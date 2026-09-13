#!/usr/bin/env python3
"""Submit four parallel training-only county fits and forecast checks."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

NAMES=('spatial_baseline','iid_baseline','spatial_county_time','iid_county_time')
def prepare(root,audit,container,dest):
    for path in (root,audit,container,dest):
        if any(c in str(path) for c in ('\n','\r',':',',')):raise ValueError('Unsupported path character')
    dest.mkdir(parents=True,exist_ok=False);hashes={}
    for name in ('county_forecast_check.R','county_sensitivity.R','fit_county_pilot.R','diagnose_saved_county_pilot.R','collect_county_forecast.py'):
        source=root/'scripts'/name;shutil.copyfile(str(source),str(dest/name));hashes[name]=hashlib.sha256(source.read_bytes()).hexdigest()
    manifest=dict(audit=str(audit),container=str(container),models=NAMES,train_years=[2004,2016],test_years=[2017,2019],
        cpus_per_fit=8,posterior_draws=4000,forecast_origin=2016,updating_with_test_outcomes=False,
        future_populations_known=True,full_fits_reused=False,script_sha256=hashes,
        limitation='Retrospective single-origin test; model exploration already examined these years. Original production model unchanged.')
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');q=shlex.quote
    base=['singularity','exec','--cleanenv','--bind','/scicomp','--bind',str(audit)+':'+str(audit)+':ro',
        str(container),'Rscript','--vanilla',str(dest/'county_forecast_check.R'),str(audit)]
    script='#!/bin/bash\nset -uo pipefail\ncase "${SGE_TASK_ID:-}" in\n'
    for i,name in enumerate(NAMES,1):script+=str(i)+') name='+q(name)+';;\n'
    script+='*) exit 2;;\nesac\ndest='+q(str(dest))+'\nstatus=0\n'
    script+=' '.join(q(x) for x in base)+' "$dest/$name" "$name" 8 > "$dest/$name.log" 2>&1 || status=$?\n'
    script+='mkdir -p "$dest/$name/reports"\nprintf "%s\\n" "$status" > "$dest/$name/reports/exit_status.txt"\nexit "$status"\n'
    (dest/'fit.sh').write_text(script)
    (dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\npython3 '+q(str(dest/'collect_county_forecast.py'))+' '+q(str(dest))+'\n')
    return ['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_forecast','-t','1-4','-pe','smp','8',
        '-l','h_rt=12:00:00,h_rss=32768M,mem_free=32768M,h_vmem=64G','-j','y','-o',str(dest),str(dest/'fit.sh')]

def main():
    root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit-dir',default=str(root/'output/county_pilot_audit_20260912_205807_702050'))
    p.add_argument('--container',default=str(root/'foodnet-inla-fixed.sif'));p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    audit=Path(a.audit_dir).resolve();container=Path(a.container).resolve()
    for f in (container,audit/'county_panel_INTERNAL.rds',audit/'reports/status.txt'):
        if not f.is_file():p.error('Missing '+str(f))
    if (audit/'reports/status.txt').read_text().splitlines()[0]!='INPUT_AUDIT_PASS':p.error('Audit must pass')
    if not a.prepare_only:
        for tool in ('qsub','singularity'):
            if not shutil.which(tool):p.error('Load cluster modules: missing '+tool)
    dest=root/'output'/('county_forecast_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    command=prepare(root,audit,container,dest);print('Output: '+str(dest),flush=True)
    if a.prepare_only:print('Prepared only; no jobs submitted.');return
    job=subprocess.check_output(command,universal_newlines=True).strip();match=re.match(r'^(\d+)(?:[.\s]|$)',job)
    if not match:raise RuntimeError('Unexpected qsub response: '+job)
    print('Four-fit array: '+job,flush=True)
    collector=subprocess.check_output(['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_forecast_report','-hold_jid',match.group(1),
      '-l','h_rt=01:00:00,h_vmem=8G','-j','y','-o',str(dest/'collection.log'),str(dest/'collect.sh')],universal_newlines=True).strip()
    print('Collection job: '+collector+'\nFinal log: '+str(dest/'collection.log')+'\nArchive: '+str(dest)+'.tar.gz')
if __name__=='__main__':main()
