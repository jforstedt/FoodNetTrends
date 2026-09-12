#!/usr/bin/env python3
"""Build a separate final dashboard from eight original and six validated refits."""
import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from launch_comparison_refits import KEYS


def rows(path):
    with path.open(newline='') as handle:return list(csv.DictReader(handle))


def prepare(root,project,comparison):
    source=root/'output'/project
    comparison=comparison.resolve()
    if comparison.parent!=source.resolve():raise ValueError('Comparison directory must belong to this project')
    params=json.loads((source/'validation_plan/params.json').read_text())
    groups=params['pathogen_grouping'].split('|')
    if len(groups)!=14:raise ValueError('Expected the saved 14-analysis feature plan')
    prefixes=[re.sub('_+','_',re.sub('[^a-zA-Z0-9_-]','_',g)).rstrip('_') for g in groups]
    for key in KEYS:
        meta=rows(comparison/'refit_metadata'/(key+'_refit_settings.csv'))[0]
        if any(meta.get(k)!='TRUE' for k in ['same_data','same_priors','same_stan_code']):raise ValueError('Refit identity check not passed: '+key)
        chains=rows(comparison/'diagnostic_review'/(key+'_chains.csv'))
        if len(chains)!=6 or any(int(r['divergences']) or int(r['treedepth_hits']) for r in chains):raise ValueError('Unresolved sampling flags: '+key)
    for key in prefixes:
        base=comparison if key in KEYS else source
        for suffix in ['_brm.Rds','_IRCatch.csv','_IRSite.csv','_EstIRRCatch_2019_2019.csv','_analysis_settings.csv','_convergence_diagnostics.csv']:
            f=base/'spline_results'/(key+suffix)
            if not f.is_file() or not f.stat().st_size:raise ValueError('Missing result: '+str(f))
    dest=source/('final_dashboard_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    dest.mkdir();results=dest/'spline_results';results.mkdir()
    # Copies prevent any regeneration from writing through to original files.
    for f in (source/'spline_results').iterdir():
        if f.is_file():shutil.copyfile(str(f),str(results/f.name))
    for key in KEYS:
        # Replace all model-derived artifacts; retain source input audit metadata.
        for f in results.glob(key+'_*'):
            if f.suffix=='.png' or f.name==key+'_summary.txt':f.unlink()
        if (results/(key+'_error.txt')).exists():raise ValueError('Source error file requires review: '+key)
        for f in (comparison/'spline_results').glob(key+'_*'):
            if f.is_file():shutil.copyfile(str(f),str(results/f.name))
    manifest={'source_project':project,'source_directory':str(source),'comparison_directory':str(comparison),
              'analysis_sources':{k:str(comparison if k in KEYS else source) for k in prefixes},
              'baseline':[2019,2019],'refit_adapt_delta':0.999,'original_adapt_delta':0.99,
              'note':'Mixed provenance: eight original fits and six comparison fits. No sampling during consolidation.'}
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (dest/'params.json').write_text(json.dumps(params,indent=2)+'\n')
    for f in ['bin/functions.R','scripts/finalize_feature_dashboard.R']:
        shutil.copyfile(str(root/f),str(dest/Path(f).name))
    q=shlex.quote
    script='#!/bin/bash\nset -euo pipefail\ncd '+q(str(root))+'\n'
    script+='singularity exec --bind /scicomp '+q(str(root/'foodnet.sif'))+' Rscript '+q(str(dest/'finalize_feature_dashboard.R'))+' '+q(str(dest))+'\n'
    script+='singularity exec --bind /scicomp '+q(str(root/'foodnet.sif'))+' Rscript dashboard/generate_dashboard.R --output_dir '+q(str(dest))+' --projID '+q(project)+' --output '+q(str(dest/'dashboard.html'))+' --cleanFile '+q(params['cleanFile'])+' --pipeline_params '+q(str(dest/'params.json'))+'\n'
    annotation = '''from pathlib import Path
p=Path(__file__).resolve().parent/'dashboard.html'
s=p.read_text()
if '<body>' not in s: raise SystemExit('Dashboard body marker missing')
note='<div style="padding:12px;background:#eef4fa;border-bottom:1px solid #9bb4cc">Final feature validation: 14 analyses; six improved fits use adapt_delta=0.999 and eight retained fits use 0.99. Original results are preserved. See manifest.json for per-analysis provenance.</div>'
p.write_text(s.replace('<body>', '<body>'+note, 1))
'''
    (dest/'annotate.py').write_text(annotation)
    script+='python3 '+q(str(dest/'annotate.py'))+'\n'
    script+='echo '+q('FINAL DASHBOARD COMPLETE: '+str(dest/'dashboard.html'))+'\n'
    (dest/'finalize.sh').write_text(script)
    return dest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project');p.add_argument('comparison');p.add_argument('--prepare-only',action='store_true');a=p.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]+',a.project):p.error('Invalid project ID')
    root=Path(__file__).resolve().parent.parent
    try:dest=prepare(root,a.project,Path(a.comparison))
    except (ValueError,OSError,KeyError) as e:p.error(str(e))
    print('Final output: '+str(dest),flush=True)
    if a.prepare_only:return
    result=subprocess.check_output(['qsub','-terse','-V','-cwd','-S','/bin/bash','-N','foodnet_finalize','-pe','smp','1','-l','h_rt=02:00:00,h_rss=16384M,mem_free=16384M,h_vmem=32G','-j','y','-o',str(dest/'finalize.log'),str(dest/'finalize.sh')],universal_newlines=True)
    print('Dashboard job: '+result.strip()+'\nLog: '+str(dest/'finalize.log'))

if __name__=='__main__':main()
