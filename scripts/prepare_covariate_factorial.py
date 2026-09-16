#!/usr/bin/env python3
"""Public, outcome-free age and fixed-window weather features for paired experiments."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from join_county_covariates import read_bound, key
from prepare_weather_experiment import build


def transform(weather, ages, cutoff, window, counties=486):
    if window not in ('current', 'lag01'):
        raise ValueError('Unknown prespecified weather window')
    indexed = {}
    for row in weather:
        k = key(row)
        if k in indexed: raise ValueError('Duplicate weather key')
        t, p = float(row['tavg_c']), float(row['prcp_mm'])
        if not math.isfinite(t) or not math.isfinite(p) or p < 0:
            raise ValueError('Invalid weather')
        indexed[k] = (t, math.log1p(p))
    derived = []
    for k, values in sorted(indexed.items()):
        f, y, m = k
        if not 2004 <= y <= cutoff + 3: continue
        if window == 'lag01':
            previous = (f, y if m > 1 else y - 1, m - 1 if m > 1 else 12)
            if previous not in indexed: raise ValueError('Missing actual previous-month weather')
            values = tuple((a+b)/2 for a,b in zip(values,indexed[previous]))
        derived.append(dict(fips=f, year=str(y), month=str(m), tavg_c=values[0], prcp_mm=math.expm1(values[1])))
    result, contract = build(derived, cutoff, counties)
    lookup = {}
    for row in ages:
        k = key(row, monthly=False)
        if k in lookup: raise ValueError('Duplicate age key')
        v = tuple(float(row[c]) for c in ('under5_share','age65plus_share'))
        if any(not math.isfinite(x) or not 0 <= x <= 1 for x in v) or sum(v) > 1:
            raise ValueError('Invalid disjoint population age shares')
        lookup[k] = v
    if any((r['fips'],r['year']) not in lookup for r in result):
        raise ValueError('Missing age coverage')
    training = [lookup[r['fips'],r['year']] for r in result if r['year'] <= cutoff]
    centers = [math.fsum(v[j] for v in training)/len(training) for j in (0,1)]
    scales = [math.sqrt(math.fsum((v[j]-centers[j])**2 for v in training)/len(training)) for j in (0,1)]
    if any(not math.isfinite(x) or x <= 0 for x in scales): raise ValueError('Constant/nonfinite age scale')
    for row in result:
        for j, name in enumerate(('age_under5_z','age65plus_z')):
            row[name] = (lookup[row['fips'],row['year']][j]-centers[j])/scales[j]
            if not math.isfinite(row[name]):raise ValueError('Nonfinite standardized age')
    contract.update(version='covariate_factorial_transform_v1',weather_window=window,
        lags_months=[0] if window=='current' else [0,1],
        lag_weights=[1] if window=='current' else [.5,.5],
        lag_operation='average temperature and log1p precipitation before training-only centering/scaling',
        age_covariates_used=True,age_features=['age_under5_z','age65plus_z'],
        all_feature_order=['weather_tavg_z','weather_logprcp_z','age_under5_z','age65plus_z'],
        age_centers=centers,age_scales=scales,age_scaling='pooled training county-month population SD',
        age_interpretation='ecological population composition, not individual age effects',
        conditional_inputs=['realized weather','retrospective population age shares'])
    return result, contract


def prepare(weather, weather_manifest, age, age_manifest, cutoff, window, output):
    _,wr,wm = read_bound(weather,weather_manifest)
    _,ar,am = read_bound(age,age_manifest)
    if wm['source_manifest'].get('version') != 'county_weather_v1' or am['source_manifest'].get('schema_version') != 'county_age_covariates_v1':
        raise ValueError('Native prepared sources required')
    rows, contract = transform(wr,ar,cutoff,window)
    contract['inputs'] = dict(weather=wm,age=am)
    dest=Path(output);dest.mkdir(parents=True,exist_ok=False)
    buffer=io.StringIO(newline='');writer=csv.DictWriter(buffer,fieldnames=list(rows[0]),lineterminator='\n')
    writer.writeheader();writer.writerows(rows);payload=buffer.getvalue().encode()
    (dest/'weather_experiment.csv').write_bytes(payload)
    contract['outputs']={'weather_experiment.csv':hashlib.sha256(payload).hexdigest()}
    (dest/'manifest.json').write_text(json.dumps(contract,indent=2)+'\n')
    return contract


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('weather','weather-manifest','age','age-manifest','output'):p.add_argument('--'+flag,required=True)
    a=p.parse_args()
    for cutoff in (2011,2013,2016):
        for window in ('current','lag01'):
            m=prepare(a.weather,a.weather_manifest,a.age,a.age_manifest,cutoff,window,Path(a.output)/window/str(cutoff))
            print(window,cutoff,m['rows'],flush=True)
