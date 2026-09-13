#!/usr/bin/env python3
"""Collect sensitivity reports, including failures; never archive saved fits."""
import json
from pathlib import Path
import sys
import tarfile

NAMES=('spatial_county_sd2','iid_county_sd2','spatial_county_time','iid_county_time')

def collect(dest,comparison_status):
    dest=Path(dest);rows=[]
    for name in NAMES:
        r=dest/name/'reports'
        status=(r/'status.txt').read_text().splitlines()[0] if (r/'status.txt').is_file() else 'MISSING'
        code=(r/'exit_status.txt').read_text().strip() if (r/'exit_status.txt').is_file() else 'MISSING'
        rows.append(dict(model=name,status=status,exit_status=code))
    ok=comparison_status==0 and all(r['status']=='SENSITIVITY_FIT_COMPLETE' and r['exit_status']=='0' for r in rows)
    (dest/'summary.json').write_text(json.dumps(dict(models=rows,comparison_exit_status=comparison_status,complete=ok),indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as t:
        for name in NAMES:
            for f in (dest/name/'reports',dest/(name+'.log')):
                if f.exists():t.add(str(f),arcname=str(f.relative_to(dest)))
        for name in ('comparison','comparison.log','summary.json','manifest.json','county_sensitivity.R','fit_county_pilot.R','diagnose_saved_county_pilot.R','fit.sh','collect.sh','collect_county_sensitivity.py'):
            f=dest/name
            if f.exists():t.add(str(f),arcname=name)
    print((dest/'summary.json').read_text())
    print('Archive: '+str(dest)+'.tar.gz')
    return 0 if ok else 1
if __name__=='__main__':sys.exit(collect(sys.argv[1],int(sys.argv[2])))
