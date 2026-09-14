#!/usr/bin/env python3
"""Prepare and submit independent combination branches, then collect one archive."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile

BRANCHES = (
    ('spatial', 'launch_monthly_spatial_factorial', 162, 4, '48:00:00', 53248, 68),
    ('classification', 'launch_classification_monthly_preparation', 6, 2, '04:00:00', 8192, 16),
    ('inspection', 'launch_monthly_spline_inspection', 54, 1, '04:00:00', 8192, 16),
)

def write(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(str(path))

def submit(dest, name, script, cpus, hours, rss, vmem, array=None, holds=None):
    cmd = ['qsub', '-terse', '-V', '-cwd', '-S', '/bin/bash', '-j', 'y', '-N', name,
           '-pe', 'smp', str(cpus), '-l', 'h_rt={},h_rss={}M,mem_free={}M,h_vmem={}G'.format(hours,rss,rss,vmem),
           '-o', str(dest / (name + '.log'))]
    if array: cmd += ['-t', '1-' + str(array)]
    if holds: cmd += ['-hold_jid', ','.join(holds)]
    raw = subprocess.check_output(cmd + [str(script)], universal_newlines=True).strip()
    # Preserve the response even if it cannot be parsed; never retry an ambiguous submission.
    with (dest / 'scheduler_responses.log').open('a') as f: f.write(name + ': ' + raw + '\n')
    match = re.match(r'^(\d+)(?:[.\s]|$)', raw)
    if not match: raise ValueError('Unrecognized scheduler response; inspect queue before any retry: ' + raw)
    return match.group(1)

def prepare_branch(root, dest, spec, verified):
    import importlib
    module = importlib.import_module(spec[1])
    module.prepare(root, dest / spec[0], verified=verified)
    return spec

def driver(root, dest, verified=True):
    root, dest = Path(root), Path(dest)
    ledger = dict(branches={}, issues=[], preparation_complete=False)
    write(dest / 'submission.json', ledger)
    holds = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(prepare_branch, root, dest, spec, verified): spec for spec in BRANCHES}
        for future in as_completed(futures):
            spec = futures[future]; name, module, count, cpus, hours, rss, vmem = spec
            record = ledger['branches'][name] = {}
            try:
                future.result(); record['prepared'] = True
                if verified:
                    work = dest / name
                    job = submit(work, 'foodnet_' + name, work / 'run.sh', cpus, hours, rss, vmem, array=count)
                    record['array'] = job; holds.append(job); write(dest / 'submission.json', ledger)
                    collector = submit(work, 'foodnet_' + name + '_collect', work / 'collect.sh', 1, '04:00:00', 8192, 16, holds=[job])
                    record['collector'] = collector; holds.append(collector)
                print(name + ': ' + json.dumps(record), flush=True)
            except Exception as e:
                record['error'] = str(e); ledger['issues'].append(name + ': ' + str(e))
                print(name + ' failed: ' + str(e), flush=True)
            write(dest / 'submission.json', ledger)
    ledger['preparation_complete'] = True
    write(dest / 'submission.json', ledger)
    if verified:
        try:
            ledger['final_collector'] = submit(dest, 'foodnet_combinations_collect', dest / 'collect.sh', 1, '02:00:00', 8192, 16, holds=holds)
        except Exception as e:
            ledger['issues'].append('Final collector submission failed: ' + str(e))
        write(dest / 'submission.json', ledger)
    return 1 if ledger['issues'] else 0

def verify_branch_archive(archive, summary_path):
    # Read without extracting; reject ambiguous members and hash every delivered file.
    with tarfile.open(str(archive), 'r:gz') as arc:
        members = arc.getmembers()
        names = [m.name for m in members]
        if len(names) != len(set(names)) or any(not m.isfile() or m.name.startswith('/') or '..' in Path(m.name).parts for m in members):
            raise ValueError('Unsafe or duplicate branch archive members')
        if 'report_sha256.json' not in names or 'summary.json' not in names:
            raise ValueError('Missing branch archive manifest or summary')
        manifest = json.load(arc.extractfile('report_sha256.json'))
        if not isinstance(manifest, dict) or set(manifest) != set(names) - {'report_sha256.json'}:
            raise ValueError('Branch archive manifest member mismatch')
        for name, expected in manifest.items():
            digest = hashlib.sha256()
            with arc.extractfile(name) as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b''):
                    digest.update(block)
            if digest.hexdigest() != expected:
                raise ValueError('Changed branch archive member: ' + name)
        raw = arc.extractfile('summary.json').read()
        if raw != summary_path.read_bytes():
            raise ValueError('Branch archive and on-disk summary differ')
        return json.loads(raw)


def collect(dest):
    dest = Path(dest); ledger = json.loads((dest / 'submission.json').read_text())
    result = dict(branches={}, issues=list(ledger.get('issues', [])), scientific_acceptance=False)
    files = []
    for name, *_ in BRANCHES:
        archive = dest / (name + '.tar.gz')
        try:
            summary = verify_branch_archive(archive, dest / name / 'summary.json')
            expected = {'spatial': 324, 'inspection': 54, 'classification': 6}[name]
            tasks = summary.get('tasks', [])
            valid_tasks = len(tasks) == expected and all(t.get('status') == 'COMPLETE' for t in tasks)
            if name in ('inspection', 'spatial'):
                complete = summary.get('complete') == (54 if name == 'inspection' else 324) and not summary.get('issues')
            else:
                complete = summary.get('execution_complete', False)
            complete = complete and valid_tasks and not summary.get('issues')
            files.append(archive)
            result['branches'][name] = dict(execution_complete=bool(complete), summary=summary)
            if not complete: result['issues'].append(name + ' incomplete; inspect branch report')
        except (OSError, ValueError, tarfile.TarError, KeyError, TypeError, AttributeError) as e:
            result['branches'][name] = dict(execution_complete=False, error=str(e))
            result['issues'].append(name + ': ' + str(e))
    result['execution_complete'] = not result['issues'] and len(result['branches']) == 3
    write(dest / 'summary.json', result)
    files += [p for p in dest.iterdir() if p.is_file() and p.suffix in ('.json','.log','.sh') and p.name != 'archive_sha256.json']
    write(dest / 'archive_sha256.json', {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    with tarfile.open(str(dest) + '.tar.gz', 'w:gz') as arc:
        for p in files + [dest / 'archive_sha256.json']: arc.add(str(p), arcname=p.name)
    print('Archive: ' + str(dest) + '.tar.gz', flush=True)
    print('Execution complete: ' + str(result['execution_complete']), flush=True)
    return 0 if result['execution_complete'] else 1

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true'); parser.add_argument('--driver'); parser.add_argument('--collect'); parser.add_argument('--root')
    args = parser.parse_args()
    if args.collect: return collect(args.collect)
    if args.driver: return driver(args.root, args.driver)
    root = Path(__file__).resolve().parents[1]
    if not args.prepare_only and any(not shutil.which(x) for x in ('qsub','singularity')): parser.error('Load singularity on an SGE host first')
    dest = root / 'output' / ('broader_combinations_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    dest.mkdir(parents=True)
    # Snapshot Python driver/imports before detaching; branch preparation also snapshots its R inputs.
    scripts = dest / 'scripts'; scripts.mkdir()
    for p in (root / 'scripts').glob('*.py'): shutil.copy2(str(p), str(scripts / p.name))
    launcher = scripts / Path(__file__).name
    (dest / 'collect.sh').write_text('#!/bin/bash\nset -eu\nexec python3 ' + shlex.quote(str(launcher)) + ' --collect ' + shlex.quote(str(dest)) + '\n')
    print('Output: ' + str(dest), flush=True)
    print('Preparation log: ' + str(dest / 'preparation.log'), flush=True)
    print('Final archive: ' + str(dest) + '.tar.gz', flush=True)
    if args.prepare_only: return driver(root, dest, False)
    with (dest / 'preparation.log').open('w') as log:
        process = subprocess.Popen(['python3', str(launcher), '--driver', str(dest), '--root', str(root)], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, cwd=str(root))
    print('Detached preparation PID: ' + str(process.pid) + '; do not resubmit while preparation runs.', flush=True)
    return 0

if __name__ == '__main__': sys.exit(main())
