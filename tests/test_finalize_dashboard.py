import importlib.util,json,sys,tempfile,subprocess
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root/'scripts'))
import finalize_feature_dashboard as f
with tempfile.TemporaryDirectory() as d:
 r=Path(d);(r/'bin').mkdir();(r/'scripts').mkdir()
 for src in ['bin/functions.R','scripts/finalize_feature_dashboard.R']:(r/src).write_text((root/src).read_text())
 source=r/'output/fixture';results=source/'spline_results';results.mkdir(parents=True)
 (source/'validation_plan').mkdir()
 groups=['STEC~nonO157','SALMONELLA~NONTYPHOIDAL','SALMONELLA~OTHER SEROTYPES','STEC~O157','STEC~NOT SEROGROUPED','SALMONELLA~I 4,[5],12:i:-']+['TEST~G'+str(i) for i in range(8)]
 (source/'validation_plan/params.json').write_text(json.dumps({'pathogen_grouping':'|'.join(groups),'cleanFile':'saved.csv'}))
 c=source/'comparison';(c/'spline_results').mkdir(parents=True);(c/'refit_metadata').mkdir();(c/'diagnostic_review').mkdir()
 for key in f.KEYS+['TEST_G'+str(i) for i in range(8)]:
  for suffix in ['_brm.Rds','_IRCatch.csv','_IRSite.csv','_EstIRRCatch_2019_2019.csv','_analysis_settings.csv','_convergence_diagnostics.csv']:
   (results/(key+suffix)).write_text('original')
   if key in f.KEYS:(c/'spline_results'/(key+suffix)).write_text('refit')
  (results/(key+'_overall_trend.png')).write_text('old plot')
 for key in f.KEYS:
  (c/'refit_metadata'/(key+'_refit_settings.csv')).write_text('same_data,same_priors,same_stan_code\nTRUE,TRUE,TRUE\n')
  (c/'diagnostic_review'/(key+'_chains.csv')).write_text('divergences,treedepth_hits\n'+'0,0\n'*6)
 before={p:p.read_bytes() for p in results.iterdir()}
 dest=f.prepare(r,'fixture',c)
 assert len(json.loads((dest/'manifest.json').read_text())['analysis_sources'])==14
 for key in f.KEYS:
  assert (dest/'spline_results'/(key+'_brm.Rds')).read_text()=='refit'
  assert not (dest/'spline_results'/(key+'_overall_trend.png')).exists()
 assert (dest/'spline_results/TEST_G0_brm.Rds').read_text()=='original'
 assert all(p.read_bytes()==v for p,v in before.items())
 subprocess.check_call(['bash','-n',str(dest/'finalize.sh')])
 (c/'diagnostic_review'/(f.KEYS[0]+'_chains.csv')).write_text('divergences,treedepth_hits\n'+'1,0\n'*6)
 try:f.prepare(r,'fixture',c);raise AssertionError('flagged fit accepted')
 except ValueError:pass
print('PASS: 14 sources, six replacements, no stale refit plots, original preservation, diagnostic guard and shell syntax')
