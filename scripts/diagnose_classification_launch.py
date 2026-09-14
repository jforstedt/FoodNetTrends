#!/usr/bin/env python3
"""Read-only classification launch diagnostics; no hashing, submission or cancellation."""
import argparse
from datetime import datetime
import getpass
import json
import os
from pathlib import Path
import socket
import subprocess
import time


def command(args):
    try:
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, timeout=20)
        return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)


def processes():
    found = []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if proc.stat().st_uid != os.getuid() or int(proc.name) == os.getpid():
                continue
            args = (proc/'cmdline').read_bytes().decode(errors='replace').split('\0')
            if not any(Path(arg).name == 'launch_monthly_classification_models.py' for arg in args if arg):
                continue
            if '--worker' in args or '--collect' in args:
                continue
            fds = {}
            for fd in (proc/'fd').iterdir():
                try:
                    target = os.readlink(str(fd))
                    info = (proc/'fdinfo'/fd.name).read_text()
                    position = next((line.split(':', 1)[1].strip() for line in info.splitlines() if line.startswith('pos:')), '?')
                    if target.startswith('/') and not target.startswith('/dev/'):
                        fds[fd.name] = dict(path=target, position=position)
                except (OSError, StopIteration):
                    pass
            found.append(dict(pid=int(proc.name), args=[a for a in args if a],
                              wait_channel=(proc/'wchan').read_text().strip(), files=fds))
        except (OSError, ValueError):
            continue
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    lines = ['Host: '+socket.gethostname(), 'Repository: '+str(root),
             'Run this on the host where the original launcher was started; /proc is host-local.']
    logs = sorted((root/'output').glob('monthly_classification_models_*_preparation.log'))[-3:]
    if not logs:
        lines.append('No preparation logs found.')
    for log in logs:
        lines.append('\nLOG: '+str(log))
        try:
            with log.open('rb') as handle:
                handle.seek(max(0, log.stat().st_size-16000))
                lines.append(handle.read().decode(errors='replace') or '(empty)')
            run = Path(str(log)[:-len('_preparation.log')])
            lines.append('Run directory exists: '+str(run.is_dir()))
            for path in (run/'submission.json', Path(str(run)+'_preparation')/'submission.json', run/'summary.json'):
                if path.is_file():
                    lines.append(str(path)+'\n'+path.read_text()[:12000])
            lines.append('Plan exists: '+str((run/'plan.json').is_file()))
        except OSError as exc:
            lines.append(str(exc))
    before = processes()
    time.sleep(2)
    after = processes()
    lines.extend(['\nLauncher processes, sample 1:', json.dumps(before, indent=2),
                  '\nLauncher processes, sample 2 (file positions show read progress):', json.dumps(after, indent=2),
                  '\nUser process states:', command(['ps','-u',getpass.getuser(),'-o','pid,ppid,stat,etime,pcpu,wchan:24,comm']),
                  '\nScheduler jobs:', command(['qstat','-u',getpass.getuser()])])
    report = '\n'.join(lines)+'\n'
    output = root/('classification_launch_diagnostics_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.txt')
    output.write_text(report)
    print(report)
    print('Report saved: '+str(output))


if __name__ == '__main__':
    main()
