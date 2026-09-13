#!/usr/bin/env python3
"""Parallel read-only checkpoint validation followed by input and artifact auditing."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

from audit_listeria_state_inputs import audit as audit_listeria,sha256
from collect_surveillance_refits import collect

def run(dest):
    dest=Path(dest).resolve();plan=json.loads((dest/'audit_plan.json').read_text());source=Path(plan['source'])
    manifest=json.loads((source/'manifest.json').read_text());scripts=dest/'scripts'
    for name,value in plan['source_sha256'].items():
        if hashlib.sha256((scripts/name).read_bytes()).hexdigest()!=value:raise ValueError('Audit source changed: '+name)
    if (source/'manifest.json').read_bytes()!=(dest/'source_manifest.json').read_bytes():raise ValueError('Source manifest changed')
    container=Path(plan['container']);container_before=sha256(container)
    def check(job):
        target=dest/job['task'];target.mkdir(exist_ok=True)
        command=['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1',
                 '--bind','/scicomp','--bind',str(source)+':'+str(source)+':ro',str(container),
                 'Rscript','--vanilla',str(scripts/'audit_saved_state_fit.R'),str(source/job['task']),str(target/'saved_fit_validation.json')]
        with (target/'audit.log').open('w') as log:
            try:
                status=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT).returncode
            except OSError as error:
                log.write('Audit could not start: '+str(error)+'\n');status=127
        (target/'audit_exit_status.txt').write_text(str(status)+'\n')
        return dict(task=job['task'],exit_status=status)
    with ThreadPoolExecutor(max_workers=plan['workers']) as pool:tasks=list(pool.map(check,manifest['jobs']))
    listeria=audit_listeria(source,dest,dest/'listeria_input_audit.json')
    code=collect(source,validation_dir=dest,report_dir=dest)
    container_unchanged=sha256(container)==container_before
    passed=code==0 and listeria['status']=='PASS' and container_unchanged and all(t['exit_status']==0 for t in tasks)
    result=dict(status='AUDIT_CHECKS_PASS' if passed else 'REVIEW_REQUIRED',tasks=tasks,artifact_check_exit=code,
                listeria_status=listeria['status'],container_sha256=container_before,container_unchanged=container_unchanged,
                models_refitted=False,dashboard_replaced=False,
                next_step='Review all flags; rerun only models with demonstrated input or sampling problems.')
    (dest/'postrun_summary.json').write_text(json.dumps(result,indent=2)+'\n')
    # Append audit evidence to the collector archive; exclude checkpoints and input records.
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as archive:
        for base,label in ((source,'source_run'),(dest,'audit')):
            for f in sorted(base.rglob('*')):
                if f.is_file() and not f.is_symlink() and f.suffix.lower() in ('.csv','.json','.txt','.log','.r','.py','.sh','.png','.pdf'):
                    archive.add(str(f),arcname=label+'/'+str(f.relative_to(base)),recursive=False)
    print(json.dumps(result,indent=2));print('Archive: '+str(dest)+'.tar.gz')
    return 0 if passed else 1
if __name__=='__main__':sys.exit(run(sys.argv[1]))
