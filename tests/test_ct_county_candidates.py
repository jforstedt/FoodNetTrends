import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'scripts'))
from extract_ct_county_candidates import aggregate,FIPS
r=[dict(name=k,cell='one',pop='100') for k in FIPS]
a=aggregate(r,2024,['cell'],'name','pop','fixture','test')
assert len(a)==8 and all(x['approved_for_use']=='FALSE' for x in a)
for bad in (r+r[:1],r[:-1],[dict(x,pop='-1') for x in r]):
 try:aggregate(bad,2024,['cell'],'name','pop','fixture','test');raise AssertionError('bad data accepted')
 except ValueError:pass
print('PASS eight-county requirement, duplicates and negative populations rejected; candidates never automatically applied')
