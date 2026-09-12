#!/usr/bin/env python3
"""Extract candidate historical-county totals from downloaded CT DPH packages.
Requires py7zr locally. Outputs are explicitly not approved replacement denominators.
"""
import argparse,csv,hashlib,io,json,math,tempfile,zipfile
from collections import defaultdict
from pathlib import Path
import py7zr

FIPS={'Fairfield':'09001','Hartford':'09003','Litchfield':'09005','Middlesex':'09007',
      'New Haven':'09009','New London':'09011','Tolland':'09013','Windham':'09015'}

def county_code(name):
    return FIPS[name.replace(' County','').strip()]

def aggregate(rows,year,dimensions,name_col,pop_col,source,vintage):
    seen=set();totals=defaultdict(float);cells=defaultdict(set)
    for r in rows:
        code=county_code(r[name_col]);k=(code,)+tuple(r[c] for c in dimensions)
        if k in seen:raise ValueError('Duplicate demographic cell: '+str(k))
        seen.add(k);v=float(r[pop_col])
        if not math.isfinite(v) or v<0:raise ValueError('Invalid population')
        totals[code]+=v;cells[code].add(k[1:])
    if set(totals)!=set(FIPS.values()):raise ValueError('Expected eight historical counties')
    return [dict(year=year,fips=k,population=int(v) if v.is_integer() else v,
                 source_file=source,vintage=vintage,approved_for_use='FALSE') for k,v in sorted(totals.items())]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('historical_7z');p.add_argument('county_zip');p.add_argument('output');a=p.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False);result=[]
    with zipfile.ZipFile(a.county_zip) as z:
        rows=list(csv.DictReader(io.StringIO(z.read('a1sr6h_ctycepr_pcen2024.csv').decode('utf-8-sig'))))
        for year in (2020,2021):
            r=[x for x in rows if x['YEAR']==str(year)]
            assert len(r)==8*86*2*6*2
            assert {x['VINTAGE'] for x in r}=={'v2021'}
            result+=aggregate(r,year,['AGE','SEX','RACE6','HISP2'],'COUNTY_LABEL','POP','a1sr6h_ctycepr_pcen2024.csv','v2021')
    with tempfile.TemporaryDirectory() as d:
        with py7zr.SevenZipFile(a.historical_7z) as z:
            # Read only the documented CSVs, never execute package contents.
            names=['CTDPH_2022_CountyASRH.csv','CTDPH_2023_CountyASRH.csv','CTDPH_2024_CountyASRH.csv','v25_county.csv']
            z.extract(path=d,targets=names)
        for year,name in zip(range(2022,2026),names):
            with (Path(d)/name).open(encoding='utf-8-sig',newline='') as h:r=list(csv.DictReader(h))
            if year==2022:
                assert len(r)==8*18*2*7
                assert {x['YEAR'] for x in r}=={'2022'}
                dims=['AGEGP18','SEX','RACE6ETH'];pop='POP';vintage='v2022'
            else:
                assert {(x['eth'],x['race']) for x in r}=={('hisp','all')}|{('nh',s) for s in ['aa','aiana','ba','nhpia','twop','wa']}
                assert len(r)==(169 if year<2025 else 8)*18*2*7
                assert all('09'+x['v21_county'].zfill(3)==county_code(x['CTYNAME']) for x in r)
                dims=(['COUSUB'] if year<2025 else [])+['eth','race','sex','agegrp'];pop='pop'
                vintage='not explicit in CSV; source package year '+str(year)
            result+=aggregate(r,year,dims,'CTYNAME',pop,name,vintage)
    with (out/'ct_historical_county_population_candidates.csv').open('w',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
    provenance={str(Path(f).resolve()):hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in (a.historical_7z,a.county_zip)}
    (out/'source_sha256.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print('Extracted 48 county/year candidate totals (2020–2025). Mixed vintages; none approved for use.')

if __name__=='__main__':main()
