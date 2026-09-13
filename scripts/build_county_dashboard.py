#!/usr/bin/env python3
"""Build a standalone internal county dashboard from completed report archives."""
import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import tarfile

class Reports:
    def __init__(self,path):
        self.path=Path(path);self.archive=tarfile.open(str(path));self.sha256=hashlib.sha256(self.path.read_bytes()).hexdigest()
    def text(self,suffix):
        files=[m for m in self.archive.getmembers() if m.isfile() and (m.name==suffix or m.name.endswith('/'+suffix))]
        if len(files)!=1 or files[0].size>25000000:raise ValueError('Missing/ambiguous/oversized report: '+suffix)
        return self.archive.extractfile(files[0]).read().decode('utf-8-sig')
    def rows(self,suffix):return list(csv.DictReader(io.StringIO(self.text(suffix))))
    def close(self):self.archive.close()

def number(value):
    x=float(value)
    if not math.isfinite(x):raise ValueError('Nonfinite number')
    return x

def build_payload(audit,raw,sensitivity,geometry,forecast=None):
    if audit.text('reports/status.txt').splitlines()[0]!='INPUT_AUDIT_PASS':raise ValueError('Input audit did not pass')
    if raw.text('reports/status.txt').splitlines()[0]!='RAW_CLEAN_DEFAULT_HYPOTHESIS_MATCH':raise ValueError('Raw review did not pass')
    summary=raw.rows('reports/summary.csv')[0]
    if summary['panel_reconciled']!='TRUE' or int(summary['unexplained_cells'])!=0:raise ValueError('Raw/clean review is unresolved')
    checks=raw.rows('reports/input_checksums.csv')
    panel_hash=next(r['md5'] for r in checks if r['file'].endswith('/county_panel_INTERNAL.rds'))
    clean_hash=next(r['md5'] for r in checks if r['file'].endswith('/clean_mmwr.csv'))
    if any(r['unchanged']!='TRUE' for r in checks):raise ValueError('Input changed during raw review')
    audit_checks=audit.rows('reports/input_checksums.csv')
    if not any(r['file'].endswith('/clean_mmwr.csv') and r['md5']==clean_hash for r in audit_checks):raise ValueError('Archives use different clean data')
    nodes=audit.rows('reports/graph_nodes.csv');county={r['fips']:dict(fips=r['fips'],state=r['state'],name=r['county'],rows=[]) for r in nodes}
    if len(county)!=486 or len(county)!=len(nodes):raise ValueError('Unexpected county footprint')
    if {r['id'] for r in geometry['counties']}!=set(county):raise ValueError('Map differs from audited footprint')
    population={}
    for r in audit.rows('reports/population_audit.csv'):
        key=(r['fips'],int(r['year']))
        if key in population or r['population_status']!='ok' or r['state']!=county[r['fips']]['state']:raise ValueError('Invalid population keys')
        population[key]=number(r['population'])
        if population[key]<=0:raise ValueError('Nonpositive population')
    expected={(f,y) for f in county for y in range(2004,2020)}
    if set(population)!=expected:raise ValueError('Incomplete population grid')
    counts=defaultdict(int)
    for r in raw.rows('reports/all_raw_vs_clean_INTERNAL.csv'):
        key=(r['fips'],int(r['year']))
        if key not in expected or r['state']!=county[r['fips']]['state']:raise ValueError('Case outside footprint')
        n=int(r['clean_records'])
        if n<0 or int(r['raw_records'])!=n or int(r['difference'])!=0:raise ValueError('Raw and clean counts differ')
        counts[key]+=n
    if sum(counts.values())!=122024 or int(summary['clean_records'])!=122024:raise ValueError('Unexpected pilot count total')
    totals=defaultdict(int)
    for (f,y),n in counts.items():totals[county[f]['state'],y]+=n
    rec=audit.rows('reports/state_year_reconciliation.csv')
    if {(r['state'],int(r['year'])) for r in rec}!={(s,y) for s in {c['state'] for c in county.values()} for y in range(2004,2020)}:raise ValueError('Incomplete state reconciliation')
    for r in rec:
        if totals[r['state'],int(r['year'])]!=int(r['selected_cases']) or r['selected_cases']!=r['direct_matched_cases']:raise ValueError('State totals differ from audit')
    fits={}
    for model in ('spatial_county_time','iid_county_time'):
        prefix=model+'/reports/'
        if sensitivity.text(prefix+'status.txt').splitlines()[0]!='SENSITIVITY_FIT_COMPLETE' or sensitivity.text(prefix+'exit_status.txt').strip()!='0':raise ValueError('Model did not complete')
        if sensitivity.rows(prefix+'panel_checksum.csv')[0]['md5']!=panel_hash:raise ValueError('Fit and data panel differ')
        spec=sensitivity.rows(prefix+'specification.csv')[0]
        if spec['name']!=model or spec['county_time']!='TRUE' or number(spec['county_sd_upper'])!=1:raise ValueError('Unexpected model specification')
        diag=sensitivity.rows(prefix+'model_diagnostics.csv')[0]
        if int(diag['cells'])!=7776 or int(diag['cpo_failures']) or int(diag['cpo_nonpositive_or_nonfinite']):raise ValueError('Unresolved model diagnostics')
        fits[model]={}
        for r in sensitivity.rows(prefix+'county_fitted_INTERNAL.csv'):
            key=(r['fips'],int(r['year']))
            if key in fits[model] or key not in expected or r['state']!=county[r['fips']]['state']:raise ValueError('Invalid fitted keys')
            vals=[number(r[k]) for k in ('rate_mean','rate_0.5quant','rate_0.025quant','rate_0.975quant')]
            if not 0<=vals[2]<=vals[1]<=vals[3] or vals[0]<0:raise ValueError('Invalid credible interval')
            if abs(number(r['expected_count_mean'])-vals[0]*population[key]/1e5)>1e-6:raise ValueError('Fitted count/rate scale mismatch')
            fits[model][key]=vals
        if set(fits[model])!=expected:raise ValueError('Missing fitted county/year')
    for f,y in sorted(expected):
        mean,median,lower,upper=fits['spatial_county_time'][f,y]
        county[f]['rows'].append(dict(year=y,population=population[f,y],count=counts[f,y],mean=round(mean,6),median=round(median,6),
            lower=round(lower,6),upper=round(upper,6),iidMedian=round(fits['iid_county_time'][f,y][1],6)))
    zero_rows=sensitivity.rows('spatial_county_time/reports/zero_checks_INTERNAL.csv')
    zero=next(r for r in zero_rows if r['grouping']=='overall')
    zero_check=dict(observed=number(zero['observed_zeros']),expected=number(zero['expected_zeros_mean']),lower=number(zero['replicated_lower']),upper=number(zero['replicated_upper']))
    forecast_summary=None
    if forecast:
        if not json.loads(forecast.text('summary.json'))['complete']:raise ValueError('Forecast incomplete')
        if forecast.rows('spatial_county_time/reports/panel_checksum.csv')[0]['md5']!=panel_hash:raise ValueError('Forecast panel differs')
        overview=forecast.rows('forecast_overview.csv');forecast_summary={r['model']:r for r in overview}
    return dict(counties=sorted(county.values(),key=lambda c:(c['state'],c['name'])),geometry=geometry,
      scope=dict(pathogen='Salmonella',start=2004,end=2019,model='Spatial borrowing + county-specific time trends',counties=486,states=10),
      zeroCheck=zero_check,forecast=forecast_summary,provenance=dict(created=datetime.now(timezone.utc).isoformat(),panel_md5=panel_hash,
        archives=[dict(name=r.path.name,sha256=r.sha256) for r in (audit,raw,sensitivity,forecast) if r],
        model='spatial_county_time',map_vintage=2019,graph_vintage=2010))

def render(payload,template):
    # Escape HTML delimiters in the JSON block; all rendered labels use textContent.
    text=json.dumps(payload,separators=(',',':'),allow_nan=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
    if template.count('__COUNTY_DATA__')!=1:raise ValueError('Invalid dashboard template')
    return template.replace('__COUNTY_DATA__',text)

def main():
    root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser(description=__doc__)
    for name in ('audit','raw-review','sensitivity'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--forecast',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.output.exists():p.error('Refusing to overwrite existing dashboard')
    reports=[Reports(a.audit),Reports(a.raw_review),Reports(a.sensitivity)];f=Reports(a.forecast) if a.forecast else None
    try:
        payload=build_payload(*reports,json.loads((root/'dashboard/county_boundaries.json').read_text()),forecast=f)
        html=render(payload,(root/'dashboard/county_template.html').read_text())
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(html)
        print('Dashboard: '+str(a.output.resolve()));print('Offline HTML; internal exploratory use. No fits or source data changed.')
    finally:
        for r in reports+[f]:
            if r:r.close()
if __name__=='__main__':main()
