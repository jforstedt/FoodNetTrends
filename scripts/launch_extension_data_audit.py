#!/usr/bin/env python3
"""Investigate extension inputs in parallel; no model fitting or input changes."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from county_forecast_protocol import source_paths,PATHOGENS
from run_extension_data_audit import sha

FILES=('audit_model_extensions.R','audit_extension_diagnostics.R','audit_extension_seasonality.R',
       'audit_extension_count_models.R','fit_county_pilot.R','county_forecast_protocol.py',
       'run_extension_data_audit.py','collect_extension_data_audit.py')


def prepare(root,dest,data,clean,verified=True):
    root=Path(root).resolve();dest=Path(dest).resolve();data=Path(data).resolve();clean=Path(clean).resolve()
    container=root/'foodnet.sif';inputs=[data/n for n in ('mmwr9625.sas7bdat','cen9625.sas7bdat','cen9625_para.sas7bdat')]+[clean,container]
    if verified:
        for p in inputs:
            if not p.is_file():raise ValueError('Required source missing: '+str(p))
    dest.mkdir(parents=True,exist_ok=False);scripts=dest/'scripts';scripts.mkdir()
    for name in FILES:shutil.copyfile(str(root/'scripts'/name),str(scripts/name))
    sources=source_paths(root)
    tasks=[dict(id='diagnostics',kind='diagnostics'),dict(id='seasonality',kind='seasonality')]
    tasks += [dict(id='counts_'+p,kind='counts',pathogen=p,source=sources[p]) for p in PATHOGENS]
    for task in tasks:
        task['command']=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1',
          '--bind','/scicomp',str(container),'Rscript','--vanilla',str(scripts/'audit_model_extensions.R'),task['kind'],
          str(inputs[0]),str(inputs[1]),str(inputs[2]),str(clean),task.get('source',{}).get('audit','unused'),
          task.get('pathogen','ALL'),str(dest/task['id']/'reports'),str(scripts)]
    fingerprints={str(p):sha(p) for p in scripts.iterdir()}
    if verified:fingerprints.update({str(p):sha(p) for p in inputs})
    plan=dict(tasks=tasks,fingerprints=fingerprints,verified=verified,models_fitted=False,scope='Read-only extension data readiness; internal aggregate reports, no case rows or identifiers',
      limitations='Raw inventories are not eligible incidence. Dates, laboratory practices and observation calendars require interpretation. Count-model panels retain reviewed windows.')
    (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');q=shlex.quote
    lines=['#!/bin/bash','set -euo pipefail','case "${SGE_TASK_ID:?}" in']
    lines+=['%d) task=%s;;'%(i,q(t['id'])) for i,t in enumerate(tasks,1)]
    lines+=['*) exit 2;;','esac','exec > '+q(str(dest))+'/"${task}_shell.log" 2>&1','date -u','hostname','ulimit -a',
      'trap \'code=$?; printf "Shell exit status: %s\\n" "$code"\' EXIT','trap \'exit 140\' USR2',
      'python3 '+q(str(scripts/'run_extension_data_audit.py'))+' '+q(str(dest))+' "$task"']
    (dest/'audit.sh').write_text('\n'.join(lines)+'\n')
    (dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec python3 '+q(str(scripts/'collect_extension_data_audit.py'))+' '+q(str(dest))+'\n')
    return plan


def main():
    root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',default='/scicomp/groups-pure/EDEB/foodnet/trends/data')
    p.add_argument('--clean-file',default=str(root/'output/20260911_140750/preprocessed/clean_mmwr.csv'))
    p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    if not a.prepare_only:
        for tool in ('qsub','singularity'):
            if not shutil.which(tool):p.error('Load cluster module for '+tool)
    dest=root/'output'/('extension_data_audit_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    try:plan=prepare(root,dest,Path(a.data_dir),Path(a.clean_file),not a.prepare_only)
    except (OSError,ValueError) as e:p.error(str(e))
    print('Output: '+str(dest)+'\nIndependent audits: '+str(len(plan['tasks']))+'; no models fitted.',flush=True)
    if a.prepare_only:print('Prepared only; no jobs submitted.');return
    jobs={}
    for kind in ('audit','collect'):
        cmd=['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_extension_'+kind,'-pe','smp','2' if kind=='audit' else '1',
             '-l','h_rt=04:00:00,h_rss=16384M,mem_free=16384M,h_vmem=32G','-j','y','-o',str(dest/(kind+'.log'))]
        if kind=='audit':cmd+=['-t','1-'+str(len(plan['tasks']))]
        else:cmd+=['-hold_jid',jobs['audit']]
        value=subprocess.check_output(cmd+[str(dest/(kind+'.sh'))],universal_newlines=True).strip()
        match=re.match(r'^(\d+)(?:[.\s]|$)',value)
        if not match:raise ValueError('Unexpected scheduler response; inspect before retrying: '+value)
        jobs[kind]=match.group(1);(dest/'submission.json').write_text(json.dumps(jobs,indent=2)+'\n')
        print(kind+' job: '+value,flush=True)
    print('Archive: '+str(dest)+'.tar.gz\nFinal log: '+str(dest/'collect.log')+'\nAfter both job IDs appear, you can disconnect.')


if __name__=='__main__':main()
