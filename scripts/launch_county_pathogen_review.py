#!/usr/bin/env python3
"""Targeted recovery plus retrospective prediction checks; preserve original fits."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

PATHOGENS=('CAMPYLOBACTER','CRYPTOSPORIDIUM','CYCLOSPORA','LISTERIA','SHIGELLA','STEC','VIBRIO','YERSINIA')
MODELS=('spatial_county_time','iid_county_time')
SOURCES=('review_county_pathogen.R','fit_county_pilot.R','diagnose_saved_county_pilot.R',
         'county_sensitivity.R','county_forecast_check.R','collect_county_pathogen_review.py')

def prepare(root,original,audit,dest):
    dest.mkdir(parents=True,exist_ok=False)
    for name in SOURCES:shutil.copyfile(str(root/'scripts'/name),str(dest/name))
    tasks=[dict(mode='retry',pathogen='VIBRIO',model=MODELS[0])]
    tasks += [dict(mode='cpo',pathogen='SHIGELLA',model=m) for m in MODELS]
    tasks += [dict(mode='forecast',pathogen=p,model=m) for p in PATHOGENS for m in MODELS]
    q=shlex.quote
    script='#!/bin/bash\nset -uo pipefail\nexport OPENBLAS_NUM_THREADS=1\ncase "${SGE_TASK_ID:-}" in\n'
    for i,t in enumerate(tasks,1):
        name=t['mode']+'_'+t['pathogen']+'_'+t['model'];t['name']=name
        t['threads']=8 if t['mode']=='forecast' else 1
        command=['singularity','exec','--cleanenv','--bind','/scicomp',
                 '--bind',str(original)+':'+str(original)+':ro','--bind',str(audit)+':'+str(audit)+':ro',
                 str(root/'foodnet-inla-fixed.sif'),'Rscript','--vanilla',str(dest/'review_county_pathogen.R'),
                 t['mode'],str(audit/'reports'/t['pathogen']),str(original/t['pathogen']/'reconciliation'),
                 str(original/t['pathogen']/t['model']),str(dest/name),t['model']]
        script+=str(i)+')\nstatus=0\n'+' '.join(q(x) for x in command)+' > '+q(str(dest/(name+'.log')))+' 2>&1 || status=$?\n'
        script+='mkdir -p '+q(str(dest/name))+'\nprintf "%s\\n" "$status" > '+q(str(dest/name/'task_exit_status.txt'))+'\nexit "$status";;\n'
    script+='*) exit 2;;\nesac\n';(dest/'run.sh').write_text(script)
    (dest/'manifest.json').write_text(json.dumps(dict(original=str(original),audit=str(audit),tasks=tasks,
        train_years=[2004,2016],heldout_years=[2017,2019],draws=4000,
        limitation='Retrospective known-period check; future population known. No automatic dashboard promotion.'),indent=2)+'\n')
    (dest/'collect.sh').write_text('#!/bin/bash\nexec python3 '+q(str(dest/'collect_county_pathogen_review.py'))+' '+q(str(dest))+'\n')
    return tasks

def main():
    root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original',default=str(root/'output/county_pathogen_models_20260913_001441_311086'))
    p.add_argument('--prepare-only',action='store_true');a=p.parse_args();original=Path(a.original).resolve()
    if not (original/'manifest.json').is_file():p.error('Original manifest missing')
    audit=Path(json.loads((original/'manifest.json').read_text())['audit']).resolve()
    if not a.prepare_only:
        for tool in ('qsub','singularity'):
            if not shutil.which(tool):p.error('Load module for '+tool)
        for f in [root/'foodnet-inla-fixed.sif']+[original/'SHIGELLA'/m/'fit_INTERNAL.rds' for m in MODELS]+[audit/'reports'/n/'county_panel_INTERNAL.rds' for n in PATHOGENS]:
            if not f.is_file():p.error('Missing '+str(f))
    dest=root/'output'/('county_pathogen_review_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    prepare(root,original,audit,dest);print('Output: '+str(dest),flush=True)
    if a.prepare_only:return
    base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y']
    jobs=[]
    for scope,cpus in [('1-3',1),('4-19',8)]:
        answer=subprocess.check_output(base+['-N','foodnet_county_review','-t',scope,'-pe','smp',str(cpus),
          '-l','h_rt=24:00:00,h_rss=32768M,mem_free=32768M,h_vmem=64G','-o',str(dest),str(dest/'run.sh')],universal_newlines=True).strip()
        match=re.match(r'^(\d+)(?:[.\s]|$)',answer)
        if not match:raise RuntimeError('Unexpected qsub response: '+answer)
        jobs.append(match.group(1));print('Array: '+answer,flush=True)
    collector=subprocess.check_output(base+['-N','foodnet_review_report','-hold_jid',','.join(jobs),
        '-l','h_rt=02:00:00,h_vmem=8G','-o',str(dest/'collection.log'),str(dest/'collect.sh')],universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(arrays=jobs,collector=collector))+'\n')
    print('Collector: '+collector+'\nFinal log: '+str(dest/'collection.log')+'\nArchive: '+str(dest)+'.tar.gz')
if __name__=='__main__':main()
