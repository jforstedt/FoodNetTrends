#!/usr/bin/env python3
"""Submit one corrected Cryptosporidium state spline using the agreed 2015–2017 baseline."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess

def prepare(root,dest,data):
    dest.mkdir(parents=True,exist_ok=False);scripts=dest/'scripts';scripts.mkdir();results=dest/'spline_results';results.mkdir()
    hashes={}
    for n in ('trendy.R','functions.R','classification.R','input_validation.R'):
        f=root/'bin'/n;shutil.copyfile(str(f),str(scripts/n));hashes[n]=hashlib.sha256(f.read_bytes()).hexdigest()
    shutil.copyfile(str(root/'analysis_configs/classification_rules.csv'),str(scripts/'classification_rules.csv'))
    shutil.copyfile(str(root/'scripts/collect_crypto_state_refit.py'),str(dest/'collect.py'))
    clean=root/'output/20260911_140750/preprocessed/clean_mmwr.csv'
    command=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=2,OMP_NUM_THREADS=2,MKL_NUM_THREADS=2','--bind','/scicomp',str(root/'foodnet.sif'),'Rscript','--vanilla',str(scripts/'trendy.R'),
       '--mmwrFile',str(data/'mmwr9625.sas7bdat'),'--censusFileB',str(data/'cen9625.sas7bdat'),
       '--censusFileP',str(data/'cen9625_para.sas7bdat'),'--preprocessed','TRUE','--cleanFile',str(clean),
       '--pathogen','CRYPTOSPORIDIUM','--subgroup','combined','--outDir',str(results),'--projID',dest.name,
       '--travel','NO,UNKNOWN,YES','--cidt','CIDT+,CX+,PARASITIC','--cores','12','--chains','6','--iterations','10001',
       '--adapt_delta','0.99','--max_treedepth','15','--seed','123','--backend','rstan',
       '--baseline_start','2015','--baseline_end','2017','--parasite_end_year','2017',
       '--colorado_coverage','historical','--classification_rules',str(scripts/'classification_rules.csv'),
       '--serotype_source','auto','--travel_stratify','false','--debug','FALSE']
    (dest/'manifest.json').write_text(json.dumps(dict(command=command,baseline=[2015,2017],last_observed_year=2017,
        source_project='20260911_140750',model='Existing state spline, rstan',source_sha256=hashes,
        original_outputs_preserved=True),indent=2)+'\n')
    q=shlex.quote
    script='#!/bin/bash\nset -uo pipefail\nexport OPENBLAS_NUM_THREADS=2\nstatus=0\n'
    script+=' '.join(q(s) for s in command)+' > '+q(str(dest/'fit.log'))+' 2>&1 || status=$?\n'
    script+='printf "%s\\n" "$status" > '+q(str(dest/'fit_exit_status.txt'))+'\n'
    script+='python3 '+q(str(dest/'collect.py'))+' '+q(str(dest))+'\n'
    (dest/'run.sh').write_text(script)
    return ['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_crypto_state','-pe','smp','12',
      '-l','h_rt=48:00:00,h_rss=53248M,mem_free=53248M,h_vmem=68G','-j','y','-o',str(dest/'launcher.log'),str(dest/'run.sh')]

def main():
    root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',default='/scicomp/groups-pure/EDEB/foodnet/trends/data');p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    data=Path(a.data_dir).resolve()
    if not a.prepare_only:
        for tool in ('qsub','singularity'):
            if not shutil.which(tool):p.error('Load module for '+tool)
        for f in [root/'foodnet.sif',root/'output/20260911_140750/preprocessed/clean_mmwr.csv']+[data/n for n in ('mmwr9625.sas7bdat','cen9625.sas7bdat','cen9625_para.sas7bdat')]:
            if not f.is_file():p.error('Missing '+str(f))
    dest=root/'output'/('crypto_state_refit_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    cmd=prepare(root,dest,data);print('Output: '+str(dest),flush=True)
    if a.prepare_only:return
    job=subprocess.check_output(cmd,universal_newlines=True).strip()
    print('State fit job: '+job+'\nLog: '+str(dest/'launcher.log')+'\nArchive: '+str(dest)+'.tar.gz')
if __name__=='__main__':main()
