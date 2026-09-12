#!/usr/bin/env python3
"""Validate Vintage 2025 town totals on Connecticut's historical county geography.

Inputs are the Census sub-est2025_9.csv and CT DPH 2023/2024 town ASRH CSVs.
Writes candidate denominators only; never modifies pipeline inputs or fits.
"""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

COUNTIES = {'001': 'Fairfield', '003': 'Hartford', '005': 'Litchfield',
            '007': 'Middlesex', '009': 'New Haven', '011': 'New London',
            '013': 'Tolland', '015': 'Windham'}
YEARS = range(2020, 2026)


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def crosswalk(rows):
    result = {}
    for row in rows:
        town = row['COUSUB'].zfill(5)
        county = row['v21_county'].zfill(3)
        if (row['STATE'].zfill(2) != '09' or county not in COUNTIES or
                row['CTYNAME'] != COUNTIES[county] + ' County' or
                row['v21_cousub'].zfill(5) != town):
            raise ValueError('Unrecognized or changed historical geography')
        value = (row['NAME'], county, row['COUNTY'].zfill(3))
        if town in result and result[town] != value:
            raise ValueError('Conflicting town mapping: ' + town)
        result[town] = value
    if len(result) != 169 or {v[1] for v in result.values()} != set(COUNTIES):
        raise ValueError('Expected 169 towns covering eight historical counties')
    return result


def reconcile(census, dph2023, dph2024):
    mapping = crosswalk(dph2023)
    if mapping != crosswalk(dph2024):
        raise ValueError('DPH crosswalk changed between 2023 and 2024')
    states = [r for r in census if r['SUMLEV'] == '040']
    if len(states) != 1 or states[0]['STATE'] != '09':
        raise ValueError('Expected exactly one Connecticut state total')
    towns = [r for r in census if r['SUMLEV'] == '061']
    seen = set()
    totals = defaultdict(int)
    for row in towns:
        town = row['COUSUB']
        if town in seen or town not in mapping or row['STATE'] != '09':
            raise ValueError('Duplicate, unknown, or out-of-state town')
        seen.add(town)
        name, county, region = mapping[town]
        if row['NAME'] != name or row['COUNTY'] != region:
            raise ValueError('Census/DPH town geography mismatch: ' + town)
        for year in YEARS:
            population = int(row['POPESTIMATE' + str(year)])
            if population <= 0:
                raise ValueError('Town population must be positive')
            totals[(year, county)] += population
    if seen != set(mapping):
        raise ValueError('Missing towns in Census file')
    for year in YEARS:
        if sum(totals[(year, c)] for c in COUNTIES) != int(states[0]['POPESTIMATE' + str(year)]):
            raise ValueError('County sum differs from Census state total: ' + str(year))
    candidates = [dict(year=y, fips='09'+c, county=COUNTIES[c], population=totals[(y, c)],
                       vintage=2025, geography='historical county via town crosswalk',
                       coverage_verified='FALSE', approved_for_use='FALSE')
                  for y in YEARS for c in sorted(COUNTIES)]
    return candidates, mapping


def write_csv(path, rows):
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('census_csv')
    parser.add_argument('dph_2023_csv')
    parser.add_argument('dph_2024_csv')
    parser.add_argument('output')
    args = parser.parse_args()
    sources = [args.census_csv, args.dph_2023_csv, args.dph_2024_csv]
    rows, mapping = reconcile(*(read_csv(p) for p in sources))
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    write_csv(out/'ct_historical_counties_v2025_candidates.csv', rows)
    write_csv(out/'town_crosswalk.csv', [dict(town_code=t, town_name=v[0], historical_fips='09'+v[1],
                                             planning_region_fips='09'+v[2]) for t, v in sorted(mapping.items())])
    (out/'provenance.json').write_text(json.dumps(dict(
        vintage=2025, verified_towns=169, historical_counties=8, county_years=48,
        state_totals_match=True, coverage_verified=False, approved_for_use=False,
        sources={str(Path(p).resolve()): hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sources}), indent=2)+'\n')
    print('Validated 169 towns, eight historical counties, 48 county-years; all six state totals match.')
    print('Candidates only: surveillance coverage and adoption remain unresolved. Output: '+str(out))


if __name__ == '__main__':
    main()
