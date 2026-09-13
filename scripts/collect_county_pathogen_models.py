#!/usr/bin/env python3
"""Collect aggregate reports and logs; never archive model checkpoints or panels."""
import json
from pathlib import Path
import sys
import tarfile

def collect(dest):
    dest = Path(dest);plan = json.loads((dest/'manifest.json').read_text());summary = []
    for p in plan['pathogens']:
        for m in plan['models']:
            base = dest/p/m
            status = base/'reports/status.txt';code = base/'task_exit_status.txt'
            summary.append(dict(pathogen=p, model=m,
                status=status.read_text().splitlines()[0] if status.is_file() else 'MISSING_OR_BLOCKED',
                exit_status=code.read_text().strip() if code.is_file() else 'MISSING'))
    (dest/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz', 'w:gz') as t:
        for f in sorted(dest.rglob('*')):
            if f.is_file() and not f.is_symlink() and f.suffix.lower() in ('.csv','.json','.txt','.log','.pdf','.r','.py','.sh'):
                t.add(str(f), arcname=str(f.relative_to(dest)), recursive=False)
    print(json.dumps(summary, indent=2))
    print('Archive: '+str(dest)+'.tar.gz')
    print('Statistical review pending. No dashboard results promoted.')
    return 0 if all(s['status']=='SENSITIVITY_FIT_COMPLETE' and s['exit_status']=='0' for s in summary) else 1
if __name__ == '__main__': sys.exit(collect(sys.argv[1]))
