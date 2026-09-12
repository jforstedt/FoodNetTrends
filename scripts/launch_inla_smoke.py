#!/usr/bin/env python3
"""Prepare or submit an isolated synthetic INLA check (Python 3.6 compatible)."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess


def prepare(root, container, destination):
    """Snapshot the synthetic test and create a reviewable SGE execution plan."""
    for path in (root, destination):
        if any(char in str(path) for char in (':', '\n', '\r', ',')):
            raise ValueError('Bind paths cannot contain colons, commas, or newlines')
    source = root / 'scripts' / 'inla_smoke.R'
    if not source.is_file():
        raise ValueError('Missing synthetic test: ' + str(source))
    destination.mkdir(parents=True, exist_ok=False)
    reports = destination / 'reports'
    reports.mkdir()
    snapshot = destination / 'inla_smoke.R'
    shutil.copyfile(str(source), str(snapshot))
    archive = Path(str(destination) + '.tar.gz')
    command = ['singularity', 'exec', '--cleanenv', '--bind',
               str(root) + ':' + str(root) + ':ro', '--bind',
               str(destination) + ':' + str(destination) + ':rw',
               str(container), 'Rscript', '--vanilla', str(snapshot), str(reports), '2']
    manifest = {'purpose': 'Synthetic INLA smoke check; no surveillance inputs',
                'container': str(container), 'command': command,
                'threads': 2, 'script_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    (destination / 'plan.json').write_text(json.dumps(manifest, indent=2) + '\n')
    q = shlex.quote
    script = '#!/bin/bash\nset -uo pipefail\n'
    script += 'cd ' + q(str(destination)) + ' || exit 1\n'
    script += 'status=0\n'
    script += ' '.join(q(arg) for arg in command)
    script += ' > ' + q(str(destination / 'smoke.log')) + ' 2>&1 || status=$?\n'
    script += 'cp ' + q(str(destination / 'smoke.log')) + ' ' + q(str(reports / 'smoke.log')) + ' || { if [ "$status" -eq 0 ]; then status=1; fi; }\n'
    script += 'printf "%s\\n" "$status" > ' + q(str(reports / 'exit_status.txt')) + '\n'
    script += 'cat ' + q(str(reports / 'smoke.log')) + '\n'
    script += 'echo "Synthetic INLA exit status: $status"\n'
    script += 'archive_status=0\n'
    script += 'tar -czf ' + q(str(archive)) + ' -C ' + q(str(destination))
    script += ' reports inla_smoke.R plan.json run.sh || archive_status=$?\n'
    script += 'if [ "$archive_status" -eq 0 ]; then echo ' + q('Archive: ' + str(archive))
    script += '; else echo "Archive failed: $archive_status" >&2; fi\n'
    script += 'if [ "$status" -ne 0 ]; then exit "$status"; fi\nexit "$archive_status"\n'
    (destination / 'run.sh').write_text(script)
    return ['qsub', '-terse', '-V', '-cwd', '-S', '/bin/bash', '-N', 'foodnet_inla_smoke',
            '-pe', 'smp', '2', '-l', 'h_rt=00:30:00,h_rss=8192M,mem_free=8192M,h_vmem=16G',
            '-j', 'y', '-o', str(destination / 'launcher.log'), str(destination / 'run.sh')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--container', help='Dedicated INLA image; defaults to foodnet-inla.sif')
    parser.add_argument('--prepare-only', action='store_true', help='Write plan without HPC tools or an image')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    container = Path(args.container).resolve() if args.container else root / 'foodnet-inla.sif'
    if not args.prepare_only:
        for tool in ('qsub', 'singularity'):
            if not shutil.which(tool):
                parser.error('Missing ' + tool + '; load the cluster modules, or use --prepare-only')
        if not container.is_file():
            parser.error('Missing dedicated INLA image: ' + str(container))
    destination = root / 'output' / ('inla_smoke_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    try:
        command = prepare(root, container, destination)
    except ValueError as error:
        parser.error(str(error))
    (destination / 'submit.json').write_text(json.dumps(command, indent=2) + '\n')
    print('Plan: ' + str(destination), flush=True)
    if args.prepare_only:
        print('Prepared only; no job submitted.')
        return
    job = subprocess.check_output(command, universal_newlines=True).strip()
    print('Synthetic INLA job: ' + job + '\nLog: ' + str(destination / 'launcher.log') +
          '\nArchive: ' + str(destination) + '.tar.gz')


if __name__ == '__main__':
    main()
