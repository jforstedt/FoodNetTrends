#!/usr/bin/env python3
"""Recover the 17 unexecuted next-phase tasks, preserving all 53 sampling results."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
from launch_next_phase_batch import write_scripts,submit
from recover_county_forecast_validation import require_finished
from run_next_phase_task import sha,validate

DEFAULT_RUN='next_phase_parallel_20260913_151430_228763'


def prepare_recovery(source,dest):
    source=Path(source).resolve();dest=Path(dest).resolve()
    plan=json.loads((source/'plan.json').read_text())
    summary=json.loads((source/'summary.json').read_text())
    if not plan.get('verified'):raise ValueError('Source plan is unverified')
    tasks=plan['tasks'];completed=[t for t in tasks if t['kind']=='sampling']
    if len(tasks)!=70 or len(completed)!=53 or len({t['id'] for t in tasks})!=70:raise ValueError('Unexpected source task inventory')
    statuses={r['task']:r['status'] for r in summary['tasks']}
    if any(statuses.get(t['id'])!='COMPLETE' for t in completed):raise ValueError('All 53 sampling tasks must be complete; no sampling retry fallback')
    if any(statuses.get(t['id'])=='COMPLETE' for t in tasks if t['kind']!='sampling'):raise ValueError('Another task already completed; narrower recovery required')
    cache={}
    def check(path,digest):
        if path not in cache:cache[path]=sha(path)
        if cache[path]!=digest:raise ValueError('Changed source/input: '+path)
    for path,digest in plan['fingerprints'].items():check(path,digest)
    for task in completed:
        work=source/task['id'];record=json.loads((work/'task_status.json').read_text())
        if record.get('status')!='COMPLETE' or record.get('exit_status')!=0 or not record.get('outputs'):raise ValueError('Invalid sampling completion')
        for path,digest in task.get('inputs',{}).items():check(path,digest)
        validate(source,task)
        for path,digest in record['outputs'].items():
            actual=(work/path).resolve()
            if work.resolve() not in actual.parents:raise ValueError('Output path escapes task')
            check(str(actual),digest)
    dest.mkdir(parents=True,exist_ok=False)
    for folder in ('scripts','tests'):shutil.copytree(str(source/folder),str(dest/folder))
    for task in completed:shutil.copytree(str(source/task['id']),str(dest/task['id']))
    # Keep the exact scientific worker snapshots; only the dispatch shells change.
    def remap(x):
        if isinstance(x,str) and x.startswith(str(source)+'/'):return str(dest)+x[len(str(source)):]
        if isinstance(x,list):return [remap(v) for v in x]
        if isinstance(x,dict):return {remap(k):remap(v) for k,v in x.items()}
        return x
    plan=remap(plan)
    plan['recovery']=dict(source=str(source),source_plan_sha256=sha(source/'plan.json'),reused_sampling_tasks=53,new_tasks=17)
    # The original completion records are immutable evidence for the reused outputs.
    for task in completed:
        p=source/task['id']/'task_status.json';plan['fingerprints'][str(p)]=sha(p)
    (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    for task in completed:
        record=json.loads((dest/task['id']/'task_status.json').read_text())
        if any(sha(dest/task['id']/p)!=h for p,h in record['outputs'].items()):raise ValueError('Copied output changed')
    groups={'definitions':['definitions'],'cyclospora_serial':['cyclospora_threads_1'],
      'cyclospora_parallel':['cyclospora_threads_8'],'basis':['basis'],'gate':['gate'],
      'spline':[t['id'] for t in tasks if t['kind']=='spline']}
    write_scripts(dest,groups)
    return groups


def main():
    root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',nargs='?',default=DEFAULT_RUN);a=p.parse_args()
    for tool in ('qstat','qsub','singularity'):
        if not shutil.which(tool):p.error('Required tool unavailable: '+tool)
    source=Path(a.source);source=source if source.is_absolute() else root/'output'/source
    dest=root/'output'/('next_phase_recovery_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    try:
        require_finished(source)
        claim=source/'recovery_submission.json'
        with claim.open('x') as f:json.dump(dict(destination=str(dest),status='PREPARING'),f)
        groups=prepare_recovery(source,dest)
        print('Verified and reused 53 sampling tasks. Submitting only 17 unfinished tasks.\nOutput: '+str(dest),flush=True)
        claim.write_text(json.dumps(dict(destination=str(dest),status='SUBMITTING'))+'\n')
        submit(dest,groups)
        claim.write_text(json.dumps(dict(destination=str(dest),status='SUBMITTED'))+'\n')
    except (OSError,ValueError,KeyError,subprocess.SubprocessError,ET.ParseError) as e:
        p.error(str(e)+'; inspect recovery_submission.json and destination submission.json before retrying')


if __name__=='__main__':main()
