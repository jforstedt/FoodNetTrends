#!/usr/bin/env python3
"""Recover an incomplete county validation batch without changing its scientific snapshots."""
import argparse
import fcntl
import getpass
import xml.etree.ElementTree as ET
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def identity(task, fingerprints):
    return hashlib.sha256(json.dumps(dict(task=task, fingerprints=fingerprints), sort_keys=True).encode()).hexdigest()


def rebase(value, old, new):
    if isinstance(value, str):
        return str(new) + value[len(str(old)):] if value == str(old) or value.startswith(str(old) + '/') else value
    if isinstance(value, list):
        return [rebase(v, old, new) for v in value]
    if isinstance(value, dict):
        return {rebase(k, old, new): rebase(v, old, new) for k, v in value.items()}
    return value


def require_finished(old):
    jobs = json.loads((old / 'submission.json').read_text())
    if not jobs: raise ValueError('Missing previous job IDs')
    inventory = subprocess.run(['qstat', '-xml', '-u', getpass.getuser()], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
    if inventory.returncode != 0: raise ValueError('Cannot query current scheduler inventory: ' + inventory.stderr)
    try:
        tree = ET.fromstring(inventory.stdout)
        if tree.tag != 'job_info': raise ValueError('Unexpected scheduler XML root')
        live = {node.text for node in tree.iter('JB_job_number')}
    except ET.ParseError as error: raise ValueError('Malformed scheduler inventory: ' + str(error))
    for job in set(jobs.values()):
        if not re.match(r'^\d+$', str(job)): raise ValueError('Invalid previous job ID')
        result = subprocess.run(['qstat', '-j', str(job)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
        # A timeout, unavailable scheduler, permission failure or live job must block recovery.
        message = (result.stdout + result.stderr).strip()
        known_absence = re.match(r'^Following jobs do not exist(?: or permissions are not sufficient)?:\s*' + re.escape(str(job)) + r'$', message)
        if str(job) in live or result.returncode == 0 or not known_absence:
            raise ValueError('Cannot establish that previous job %s has ended: %s' % (job, message))
    return jobs


def shell(dest, ids):
    q = shlex.quote
    lines = ['#!/bin/bash', 'set -euo pipefail', 'case "${SGE_TASK_ID:-1}" in']
    lines += ['%d) task=%s;;' % (i, q(name)) for i, name in enumerate(ids, 1)]
    lines += ['*) exit 2;;', 'esac', 'work=' + q(str(dest)) + '/"$task"', 'mkdir -p "$work"',
              'exec >> "$work/shell.log" 2>&1', 'date -u', 'hostname', 'ulimit -a',
              'trap \'status=$?; if [ "$status" -ne 0 ]; then printf "Shell exit status: %s\\n" "$status" > "$work/shell_error.txt"; fi\' EXIT',
              'trap \'exit 143\' TERM', 'trap \'exit 130\' INT', 'trap \'exit 140\' USR2',
              'python3 ' + q(str(dest / 'scripts/run_county_forecast_validation.py')) + ' ' + q(str(dest)) + ' "$task"']
    return '\n'.join(lines) + '\n'


def prepare(old, dest, verify_jobs=True):
    old, dest = Path(old).resolve(), Path(dest).resolve()
    if dest.exists(): raise ValueError('Recovery directory already exists')
    jobs = require_finished(old) if verify_jobs else None
    plan = json.loads((old / 'manifest.json').read_text())
    if not plan.get('inputs_verified'): raise ValueError('Cannot recover an unverified input plan')
    if len(set(t['id'] for t in plan['tasks'])) != len(plan['tasks']): raise ValueError('Duplicate task IDs')
    for task in plan['tasks']:
        if not re.match(r'^[A-Za-z0-9_-]+$', task['id']): raise ValueError('Unsafe task ID')
    for path, digest in plan['fingerprints'].items():
        if sha(path) != digest: raise ValueError('Changed original source/container: ' + path)
    for name in ('run_county_forecast_validation.py', 'county_forecast_artifacts.py', 'gate.py', 'collect_county_forecast_validation.py'):
        if str(old / 'scripts' / name) not in plan['fingerprints']: raise ValueError('Unfingerprinted recovery dependency: ' + name)
    spec = importlib.util.spec_from_file_location('recovery_original_artifacts', str(old / 'scripts/county_forecast_artifacts.py'))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    reusable = {}
    checked_inputs = {}
    for task in plan['tasks']:
        for path, digest in task.get('input_fingerprints', {}).items():
            if path not in checked_inputs: checked_inputs[path] = sha(path)
            if checked_inputs[path] != digest: raise ValueError('Changed task input: ' + path)
        status = old / task['id'] / 'task_status.json'
        if not status.exists(): continue
        record = json.loads(status.read_text())
        if record.get('status') != 'COMPLETE': continue
        if record.get('exit_status') != 0 or record.get('task_sha256') != identity(task, plan['fingerprints']) or not record.get('outputs'):
            raise ValueError('Invalid completed task identity: ' + task['id'])
        for name, digest in record['outputs'].items():
            rel = Path(name)
            if rel.is_absolute() or '..' in rel.parts or rel.suffix.lower() == '.rds': raise ValueError('Unsafe reusable artifact: ' + name)
            if sha(old / task['id'] / rel) != digest: raise ValueError('Changed completed artifact: ' + name)
        if task['kind'] == 'forecast':
            gate = json.loads((old / 'gate.json').read_text())
            if gate.get('status') != 'PASS' or gate.get('manifest_sha256') != sha(old / 'manifest.json'): raise ValueError('Completed forecast has no valid original gate')
        module.validate_task_outputs(old / task['id'], task)
        reusable[task['id']] = record
    dest.mkdir(parents=True)
    for directory in ('scripts', 'tests'):
        (dest / directory).mkdir()
        for path in (old / directory).rglob('*'):
            if path.is_file() and str(path) in plan['fingerprints']:
                target = dest / path.relative_to(old); target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(str(path), str(target))
    new = rebase(plan, old, dest)
    # Snapshot bytes must remain identical; only manifest path references are rebased.
    for path, digest in new['fingerprints'].items():
        if sha(path) != digest: raise ValueError('Snapshot copy did not preserve fingerprint: ' + path)
    new['recovery'] = dict(original_directory=str(old), original_manifest_sha256=sha(old / 'manifest.json'), reused_tasks=sorted(reusable))
    (dest / 'manifest.json').write_text(json.dumps(new, indent=2) + '\n')
    if (old / 'protocol.json').exists(): shutil.copyfile(str(old / 'protocol.json'), str(dest / 'protocol.json'))
    provenance = dest / 'recovery_provenance'; provenance.mkdir()
    shutil.copyfile(str(old / 'manifest.json'), str(provenance / 'original_manifest.json'))
    (provenance / 'previous_jobs.json').write_text(json.dumps(jobs, indent=2) + '\n')
    for task in new['tasks']:
        name = task['id']
        if name not in reusable: continue
        original = reusable[name]; work = dest / name; work.mkdir()
        for artifact, digest in original['outputs'].items():
            target = work / artifact; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(old / name / artifact), str(target))
            if sha(target) != digest: raise ValueError('Reused copy fingerprint mismatch')
        module.validate_task_outputs(work, task)
        (provenance / (name + '.json')).write_text(json.dumps(original, indent=2) + '\n')
        record = dict(original, task_sha256=identity(task, new['fingerprints']))
        (work / 'task_status.json').write_text(json.dumps(record, indent=2) + '\n')
    missing_screen = [t['id'] for t in new['tasks'] if t['kind'] != 'forecast' and t['id'] not in reusable]
    missing_forecast = [t['id'] for t in new['tasks'] if t['kind'] == 'forecast' and t['id'] not in reusable]
    for kind, names in (('screen', missing_screen), ('forecast', missing_forecast)):
        (dest / (kind + '.sh')).write_text(shell(dest, names))
    for kind, script in (('gate', 'gate.py'), ('collect', 'collect_county_forecast_validation.py')):
        (dest / (kind + '.sh')).write_text('#!/bin/bash\nset -euo pipefail\nexec python3 ' + shlex.quote(str(dest / 'scripts' / script)) + ' ' + shlex.quote(str(dest)) + '\n')
    recovery = dict(original=str(old), reused=sorted(reusable), missing_screen=missing_screen, missing_forecast=missing_forecast, previous_jobs_verified=verify_jobs)
    (dest / 'recovery_plan.json').write_text(json.dumps(recovery, indent=2) + '\n')
    return recovery


def submit(dest, recovery):
    submitted = {}
    def job(kind, count=None, hold=None):
        cpus = 8 if kind == 'forecast' else (1 if kind == 'collect' else 2)
        resources = 'h_rt=24:00:00,h_rss=32768M,mem_free=32768M,h_vmem=64G' if kind == 'forecast' else 'h_rt=04:00:00,h_rss=16384M,mem_free=16384M,h_vmem=32G'
        cmd = ['qsub', '-terse', '-V', '-cwd', '-S', '/bin/bash', '-N', 'foodnet_recovery_' + kind, '-pe', 'smp', str(cpus), '-l', resources, '-j', 'y', '-o', str(dest / (kind + '.log'))]
        if count: cmd += ['-t', '1-' + str(count)]
        if hold: cmd += ['-hold_jid', hold]
        value = subprocess.check_output(cmd + [str(dest / (kind + '.sh'))], universal_newlines=True).strip()
        match = re.match(r'^(\d+)(?:[.\s]|$)', value)
        if not match: raise ValueError('Unrecognized submission response; inspect scheduler before any retry: ' + value)
        submitted[kind] = match.group(1)
        temp = dest / 'submission.json.tmp'; temp.write_text(json.dumps(submitted, indent=2) + '\n'); temp.replace(dest / 'submission.json')
        print(kind + ' job: ' + value, flush=True)
        return match.group(1)
    dependency = job('screen', len(recovery['missing_screen'])) if recovery['missing_screen'] else None
    dependency = job('gate', hold=dependency)
    if recovery['missing_forecast']: dependency = job('forecast', len(recovery['missing_forecast']), dependency)
    job('collect', hold=dependency)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run'); parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args(); root = Path(__file__).resolve().parents[1]
    old = Path(args.run)
    if not old.is_absolute(): old = root / 'output' / old
    dest = root / 'output' / ('county_forecast_recovery_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    try:
        # Serialize launchers for this source run and retain an explicit submission claim.
        with (old / '.recovery.lock').open('a') as lock:
            try: fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise ValueError('Another recovery launcher is preparing this run')
            claim = old / 'recovery_submission.json'
            if claim.exists(): raise ValueError('Recovery already claimed; inspect ' + str(claim) + ' and recover that descendant if needed. Do not resubmit the original run.')
            recovery = prepare(old, dest)
            print('Output: ' + str(dest), flush=True)
            print('Reused: %d; numerical tasks to run: %d; gated county tasks to run: %d' % (len(recovery['reused']), len(recovery['missing_screen']), len(recovery['missing_forecast'])), flush=True)
            if args.prepare_only: print('Prepared only; no jobs submitted.'); return
            # Claim before the first qsub; a partial submission cannot be launched twice.
            claim.write_text(json.dumps(dict(recovery_directory=str(dest), submission_ledger=str(dest / 'submission.json')), indent=2) + '\n')
            submit(dest, recovery)
            print('Archive: ' + str(dest) + '.tar.gz\nFinal log: ' + str(dest / 'collect.log') + '\nYou can disconnect after all job IDs above have appeared (four when numerical and forecast tasks remain).')
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.error(str(error))


if __name__ == '__main__': main()
