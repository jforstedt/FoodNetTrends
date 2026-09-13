#!/usr/bin/env python3
"""Check corrected saved-state coverage, baselines and sampling; preserve original outputs."""
import csv
import json
import math
from pathlib import Path
import sys
import tarfile

def rows(path):
    with path.open(newline='') as handle:return list(csv.DictReader(handle))

def collect(dest):
    dest=Path(dest);manifest=json.loads((dest/'manifest.json').read_text());results=[]
    for job in manifest['jobs']:
        work=dest/job['task'];output=work/'spline_results';prefix=job['prefix'];issues=[];diagnostics={}
        try:
            if (work/'exit_status.txt').read_text().strip()!='0':issues.append('Fit process failed')
        except OSError:issues.append('Missing fit exit status')
        first,last=job['first_year'],job['last_year'];s=job['settings'];bs,be=int(s['baseline_start']),int(s['baseline_end'])
        for suffix in ('_IRCatch.csv','_IRSite.csv','_EstIRRCatch_%s_%s.csv'%(bs,be)):
            try:
                data=rows(output/(prefix+suffix));years=set(int(float(r['year'])) for r in data)
                if years!=set(range(first,last+1)):issues.append('Unexpected or incomplete coverage: '+suffix)
                if not set(range(bs,be+1)).issubset(years):issues.append('Missing baseline years: '+suffix)
                if suffix.startswith('_EstIRR') and any(int(float(r['baseline_start']))!=bs or int(float(r['baseline_end']))!=be for r in data):
                    issues.append('Incorrect baseline values in comparison output')
            except (OSError,ValueError,KeyError) as e:issues.append(suffix+': '+str(e))
        try:
            settings=rows(output/(prefix+'_analysis_settings.csv'))[0]
            for key in ('pathogen','subgroup','travel','cidt','states','baseline_start','baseline_end','colorado_coverage','parasite_end_year','serotype_source','selected_serotypes'):
                if settings.get(key)!=s.get(key):issues.append('Setting changed: '+key)
            if int(settings['analysis_start_year'])!=first or int(settings['analysis_end_year'])!=last:issues.append('Incorrect settings coverage')
        except (OSError,ValueError,KeyError,IndexError) as e:issues.append('Settings: '+str(e))
        try:
            diagnostics=rows(output/(prefix+'_convergence_diagnostics.csv'))[0]
            if str(diagnostics.get('converged','')).strip().lower()!='true':issues.append('Convergence not certified by saved diagnostics')
            if str(diagnostics.get('warnings','')).strip():issues.append('Saved diagnostic warnings require review')
            for key,accept in [('max_rhat',lambda v:v<=1.01),('min_ess',lambda v:v>=400),('n_divergent',lambda v:v==0)]:
                value=float(diagnostics[key])
                if not math.isfinite(value) or not accept(value):issues.append('Sampling diagnostic requires review: '+key)
        except (OSError,ValueError,KeyError,IndexError) as e:issues.append('Diagnostics unavailable: '+str(e))
        fit=output/(prefix+'_brm.Rds')
        if not fit.is_file() or fit.stat().st_size==0:issues.append('Saved fit missing or empty')
        if list(output.glob('*_error.txt')):issues.append('Model error artifact present')
        results.append(dict(task=job['task'],analysis=prefix,source=job['source'],status='CHECKS_PASS' if not issues else 'REVIEW_REQUIRED',issues=issues,diagnostics=diagnostics))
    summary=dict(results=results,pending_review=manifest['pending_review'],dashboard_replaced=False,
       note='Checks verify selected output coverage and reported R-hat/ESS/divergences; no claim of complete scientific validation.')
    (dest/'review_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    with tarfile.open(str(dest)+'.tar.gz','w:gz') as archive:
        for f in sorted(dest.rglob('*')):
            if f.is_file() and not f.is_symlink() and f.suffix.lower() in ('.csv','.json','.txt','.log','.r','.py','.sh','.png','.pdf'):
                archive.add(str(f),arcname=str(f.relative_to(dest)),recursive=False)
    print(json.dumps(summary,indent=2));print('Archive: '+str(dest)+'.tar.gz')
    return 0 if all(r['status']=='CHECKS_PASS' for r in results) else 1
if __name__=='__main__':sys.exit(collect(sys.argv[1]))
