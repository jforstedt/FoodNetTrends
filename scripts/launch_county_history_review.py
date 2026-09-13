#!/usr/bin/env python3
"""Review county case histories and source mappings without fitting models."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess


def prepare(root, fit_root, audit, container, dest):
    for path in (root, fit_root, audit, container, dest):
        if any(c in str(path) for c in ('\n', '\r', ':', ',')):
            raise ValueError('Unsupported character in path')
    dest.mkdir(parents=True, exist_ok=False)
    source = root / 'scripts/review_county_histories.R'
    shutil.copyfile(str(source), str(dest / source.name))
    shutil.copyfile(str(root / 'scripts/county_matching.R'), str(dest / 'county_matching.R'))
    import csv
    with (audit / 'reports/input_checksums.csv').open() as handle:
        inputs = list(csv.DictReader(handle))
    candidates = [r['file'] for r in inputs if r['file'].lower().endswith('.csv')]
    if len(candidates) != 1:
        raise ValueError('Cannot identify unique audited clean CSV')
    clean = Path(candidates[0])
    if any(c in str(clean) for c in ('\n', '\r', ':', ',')):
        raise ValueError('Unsupported character in clean input path')
    manifest = dict(fit_root=str(fit_root), audit=str(audit), container=str(container), clean=str(clean),
                    script_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    purpose='Read-only source history review; no refitting; internal aggregate reports')
    (dest / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    q = shlex.quote
    # Overlay the saved input directories as read-only inside the container.
    command = ['singularity', 'exec', '--cleanenv', '--bind', '/scicomp',
               '--bind', str(fit_root) + ':' + str(fit_root) + ':ro',
               '--bind', str(audit) + ':' + str(audit) + ':ro',
               '--bind', str(clean) + ':' + str(clean) + ':ro',
               str(container), 'Rscript', '--vanilla', str(dest / source.name),
               str(audit), str(fit_root), str(clean), str(dest / 'reports')]
    script = '#!/bin/bash\nset -uo pipefail\nstatus=0\n'
    script += ' '.join(q(x) for x in command) + ' > ' + q(str(dest / 'diagnostics.log')) + ' 2>&1 || status=$?\n'
    script += 'printf "%s\\n" "$status" > ' + q(str(dest / 'exit_status.txt')) + '\n'
    script += 'tar -czf ' + q(str(dest) + '.tar.gz') + ' -C ' + q(str(dest.parent)) + ' ' + q(dest.name) + ' || { if [ "$status" -eq 0 ]; then status=1; fi; }\n'
    script += 'echo "County history exit status: $status"\necho ' + q('Archive: ' + str(dest) + '.tar.gz') + '\nexit "$status"\n'
    (dest / 'run.sh').write_text(script)
    return ['qsub', '-terse', '-V', '-cwd', '-S', '/bin/bash', '-N', 'foodnet_county_history',
            '-pe', 'smp', '4', '-l', 'h_rt=02:00:00,h_rss=16384M,mem_free=16384M,h_vmem=32G',
            '-j', 'y', '-o', str(dest / 'launcher.log'), str(dest / 'run.sh')]


def main():
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fit-dir', default=str(root / 'output/county_pilot_fit_20260912_212322_668317'))
    p.add_argument('--container', default=str(root / 'foodnet.sif'))
    p.add_argument('--prepare-only', action='store_true')
    a = p.parse_args()
    fit_root = Path(a.fit_dir).resolve()
    container = Path(a.container).resolve()
    if not (fit_root / 'manifest.json').is_file():
        p.error('Missing original fit manifest: ' + str(fit_root / 'manifest.json'))
    audit = Path(json.loads((fit_root / 'manifest.json').read_text())['audit']).resolve()
    for f in (container, audit / 'county_panel_INTERNAL.rds',
              fit_root / 'spatial/reports/county_incidence_INTERNAL.csv', fit_root / 'iid/reports/county_incidence_INTERNAL.csv'):
        if not f.is_file():
            p.error('Missing saved input (no refitting fallback): ' + str(f))
    if not a.prepare_only:
        for tool in ('singularity', 'qsub'):
            if not shutil.which(tool):
                p.error('Load cluster modules: missing ' + tool)
    dest = root / 'output' / ('county_history_review_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    command = prepare(root, fit_root, audit, container, dest)
    print('Output: ' + str(dest), flush=True)
    if a.prepare_only:
        print('Prepared only; no jobs submitted.')
        return
    job = subprocess.check_output(command, universal_newlines=True).strip()
    print('History review job: ' + job + '\nLog: ' + str(dest / 'diagnostics.log') +
          '\nFinal status: ' + str(dest / 'launcher.log') + '\nArchive: ' + str(dest) + '.tar.gz')


if __name__ == '__main__':
    main()
