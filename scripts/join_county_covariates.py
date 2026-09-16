#!/usr/bin/env python3
"""Strict retrospective covariate assembly; does not fit a model."""
import argparse
import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path

FEATURES = ('tavg_c', 'prcp_mm', 'under5_share', 'age65plus_share')
ADDED = FEATURES + tuple(x + '_z' for x in FEATURES)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_csv_bytes(data, label):
    reader = csv.DictReader(io.StringIO(data.decode('utf-8-sig'), newline=''))
    fields = reader.fieldnames
    if not fields or len(set(fields)) != len(fields):
        raise ValueError(label + ': missing or duplicate header')
    rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError(label + ': malformed CSV row')
    return fields, rows


def unique_json(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError('Duplicate manifest JSON key: ' + k)
        result[k] = v
    return result


def read_bound(path, manifest):
    """Read a snapshot using native source-adapter manifests, without wrappers."""
    path, manifest = Path(path), Path(manifest)
    mb = manifest.read_bytes()
    meta = json.loads(mb, object_pairs_hook=unique_json)
    if meta.get('version') == 'county_weather_v1':
        if meta.get('mode') != 'historical_conditional' or meta.get('forecast_asof_validated') is not False:
            raise ValueError('Unsupported weather availability contract')
        if meta.get('units') != dict(tavg_c='degrees_C_daily_mean', prcp_mm='mm_monthly_sum'):
            raise ValueError('Unsupported weather units')
        sources = meta.get('sources', {})
        if not sources or not all(isinstance(v, dict) and valid_hash(v.get('sha256')) and str(v.get('url', '')).startswith('https://') for v in sources.values()):
            raise ValueError('Weather source bindings missing or invalid')
        digest = meta.get('outputs', {}).get(path.name)
    elif meta.get('schema_version') == 'county_age_covariates_v1':
        if (meta.get('retrospective_vintages') is not True or meta.get('forecast_asof_validated') is not False
                or meta.get('population_offset_replaced') is not False or meta.get('case_data_used') is not False):
            raise ValueError('Unsupported age availability/target contract')
        if path.name != 'county_age_shares.csv':
            raise ValueError('Unexpected age payload name')
        sources = meta.get('inputs', {})
        if not sources or not all(valid_hash(v) for v in sources.values()) or not meta.get('source_urls') or not all(str(u).startswith('https://') for u in meta['source_urls']):
            raise ValueError('Age source bindings missing or invalid')
        digest = meta.get('output_sha256')
    elif meta.get('schema') == 'county_covariate_source_v1':
        if not isinstance(meta.get('source_url'), str) or not meta['source_url'].startswith('https://'):
            raise ValueError('Manifest requires HTTPS source_url')
        if not isinstance(meta.get('retrieved_at'), str) or not meta['retrieved_at'].strip():
            raise ValueError('Manifest requires retrieved_at')
        digest = meta.get('files', {}).get(path.name)
    else:
        raise ValueError('Unsupported source manifest schema')
    data = path.read_bytes()
    if not valid_hash(digest) or digest != sha(data):
        raise ValueError('Source payload SHA256 mismatch: ' + path.name)
    fields, rows = read_csv_bytes(data, path.name)
    return fields, rows, {'payload_sha256': sha(data), 'manifest_sha256': sha(mb),
                         'source_manifest': meta, 'upstream_raw_hashes_rechecked_here': False}


def valid_hash(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def key(row, monthly=True):
    fips = row.get('fips', '')
    if not re.fullmatch(r'[0-9]{5}', fips):
        raise ValueError('FIPS must be exactly five digits')
    year = row.get('year', '')
    if not re.fullmatch(r'[0-9]{4}', year) or not 1900 <= int(year) <= 2200:
        raise ValueError('Invalid year')
    if not monthly:
        return fips, int(year)
    month = row.get('month', '')
    if not re.fullmatch(r'[0-9]{1,2}', month) or not 1 <= int(month) <= 12:
        raise ValueError('Invalid month')
    return fips, int(year), int(month)


def index(rows, monthly):
    result = {}
    for row in rows:
        k = key(row, monthly)
        if k in result:
            raise ValueError('Duplicate covariate key: ' + str(k))
        result[k] = row
    return result


def values(weather, ages):
    try:
        v = {f: float((weather if f in FEATURES[:2] else ages)[f]) for f in FEATURES}
    except (ValueError, KeyError):
        raise ValueError('Missing or invalid covariate')
    if not all(math.isfinite(x) for x in v.values()):
        raise ValueError('Nonfinite covariate')
    if v['prcp_mm'] < 0 or not 0 <= v['under5_share'] <= 1 or not 0 <= v['age65plus_share'] <= 1:
        raise ValueError('Covariate outside physical/share domain')
    if v['under5_share'] + v['age65plus_share'] > 1 + 1e-12:
        raise ValueError('Disjoint age shares exceed one')
    return v


def assemble(reference, weather, ages, weather_manifest, ages_manifest, cutoff, mode):
    if mode != 'historical_conditional':
        raise ValueError('Only historical_conditional is supported; operational forecasts require verified release/vintage and future-covariate contracts')
    if not re.fullmatch(r'[0-9]{4}-[0-9]{2}', cutoff):
        raise ValueError('Training cutoff must be YYYY-MM')
    cy, cm = map(int, cutoff.split('-'))
    key({'fips': '00001', 'year': str(cy), 'month': str(cm)})
    reference_data = Path(reference).read_bytes()
    fields, rows = read_csv_bytes(reference_data, 'reference')
    if not rows:
        raise ValueError('Empty reference domain')
    if set(fields) & set(ADDED):
        raise ValueError('Reference column conflicts with added covariates')
    wf, wr, wp = read_bound(weather, weather_manifest)
    af, ar, ap = read_bound(ages, ages_manifest)
    if not set(('fips', 'year', 'month') + FEATURES[:2]) <= set(wf):
        raise ValueError('Weather schema missing required columns')
    if not set(('fips', 'year') + FEATURES[2:]) <= set(af):
        raise ValueError('Age schema missing required columns')
    wi, ai = index(wr, True), index(ar, False)
    seen, vals, train = set(), [], []
    for row in rows:
        k = key(row)
        if k in seen:
            raise ValueError('Duplicate reference county-month; assemble each unique exposure domain separately')
        seen.add(k)
        if k not in wi or k[:2] not in ai:
            raise ValueError('Missing covariate support: ' + str(k))
        v = values(wi[k], ai[k[:2]])
        vals.append(v)
        if k[1:] <= (cy, cm):
            train.append(v)
    if len(train) < 2:
        raise ValueError('At least two training rows required')
    stats = {}
    for f in FEATURES:
        mean = math.fsum(v[f] for v in train) / len(train)
        sd = math.sqrt(math.fsum((v[f] - mean) ** 2 for v in train) / len(train))
        if not math.isfinite(sd) or sd == 0:
            raise ValueError('Constant or invalid training covariate: ' + f)
        stats[f] = {'mean': mean, 'sd_population': sd}
    out = []
    for row, v in zip(rows, vals):
        joined = dict(row)
        joined.update(v)
        joined.update({f + '_z': (v[f] - stats[f]['mean']) / stats[f]['sd_population'] for f in FEATURES})
        if not all(math.isfinite(joined[f + '_z']) for f in FEATURES):
            raise ValueError('Nonfinite standardized covariate')
        out.append(joined)
    meta = {'schema': 'county_covariate_join_v1', 'analysis_mode': mode,
            'operational_forecast_ready': False, 'scientific_acceptance': False,
            'target_values_used_for_transform': False, 'reference_sha256': sha(reference_data),
            'weather': wp, 'ages': ap, 'training_cutoff': cutoff,
            'reference_rows': len(rows), 'training_rows': len(train),
            'standardization': stats, 'standardization_weighting': 'equal reference county-month rows',
            'original_columns': fields, 'added_columns': list(ADDED)}
    return fields + list(ADDED), out, meta


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'weather', 'ages', 'weather-manifest', 'ages-manifest', 'training-cutoff', 'mode', 'output'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    fields, rows, meta = assemble(a.reference, a.weather, a.ages, a.weather_manifest,
                                  a.ages_manifest, a.training_cutoff, a.mode)
    dest = Path(a.output)
    dest.mkdir(parents=True, exist_ok=False)
    data = io.StringIO(newline='')
    w = csv.DictWriter(data, fieldnames=fields, lineterminator='\n')
    w.writeheader(); w.writerows(rows)
    payload = data.getvalue().encode('utf-8')
    (dest / 'joined_covariates.csv').write_bytes(payload)
    meta['joined_sha256'] = sha(payload)
    (dest / 'contract.json').write_text(json.dumps(meta, indent=2, sort_keys=True) + '\n')
    print('Historical conditional covariates assembled: ' + str(dest))


if __name__ == '__main__':
    main()
