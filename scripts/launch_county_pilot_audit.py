#!/usr/bin/env python3
"""Submit one read-only Salmonella pilot input/graph audit; never fit models."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shlex
import shutil
import subprocess


def prepare(root, dest, clean, census):
    dest.mkdir(parents=True,exist_ok=False)
    for name in ('audit_county_pilot.R','county_matching.R'):
        shutil.copyfile(str(root/'scripts'/name),str(dest/name))
    shutil.copytree(str(root/'analysis_configs/county_pilot'),str(dest/'geography'))
    command=['singularity','exec','--bind','/scicomp',str(root/'foodnet.sif'),
             'Rscript','--vanilla',str(dest/'audit_county_pilot.R'),str(clean),str(census),
             str(dest/'geography'),str(dest/'reports')]
    (dest/'plan.json').write_text(json.dumps(dict(command=command,purpose='Input audit only; no fitting',
        pathogen='SALMONELLA',start_year=2004,end_year=2019,exact_count_panel_in_archive=False),indent=2)+'\n')
    q=shlex.quote
    script='#!/bin/bash\nset -uo pipefail\nstatus=0\n'
    script+=' '.join(q(a) for a in command)+' > '+q(str(dest/'audit.log'))+' 2>&1 || status=$?\n'
    script+='mkdir -p '+q(str(dest/'reports'))+'\n'
    script+='cp '+q(str(dest/'audit.log'))+' '+q(str(dest/'reports/audit.log'))+' || { if [ "$status" -eq 0 ]; then status=1; fi; }\n'
    script+='cat '+q(str(dest/'audit.log'))+'\n'
    script+='echo "Audit process exit status: $status"\n'
    script+='archive_status=0\ntar -czf '+q(str(dest)+'.tar.gz')+' -C '+q(str(dest))+' reports geography plan.json audit_county_pilot.R county_matching.R run.sh || archive_status=$?\n'
    script+='if [ "$archive_status" -eq 0 ]; then echo '+q('Archive: '+str(dest)+'.tar.gz')+'; fi\n'
    script+='if [ "$status" -ne 0 ]; then exit "$status"; fi\nexit "$archive_status"\n'
    (dest/'run.sh').write_text(script)
    return ['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_pilot_audit','-pe','smp','1',
            '-l','h_rt=01:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G','-j','y','-o',str(dest/'launcher.log'),str(dest/'run.sh')]


def main():
    root=Path(__file__).resolve().parent.parent
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--clean-file',default=str(root/'output/20260911_140750/preprocessed/clean_mmwr.csv'))
    p.add_argument('--census-file',default='/scicomp/groups-pure/EDEB/foodnet/trends/data/cen9625.sas7bdat')
    p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    clean=Path(a.clean_file).resolve();census=Path(a.census_file).resolve()
    if not a.prepare_only:
        for cmd in ('qsub','singularity'):
            if not shutil.which(cmd):p.error('Load cluster modules: missing '+cmd)
        for f in (clean,census,root/'foodnet.sif'):
            if not f.is_file():p.error('Missing '+str(f))
    dest=root/'output'/('county_pilot_audit_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    cmd=prepare(root,dest,clean,census)
    print('Plan: '+str(dest),flush=True)
    if a.prepare_only:print('Prepared only; no cluster job submitted.');return
    job=subprocess.check_output(cmd,universal_newlines=True).strip()
    print('Audit job: '+job+'\nLog: '+str(dest/'launcher.log')+'\nArchive: '+str(dest)+'.tar.gz')
if __name__=='__main__':main()
