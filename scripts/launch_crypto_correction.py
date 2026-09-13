#!/usr/bin/env python3
"""Rebuild only Cryptosporidium county results and inspect existing state outputs."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

NAMES=('full_spatial','full_iid','forecast_spatial','forecast_iid')
def prepare(root,dest,state_run):
    dest.mkdir(parents=True,exist_ok=False)
    sources=('correct_crypto_coverage.R','county_matching.R','audit_county_pilot.R','reconcile_raw_county.R',
        'fit_county_pilot.R','diagnose_saved_county_pilot.R','county_sensitivity.R','county_forecast_check.R','county_forecast_model.R',
        'audit_crypto_state_outputs.py','collect_county_pathogen_review.py')
    for n in sources:shutil.copyfile(str(root/'scripts'/n),str(dest/n))
    shutil.copytree(str(root/'analysis_configs/county_pilot'),str(dest/'geography'))
    clean=root/'output/20260911_140750/preprocessed/clean_mmwr.csv'
    data=Path('/scicomp/groups-pure/EDEB/foodnet/trends/data');q=shlex.quote
    def command(mode,image):
        return ' '.join(q(str(x)) for x in ['singularity','exec','--cleanenv','--bind','/scicomp',root/image,
            'Rscript','--vanilla',dest/'correct_crypto_coverage.R',mode,dest,clean,data/'cen9625_para.sas7bdat',
            data/'mmwr9625.sas7bdat',clean.with_name('clean_mmwr_preprocessing_report.csv')])
    script='#!/bin/bash\nset -uo pipefail\n'
    script+='python3 '+q(str(dest/'audit_crypto_state_outputs.py'))+' '+q(str(state_run))+' '+q(str(dest/'state_audit'))+'\n'
    script+=command('prepare','foodnet.sif')+'\n'
    (dest/'prepare.sh').write_text(script)
    script='#!/bin/bash\nset -uo pipefail\nexport OPENBLAS_NUM_THREADS=1\ncase "${SGE_TASK_ID:-}" in\n'
    for i,n in enumerate(NAMES,1):
        script+=str(i)+')\nstatus=0\n'+command(n,'foodnet-inla-fixed.sif')+' > '+q(str(dest/(n+'.log')))+' 2>&1 || status=$?\n'
        script+='mkdir -p '+q(str(dest/n))+'\nprintf "%s\\n" "$status" > '+q(str(dest/n/'task_exit_status.txt'))+'\nexit "$status";;\n'
    script+='*) exit 2;;\nesac\n';(dest/'run.sh').write_text(script)
    tasks=[dict(name=n,mode='forecast' if n.startswith('forecast') else 'retry',pathogen='CRYPTOSPORIDIUM') for n in NAMES]
    (dest/'manifest.json').write_text(json.dumps(dict(tasks=tasks,observed_years=[2004,2017],
        forecast_training=[2004,2014],forecast_test=[2015,2017],state_run=str(state_run),
        state_refit=False,baseline_selection='Not changed; invalid post-2017 baselines rejected'),indent=2)+'\n')
    (dest/'collect.sh').write_text('#!/bin/bash\nexec python3 '+q(str(dest/'collect_county_pathogen_review.py'))+' '+q(str(dest))+'\n')

def main():
    root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state-run',default=str(root/'output/20260911_140750'));p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    if not a.prepare_only:
        for tool in ('qsub','singularity'):
            if not shutil.which(tool):p.error('Missing '+tool)
        for f in (root/'foodnet.sif',root/'foodnet-inla-fixed.sif'):
            if not f.is_file():p.error('Missing '+str(f))
    dest=root/'output'/('crypto_coverage_correction_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    prepare(root,dest,Path(a.state_run).resolve());print('Output: '+str(dest),flush=True)
    if a.prepare_only:return
    jobs=[]
    for script,cpus,array in [('prepare',4,None),('run',8,'1-4'),('collect',1,None)]:
        cmd=['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_crypto_'+script,'-pe','smp',str(cpus),
            '-l','h_rt=24:00:00,h_rss=32768M,mem_free=32768M,h_vmem=64G','-j','y','-o',str(dest/(script+'.log')) if not array else str(dest)]
        if jobs:cmd+=['-hold_jid',jobs[-1]]
        if array:cmd+=['-t',array]
        answer=subprocess.check_output(cmd+[str(dest/(script+'.sh'))],universal_newlines=True).strip()
        m=re.match(r'^(\d+)(?:[.\s]|$)',answer)
        if not m:raise RuntimeError('Unexpected scheduler response: '+answer)
        jobs.append(m.group(1));print(script+' job: '+answer,flush=True)
    print('Final log: '+str(dest/'collect.log')+'\nArchive: '+str(dest)+'.tar.gz')
if __name__=='__main__':main()
