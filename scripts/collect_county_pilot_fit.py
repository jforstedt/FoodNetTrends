#!/usr/bin/env python3
"""Archive aggregate exploratory reports even when one or both fits failed."""
import csv,json,sys,tarfile
from pathlib import Path

def collect(dest):
    dest=Path(dest);results=[];ok=True
    for variant in ('spatial','iid'):
        report=dest/variant/'reports'
        status=(report/'status.txt').read_text().splitlines()[0] if (report/'status.txt').is_file() else 'MISSING'
        exit_code=(report/'exit_status.txt').read_text().strip() if (report/'exit_status.txt').is_file() else 'MISSING'
        row=dict(model=variant,status=status,exit_status=exit_code)
        if (report/'diagnostics.csv').is_file():
            with (report/'diagnostics.csv').open() as h:row.update(next(csv.DictReader(h)))
        results.append(row);ok=ok and status=='EXPLORATORY_FIT_COMPLETE' and exit_code=='0'
    (dest/'fit_summary.json').write_text(json.dumps(results,indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as archive:
        for variant in ('spatial','iid'):
            report=dest/variant/'reports'
            if report.is_dir():archive.add(str(report),arcname=variant+'/reports')
            log=dest/(variant+'.log')
            if log.is_file():archive.add(str(log),arcname=log.name)
        for name in ('fit_summary.json','manifest.json','fit_county_pilot.R','fit.sh','collect.py','collect.sh'):
            f=dest/name
            if f.exists():archive.add(str(f),arcname=name)
    print(json.dumps(results,indent=2))
    print('Archive: '+str(dest)+'.tar.gz')
    print('Exploratory execution complete; statistical review pending.' if ok else 'One or more fits failed or lack outputs; inspect archive.')
    return 0 if ok else 1
if __name__=='__main__':sys.exit(collect(sys.argv[1]))
