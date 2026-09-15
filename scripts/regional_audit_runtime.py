"""Small runtime helpers for the read-only regional audit."""
VERSION="county_covariate_experiment_v1"

import argparse

import csv

from datetime import datetime

import hashlib

import json

import math

from pathlib import Path

import re

import shlex

import shutil

import subprocess

import sys

import tarfile

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def read(path):return json.loads(Path(path).read_text())

def write(path,obj):Path(path).write_text(json.dumps(obj,indent=2)+'\n')

def check(bindings):
    for path,digest in bindings.items():
        if Path(path).is_symlink() or sha(path)!=digest:raise ValueError('Changed or unsafe input: '+path)

def matrix():
    combinations = ((p,t,c,l,w,a) for p,t in [('SALMONELLA','ar1'),('CAMPYLOBACTER','rw1')]
                    for c in (2011,2013,2016) for l in (False,True)
                    for w in ('off','current','lag01') for a in (False,True))
    return [dict(task_id=f'{p}_{c}_local{int(local)}_weather{window}_age{int(age)}',pathogen=p,cutoff=c,
                 temporal=temporal,local_seasonality=local,weather=window!='off',age=age,
                 weather_window='current' if window=='off' else window,end_year=2019,
                 draws_per_stream=1000,threads=4,seed=100000000+i*1000000)
            for i,(p,temporal,c,local,window,age) in enumerate(combinations)]

def runtime_command(container,script,*args):
    library=str(Path(container).parent/'r_library')
    if any(x in library for x in (',','\n')):raise ValueError('Unsupported library path')
    return ['singularity','exec','--cleanenv','--env','OPENBLAS_NUM_THREADS=1,OMP_NUM_THREADS=1,MKL_NUM_THREADS=1,R_LIBS='+library,'--bind','/scicomp',str(container),'Rscript','--vanilla',str(script)]+[str(x) for x in args]

def submit(script,name,log,resources,extra=()):
    cmd=['qsub','-terse','-V','-cwd','-S','/bin/bash','-j','y','-N',name,'-pe','smp',str(resources[0]),'-l',resources[1],'-o',str(log)]+list(extra)+[str(script)]
    result=subprocess.check_output(cmd,universal_newlines=True).strip()
    if not re.fullmatch(r'\d+(?:\.\d+-\d+:\d+)?',result):raise ValueError('Unexpected qsub response; inspect queue: '+result)
    return result

def archive(dest):
    names=[]
    for path in dest.rglob('*'):
        rel=path.relative_to(dest)
        if not path.is_file() or path.is_symlink() or any('_INTERNAL' in p for p in rel.parts):continue
        if rel.parts[0] in ('bundle','runtime.sif','r_library'):continue
        if path.suffix in ('.json','.csv','.txt','.log','.sh'):names.append(path)
    write(dest/'report_sha256.json',{str(p.relative_to(dest)):sha(p) for p in names if p.name!='report_sha256.json'})
    names=[p for p in names if p.name!='report_sha256.json']+[dest/'report_sha256.json']
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as t:
        for p in names:t.add(str(p),arcname=str(p.relative_to(dest)))
    print('Archive: '+str(dest)+'.tar.gz',flush=True)

def verify(dest,plan,digest):
    if sha(dest/'plan.json')!=digest or plan.get('version')!=VERSION or plan.get('mode')!='historical_conditional' or len(plan.get('tasks',[]))!=72:raise ValueError('Changed experiment plan')
    for entry,expected in zip(plan['tasks'],matrix()):
        if any(entry['task'].get(k)!=v for k,v in expected.items()):raise ValueError('Experiment matrix differs')
        check({entry['task_json']:entry['task_sha256']})
    check(plan['bindings']);p=Path(plan['container'])
    if dict(size=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns)!=plan['container_stat']:raise ValueError('Container snapshot changed')
