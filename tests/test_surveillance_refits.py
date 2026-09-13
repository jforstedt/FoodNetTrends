import csv
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/'scripts'/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
L=load('launch_surveillance_refits');C=load('collect_surveillance_refits')
def write(path,data):
 with path.open('w',newline='') as h:
  w=csv.DictWriter(h,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
def settings(p,g='combined',start=1996,end=2025):
 return dict(pathogen=p,subgroup=g,analysis_start_year=str(start),analysis_end_year=str(end),baseline_start='2019',baseline_end='2019',travel='NO,UNKNOWN,YES',cidt='CIDT+,CX+,PARASITIC',states='',colorado_coverage='historical',parasite_end_year='2024',serotype_source='auto',selected_serotypes='',travel_stratify='false',catchment_config='')
class RefitTests(unittest.TestCase):
 def test_selective_parallel_and_collector(self):
  with tempfile.TemporaryDirectory() as temp:
   base=Path(temp);source=base/'source';source.mkdir()
   for s in [settings('SALMONELLA'),settings('CAMPYLOBACTER'),settings('STEC','nonO157'),settings('YERSINIA'),settings('CRYPTOSPORIDIUM',start=1997,end=2024)]:
    prefix=s['pathogen']+'_'+s['subgroup'];write(source/(prefix+'_analysis_settings.csv'),[s]);(source/(prefix+'_classification_rules.csv')).write_text('pathogen,rule\n')
   dest=base/'run space';cmd=L.prepare(ROOT,dest,Path('/data'),[source]);self.assertEqual(cmd[cmd.index('-t')+1],'1-3');self.assertNotIn('-tc',cmd)
   manifest=json.loads((dest/'manifest.json').read_text());self.assertEqual(len(manifest['jobs']),3)
   for f in dest.rglob('*.sh'):subprocess.check_call(['bash','-n',str(f)])
   for job in manifest['jobs']:
    work=dest/job['task'];output=work/'spline_results';prefix=job['prefix'];s=dict(job['settings'],analysis_start_year=str(job['first_year']),analysis_end_year=str(job['last_year']))
    data=[dict(year=str(y),baseline_start='2019',baseline_end='2019') for y in range(job['first_year'],job['last_year']+1)]
    for suffix in ('_IRCatch.csv','_IRSite.csv','_EstIRRCatch_2019_2019.csv'):write(output/(prefix+suffix),data)
    write(output/(prefix+'_analysis_settings.csv'),[s]);write(output/(prefix+'_convergence_diagnostics.csv'),[dict(max_rhat='1.001',min_ess='5000',n_divergent='0',converged='TRUE',warnings='')]);(output/(prefix+'_brm.Rds')).write_text('private');(work/'exit_status.txt').write_text('0\n')
   self.assertEqual(C.collect(dest),0)
   with tarfile.open(str(dest)+'.tar.gz') as a:self.assertFalse(any(n.lower().endswith('.rds') for n in a.getnames()))
   job=manifest['jobs'][0]
   write(dest/job['task']/'spline_results'/(job['prefix']+'_convergence_diagnostics.csv'),[dict(max_rhat='1.001',min_ess='5000',n_divergent='0',converged='TRUE',warnings='Diagnostic extraction warning')]);self.assertEqual(C.collect(dest),1)
   write(dest/job['task']/'spline_results'/(job['prefix']+'_convergence_diagnostics.csv'),[dict(max_rhat='1.1',min_ess='20',n_divergent='4')]);self.assertEqual(C.collect(dest),1)
 def test_unknown_settings_and_baseline_fail_before_plan(self):
  with tempfile.TemporaryDirectory() as temp:
   source=Path(temp);s=settings('STEC','nonO157');s['baseline_start']='1996';s['baseline_end']='1998';write(source/'STEC_nonO157_analysis_settings.csv',[s])
   with self.assertRaisesRegex(ValueError,'Baseline'):L.scan([source])
   s=settings('STEC','nonO157');s.pop('travel_stratify');s.pop('catchment_config');write(source/'STEC_nonO157_analysis_settings.csv',[s]);(source/'STEC_nonO157_classification_rules.csv').write_text('pathogen,rule\n')
   with self.assertRaisesRegex(ValueError,'provenance'):L.scan([source])
if __name__=='__main__':unittest.main()
