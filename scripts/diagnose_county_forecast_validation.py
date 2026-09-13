#!/usr/bin/env python3
"""Collect scheduler evidence for an existing validation batch without submitting jobs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import getpass
import json
from pathlib import Path
import re
import subprocess
import tarfile


def capture(argv):
    try:
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, timeout=45)
        return {'command': argv, 'exit_status': result.returncode, 'output': result.stdout}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'command': argv, 'exit_status': None, 'error': str(exc)}


def collect(source):
    source = Path(source).resolve()
    plan = json.loads((source / 'manifest.json').read_text())
    submitted = json.loads((source / 'submission.json').read_text())
    dest = source.parent / ('county_forecast_diagnostics_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    dest.mkdir()
    commands = [('qstat', ['qstat', '-u', getpass.getuser()])]
    for kind, job in submitted.items():
        if not re.fullmatch(r'[a-z]+', kind) or not re.fullmatch(r'\d+', str(job)):
            raise ValueError('Invalid scheduler job identity')
        commands.extend([(kind + '_accounting', ['qacct', '-j', str(job)]),
                         (kind + '_live', ['qstat', '-j', str(job)])])
    # Independent read-only scheduler queries; bounded to avoid serial delays.
    with ThreadPoolExecutor(max_workers=4) as pool:
        evidence = list(pool.map(capture, [argv for _, argv in commands]))
    for (name, _), data in zip(commands, evidence):
        (dest / (name + '.json')).write_text(json.dumps(data, indent=2) + '\n')
    inventory = []
    for task in plan['tasks']:
        name = task['id']
        if not re.fullmatch(r'[A-Za-z0-9_]+', name):
            raise ValueError('Invalid task identity')
        path = source / name / 'task_status.json'
        try:
            status = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            status = {'status': 'MISSING_OR_UNREADABLE', 'reason': str(exc)}
        inventory.append({'task': name, 'kind': task['kind'], 'record': status})
    (dest / 'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    (dest / 'source.txt').write_text(str(source) + '\nNo jobs submitted, cancelled or modified.\n')
    # Keep existing evidence and the tails of task logs; exclude fitted objects and datasets.
    candidates = list(source.glob('*.json')) + list(source.glob('*.log'))
    for task in plan['tasks']:
        work = source / task['id']
        candidates.extend(work.glob('*.log'))
        candidates.extend(work.glob('task_status.json'))
        candidates.extend((work / 'result').glob('status.txt'))
        candidates.extend((work / 'result/reports').glob('status.txt'))
    for path in candidates:
        if path.is_file() and not path.is_symlink():
            target = dest / 'batch_evidence' / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            with path.open('rb') as handle:
                if path.stat().st_size > 200000:
                    handle.seek(-200000, 2)
                target.write_bytes(handle.read())
    archive = str(dest) + '.tar.gz'
    with tarfile.open(archive, 'w:gz') as handle:
        for path in sorted(dest.rglob('*')):
            if path.is_file():
                handle.add(str(path), arcname=str(path.relative_to(dest)), recursive=False)
    print('Read-only diagnostics complete. No jobs submitted.')
    print('Archive: ' + archive)
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', help='Existing run ID or output directory')
    args = parser.parse_args()
    source = Path(args.run)
    if not source.is_dir():
        source = Path(__file__).resolve().parents[1] / 'output' / args.run
    collect(source)


if __name__ == '__main__':
    main()
