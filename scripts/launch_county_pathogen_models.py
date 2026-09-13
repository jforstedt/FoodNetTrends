#!/usr/bin/env python3
"""Reconcile eight new pathogens, then run 16 independently gated comparison fits."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

PATHOGENS = ('CAMPYLOBACTER', 'CRYPTOSPORIDIUM', 'CYCLOSPORA', 'LISTERIA', 'SHIGELLA', 'STEC', 'VIBRIO', 'YERSINIA')
MODELS = ('spatial_county_time', 'iid_county_time')
SOURCES = ('run_county_pathogen.R', 'reconcile_raw_county.R', 'county_matching.R', 'fit_county_pilot.R',
           'diagnose_saved_county_pilot.R', 'county_sensitivity.R', 'collect_county_pathogen_models.py')

def prepare(root, audit, dest, raw, clean, mapping):
    dest.mkdir(parents=True, exist_ok=False)
    for name in SOURCES: shutil.copyfile(str(root/'scripts'/name), str(dest/name))
    q = shlex.quote
    manifest = dict(audit=str(audit), raw=str(raw), clean=str(clean), mapping=str(mapping),
                    pathogens=PATHOGENS, models=MODELS, fit_cpus=8, posterior_draws=2000,
                    salmonella='Existing results retained; no new task', scope='2004-2019 combined pathogens')
    (dest/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    for mode in ('reconcile', 'fit'):
        tasks = [(p, None) for p in PATHOGENS] if mode == 'reconcile' else [(p, m) for p in PATHOGENS for m in MODELS]
        script = '#!/bin/bash\nset -uo pipefail\nexport OPENBLAS_NUM_THREADS=1\ncase "${SGE_TASK_ID:-}" in\n'
        for i, (p, m) in enumerate(tasks, 1):
            output = dest/p/('reconciliation' if m is None else m)
            log = dest/(p+'_'+(m or mode)+'.log')
            container = root/('foodnet.sif' if mode == 'reconcile' else 'foodnet-inla-fixed.sif')
            args = [mode, p, str(audit/'reports'/p), str(output)]
            args += [str(raw), str(clean), str(mapping)] if mode == 'reconcile' else [str(dest/p/'reconciliation'), m]
            command = ['singularity', 'exec', '--cleanenv', '--bind', '/scicomp', str(container),
                       'Rscript', '--vanilla', str(dest/'run_county_pathogen.R')]+args
            script += str(i)+')\nmkdir -p '+q(str(output.parent))+'\nstatus=0\n'
            script += ' '.join(q(s) for s in command)+' > '+q(str(log))+' 2>&1 || status=$?\n'
            script += 'mkdir -p '+q(str(output))+'\nprintf "%s\\n" "$status" > '+q(str(output/'task_exit_status.txt'))+'\nexit "$status";;\n'
        script += '*) exit 2;;\nesac\n'
        (dest/(mode+'.sh')).write_text(script)
    (dest/'collect.sh').write_text('#!/bin/bash\nexec python3 '+q(str(dest/'collect_county_pathogen_models.py'))+' '+q(str(dest))+'\n')
    return dest

def submit(dest, script, count, cpus, hold=None):
    cmd = ['qsub', '-terse', '-V', '-cwd', '-S', '/bin/bash', '-N', 'foodnet_county_'+script,
           '-pe', 'smp', str(cpus), '-l', 'h_rt=12:00:00,h_rss=32768M,mem_free=32768M,h_vmem=64G',
           '-j', 'y', '-o', str(dest/'collection.log') if script=='collect' else str(dest)]
    if count: cmd += ['-t', '1-'+str(count)]
    if hold: cmd += ['-hold_jid', hold]
    answer = subprocess.check_output(cmd+[str(dest/(script+'.sh'))], universal_newlines=True).strip()
    match = re.match(r'^(\d+)(?:[.\s]|$)', answer)
    if not match: raise RuntimeError('Unexpected scheduler response: '+answer)
    print(script+' job: '+answer, flush=True)
    return match.group(1)

def main():
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit', default=str(root/'output/county_pathogen_audit_20260912_235314_491415'))
    p.add_argument('--raw', default='/scicomp/groups-pure/EDEB/foodnet/trends/data/mmwr9625.sas7bdat')
    p.add_argument('--prepare-only', action='store_true');a = p.parse_args()
    audit = Path(a.audit).resolve();raw = Path(a.raw).resolve()
    clean = root/'output/20260911_140750/preprocessed/clean_mmwr.csv'
    mapping = clean.with_name('clean_mmwr_preprocessing_report.csv')
    if not a.prepare_only:
        for tool in ('qsub', 'singularity'):
            if not shutil.which(tool): p.error('Missing module: '+tool)
        for f in [raw, clean, mapping, root/'foodnet.sif', root/'foodnet-inla-fixed.sif']+[audit/'reports'/n/'county_panel_INTERNAL.rds' for n in PATHOGENS]:
            if not f.is_file(): p.error('Missing '+str(f))
    dest = root/'output'/('county_pathogen_models_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    prepare(root, audit, dest, raw, clean, mapping)
    print('Output: '+str(dest), flush=True)
    if a.prepare_only: return
    r = submit(dest, 'reconcile', 8, 4)
    f = submit(dest, 'fit', 16, 8, r)
    c = submit(dest, 'collect', None, 1, f)
    (dest/'submission.json').write_text(json.dumps(dict(reconciliation=r, fits=f, collection=c))+'\n')
    print('Final log: '+str(dest/'collection.log')+'\nArchive: '+str(dest)+'.tar.gz')
if __name__ == '__main__': main()
