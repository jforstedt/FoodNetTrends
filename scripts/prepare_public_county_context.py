#!/usr/bin/env python3
"""Normalize acquired public context data; no case data or model fitting.

Historical edition availability is not certification of original-release bytes.
Outputs preserve the complete roster and never impute suppressed/absent values.
"""
import argparse
import collections
import csv
import datetime
import hashlib
import json
import math
from pathlib import Path

RELEASES = {
    ('ag', 2002): ('2004-12-31', 'conservative_publication_year_end'),
    ('ag', 2007): ('2009-12-31', 'conservative_publication_year_end'),
    ('water', 2000): ('2004-12-31', 'conservative_publication_year_end'),
    ('water', 2005): ('2009-10-27', 'report_first_posted'),
    ('water', 2010): ('2014-12-31', 'conservative_publication_year_end'),
    ('crowding', 2010): ('2011-12-08', 'release_date'),
    ('crowding', 2012): ('2013-12-17', 'release_date'),
    ('crowding', 2015): ('2016-12-08', 'release_date'),
}
AG = {
    'CATTLE, INCL CALVES - INVENTORY': ('cattle_inventory_head', 'HEAD'),
    'CHICKENS, BROILERS - SALES, MEASURED IN HEAD': ('broiler_sales_head', 'HEAD'),
    'AG LAND - TREATED, MEASURED IN ACRES': ('manure_treated_acres', 'ACRES'),
}
FIELDS = ['fips', 'variable', 'reference_year', 'period_start', 'edition_available_by',
          'availability_basis', 'status', 'value', 'raw_value', 'raw_denominator',
          'unit', 'source_load_time', 'source_file', 'moe_components_json']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path, delimiter=','):
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))


def numeric(token):
    token = str(token).strip()
    if token == '(D)':
        return 'suppressed', ''
    if not token:
        return 'missing', ''
    try:
        value = float(token.replace(',', ''))
    except ValueError:
        return 'non_numeric_source_token', ''
    if not math.isfinite(value) or value < 0:
        return 'invalid', ''
    return 'valid', value


def unique(rows, key):
    result = {}
    for row in rows:
        k = key(row)
        if k in result:
            raise ValueError('Duplicate source key: ' + str(k))
        result[k] = row
    return result


def base(fips, variable, family, year, unit, source):
    date, basis = RELEASES[family, year]
    return dict(dict.fromkeys(FIELDS, ''), fips=fips, variable=variable,
        reference_year=year, period_start=year, edition_available_by=date,
        availability_basis=basis, status='absent_record', unit=unit,
        source_file=source)


def agriculture(roster, rows, year, source, descriptions):
    indexed = unique(rows, lambda r: (r['STATE_ANSI'].zfill(2) + r['COUNTY_ANSI'].zfill(3), r['SHORT_DESC']))
    output = []
    for desc in descriptions:
        variable, unit = AG[desc]
        for fips in roster:
            out = base(fips, variable, 'ag', year, unit, source)
            row = indexed.get((fips, desc))
            if row:
                manure = variable == 'manure_treated_acres'
                expected = ('FERTILIZER', 'FERTILIZER: (MANURE)') if manure else ('TOTAL', 'NOT SPECIFIED')
                if (row['DOMAIN_DESC'], row['DOMAINCAT_DESC']) != expected or row['UNIT_DESC'] != unit or int(row['YEAR']) != year or row['AGG_LEVEL_DESC'] != 'COUNTY':
                    raise ValueError('Unexpected agriculture definition')
                out.update(raw_value=row['VALUE'], source_load_time=row['LOAD_TIME'])
                out['status'], out['value'] = numeric(row['VALUE'])
            output.append(out)
    return output


def water(roster, rows, year, source):
    indexed = unique([r for r in rows if r['FIPS'].strip().zfill(5) in roster], lambda r: r['FIPS'].strip().zfill(5))
    output = []
    for fips in roster:
        out = base(fips, 'domestic_self_supply_fraction', 'water', year, 'fraction; source populations in thousands', source)
        row = indexed.get(fips)
        if row:
            out.update(raw_value=row['DO-SSPop'], raw_denominator=row['TP-TotPop'])
            ns, n = numeric(row['DO-SSPop']); ds, d = numeric(row['TP-TotPop'])
            if ns == ds == 'valid' and d > 0 and n <= d:
                out.update(status='valid', value=n / d)
            elif ns in ('missing', 'non_numeric_source_token') or ds in ('missing', 'non_numeric_source_token'):
                out['status'] = 'missing_source_population'
            else:
                out['status'] = 'invalid_source_population'
        output.append(out)
    return output


def crowding(roster, rows, source):
    indexed = unique(rows, lambda r: (r['fips'], int(r['vintage'])))
    output = []
    for year in (2010, 2012, 2015):
        for fips in roster:
            out = base(fips, 'crowded_housing_share', 'crowding', year, 'fraction of occupied housing units', source)
            row = indexed.get((fips, year))
            if row:
                es = [numeric(row['B25014_%03dE' % i]) for i in range(1, 14)]
                ms = [numeric(row['B25014_%03dM' % i]) for i in range(1, 14)]
                if any(s != 'valid' for s, _ in es + ms):
                    raise ValueError('Invalid ACS estimate or MOE')
                e = [v for _, v in es]
                count = sum(e[i - 1] for i in (5, 6, 7, 11, 12, 13))
                if e[0] <= 0 or e[1] + e[7] != e[0] or sum(e[2:7]) != e[1] or sum(e[8:13]) != e[7] or not 0 <= count <= e[0]:
                    raise ValueError('ACS accounting failed')
                share = count / e[0]
                if not math.isclose(share, float(row['crowded_share']), abs_tol=1e-12):
                    raise ValueError('ACS supplied share mismatch')
                if int(row['period_start']) != year - 4:
                    raise ValueError('Unexpected ACS survey period')
                out.update(status='valid', value=share, raw_value=count, raw_denominator=e[0], period_start=year - 4,
                           moe_components_json=json.dumps({k: v for k, v in row.items() if k.startswith('B25014_')}, sort_keys=True))
            output.append(out)
    return output


def freeze(rows, origins):
    groups = collections.defaultdict(list)
    for row in rows:
        groups[row['fips'], row['variable']].append(row)
    output = []
    for origin in origins:
        if datetime.datetime.strptime(origin, '%Y-%m-%d').strftime('%Y-%m-%d') != origin:
            raise ValueError('Origin must use zero-padded ISO date')
        for key in sorted(groups):
            available = [r for r in groups[key] if r['edition_available_by'] <= origin]
            if not available:
                continue
            # Select edition globally, never fall back to older valid values county by county.
            selected = max(available, key=lambda r: int(r['reference_year']))
            output.append(dict(selected, origin_date=origin))
    return output


def write(path, rows, fields):
    with Path(path).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def prepare(roster_path, ag_dir, crowd_dir, dest, origins):
    roster = unique(read(roster_path), lambda r: r['fips'])
    if any(len(f) != 5 or not f.isdigit() for f in roster):
        raise ValueError('Invalid roster FIPS')
    sources = [Path(roster_path)]
    rows = []
    for year in (2002, 2007):
        for prefix, descriptions in [('ag', list(AG)[:2]), ('manure', list(AG)[2:])]:
            p = ag_dir / ('%s%d_selected.csv' % (prefix, year)); sources.append(p)
            rows += agriculture(roster, read(p), year, p.name, descriptions)
    receipt = json.loads((ag_dir / 'receipt.json').read_text())
    sources.append(ag_dir / 'receipt.json')
    for year in (2000, 2005, 2010):
        p = ag_dir / ('usco%d.txt' % year); sources.append(p)
        if sha(p) != receipt['water%d' % year]['sha256']:
            raise ValueError('Water source receipt mismatch')
        rows += water(roster, read(p, '\t'), year, p.name)
    p = crowd_dir / 'county_crowding_estimates.csv'; sources.append(p)
    manifest = json.loads((crowd_dir / 'manifest.json').read_text()); sources.append(crowd_dir / 'manifest.json')
    if sha(p) != manifest['derived_outputs'][p.name]:
        raise ValueError('Crowding source receipt mismatch')
    rows += crowding(roster, read(p), p.name)
    frozen = freeze(rows, origins)
    dest.mkdir(parents=True, exist_ok=False)
    write(dest / 'public_context_editions.csv', rows, FIELDS)
    write(dest / 'origin_frozen_context.csv', frozen, ['origin_date'] + FIELDS)
    summary = collections.Counter((r['variable'], r['reference_year'], r['status']) for r in rows)
    report = dict(status='PUBLIC_CONTEXT_PREPARATION_COMPLETE', county_count=len(roster), edition_rows=len(rows), origin_rows=len(frozen),
        models_fitted=False, forecast_ready=False, exact_historical_bytes_verified=False,
        implementation_sha256=sha(__file__),
        counts=[dict(variable=v, reference_year=y, status=s, rows=n) for (v,y,s),n in sorted(summary.items())],
        sources={str(p): sha(p) for p in sources}, outputs={p.name:sha(p) for p in dest.glob('*.csv')},
        limitations=['Current archived bytes, not certified original vintages.', 'Origin-frozen static context is not historical monthly exposure.',
                      'No suppression imputation, clipping, interpolation, county dropping or density conversion.',
                      'ACS component estimates and MOEs retained; derived share uncertainty not calculated.',
                      'Agriculture selected extracts hashed here; selection is not independently replayed from bulk exports.',
                      'Publication-year end is a conservative availability bound where an exact date is not established.',
                      'Origin tables are inventories: model transformations, matched support and uncertainty policy remain to be specified.'])
    (dest / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--roster', type=Path, default=Path('analysis_configs/county_pilot/counties.csv'))
    parser.add_argument('--ag-water-dir', type=Path, default=Path('output/historical_livestock_water_20260915_LOCAL'))
    parser.add_argument('--crowding-dir', type=Path, default=Path('output/historical_crowding_20260915_LOCAL'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--origins', nargs='+', default=['2011-12-31', '2013-12-31', '2016-12-31'])
    a = parser.parse_args()
    result = prepare(a.roster, a.ag_water_dir, a.crowding_dir, a.out, a.origins)
    print(json.dumps({k: result[k] for k in ('status','county_count','edition_rows','origin_rows','models_fitted','forecast_ready')}, indent=2))

if __name__ == '__main__':
    main()
