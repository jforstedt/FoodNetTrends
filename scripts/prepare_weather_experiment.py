#!/usr/bin/env python3
"""Freeze county-calendar-month weather anomalies for retrospective experiments."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from join_county_covariates import read_bound, key


def build(rows, cutoffyear, expected_counties=486):
    """Pure transformation; configurable footprint size exists for synthetic tests."""
    cutoffyear = int(cutoffyear)
    if not 2005 <= cutoffyear <= 2197:
        raise ValueError('Cutoff must permit at least two training years since 2004')
    indexed = {}
    for r in rows:
        k = key(r)
        if k in indexed:
            raise ValueError('Duplicate county-month')
        indexed[k] = r
    ids = sorted({k[0] for k in indexed})
    if len(ids) != expected_counties:
        raise ValueError('Unexpected county footprint size')
    expected = {(f,y,m) for f in ids for y in range(2004,cutoffyear+4) for m in range(1,13)}
    if not expected <= set(indexed):
        raise ValueError('Incomplete training/three-year forecast weather support')
    transformed = {}
    groups = {}
    for k in sorted(expected):
        r = indexed[k]
        try:
            t, p = float(r['tavg_c']), float(r['prcp_mm'])
        except (ValueError, KeyError):
            raise ValueError('Invalid/missing weather')
        if not math.isfinite(t) or not math.isfinite(p) or p < 0:
            raise ValueError('Nonfinite weather or negative precipitation')
        v = (t, math.log1p(p))
        transformed[k] = v
        if k[1] <= cutoffyear:
            groups.setdefault((k[0],k[2]),[]).append(v)
    centers = {g: [math.fsum(v[j] for v in vv)/len(vv) for j in (0,1)] for g,vv in groups.items()}
    train = [k for k in sorted(expected) if k[1] <= cutoffyear]
    scales = [math.sqrt(math.fsum((transformed[k][j]-centers[k[0],k[2]][j])**2 for k in train)/len(train)) for j in (0,1)]
    if not all(math.isfinite(s) and s>0 for s in scales):
        raise ValueError('Zero/nonfinite pooled training anomaly scale')
    out=[]
    for k in sorted(expected):
        z=[(transformed[k][j]-centers[k[0],k[2]][j])/scales[j] for j in (0,1)]
        if not all(math.isfinite(v) for v in z):raise ValueError('Nonfinite weather anomaly')
        out.append(dict(fips=k[0],year=k[1],month=k[2],weather_tavg_z=z[0],weather_logprcp_z=z[1]))
    contract=dict(version='weather_experiment_transform_v1',mode='historical_conditional',operational_forecast_ready=False,
                  contemporary_weather=True,lags_months=[0],age_covariates_used=False,target_values_used=False,
                  start_year=2004,training_cutoff_year=cutoffyear,forecast_years=list(range(cutoffyear+1,cutoffyear+4)),
                  counties=len(ids),rows=len(out),training_rows=len(train),
                  feature_order=['weather_tavg_z','weather_logprcp_z'],
                  precursor_transform=['identity_tavg_c','log1p_prcp_mm'],
                  centering='county_by_calendar_month_training_mean',scaling='pooled_training_anomaly_population_sd',
                  scales=scales,centers=[dict(fips=g[0],month=g[1],tavg_c_mean=v[0],log1p_prcp_mm_mean=v[1]) for g,v in sorted(centers.items())],
                  scientific_acceptance=False,surveillance_eligibility_applied=False)
    return out,contract


def prepare(panelpath, manifestpath, cutoffyear, output):
    fields,rows,receipt=read_bound(panelpath,manifestpath)
    if receipt['source_manifest'].get('version')!='county_weather_v1':
        raise ValueError('Native NOAA county_weather_v1 manifest required')
    if not {'fips','year','month','tavg_c','prcp_mm'} <= set(fields):
        raise ValueError('Weather schema missing required fields')
    result,contract=build(rows,cutoffyear)
    contract['input']=receipt
    out=Path(output)
    out.mkdir(parents=True,exist_ok=False)
    buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=list(result[0]),lineterminator='\n');w.writeheader();w.writerows(result)
    payload=buf.getvalue().encode('utf-8');(out/'weather_experiment.csv').write_bytes(payload)
    contract['outputs']={'weather_experiment.csv':hashlib.sha256(payload).hexdigest()}
    (out/'manifest.json').write_text(json.dumps(contract,indent=2,sort_keys=True)+'\n')
    return contract


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--panel',required=True);p.add_argument('--manifest',required=True)
    p.add_argument('--cutoff',type=int,required=True);p.add_argument('--output',required=True)
    a=p.parse_args();m=prepare(a.panel,a.manifest,a.cutoff,a.output)
    print(json.dumps({k:m[k] for k in ['version','mode','rows','training_rows','outputs']}))
