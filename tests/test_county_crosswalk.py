import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'scripts'))
from build_county_crosswalk import build

def row(status,code='06001',county='Alpha',**kw):
    return dict(dict(state='CA',county=county,year='2023',candidate_fips=code,
       population_class='bacterial',match_status=status,siteid='CA'),**kw)
a=row('direct_fips_candidate');b=row('name_candidate_requires_review')
c,e=build([a,b]);assert c[0]['evidence_status']=='historically_supported_unique_mapping'
assert c[0]['approved_for_model']=='FALSE'
c,e=build([a,b,row('name_candidate_requires_review','06003')]);assert c[0]['evidence_status']=='needs_identifier_review'
c,e=build([b]);assert c[0]['evidence_status']=='needs_identifier_review'
r=row('no_unique_year_state_name_match');r.update(year='2025',population_class='parasitic',siteid='COEX')
c,e=build([r]);assert e[0]['review_reason']=='parasite_population_year_unavailable'
assert e[0]['action_applied']=='none'
print('PASS historical corroboration, ambiguity and missing-evidence guards, exclusive exception grouping, no automatic approval')
