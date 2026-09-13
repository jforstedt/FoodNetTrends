#!/usr/bin/env python3
"""Submit four parallel exploratory sensitivity fits; reuse saved baselines."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

NAMES=('spatial_county_sd2','iid_county_sd2','spatial_county_time','iid_county_time')

def prepare(root,audit,baseline,diagnostics,container,dest):
    for path in (root,audit,baseline,diagnostics,container,dest):
        if any(c in str(path) for c in ('\n','\r',':',',')):raise ValueError('Unsupported path character')
    dest.mkdir(parents=True,exist_ok=False)
    hashes={}
    for name in ('county_sensitivity.R','fit_county_pilot.R','diagnose_saved_county_pilot.R','collect_county_sensitivity.py'):
        source=root/'scripts'/name;shutil.copyfile(str(source),str(dest/name));hashes[name]=hashlib.sha256(source.read_bytes()).hexdigest()
    manifest=dict(audit=str(audit),baseline=str(baseline),baseline_diagnostics=str(diagnostics),container=str(container),models=NAMES,
        cpus_per_fit=8,posterior_draws=2000,county_sd_change=dict(original=1,sensitivity=2,tail_probability=.01),
        county_time_change='Additional independent county RW1 curves, scaled and sum-to-zero over time, shared PC precision P(SD>0.5)=0.01',
        unchanged='State trends, intercept priors, NB likelihood/size prior, graph, population, observations; original state model untouched',
        script_sha256=hashes)
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    q=shlex.quote
    base=['singularity','exec','--cleanenv','--bind','/scicomp','--bind',str(audit)+':'+str(audit)+':ro',
          '--bind',str(baseline)+':'+str(baseline)+':ro','--bind',str(diagnostics)+':'+str(diagnostics)+':ro',str(container),
          'Rscript','--vanilla',str(dest/'county_sensitivity.R')]
    script='#!/bin/bash\nset -uo pipefail\ncase "${SGE_TASK_ID:-}" in\n'
    for i,n in enumerate(NAMES,1):script+=str(i)+') name='+q(n)+';;\n'
    script+='*) exit 2;;\nesac\ndest='+q(str(dest))+'\nstatus=0\n'
    script+=' '.join(q(x) for x in base+['fit',str(audit)])+' "$dest/$name" "$name" 8 > "$dest/$name.log" 2>&1 || status=$?\n'
    script+='mkdir -p "$dest/$name/reports"\nprintf "%s\\n" "$status" > "$dest/$name/reports/exit_status.txt"\nexit "$status"\n'
    (dest/'fit.sh').write_text(script)
    command=base+['compare',str(audit),str(baseline),str(diagnostics),str(dest)]
    script='#!/bin/bash\nset -uo pipefail\nstatus=0\n'+' '.join(q(x) for x in command)+' > '+q(str(dest/'comparison.log'))+' 2>&1 || status=$?\n'
    script+='python3 '+q(str(dest/'collect_county_sensitivity.py'))+' '+q(str(dest))+' "$status"\n'
    (dest/'collect.sh').write_text(script)
    return ['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_sensitivity','-t','1-4','-pe','smp','8',
            '-l','h_rt=12:00:00,h_rss=32768M,mem_free=32768M,h_vmem=64G','-j','y','-o',str(dest),str(dest/'fit.sh')]

def main():
    root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',default=str(root/'output/county_pilot_fit_20260912_212322_668317'))
    p.add_argument('--baseline-diagnostics',default=str(root/'output/saved_county_diagnostics_20260912_214414_854891'))
    p.add_argument('--container',default=str(root/'foodnet-inla-fixed.sif'));p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    baseline=Path(a.baseline).resolve();diag=Path(a.baseline_diagnostics).resolve();container=Path(a.container).resolve()
    if not (baseline/'manifest.json').is_file():p.error('Missing original baseline manifest')
    audit=Path(json.loads((baseline/'manifest.json').read_text())['audit']).resolve()
    for f in (container,audit/'county_panel_INTERNAL.rds',baseline/'spatial/fit_INTERNAL.rds',baseline/'iid/fit_INTERNAL.rds',diag/'reports/input_checksums.csv'):
        if not f.is_file():p.error('Missing '+str(f))
    if not a.prepare_only:
        for tool in ('qsub','singularity'):
            if not shutil.which(tool):p.error('Load cluster modules: missing '+tool)
    dest=root/'output'/('county_sensitivity_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    command=prepare(root,audit,baseline,diag,container,dest);print('Output: '+str(dest),flush=True)
    if a.prepare_only:print('Prepared only; no jobs submitted.');return
    job=subprocess.check_output(command,universal_newlines=True).strip();match=re.match(r'^(\d+)(?:[.\s]|$)',job)
    if not match:raise RuntimeError('Unexpected qsub response: '+job)
    print('Four-fit array: '+job,flush=True)
    collector=subprocess.check_output(['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_sens_report','-hold_jid',match.group(1),
       '-pe','smp','4','-l','h_rt=02:00:00,h_rss=16384M,mem_free=16384M,h_vmem=32G','-j','y','-o',str(dest/'collection.log'),str(dest/'collect.sh')],universal_newlines=True).strip()
    print('Collection job: '+collector+'\nFinal log: '+str(dest/'collection.log')+'\nArchive: '+str(dest)+'.tar.gz')
if __name__=='__main__':main()
