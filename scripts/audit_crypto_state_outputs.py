#!/usr/bin/env python3
"""Inspect existing state result CSV years without modifying or refitting results."""
import csv
import hashlib
import json
from pathlib import Path
import sys

def audit(root,out):
    root=Path(root);out=Path(out);out.mkdir(parents=True,exist_ok=False);results=[]
    for f in sorted(root.rglob('*.csv')):
        if 'CRYPTOSPORIDIUM' not in f.name.upper():continue
        if not any(k in f.name.upper() for k in ('IRCATCH','IRSITE','ESTIRR')):continue
        try:
            with f.open(newline='',encoding='utf-8-sig') as h:
                reader=csv.DictReader(h);cols=reader.fieldnames or []
                key=next((c for c in cols if c.lower()=='year'),None)
                rows=list(reader);years=sorted(set(int(float(r[key])) for r in rows if key and r.get(key)))
            results.append(dict(file=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),rows=len(rows),
                years=years,post_surveillance_years=[y for y in years if y>2017],
                status='AFFECTED_POST_2017' if any(y>2017 for y in years) else 'NO_POST_2017_ROWS' if years else 'YEAR_FIELD_REVIEW_REQUIRED'))
        except Exception as e:results.append(dict(file=str(f),status='READ_ERROR',error=str(e)))
    (out/'state_output_audit.json').write_text(json.dumps(results,indent=2)+'\n')
    (out/'scope.txt').write_text('Read-only CSV audit. Result years beyond 2017 require review; these are not proof of fit internals.\n'
        'The corrected state input rule ends Cryptosporidium observation in 2017. Baselines containing later years must be explicitly replaced.\n'
        'Saved fits and prior dashboards were not modified.\n')
    print('State CSV files checked: '+str(len(results)))
    print('Files containing post-2017 years: '+str(sum(r['status']=='AFFECTED_POST_2017' for r in results)))
    if not results:print('NO_MATCHING_OUTPUTS: check the supplied state run directory')
if __name__=='__main__':audit(sys.argv[1],sys.argv[2])
