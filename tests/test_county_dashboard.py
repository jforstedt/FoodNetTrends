import copy
import csv
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('builder',str(ROOT/'scripts/build_county_dashboard.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ReportFixture:
 def __init__(self,rows,text,path):self.data=rows;self.texts=text;self.path=Path(path);self.sha256='synthetic'
 def rows(self,n):return copy.deepcopy(self.data[n])
 def text(self,n):return self.texts[n]

def fixture():
 with (ROOT/'analysis_configs/county_pilot/counties.csv').open() as f:nodes=list(csv.DictReader(f))
 pop=[];counts=[];rec={};fits=[]
 for i,(f,y) in enumerate((r,y) for r in nodes for y in range(2004,2020)):
  n=16 if i<5384 else 15
  pop.append(dict(fips=f['fips'],state=f['state'],year=str(y),population='10000',population_status='ok'))
  counts.append(dict(fips=f['fips'],state=f['state'],year=str(y),raw_records=str(n),clean_records=str(n),difference='0'))
  rec[f['state'],y]=rec.get((f['state'],y),0)+n
  fits.append(dict(fips=f['fips'],state=f['state'],year=str(y),rate_mean='100',**{'rate_0.5quant':'99','rate_0.025quant':'50','rate_0.975quant':'150'},expected_count_mean='10'))
 a=ReportFixture({'reports/graph_nodes.csv':nodes,'reports/population_audit.csv':pop,'reports/input_checksums.csv':[dict(file='/clean_mmwr.csv',md5='clean')],
   'reports/state_year_reconciliation.csv':[dict(state=s,year=str(y),selected_cases=str(n),direct_matched_cases=str(n)) for (s,y),n in rec.items()]},
   {'reports/status.txt':'INPUT_AUDIT_PASS'},'audit.tar.gz')
 r=ReportFixture({'reports/summary.csv':[dict(panel_reconciled='TRUE',unexplained_cells='0',clean_records='122024')],
  'reports/input_checksums.csv':[dict(file='/county_panel_INTERNAL.rds',md5='panel',unchanged='TRUE'),dict(file='/clean_mmwr.csv',md5='clean',unchanged='TRUE')],
  'reports/all_raw_vs_clean_INTERNAL.csv':counts},{'reports/status.txt':'RAW_CLEAN_DEFAULT_HYPOTHESIS_MATCH'},'raw.tar.gz')
 sd={};st={}
 for model in ('spatial_county_time','iid_county_time'):
  p=model+'/reports/';sd[p+'panel_checksum.csv']=[dict(md5='panel')];sd[p+'county_fitted_INTERNAL.csv']=fits
  sd[p+'specification.csv']=[dict(name=model,county_time='TRUE',county_sd_upper='1')]
  sd[p+'model_diagnostics.csv']=[dict(cells='7776',cpo_failures='0',cpo_nonpositive_or_nonfinite='0')]
  sd[p+'zero_checks_INTERNAL.csv']=[dict(grouping='overall',observed_zeros='0',expected_zeros_mean='2',replicated_lower='0',replicated_upper='5')]
  st[p+'status.txt']='SENSITIVITY_FIT_COMPLETE';st[p+'exit_status.txt']='0'
 return a,r,ReportFixture(sd,st,'fits.tar.gz'),dict(counties=[dict(id=r['fips']) for r in nodes])
class DashboardTests(unittest.TestCase):
 def test_reconciliation_and_rejection(self):
  a,r,s,g=fixture();payload=m.build_payload(a,r,s,g)
  self.assertEqual(sum(z['count'] for c in payload['counties'] for z in c['rows']),122024)
  self.assertEqual(len(payload['counties']),486)
  self.assertEqual(payload['counties'][0]['rows'][0]['lower'],50)
  s.data['spatial_county_time/reports/panel_checksum.csv'][0]['md5']='changed'
  with self.assertRaisesRegex(ValueError,'panel differ'):m.build_payload(a,r,s,g)
  s.data['spatial_county_time/reports/panel_checksum.csv'][0]['md5']='panel'
  r.data['reports/all_raw_vs_clean_INTERNAL.csv'][0]['difference']='1'
  with self.assertRaisesRegex(ValueError,'counts differ'):m.build_payload(a,r,s,g)
 def test_safe_embedding_and_public_geometry(self):
  html=m.render(dict(name='</script><img src=x onerror=alert(1)>'),'<script type="application/json">__COUNTY_DATA__</script>')
  self.assertEqual(html.count('</script>'),1);self.assertIn('\\u003c',html)
  geometry=json.loads((ROOT/'dashboard/county_boundaries.json').read_text())
  self.assertEqual(len(geometry['counties']),486)
  self.assertTrue(all(r['path'].startswith('M') and r['path'].endswith('Z') for r in geometry['counties']))
if __name__=='__main__':unittest.main()
