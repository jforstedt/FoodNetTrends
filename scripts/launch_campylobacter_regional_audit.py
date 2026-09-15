#!/usr/bin/env python3
"""Run a source-bound regional history audit; never fit or install packages."""
import argparse
import csv
import math
from datetime import datetime
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
# Keep the verified code snapshot immutable when this entry point imports helpers.
sys.dont_write_bytecode = True
import regional_audit_runtime as base

VERSION='campylobacter_regional_audit_v1'
MEMBERS={'launch_campylobacter_regional_audit.py','regional_audit_runtime.py','audit_campylobacter_regional_history.R','source_receipt.json','protocol.md'}
REPORTS=('state_month_history.csv','state_year_history.csv','state_year_origin_history.csv','county_domain_summary.csv','audit_metadata.json','input_checksums.csv','status.txt')


def package_check(bundle,digest):
    if base.sha(bundle/'bundle.json')!=digest:raise ValueError('Changed bundle manifest')
    manifest=base.read(bundle/'bundle.json')
    actual={str(p.relative_to(bundle)) for p in bundle.rglob('*') if p.is_file() and p.name!='bundle.json'}
    if manifest.get('version')!=VERSION or set(manifest['files'])!=MEMBERS or actual!=MEMBERS:raise ValueError('Wrong bundle members')
    base.check({str(bundle/n):h for n,h in manifest['files'].items()})
    return manifest


def validate(reports):
    if (reports/'status.txt').read_text().strip()!='CAMPYLOBACTER_REGIONAL_HISTORY_COMPLETE':raise ValueError('Audit incomplete')
    for name in REPORTS:
        if not (reports/name).is_file() or not (reports/name).stat().st_size:raise ValueError('Missing audit report: '+name)
    metadata=base.read(reports/'audit_metadata.json')
    if metadata.get('models_fitted') is not False or metadata.get('refitted') is not False:raise ValueError('Audit must not fit models')
    states={'CA','CO','CT','GA','MD','MN','NM','NY','OR','TN'}
    if metadata.get('version')!='campylobacter_regional_history_v1' or metadata.get('pathogen')!='CAMPYLOBACTER' or metadata.get('years')!=list(range(2004,2020)) or set(metadata.get('states',[]))!=states:raise ValueError('Wrong audit scope')
    tables={}
    for name in REPORTS:
        if name.endswith('.csv'):
            with (reports/name).open() as f:
                reader=csv.DictReader(f)
                if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames):raise ValueError('Invalid report header')
                rows=list(reader)
            if not rows or any(None in row or any(v is None for v in row.values()) for row in rows):raise ValueError('Malformed or empty report: '+name)
            tables[name]=rows
    def keyed(name,fields,expected):
        rows=tables[name];keys=[tuple(r[k] if k=='state' else int(r[k]) for k in fields) for r in rows]
        if len(keys)!=len(expected) or set(keys)!=expected:raise ValueError('Wrong report domain: '+name)
        return dict(zip(keys,rows))
    sy={(st,y) for st in states for y in range(2004,2020)}
    month=keyed('state_month_history.csv',('state','year','month'),{(st,y,m) for st,y in sy for m in range(1,13)})
    year=keyed('state_year_history.csv',('state','year'),sy)
    origins=keyed('state_year_origin_history.csv',('state','year','cutoff'),{(st,y,c) for st,y in sy for c in (2011,2013,2016)})
    domain=keyed('county_domain_summary.csv',('state','year'),sy)
    for row in list(month.values())+list(year.values())+list(origins.values()):
        count=float(row['count']);exposure=float(row['person_years']);rate=float(row['record_rate_per_100000_person_years'])
        if not all(math.isfinite(v) for v in (count,exposure,rate)) or count<0 or count!=int(count) or exposure<=0 or not math.isclose(rate,count/exposure*1e5,rel_tol=1e-9,abs_tol=1e-8):raise ValueError('Invalid count/exposure/rate')
    for (st,y),r in year.items():
        for field in ('count','person_years'):
            if not math.isclose(float(r[field]),sum(float(month[st,y,m][field]) for m in range(1,13)),rel_tol=1e-9,abs_tol=1e-8):raise ValueError('Month/year totals differ')
            if any(float(origins[st,y,c][field])!=float(r[field]) for c in (2011,2013,2016)):raise ValueError('Origin/year totals differ')
        dr=domain[st,y];n=int(dr['counties'])
        if n<=0 or any(not 0<=int(dr[k])<=n for k in ('zero_record_counties','all_zero_month_counties')):raise ValueError('Invalid county domain summary')
    return metadata


def run(dest,digest):
    result=dict(version=VERSION,status='FAILED',models_fitted=False,scientific_acceptance=False)
    try:
        if base.sha(dest/'bootstrap.json')!=digest:raise ValueError('Changed bootstrap')
        boot=base.read(dest/'bootstrap.json');bundle=dest/'bundle';package=package_check(bundle,boot['bundle_sha256'])
        receipt=base.read(bundle/'source_receipt.json')
        if receipt.get('version')!=VERSION:raise ValueError('Wrong source receipt')
        source=Path(boot['root'])/'output'/receipt['source_run']
        print('Verifying source plan, frozen runtime and input hashes',flush=True)
        base.check({str(source/'plan.json'):receipt['plan_sha256'],str(source/'summary.json'):receipt['summary_sha256']})
        old=base.read(source/'plan.json');base.verify(source,old,receipt['plan_sha256'])
        if base.sha(old['container'])!=old['container_sha256']:raise ValueError('Source container changed')
        if receipt.get('derive_inputs'):
            entries=[e for e in old['tasks'] if e['task']['pathogen']=='CAMPYLOBACTER']
            inputs={k:v for e in entries for k,v in e['inputs'].items()}
            candidates={e['task']['candidate'] for e in entries}
            if len(candidates)!=1:raise ValueError('Ambiguous candidate')
            parent=Path(candidates.pop()).parent
            for name,h in receipt['preparation_files'].items():
                if Path(name).name!=name:raise ValueError('Unsafe preparation filename')
                inputs[str(parent/name)]=h
        else:
            inputs=dict(receipt['inputs'])
        base.check(inputs)
        task=dict(source_run=str(source),source_scripts=str(source/'bundle/scripts'),output=str(dest/'reports'))
        base.write(dest/'task.json',task);taskhash=base.sha(dest/'task.json')
        provenance=dict(version=VERSION,source_plan_sha256=receipt['plan_sha256'],source_summary_sha256=receipt['summary_sha256'],source_run=str(source),inputs=inputs,runtime_bindings=old['bindings'],container_sha256=old['container_sha256'],task_sha256=taskhash,models_fitted=False,scientific_acceptance=False)
        base.write(dest/'plan.json',provenance)
        print('Running regional history audit; no model fitting',flush=True)
        with (dest/'audit.log').open('w') as log:
            code=subprocess.call(base.runtime_command(old['container'],bundle/'audit_campylobacter_regional_history.R',dest/'task.json'),stdout=log,stderr=subprocess.STDOUT)
        if code:raise ValueError('R audit exited '+str(code)+'; see audit.log')
        validate(dest/'reports')
        base.check(inputs);base.verify(source,old,receipt['plan_sha256'])
        base.check({str(source/'summary.json'):receipt['summary_sha256'],str(dest/'task.json'):taskhash})
        package_check(bundle,boot['bundle_sha256'])
        if base.sha(old['container'])!=old['container_sha256']:raise ValueError('Container changed during audit')
        result.update(status='COMPLETE',outputs={str(p.relative_to(dest/'reports')):base.sha(p) for p in (dest/'reports').rglob('*') if p.is_file()})
    except (OSError,ValueError,KeyError,TypeError) as e:result['reason']=str(e)
    base.write(dest/'summary.json',result);base.archive(dest)
    return 0 if result['status']=='COMPLETE' else 1


def launch(root,bundle=None):
    root=Path(root).resolve()
    if any(not shutil.which(x) for x in ('qsub','singularity')):raise ValueError('Load Singularity on an SGE host')
    # Only small code/receipt copying happens here; data verification runs visibly on SGE.
    dest=root/'output'/('campylobacter_regional_audit_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'));dest.mkdir(parents=True)
    if bundle is not None:
        shutil.copytree(str(Path(bundle).resolve()),str(dest/'bundle'))
    else:
        snapshot=dest/'bundle';snapshot.mkdir()
        for name in ('launch_campylobacter_regional_audit.py','regional_audit_runtime.py','audit_campylobacter_regional_history.R'):
            shutil.copyfile(str(root/'scripts'/name),str(snapshot/name))
        shutil.copyfile(str(root/'docs/campylobacter_regional_audit_protocol.md'),str(snapshot/'protocol.md'))
        shutil.copyfile(str(root/'analysis_configs/campylobacter_regional_audit_source.json'),str(snapshot/'source_receipt.json'))
        base.write(snapshot/'bundle.json',dict(version=VERSION,files={n:base.sha(snapshot/n) for n in sorted(MEMBERS)}))
    base.write(dest/'bootstrap.json',dict(root=str(root),bundle_sha256=base.sha(dest/'bundle/bundle.json')))
    q=shlex.quote;script=dest/'bundle/launch_campylobacter_regional_audit.py'
    (dest/'run.sh').write_text('#!/bin/bash\nset -euo pipefail\nexec python3 '+q(str(script))+' --run '+q(str(dest))+' --digest '+base.sha(dest/'bootstrap.json')+'\n')
    job=base.submit(dest/'run.sh','foodnet_campy_audit',dest/'launcher.log',(2,'h_rt=08:00:00,h_rss=16384M,mem_free=16384M,h_vmem=24G'))
    base.write(dest/'submission.json',dict(job=job));print('Audit job: '+job+'\nLog: '+str(dest/'launcher.log')+'\nArchive: '+str(dest)+'.tar.gz')
    return dest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',default='.');p.add_argument('--bundle');p.add_argument('--run');p.add_argument('--digest');a=p.parse_args()
    if a.run:sys.exit(run(Path(a.run),a.digest))
    elif a.bundle:launch(a.root,a.bundle)
    else:launch(a.root)
