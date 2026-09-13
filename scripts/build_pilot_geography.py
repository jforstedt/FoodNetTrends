#!/usr/bin/env python3
"""Build public candidate pilot geography from the official 2010 adjacency file."""
import csv, hashlib, io, json, sys, zipfile
from pathlib import Path
FULL = {'CT':8,'GA':159,'MD':24,'MN':87,'NM':33,'OR':36,'TN':95}
PART = {'CA': {'Alameda','Contra Costa','San Francisco'},
        'CO': {'Adams','Arapahoe','Boulder','Broomfield','Denver','Douglas','Jefferson'},
        'NY': set()}
PART['NY'] = set('Albany Allegany Cattaraugus Chautauqua Chemung Clinton Columbia Delaware Erie Essex Franklin Fulton Genesee Greene Hamilton Livingston Monroe Montgomery Niagara Ontario Orleans Otsego Rensselaer Saratoga Schenectady Schoharie Schuyler Seneca Steuben Warren Washington Wayne Wyoming Yates'.split())

def build(source, gazetteer, output):
    names = {}; edges = set(); current = None; labels = []
    with Path(source).open(encoding='latin-1', newline='') as h:
        for r in csv.reader(h, delimiter='\t'):
            if len(r) != 4: raise ValueError('Unexpected adjacency layout')
            if r[1]:
                current = r[1]
                if r[0]: names[current] = r[0]
            if not current or len(r[3]) != 5: raise ValueError('Invalid county key')
            labels.append((current,r[3],r[2]))
            edges.add((current, r[3]))
    # One source county header (27165) lacks its name. Recover only when all
    # neighboring references agree; preserve conflicting neighbor labels below.
    for code in {a for a,b in edges} - set(names):
        candidates={n for a,b,n in labels if b==code}
        if len(candidates)!=1: raise ValueError('Ambiguous missing county name')
        names[code]=candidates.pop()
    if any(a not in names or b not in names or (b,a) not in edges for a,b in edges):
        raise ValueError('Unknown graph node or asymmetric source adjacency')
    headers = dict(names)
    with zipfile.ZipFile(gazetteer) as z:
        gaz=list(csv.DictReader(io.StringIO(z.read('2019_Gaz_counties_national.txt').decode('utf-8-sig')),delimiter='\t'))
    official={r['GEOID']:r['NAME']+', '+r['USPS'] for r in gaz}
    if len(official)!=len(gaz): raise ValueError('Duplicate gazetteer county')
    names.update(official)
    selected = []
    for fips, name in sorted(names.items()):
        if ', ' not in name: continue  # Island-area names outside the pilot
        county, state = name.rsplit(', ',1)
        short = county.removesuffix(' County') if hasattr(county,'removesuffix') else county[:-7] if county.endswith(' County') else county
        if state in FULL or short in PART.get(state,set()):
            selected.append(dict(fips=fips,state=state,county=county,start_year=2004,end_year=2019))
    for state, count in dict(FULL,CA=3,CO=7,NY=34).items():
        if sum(x['state']==state for x in selected)!=count: raise ValueError('County footprint mismatch: '+state)
    ids={x['fips'] for x in selected}
    out=Path(output);out.mkdir(parents=True,exist_ok=False)
    def write(name,rows):
        with (out/name).open('w',newline='') as h:
            w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    write('counties.csv',selected)
    write('edges.csv',[dict(fips_a=a,fips_b=b) for a,b in sorted(edges) if a<b and a in ids and b in ids])
    issues=[dict(source_fips=a,neighbor_fips=b,neighbor_label=n,canonical_label=names[b])
            for a,b,n in labels if a in ids and b in ids and n!=names[b]]
    issues += [dict(source_fips=f,neighbor_fips=f,neighbor_label=n,canonical_label=names[f])
               for f,n in headers.items() if f in ids and n!=names[f]]
    if not ids.issubset(official) or not ids.issubset({a for a,b in edges}): raise ValueError('Pilot missing in source geography')
    if issues: write('source_label_issues.csv',issues)
    (out/'provenance.json').write_text(json.dumps(dict(
        adjacency_url='https://www2.census.gov/geo/docs/reference/county_adjacency/county_adjacency2010.txt',
        gazetteer_url='https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2019_Gazetteer/2019_Gaz_counties_national.zip',
        gazetteer_sha256=hashlib.sha256(Path(gazetteer).read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),
        coverage_source='https://www.cdc.gov/mmwr/volumes/73/wr/mm7326a1.htm',
        county_detail_source='https://stacks.cdc.gov/view/cdc/152214/cdc_152214_DS1.pdf',
        source_label_conflicts=len(issues),graph_vintage=2010,water_neighbors_included=True,cross_state_edges_included=True,
        status='candidate pilot geography; not a model validation'),indent=2)+'\n')
    print('Prepared',len(selected),'counties')
if __name__=='__main__':build(sys.argv[1],sys.argv[2],sys.argv[3])
