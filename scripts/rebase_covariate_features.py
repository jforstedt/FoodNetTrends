"""Recenter existing affine public features at an earlier training cutoff.

No outcomes are read. Subtracting the earlier group mean cancels the original
center; dividing by the earlier SD cancels the original positive scale. This
therefore reproduces a direct earlier-cutoff transform, up to floating rounding.
Weather groups are county/calendar-month; age uses a pooled training mean.
"""
import csv
import hashlib
import io
import json
import math
from pathlib import Path

FEATURES=('weather_tavg_z','weather_logprcp_z','age_under5_z','age65plus_z')

def rebase(rows, cutoff, source_cutoff, counties=486):
    if not 2005 <= cutoff < source_cutoff: raise ValueError('Earlier cutoff required')
    selected=[]; seen=set()
    for row in rows:
        key=(row['fips'],int(row['year']),int(row['month']))
        if key in seen: raise ValueError('Duplicate feature key')
        seen.add(key)
        if not 2004 <= key[1] <= cutoff+3: continue
        if len(key[0])!=5 or not key[0].isdigit() or not 1<=key[2]<=12: raise ValueError('Invalid key')
        r=dict(zip(('fips','year','month'),key))
        for f in FEATURES:
            r[f]=float(row[f])
            if not math.isfinite(r[f]): raise ValueError('Nonfinite feature')
        selected.append(r)
    ids={r['fips'] for r in selected}
    expected={(f,y,m) for f in ids for y in range(2004,cutoff+4) for m in range(1,13)}
    if len(ids)!=counties or {(r['fips'],r['year'],r['month']) for r in selected}!=expected:
        raise ValueError('Incomplete feature domain')
    parameters={}
    for f in FEATURES:
        group=lambda r: (r['fips'],r['month']) if f.startswith('weather_') else ('ALL',0)
        training={}
        for r in selected:
            if r['year']<=cutoff: training.setdefault(group(r),[]).append(r[f])
        centers={k:math.fsum(v)/len(v) for k,v in training.items()}
        residuals=[r[f]-centers[group(r)] for r in selected if r['year']<=cutoff]
        scale=math.sqrt(math.fsum(x*x for x in residuals)/len(residuals))
        if not math.isfinite(scale) or scale<=0: raise ValueError('Zero/nonfinite training scale')
        for r in selected: r[f]=(r[f]-centers[group(r)])/scale
        parameters[f]={'scale_in_source_units':scale,'centers_in_source_units':[
            dict(fips=k[0],month=k[1],mean=v) for k,v in sorted(centers.items())]}
    return selected,parameters

def prepare(source_csv, source_manifest, cutoff, output):
    source_csv=Path(source_csv);source_manifest=Path(source_manifest);output=Path(output)
    payload=source_csv.read_bytes();m=json.loads(source_manifest.read_text())
    if (m.get('version')!='covariate_factorial_transform_v1' or m.get('mode')!='historical_conditional'
        or m.get('centering')!='county_by_calendar_month_training_mean'
        or m.get('scaling')!='pooled_training_anomaly_population_sd'
        or m.get('age_scaling')!='pooled training county-month population SD'
        or m.get('outputs',{}).get(source_csv.name)!=hashlib.sha256(payload).hexdigest()):
        raise ValueError('Unrecognized or changed source transform')
    rows,parameters=rebase(list(csv.DictReader(io.StringIO(payload.decode()))),cutoff,m['training_cutoff_year'])
    output.mkdir(parents=True,exist_ok=False)
    buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    data=buf.getvalue().encode();(output/'weather_experiment.csv').write_bytes(data)
    # Preserve public source provenance and model-facing contract, but remove
    # obsolete raw-unit transform parameters rather than mislabel them as current.
    m={k:v for k,v in m.items() if k not in ('centers','scales','age_centers','age_scales','outputs')}
    m.update(training_cutoff_year=cutoff,forecast_years=list(range(cutoff+1,cutoff+4)),rows=len(rows),
             training_rows=sum(r['year']<=cutoff for r in rows),rebase_parameters=parameters,
             rebase_source={'csv_sha256':hashlib.sha256(payload).hexdigest(),
                            'manifest_sha256':hashlib.sha256(source_manifest.read_bytes()).hexdigest()},
             outputs={'weather_experiment.csv':hashlib.sha256(data).hexdigest()})
    (output/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    return m
