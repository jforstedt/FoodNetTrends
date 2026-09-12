#!/usr/bin/env python3
"""Submit a county geography preparation job; never fit or alter a model."""
import argparse
from datetime import datetime
from pathlib import Path
import shlex
import shutil
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',default='/scicomp/groups-pure/EDEB/foodnet/trends/data')
    p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    root=Path(__file__).resolve().parent.parent
    for tool in ['qsub','singularity']:
        if not shutil.which(tool):p.error('Missing '+tool+'; load cluster modules')
    for name in ['mmwr9625.sas7bdat','cen9625.sas7bdat','cen9625_para.sas7bdat']:
        if not (Path(a.data_dir)/name).is_file():p.error('Missing input: '+name)
    if not (root/'foodnet.sif').is_file():p.error('Missing foodnet.sif')
    dest=root/'output'/('county_preparation_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    dest.mkdir(parents=True)
    for name in ['county_matching.R','prepare_county_inputs.R']:
        shutil.copyfile(str(root/'scripts'/name),str(dest/name))
    q=shlex.quote
    script='#!/bin/bash\nset -euo pipefail\ncd '+q(str(root))+'\n'
    script+='status=0\nsingularity exec --bind /scicomp '+q(str(root/'foodnet.sif'))+' Rscript '+q(str(dest/'prepare_county_inputs.R'))+' '+q(str(Path(a.data_dir).resolve()))+' '+q(str(dest/'reports'))+' || status=$?\n'
    script+='echo "County preparation exit status: $status"\n'
    script+='mkdir -p '+q(str(dest/'reports'))+'\n'
    script+='cp '+q(str(dest/'preparation.log'))+' '+q(str(dest/'reports/job.log'))+' 2>/dev/null || true\n'
    script+='tar -czf '+q(str(dest)+'.tar.gz')+' -C '+q(str(dest))+' reports\n'
    script+='echo '+q('Report archive: '+str(dest)+'.tar.gz')+'\nexit "$status"\n'
    (dest/'run.sh').write_text(script)
    print('Output directory: '+str(dest),flush=True)
    if a.prepare_only:return
    job=subprocess.check_output(['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_county_prep',
        '-pe','smp','1','-l','h_rt=02:00:00,h_rss=16384M,mem_free=16384M,h_vmem=32G',
        '-j','y','-o',str(dest/'preparation.log'),str(dest/'run.sh')],universal_newlines=True).strip()
    print('Preparation job: '+job+'\nLog: '+str(dest/'preparation.log')+'\nArchive: '+str(dest)+'.tar.gz')

if __name__=='__main__':main()
