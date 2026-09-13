#!/usr/bin/env python3
"""Execute one read-only audit and validate its declared aggregate reports."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from county_forecast_protocol import validate_source


def sha(path, algorithm='sha256'):
    h=hashlib.new(algorithm)
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def validate_reports(out,kind):
    out=Path(out)
    if (out/'status.txt').read_text().splitlines()[0]!='EXTENSION_DATA_AUDIT_COMPLETE':raise ValueError('Audit did not complete')
    with (out/'report_manifest.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    names=[r['file'] for r in rows]
    required={'diagnostics':{'fields.csv','categories.csv','readiness.csv'},
              'seasonality':{'field_inventory.csv','date_completeness.csv','limitations.csv'},
              'counts':{'state_year_count_support.csv','county_history_support.csv','geography.csv','interpretation.csv'}}[kind]
    if not rows or len(set(names))!=len(names) or not required.issubset(names):raise ValueError('Missing/duplicate expected report tables')
    for row in rows:
        name=row['file']
        if Path(name).name!=name or not name.endswith('.csv'):raise ValueError('Unsafe report path')
        if sha(out/name,'md5')!=row['md5']:raise ValueError('Report checksum mismatch')
        with (out/name).open(newline='') as f:
            reader=csv.DictReader(f);data=list(reader);fields=reader.fieldnames
        if int(row['source_columns'])>0 and (len(data)!=int(row['source_rows']) or len(fields or [])!=int(row['source_columns'])):raise ValueError('Report dimensions mismatch')
    return len(rows)


def run(dest,task_id):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());task=next(t for t in plan['tasks'] if t['id']==task_id)
    work=dest/task_id;work.mkdir(exist_ok=False)
    result=dict(task=task_id,kind=task['kind'],status='FAILED',scientific_readiness='REVIEW_REQUIRED')
    try:
        if not plan['verified']:raise ValueError('Prepare-only plan cannot execute')
        for path,digest in plan['fingerprints'].items():
            if sha(path)!=digest:raise ValueError('Changed source/container/input: '+path)
        if task['kind']=='counts':validate_source(task['pathogen'],task['source'])
        with (work/'audit.log').open('w') as f:code=subprocess.run(task['command'],stdout=f,stderr=subprocess.STDOUT,cwd=str(dest)).returncode
        result['exit_status']=code
        if code:raise ValueError('R audit failed; see audit.log')
        result['report_tables']=validate_reports(work/'reports',task['kind'])
        for path,digest in plan['fingerprints'].items():
            if sha(path)!=digest:raise ValueError('Inputs changed during audit: '+path)
        if task['kind']=='counts':validate_source(task['pathogen'],task['source'])
        result['status']='COMPLETE'
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as e:result['reason']=str(e)
    (work/'task_status.json').write_text(json.dumps(result,indent=2)+'\n')
    return 0 if result['status']=='COMPLETE' else 1


if __name__=='__main__':sys.exit(run(sys.argv[1],sys.argv[2]))
