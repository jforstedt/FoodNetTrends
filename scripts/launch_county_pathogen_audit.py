#!/usr/bin/env python3
"""Collect all nine county pathogen input audits in one job and one archive."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shlex
import shutil
import subprocess


def prepare(root, dest, clean, bacterial, parasitic):
    dest.mkdir(parents=True, exist_ok=False)
    for name in ('audit_county_pathogens.R', 'audit_county_pilot.R', 'county_matching.R'):
        shutil.copyfile(str(root/'scripts'/name), str(dest/name))
    shutil.copyfile(str(root/'bin/classification.R'), str(dest/'classification.R'))
    shutil.copyfile(str(root/'analysis_configs/classification_rules.csv'), str(dest/'classification_rules.csv'))
    shutil.copytree(str(root/'analysis_configs/county_pilot'), str(dest/'geography'))
    command = ['singularity', 'exec', '--cleanenv', '--bind', '/scicomp', str(root/'foodnet.sif'),
               'Rscript', '--vanilla', str(dest/'audit_county_pathogens.R'), str(clean), str(bacterial),
               str(parasitic), str(dest/'geography'), str(dest/'classification_rules.csv'), str(dest/'reports')]
    (dest/'plan.json').write_text(json.dumps(dict(command=command, years=[2004, 2019],
        scope='Nine combined pathogens; input audit only', fitting=False,
        raw_reconciliation='Pending', exact_panels_archived=False), indent=2)+'\n')
    q = shlex.quote
    script = '#!/bin/bash\nset -uo pipefail\nexport OPENBLAS_NUM_THREADS=1\nstatus=0\n'
    script += ' '.join(q(x) for x in command)+' > '+q(str(dest/'audit.log'))+' 2>&1 || status=$?\n'
    script += 'cat '+q(str(dest/'audit.log'))+'\n'
    script += 'mkdir -p '+q(str(dest/'reports'))+'\n'
    script += 'printf "%s\\n" "$status" > '+q(str(dest/'reports/process_exit_status.txt'))+'\n'
    script += 'tar --exclude=county_panel_INTERNAL.rds -czf '+q(str(dest)+'.tar.gz')+' -C '+q(str(dest))+' reports geography plan.json audit.log audit_county_pathogens.R audit_county_pilot.R county_matching.R classification.R classification_rules.csv run.sh || exit $?\n'
    script += 'echo '+q('Archive: '+str(dest)+'.tar.gz')+'\nexit "$status"\n'
    (dest/'run.sh').write_text(script)
    return ['qsub', '-terse', '-V', '-cwd', '-S', '/bin/bash', '-N', 'foodnet_county_audit',
            '-pe', 'smp', '4', '-l', 'h_rt=02:00:00,h_rss=16384M,mem_free=16384M,h_vmem=32G',
            '-j', 'y', '-o', str(dest/'launcher.log'), str(dest/'run.sh')]


def main():
    root = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--clean-file', default=str(root/'output/20260911_140750/preprocessed/clean_mmwr.csv'))
    p.add_argument('--data-dir', default='/scicomp/groups-pure/EDEB/foodnet/trends/data')
    p.add_argument('--prepare-only', action='store_true')
    a = p.parse_args()
    clean = Path(a.clean_file).resolve()
    bacterial = Path(a.data_dir).resolve()/'cen9625.sas7bdat'
    parasitic = Path(a.data_dir).resolve()/'cen9625_para.sas7bdat'
    if not a.prepare_only:
        for tool in ('qsub', 'singularity'):
            if not shutil.which(tool): p.error('Load cluster modules: missing '+tool)
        for path in (clean, bacterial, parasitic, root/'foodnet.sif'):
            if not path.is_file(): p.error('Missing '+str(path))
    dest = root/'output'/('county_pathogen_audit_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    cmd = prepare(root, dest, clean, bacterial, parasitic)
    print('Output: '+str(dest), flush=True)
    if a.prepare_only:
        print('Prepared only; no job submitted.')
        return
    job = subprocess.check_output(cmd, universal_newlines=True).strip()
    print('Audit job: '+job+'\nLog: '+str(dest/'launcher.log')+'\nArchive: '+str(dest)+'.tar.gz')

if __name__ == '__main__': main()
