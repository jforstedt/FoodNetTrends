#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import tarfile
from run_extension_data_audit import validate_reports


def collect(dest):
    dest=Path(dest);plan=json.loads((dest/'plan.json').read_text());results=[]
    for task in plan['tasks']:
        work=dest/task['id']
        try:
            r=json.loads((work/'task_status.json').read_text())
            if r['status']=='COMPLETE':validate_reports(work/'reports',task['kind'])
        except (OSError,ValueError,KeyError) as e:r=dict(status='MISSING_OR_INVALID',reason=str(e))
        results.append(dict(task=task['id'],kind=task['kind'],**{k:v for k,v in r.items() if k not in ('task','kind')}))
    summary=dict(tasks=results,execution_complete=all(r['status']=='COMPLETE' for r in results),scientific_readiness='REVIEW_REQUIRED',models_fitted=False)
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as tar:
        for p in sorted(dest.rglob('*')):
            if p.is_file() and not p.is_symlink() and p.suffix.lower() in ('.csv','.json','.txt','.log','.py','.r','.sh'):
                tar.add(str(p),arcname=str(p.relative_to(dest)),recursive=False)
    print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz')
    return 0 if summary['execution_complete'] else 1


if __name__=='__main__':sys.exit(collect(sys.argv[1]))
