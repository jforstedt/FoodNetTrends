#!/usr/bin/env python3
"""Build review artifacts from the aggregate county preparation archive, without HPC access."""
import argparse,csv,io,json,re,tarfile
from collections import defaultdict,Counter
from pathlib import Path

def key_name(x):return re.sub('[^A-Z0-9]','',x.strip().upper())
def build(records):
    history=defaultdict(set);recent=defaultdict(list)
    for r in records:
        k=(r['state'],key_name(r['county']))
        if r['match_status']=='direct_fips_candidate':history[k].add(r['candidate_fips'])
        if r['match_status']=='name_candidate_requires_review':recent[k].append(r)
    crosswalk=[]
    for k,rs in sorted(recent.items()):
        codes={r['candidate_fips'] for r in rs}
        supported=len(codes)==1 and history[k]==codes
        crosswalk.append(dict(state=k[0],county_key=k[1],county_labels='|'.join(sorted({r['county'] for r in rs})),
            candidate_fips='|'.join(sorted(codes)),candidate_years='|'.join(sorted({r['year'] for r in rs})),
            population_classes='|'.join(sorted({r['population_class'] for r in rs})),
            historical_direct_fips='|'.join(sorted(history[k])),
            evidence_status='historically_supported_unique_mapping' if supported else 'needs_identifier_review',
            coverage_status='not_verified',approved_for_model='FALSE'))
    exceptions=[]
    for r in records:
        if r['match_status'] in ('direct_fips_candidate','name_candidate_requires_review'):continue
        if r['population_class']=='parasitic' and r['year']=='2025':reason='parasite_population_year_unavailable'
        elif r.get('siteid')=='COEX':reason='expansion_outside_historical_analysis_scope'
        elif r['state']=='CT' and r['match_status']=='missing_or_nonpositive_population':reason='historical_county_population_needed'
        elif r['state']=='CA' and r['population_class']=='parasitic' and r['match_status']=='no_fips_year_population_row':reason='early_california_parasite_coverage_review'
        else:reason='unresolved_case_geography'
        exceptions.append(dict(r,review_reason=reason,action_applied='none'))
    return crosswalk,exceptions

def write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive');p.add_argument('output');a=p.parse_args()
    dest=Path(a.output);dest.mkdir(parents=True,exist_ok=False)
    with tarfile.open(a.archive) as t:
        with t.extractfile('reports/geographic_candidates_INTERNAL.csv') as h:
            rows=list(csv.DictReader(io.TextIOWrapper(h)))
    crosswalk,exceptions=build(rows)
    write_csv(dest/'candidate_crosswalk.csv',crosswalk)
    write_csv(dest/'exceptions_INTERNAL.csv',exceptions)
    summary={'source_archive':str(Path(a.archive).resolve()),'geographic_tuples':len(rows),
             'candidate_crosswalk_entries':len(crosswalk),'crosswalk_evidence':dict(Counter(r['evidence_status'] for r in crosswalk)),
             'exception_tuples':dict(Counter(r['review_reason'] for r in exceptions)),
             'note':'Tuple counts are not case counts. No mappings, exclusions or model eligibility applied.'}
    (dest/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
