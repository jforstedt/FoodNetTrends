#!/usr/bin/env python3
"""Collect all recovery and forecast outcomes, including failures, without RDS files."""
import json
from pathlib import Path
import sys
import tarfile

def collect(dest):
    dest=Path(dest);plan=json.loads((dest/'manifest.json').read_text());rows=[]
    for task in plan['tasks']:
        base=dest/task['name'];s=base/'reports/status.txt';e=base/'task_exit_status.txt'
        row=dict(task);row.update(status=s.read_text().splitlines()[0] if s.is_file() else 'MISSING_OR_BLOCKED',
                               exit_status=e.read_text().strip() if e.is_file() else 'MISSING');rows.append(row)
    (dest/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as t:
        for f in sorted(dest.rglob('*')):
            if f.is_file() and not f.is_symlink() and f.suffix.lower() in ('.csv','.json','.txt','.log','.pdf','.r','.py','.sh'):
                t.add(str(f),arcname=str(f.relative_to(dest)),recursive=False)
    print(json.dumps(rows,indent=2));print('Archive: '+str(dest)+'.tar.gz')
    print('Statistical review pending; original results retained.')
    expected={'retry':'SENSITIVITY_FIT_COMPLETE','cpo':'CPO_REPAIR_COMPLETE','forecast':'FORECAST_CHECK_COMPLETE'}
    return 0 if all(r['status']==expected[r['mode']] and r['exit_status']=='0' for r in rows) else 1
if __name__=='__main__':sys.exit(collect(sys.argv[1]))
