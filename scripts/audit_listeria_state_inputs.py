#!/usr/bin/env python3
"""Read-only CSTE audit of the exact Listeria scope used by saved state fits."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def audit(source, validation_dir, output):
    source=Path(source);validation_dir=Path(validation_dir);output=Path(output)
    plan=json.loads((source/'manifest.json').read_text());results=[]
    for job in plan['jobs']:
        s=job['settings']
        if s['pathogen']!='LISTERIA':continue
        issues=[];included=Counter();verified=Counter();unverified=Counter();before=None;clean=None
        try:
            if s['subgroup']!='combined':raise ValueError('Listeria subgroup needs an explicit selection audit')
            proof=json.loads((validation_dir/job['task']/'saved_fit_validation.json').read_text())
            if proof.get('eligibility_status')!='PASS':raise ValueError('Expected state/year eligibility could not be established')
            expected={(int(r['year']),r['state']) for r in proof['expected_keys']}
            fitted={(int(r['year']),r['state']):int(r['count']) for r in proof['model_data']}
            if set(fitted)!=expected:raise ValueError('Saved model and expected keys differ')
            command=job['command'];clean=Path(command[command.index('--cleanFile')+1]);before=sha256(clean)
            travel=set(s['travel'].split(','));diagnoses=set(s['cidt'].split(','))
            with clean.open(newline='',encoding='utf-8-sig') as f:
                reader=csv.DictReader(f);names={n.lower():n for n in (reader.fieldnames or [])}
                needed={'year','state','pathogen','county','travelint','cxcidt','cste'}
                if s['colorado_coverage']=='historical' and any(y>=2023 and st=='CO' for y,st in expected):needed.add('siteid')
                missing=needed-set(names)
                if missing:raise ValueError('Clean input lacks required fields: '+', '.join(sorted(missing)))
                for raw in reader:
                    r={k:raw[v] for k,v in names.items()}
                    if r['pathogen']!='LISTERIA':continue
                    y=float(r['year'])
                    if not y.is_integer():raise ValueError('Noninteger Listeria year')
                    key=(int(y),r['state'])
                    if key not in expected or r['travelint'] not in travel or r['cxcidt'] not in diagnoses:continue
                    if r['county'] in ('OUT OF STATE','UNKNOWN','99997'):continue
                    if s['colorado_coverage']=='historical' and any(yr>=2023 and st=='CO' for yr,st in expected):
                        if r.get('siteid','').strip().upper()=='COEX':continue
                    included[key]+=1
                    if r['cste']=='YES':verified[key]+=1
                    else:unverified[(key[0],key[1],r['cste'] or 'MISSING')]+=1
            if sha256(clean)!=before:issues.append('Clean input changed during audit')
            mismatches=[dict(year=y,state=st,fit_count=fitted[y,st],clean_count=included[y,st],verified_count=verified[y,st])
                        for y,st in sorted(expected) if fitted[y,st]!=verified[y,st]]
            if mismatches:issues.append('Saved counts do not exactly match verified CSTE-YES counts/current input selection')
        except (OSError,ValueError,KeyError,TypeError,IndexError) as e:
            issues.append(str(e));mismatches=[]
        results.append(dict(task=job['task'],analysis=job['prefix'],status='PASS' if not issues else 'REVIEW_REQUIRED',issues=issues,
                            clean_file=str(clean) if clean else None,clean_sha256=before,
                            included_records=sum(included.values()),verified_records=sum(verified.values()),
                            unverified=[dict(year=y,state=st,cste=c,records=n) for (y,st,c),n in sorted(unverified.items())],
                            mismatches=mismatches))
    summary=dict(status='PASS' if all(r['status']=='PASS' for r in results) else 'REVIEW_REQUIRED',results=results,
                 scope='Exact saved Listeria state-year/case-filter scope. No refitting or source edits.',
                 limitation='Hashes describe current audit inputs. Older runs did not fingerprint these at fitting; matching aggregated counts does not prove individual-record identity.')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(summary,indent=2)+'\n')
    return summary
