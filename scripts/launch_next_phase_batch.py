#!/usr/bin/env python3
"""Launch independent next-phase investigations with a gated county spline pilot."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from county_forecast_protocol import source_paths,validate_source,PATHOGENS,ORIGINS,CRYPTO_ORIGINS
from run_next_phase_task import sha

FILES=('county_spline_candidate.R','audit_saved_forecast_sampling.R','audit_extension_definitions.R','run_next_phase_models.R',
 'fit_county_pilot.R','county_forecast_check.R','county_forecast_model.R','diagnose_saved_county_pilot.R','county_forecast_protocol.py',
 'run_next_phase_task.py','collect_next_phase_batch.py')
SOURCE_RUN='county_forecast_recovery_20260913_140522_657935'


def prepare(root,dest,source,raw,verified=True):
    root=Path(root).resolve();dest=Path(dest).resolve();source=Path(source).resolve();raw=Path(raw).resolve()
    foodnet=root/'foodnet.sif';inla=root/'foodnet-inla-fixed.sif'
    if verified:
        for p in (foodnet,inla,raw,source/'manifest.json',source/'gate.json'):
            if not p.is_file():raise ValueError('Missing prerequisite: '+str(p))
        old=json.loads((source/'manifest.json').read_text());gate=json.loads((source/'gate.json').read_text())
        if gate['status']!='PASS' or gate['manifest_sha256']!=sha(source/'manifest.json'):raise ValueError('Original numerical gate not verified')
        saved=[];failures=[]
        for task in old['tasks']:
            if task['kind']!='forecast':continue
            record=json.loads((source/task['id']/'task_status.json').read_text())
            if record.get('status')=='COMPLETE' and record.get('exit_status')==0:
                fit=source/task['id']/'result/fit_INTERNAL.rds'
                if not fit.is_file():raise ValueError('Saved fit missing; no refit fallback: '+str(fit))
                saved.append(task)
            else:failures.append(task['id'])
    else:
        saved=[dict(id='%s_%s_%s'%(p,y,m),kind='forecast',pathogen=p,origin=y,horizon=3,model=m) for p in PATHOGENS for y in (CRYPTO_ORIGINS if p=='CRYPTOSPORIDIUM' else ORIGINS) for m in ('spatial_county_time','iid_county_time') if (p,y,m)!=('CYCLOSPORA',2011,'spatial_county_time')];failures=['CYCLOSPORA_2011_spatial_county_time']
    dest.mkdir(parents=True,exist_ok=False);scripts=dest/'scripts';scripts.mkdir();(dest/'tests').mkdir()
    for name in FILES:shutil.copyfile(str(root/'scripts'/name),str(scripts/name))
    shutil.copyfile(str(root/'tests/test_county_spline_candidate.R'),str(dest/'tests/test_county_spline_candidate.R'))
    fingerprints={str(p):sha(p) for p in list(scripts.iterdir())+list((dest/'tests').iterdir())}
    cached={}
    def digest(path):
        path=str(path)
        if path not in cached:cached[path]=sha(path)
        return cached[path]
    def command(container,script,*args):return ['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1','--bind','/scicomp',str(container),'Rscript','--vanilla',str(script)]+list(map(str,args))
    tasks=[];sources=source_paths(root)
    if verified:
        source_cache={}
        sources={p:validate_source(p,src,hash_cache=source_cache) for p,src in sources.items()}
    def add(task,container,commands,inputs=()):
        task.update(commands=commands,inputs={str(p):digest(p) for p in [container]+list(inputs)} if verified else {})
        if verified and task.get('source'):
            task['inputs'].update(task['source']['evidence_sha256'])
            task['inputs'][str(Path(task['source']['audit'])/'county_panel_INTERNAL.rds')]=task['source']['panel_sha256']
        tasks.append(task)
    for oldtask in saved:
        p=oldtask['pathogen'];name='sampling_'+oldtask['id'];fit=source/oldtask['id']/'result/fit_INTERNAL.rds'
        add(dict(id=name,kind='sampling',pathogen=p,origin=oldtask['origin'],model=oldtask['model'],source=sources[p]),inla,
          [command(inla,scripts/'audit_saved_forecast_sampling.R',sources[p]['audit'],fit,oldtask['origin'],3,dest/name/'result',oldtask['model'])],[fit,source/'manifest.json',source/'gate.json',source/oldtask['id']/'task_status.json'])
    add(dict(id='definitions',kind='definitions'),foodnet,[command(foodnet,scripts/'run_next_phase_models.R','definitions',scripts,raw,dest/'definitions/result')],[raw])
    for threads in (1,8):
        name='cyclospora_threads_'+str(threads)
        add(dict(id=name,kind='cyclospora',pathogen='CYCLOSPORA',source=sources['CYCLOSPORA'],threads=threads),inla,
          [command(inla,scripts/'run_next_phase_models.R','cyclospora',scripts,sources['CYCLOSPORA']['audit'],dest/name/'result',threads)])
    add(dict(id='basis',kind='basis'),foodnet,[command(foodnet,scripts/'run_next_phase_models.R','basis',scripts,dest/'basis/result'),
        command(foodnet,dest/'tests/test_county_spline_candidate.R','prepare',dest/'basis/result/synthetic')])
    add(dict(id='gate',kind='gate',requires=['basis']),inla,[command(inla,dest/'tests/test_county_spline_candidate.R','run',dest/'basis/result/synthetic',dest/'gate/result')])
    for p in ('SALMONELLA','CAMPYLOBACTER'):
        for origin in ORIGINS:
            for variant in ('spatial','iid'):
                name='spline_%s_%s_%s'%(p,origin,variant)
                add(dict(id=name,kind='spline',pathogen=p,origin=origin,variant=variant,source=sources[p],requires=['basis','gate']),inla,
                  [command(inla,scripts/'run_next_phase_models.R','spline',scripts,sources[p]['audit'],origin,variant,dest/'basis/result'/('basis_%s.rds'%origin),dest/name/'result')])
    plan=dict(tasks=tasks,fingerprints=fingerprints,verified=verified,source_run=str(source),source_failures=failures,
      scientific_status='EXPLORATORY: distinct spline priors, no published-state equivalence or dashboard promotion',state_fits_unchanged=True)
    (dest/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');q=shlex.quote
    groups={'sampling':[t['id'] for t in tasks if t['kind']=='sampling'],'definitions':['definitions'],'cyclospora_serial':['cyclospora_threads_1'],
      'cyclospora_parallel':['cyclospora_threads_8'],'basis':['basis'],'gate':['gate'],'spline':[t['id'] for t in tasks if t['kind']=='spline']}
    for kind,ids in groups.items():
        lines=['#!/bin/bash','set -euo pipefail','ulimit -c 0','case "${SGE_TASK_ID:-1}" in']
        lines+=['%d) task=%s;;'%(i,q(name)) for i,name in enumerate(ids,1)]
        lines+=['*) exit 2;;','esac','exec > '+q(str(dest))+'/"${task}_shell.log" 2>&1','date -u','hostname','ulimit -a',
          'trap \'code=$?; printf "Shell exit status: %s\\n" "$code"\' EXIT','trap \'exit 140\' USR2',
          'python3 '+q(str(scripts/'run_next_phase_task.py'))+' '+q(str(dest))+' "$task"']
        (dest/(kind+'.sh')).write_text('\n'.join(lines)+'\n')
    (dest/'collect.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec python3 '+q(str(scripts/'collect_next_phase_batch.py'))+' '+q(str(dest))+'\n')
    return plan,groups


def main():
    root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-run',default=SOURCE_RUN);p.add_argument('--raw',default='/scicomp/groups-pure/EDEB/foodnet/trends/data/mmwr9625.sas7bdat');p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    if not a.prepare_only:
        for tool in ('qsub','singularity'):
            if not shutil.which(tool):p.error('Load module for '+tool)
    source=Path(a.source_run);source=source if source.is_absolute() else root/'output'/source
    dest=root/'output'/('next_phase_parallel_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    try:plan,groups=prepare(root,dest,source,Path(a.raw),not a.prepare_only)
    except (OSError,ValueError,KeyError) as e:p.error(str(e))
    print('Output: '+str(dest)+'\nSaved fits to sample: '+str(len(groups['sampling']))+'; gated spline fits: 12; separate Cyclospora diagnostic fits: 2',flush=True)
    if a.prepare_only:print('Unverified preparation only; no jobs submitted.');return
    jobs={}
    for kind in ['sampling','definitions','cyclospora_serial','cyclospora_parallel','basis','gate','spline','collect']:
        cpus=8 if kind in ('spline','cyclospora_parallel') else 1 if kind in ('cyclospora_serial','collect') else 2
        resource='h_rt=24:00:00,h_rss=32768M,mem_free=32768M,h_vmem=64G' if kind in ('spline','cyclospora_parallel','cyclospora_serial','sampling') else 'h_rt=04:00:00,h_rss=16384M,mem_free=16384M,h_vmem=32G'
        cmd=['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_phase_'+kind,'-pe','smp',str(cpus),'-l',resource,'-j','y','-o',str(dest/(kind+'.log'))]
        if kind in ('sampling','spline'):cmd+=['-t','1-'+str(len(groups[kind]))]
        hold=['basis'] if kind=='gate' else ['gate'] if kind=='spline' else list(jobs) if kind=='collect' else []
        if hold:cmd+=['-hold_jid',','.join(jobs[k] for k in hold)]
        value=subprocess.check_output(cmd+[str(dest/(kind+'.sh'))],universal_newlines=True).strip();match=re.match(r'^(\d+)(?:[.\s]|$)',value)
        if not match:raise ValueError('Unexpected scheduler response; inspect before retry: '+value)
        jobs[kind]=match.group(1);(dest/'submission.json').write_text(json.dumps(jobs,indent=2)+'\n');print(kind+' job: '+value,flush=True)
    print('After all eight IDs appear you can disconnect.\nFinal log: '+str(dest/'collect.log')+'\nArchive: '+str(dest)+'.tar.gz')


if __name__=='__main__':main()
