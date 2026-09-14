#!/usr/bin/env python3
"""Inspect all 54 saved spline fits without refitting or sampling."""
import argparse
import csv
import math
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import launch_monthly_spline_factorial as source

RUN='monthly_spline_factorial_20260914_120120_695932'


def prepare(root,dest,verified=True):
    root=Path(root).resolve();dest=Path(dest).resolve();base=root/'output'/RUN
    original=json.loads((base/'plan.json').read_text()) if verified else dict(tasks=source.matrix())
    if verified:
        source.verify(base,original,source.f.sha(base/'plan.json'),all_inputs=True)
        if {t['id'] for t in original['tasks']}!={t['id'] for t in source.matrix()}:raise ValueError('Wrong saved spline grid')
    dest.mkdir(parents=True,exist_ok=False);(dest/'scripts').mkdir();inputs={}
    for n in tuple(source.FILES)+('launch_monthly_spline_inspection.py','inspect_monthly_spline_saved.R'):
        p=dest/'scripts'/n;shutil.copyfile(str(root/'scripts'/n),str(p));inputs[str(p)]=source.f.sha(p)
    container=root/'foodnet-inla-fixed.sif'
    if verified:inputs[str(container)]=source.f.sha(container)
    tasks=[]
    for t in original['tasks']:
        work=base/t['id'];bound={}
        if verified:
            record=json.loads((work/'task_status.json').read_text())
            if record.get('status')!='COMPLETE' or record.get('exit_status')!=0 or record.get('plan_sha256')!=source.f.sha(base/'plan.json') or record.get('task')!=t['id']:raise ValueError('Incomplete saved task')
            truth=source.validate(work,t)
            if truth!=record.get('truth_sha256'):raise ValueError('Changed saved truth')
            bound=source.f.bind_record(work,record);bound[str(base/'plan.json')]=source.f.sha(base/'plan.json')
        tasks.append(dict(id=t['id'],inputs=bound,cutoff=t['cutoff'],seasonal=t['seasonal'],command=['singularity','exec','--cleanenv','--bind','/scicomp',str(container),'Rscript','--vanilla',str(dest/'scripts/inspect_monthly_spline_saved.R'),str(work/'fit_INTERNAL.rds'),str(work/'heldout_truth_INTERNAL.csv'),str(dest/t['id']/'result'),str(t['cutoff']),'TRUE' if t['seasonal'] else 'FALSE']))
    plan=dict(version='monthly_spline_inspection_v1',verified=verified,inputs=inputs,tasks=tasks,refitted=False,resampled=False)
    (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');digest=source.f.sha(dest/'plan.json');q=shlex.quote;command='python3 '+q(str(dest/'scripts/launch_monthly_spline_inspection.py'))
    shell='#!/bin/bash\nset -euo pipefail\ncase "${SGE_TASK_ID:-undefined}" in\n'
    for i,t in enumerate(tasks,1):shell+=str(i)+') task='+t['id']+';;\n'
    shell+='*) exit 2;;\nesac\nexec '+command+' --worker '+q(str(dest))+' --task "$task" --digest '+digest+'\n'
    (dest/'run.sh').write_text(shell);(dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec '+command+' --collect '+q(str(dest))+' --digest '+digest+'\n')
    return plan


def verify(dest,plan,digest,t=None):
    if source.f.sha(dest/'plan.json')!=digest or plan.get('version')!='monthly_spline_inspection_v1' or not plan.get('verified'):raise ValueError('Unverified or changed inspection plan')
    if len(plan['tasks'])!=54 or {x['id'] for x in plan['tasks']}!={x['id'] for x in source.matrix()}:raise ValueError('Invalid inspection matrix')
    source.f.check_hashes(plan['inputs'])
    if t:source.f.check_hashes(t['inputs'])


def validate_result(work,t):
    out=work/'result'
    if (out/'status.txt').read_text().strip()!='SAVED_SPLINE_COMPONENT_INSPECTION_COMPLETE':raise ValueError('Incomplete inspection')
    def rows(n):
        with (out/n).open(newline='') as f:return list(csv.DictReader(f))
    settings=rows('settings.csv')
    if len(settings)!=1 or int(settings[0]['cutoff'])!=t['cutoff'] or settings[0]['seasonal']!=('TRUE' if t['seasonal'] else 'FALSE') or any(settings[0][n]!='FALSE' for n in ('refitted','resampled','joint_intervals')):raise ValueError('Wrong inspection settings')
    data=rows('state_month_components.csv');seen=set();states=set()
    numeric=('observed','person_years','mean_log_linear','mean_log_nonlinear','mean_log_temporal','linear_change_from_origin','nonlinear_change_from_origin','temporal_change_from_origin')
    for r in data:
        k=(r['state'],int(r['year']),int(r['month']))
        if k in seen or k[2] not in range(1,13) or any(not math.isfinite(float(r[n])) for n in numeric):raise ValueError('Invalid component row')
        seen.add(k);states.add(k[0])
        if float(r['person_years'])<=0 or float(r['observed'])<0 or float(r['observed'])!=int(float(r['observed'])) or r['in_training']!=('TRUE' if k[1]<=t['cutoff'] else 'FALSE'):raise ValueError('Invalid exposure/count/training marker')
        for total,a,b in (('mean_log_temporal','mean_log_linear','mean_log_nonlinear'),('temporal_change_from_origin','linear_change_from_origin','nonlinear_change_from_origin')):
            if not math.isclose(float(r[total]),float(r[a])+float(r[b]),rel_tol=1e-9,abs_tol=1e-9):raise ValueError('Temporal decomposition mismatch')
    expected={ (state,y,m) for state in source.f.STATES for y in range(2004,t['cutoff']+4) for m in range(1,13)}
    if seen!=expected:raise ValueError('Incomplete inspection domain')
    december=rows('december_temporal_changes.csv');expected_dec=[r for r in data if int(r['year'])>t['cutoff'] and r['month']=='12']
    if sorted(december,key=lambda r:(r['state'],r['year']))!=sorted(expected_dec,key=lambda r:(r['state'],r['year'])):raise ValueError('December summary mismatch')
    coefficients=rows('state_coefficients.csv');keys={(r['state'],r['component'],int(r['basis_column'])) for r in coefficients}
    expected_coeff={(state,'linear',0) for state in states}|{(state,'nonlinear',i) for state in states for i in range(1,5)}
    if len(coefficients)!=len(expected_coeff) or keys!=expected_coeff or any(not math.isfinite(float(r['posterior_mean'])) for r in coefficients):raise ValueError('Invalid coefficient summaries')
    checks=rows('input_checksums.csv')
    if len(checks)!=2 or any(not re.match(r'^[0-9a-f]{32}$',r['md5']) for r in checks):raise ValueError('Missing input checksums')


def worker(dest,name,digest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());t=next(t for t in plan['tasks'] if t['id']==name);work=dest/name;work.mkdir(exist_ok=False)
    record=dict(task=name,status='FAILED',exit_status=1,plan_sha256=digest)
    try:
        verify(dest,plan,digest,t)
        with (work/'task.log').open('w') as log:code=subprocess.call(t['command'],stdout=log,stderr=subprocess.STDOUT)
        if code or (work/'result/status.txt').read_text().strip()!='SAVED_SPLINE_COMPONENT_INSPECTION_COMPLETE':raise ValueError('Inspection failed: '+str(code))
        validate_result(work,t);verify(dest,plan,digest,t);record.update(status='COMPLETE',exit_status=0,outputs={str(p.relative_to(work)):source.f.sha(p) for p in work.rglob('*') if p.is_file()})
    except (OSError,ValueError,KeyError) as e:record['reason']=str(e)
    (work/'task_status.json').write_text(json.dumps(record,indent=2)+'\n');return record['exit_status']


def collect(dest,digest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());issues=[];tasks=[]
    try:verify(dest,plan,digest)
    except (OSError,ValueError,KeyError) as e:issues.append(str(e))
    for t in plan['tasks']:
        try:
            verify(dest,plan,digest,t);work=dest/t['id'];r=json.loads((work/'task_status.json').read_text())
            if r.get('status')!='COMPLETE' or r.get('task')!=t['id'] or r.get('plan_sha256')!=digest or r.get('exit_status')!=0:raise ValueError(r.get('reason','Incomplete inspection'))
            validate_result(work,t);source.f.bind_record(work,r);tasks.append(dict(task=t['id'],status='COMPLETE'))
        except (OSError,ValueError,KeyError) as e:tasks.append(dict(task=t['id'],status='FAILED_OR_MISSING',reason=str(e)))
    result=dict(tasks=tasks,issues=issues,complete=sum(t['status']=='COMPLETE' for t in tasks),expected=54,refitted=False,resampled=False)
    (dest/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    files=[p for p in dest.rglob('*') if p.is_file() and not p.is_symlink() and '_INTERNAL' not in p.name and p.name!='report_sha256.json']
    (dest/'report_sha256.json').write_text(json.dumps({str(p.relative_to(dest)):source.f.sha(p) for p in files},indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as tar:
        for p in files+[dest/'report_sha256.json']:tar.add(str(p),arcname=str(p.relative_to(dest)))
    print(json.dumps(result,indent=2));return 0 if result['complete']==54 and not issues else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-only',action='store_true');p.add_argument('--worker');p.add_argument('--collect');p.add_argument('--task');p.add_argument('--digest');a=p.parse_args()
    if a.worker or a.collect:
        if not a.digest or (a.worker and not a.task):p.error('Missing task identity')
        return worker(a.worker,a.task,a.digest) if a.worker else collect(a.collect,a.digest)
    root=Path(__file__).resolve().parents[1];dest=root/'output'/('monthly_spline_inspection_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    if not a.prepare_only and any(not shutil.which(x) for x in ('singularity','qsub')):p.error('Load singularity and run on SGE host')
    prepare(root,dest,not a.prepare_only);print('Output: '+str(dest),flush=True)
    if a.prepare_only:return 0
    base=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y','-o',str(dest)]
    raw=subprocess.check_output(base+['-N','foodnet_spline_inspect','-pe','smp','1','-l','h_rt=04:00:00,h_rss=8192M,mem_free=8192M,h_vmem=16G','-t','1-54',str(dest/'run.sh')],universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(array_response=raw),indent=2)+'\n');match=re.match(r'^(\d+)(?:[.\s]|$)',raw)
    if not match:raise ValueError('Unexpected submission response; inspect queue before retry')
    collect_job=subprocess.check_output(base+['-N','foodnet_inspect_collect','-pe','smp','1','-l','h_rt=02:00:00,h_rss=4096M,mem_free=4096M,h_vmem=8G','-hold_jid',match.group(1),str(dest/'collect.sh')],universal_newlines=True).strip()
    (dest/'submission.json').write_text(json.dumps(dict(array_response=raw,collector_response=collect_job),indent=2)+'\n')
    print('Inspection array: '+raw+'; collector: '+collect_job+'; archive: '+str(dest)+'.tar.gz');return 0
if __name__=='__main__':sys.exit(main())
