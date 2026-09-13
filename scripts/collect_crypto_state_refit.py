#!/usr/bin/env python3
"""Check corrected state output coverage and collect review artifacts without saved fits."""
import csv
import json
from pathlib import Path
import sys
import tarfile

def collect(dest):
    dest=Path(dest);code=dest/'fit_exit_status.txt';issues=[];inventory=[]
    if not code.is_file() or code.read_text().strip()!='0':issues.append('Model process failed or missing exit status')
    prefix='CRYPTOSPORIDIUM_combined'
    for suffix in ('_IRCatch.csv','_IRSite.csv','_EstIRRCatch_2015_2017.csv'):
        f=dest/'spline_results'/(prefix+suffix)
        try:
            with f.open(newline='') as h:rows=list(csv.DictReader(h))
            years=sorted(set(int(float(r['year'])) for r in rows))
            if not years or max(years)!=2017 or any(y>2017 for y in years) or not {2015,2016,2017}.issubset(years):issues.append('Invalid coverage: '+f.name)
            inventory.append(dict(file=f.name,years=years,rows=len(rows)))
        except Exception as e:issues.append(f.name+': '+str(e))
    for suffix in ('_analysis_settings.csv','_convergence_diagnostics.csv','_brm.Rds'):
        if not (dest/'spline_results'/(prefix+suffix)).is_file():issues.append('Missing '+suffix)
    summary=dict(execution_and_coverage='PASS' if not issues else 'REVIEW_REQUIRED',issues=issues,outputs=inventory,
                 statistical_status='Sampling diagnostics require review; no dashboard replacement performed')
    (dest/'review_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as t:
        for f in sorted(dest.rglob('*')):
            if f.is_file() and not f.is_symlink() and f.suffix.lower() in ('.csv','.json','.txt','.log','.r','.py','.sh','.png','.pdf'):
                t.add(str(f),arcname=str(f.relative_to(dest)),recursive=False)
    print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz')
    return 0 if not issues else 1
if __name__=='__main__':sys.exit(collect(sys.argv[1]))
