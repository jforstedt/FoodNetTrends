#!/usr/bin/env python3
"""Reconcile raw Salmonella county aggregates against the existing cleaned input."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess


def collect_provenance(root, clean, dest):
    """Collect bounded, project-owned process evidence; never execute it."""
    import csv
    import re
    evidence = dest / 'provenance'
    evidence.mkdir()
    for name in ('data_rules.csv',):
        shutil.copyfile(str(root / 'analysis_configs' / name), str(evidence / ('current_' + name)))
    shutil.copyfile(str(root / 'bin/preprocess.R'), str(evidence / 'current_preprocess.R'))
    traces = sorted((clean.parent.parent / 'pipeline_info').glob('execution_trace_*.txt'))
    work = Path('/scicomp/scratch') / root.parts[root.parts.index('home-pure') + 1] / 'nextflow/work' if 'home-pure' in root.parts else None
    found = []
    for trace in traces:
        with trace.open() as handle:
            for row in csv.DictReader(handle, delimiter='\t'):
                if 'PREPROCESS' not in row.get('name', ''):
                    continue
                prefix = row.get('hash', '')
                if work is None or not re.match(r'^[0-9a-f]{2}/[0-9a-f]{6,}$', prefix):
                    continue
                for task in work.glob(prefix + '*'):
                    target = evidence / ('task_' + task.parent.name + '_' + task.name)
                    target.mkdir(exist_ok=True)
                    collected = []
                    for filename in ('.command.sh', '.command.out', '.command.err', '.exitcode', 'data_rules.csv'):
                        source = task / filename
                        if source.is_file() and source.stat().st_size < 2000000:
                            shutil.copyfile(str(source), str(target / filename.lstrip('.')))
                            collected.append(dict(name=filename, symlink=source.is_symlink(), resolved=str(source.resolve()), sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
                    found.append(dict(trace=str(trace), workdir=str(task), hash=prefix, files=collected))
    (evidence / 'collection.json').write_text(json.dumps(dict(tasks=found,
        limitation='Current files are labeled current; historical evidence may be missing. A matching default hypothesis does not prove historical rule use.'), indent=2) + '\n')


def prepare(root, fit_root, audit, container, dest, raw):
    for path in (root, fit_root, audit, container, dest, raw):
        if any(c in str(path) for c in ('\n', '\r', ':', ',')):
            raise ValueError('Unsupported character in path')
    dest.mkdir(parents=True, exist_ok=False)
    source = root / 'scripts/reconcile_raw_county.R'
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
    report = clean.with_name(clean.stem + '_preprocessing_report.csv')
    collect_provenance(root, clean, dest)
    manifest = dict(raw=str(raw), preprocessing_report=str(report), fit_root=str(fit_root), audit=str(audit), container=str(container), clean=str(clean),
                    script_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    purpose='Raw-to-clean diagnostic only; default removal rules are hypotheses')
    (dest / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    q = shlex.quote
    # Overlay the saved input directories as read-only inside the container.
    command = ['singularity', 'exec', '--cleanenv', '--bind', '/scicomp',
               '--bind', str(fit_root) + ':' + str(fit_root) + ':ro',
               '--bind', str(audit) + ':' + str(audit) + ':ro',
               '--bind', str(clean) + ':' + str(clean) + ':ro',
               '--bind', str(raw) + ':' + str(raw) + ':ro',
               str(container), 'Rscript', '--vanilla', str(dest / source.name),
               str(raw), str(clean), str(report), str(audit), str(dest / 'reports')]
    script = '#!/bin/bash\nset -uo pipefail\nstatus=0\n'
    script += ' '.join(q(x) for x in command) + ' > ' + q(str(dest / 'diagnostics.log')) + ' 2>&1 || status=$?\n'
    script += 'printf "%s\\n" "$status" > ' + q(str(dest / 'exit_status.txt')) + '\n'
    script += 'tar -czf ' + q(str(dest) + '.tar.gz') + ' -C ' + q(str(dest.parent)) + ' ' + q(dest.name) + ' || { if [ "$status" -eq 0 ]; then status=1; fi; }\n'
    script += 'echo "Raw review exit status: $status"\necho ' + q('Archive: ' + str(dest) + '.tar.gz') + '\nexit "$status"\n'
    (dest / 'run.sh').write_text(script)
    return ['qsub', '-terse', '-V', '-cwd', '-S', '/bin/bash', '-N', 'foodnet_raw_review',
            '-pe', 'smp', '4', '-l', 'h_rt=02:00:00,h_rss=16384M,mem_free=16384M,h_vmem=32G',
            '-j', 'y', '-o', str(dest / 'launcher.log'), str(dest / 'run.sh')]


def main():
    root = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fit-dir', default=str(root / 'output/county_pilot_fit_20260912_212322_668317'))
    p.add_argument('--container', default=str(root / 'foodnet.sif'))
    p.add_argument('--raw-file', default='/scicomp/groups-pure/EDEB/foodnet/trends/data/mmwr9625.sas7bdat')
    p.add_argument('--prepare-only', action='store_true')
    a = p.parse_args()
    fit_root = Path(a.fit_dir).resolve()
    container = Path(a.container).resolve()
    raw = Path(a.raw_file).resolve()
    if not (fit_root / 'manifest.json').is_file():
        p.error('Missing original fit manifest: ' + str(fit_root / 'manifest.json'))
    audit = Path(json.loads((fit_root / 'manifest.json').read_text())['audit']).resolve()
    for f in (raw, container, audit / 'county_panel_INTERNAL.rds',
              fit_root / 'spatial/reports/county_incidence_INTERNAL.csv', fit_root / 'iid/reports/county_incidence_INTERNAL.csv'):
        if not f.is_file():
            p.error('Missing saved input (no refitting fallback): ' + str(f))
    if not a.prepare_only:
        for tool in ('singularity', 'qsub'):
            if not shutil.which(tool):
                p.error('Load cluster modules: missing ' + tool)
    dest = root / 'output' / ('raw_county_review_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    command = prepare(root, fit_root, audit, container, dest, raw)
    print('Output: ' + str(dest), flush=True)
    if a.prepare_only:
        print('Prepared only; no jobs submitted.')
        return
    job = subprocess.check_output(command, universal_newlines=True).strip()
    print('Raw review job: ' + job + '\nLog: ' + str(dest / 'diagnostics.log') +
          '\nFinal status: ' + str(dest / 'launcher.log') + '\nArchive: ' + str(dest) + '.tar.gz')


if __name__ == '__main__':
    main()
