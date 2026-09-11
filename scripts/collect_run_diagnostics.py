#!/usr/bin/env python3
"""Collect existing FoodNet run diagnostics; never submit jobs or read raw case data."""
import argparse
import csv
from datetime import datetime
import getpass
from pathlib import Path
import re
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project_id')
    parser.add_argument('--compare', help='Previous successful project ID')
    parser.add_argument('--outdir', default='output')
    parser.add_argument('--work-dir', default=f'/scicomp/scratch/{getpass.getuser()}/nextflow/work')
    parser.add_argument('--report', help='New report filename (existing files are never overwritten)')
    parser.add_argument('--skip-accounting', action='store_true')
    args = parser.parse_args()
    projects = list(dict.fromkeys(p for p in (args.project_id, args.compare) if p))
    if any(Path(p).name != p or p in ('.', '..') for p in projects):
        parser.error('Project IDs must be directory names, not paths')
    roots = [Path(args.outdir) / p for p in projects]
    if not roots[0].is_dir():
        parser.error(f'Run output directory not found: {roots[0]}')
    report = Path(args.report or f'foodnet_run_diagnostics_{args.project_id}_{datetime.now():%Y%m%d_%H%M%S}.txt')
    jobs = set()
    tasks = set()
    work_roots = {Path(args.work_dir)}
    with report.open('x') as out:
        def section(title, body):
            out.write(f'\n========== {title} ==========\n{body}\n')
            out.flush()

        def read(path):
            try:
                return path.read_text(errors='replace')
            except OSError as exc:
                return f'Unavailable: {exc}'

        def command(argv, timeout=10):
            try:
                # HPC login nodes use Python 3.6; capture_output/text need 3.7.
                result = subprocess.run(argv, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        universal_newlines=True, timeout=timeout)
                return f'Exit: {result.returncode}\n{result.stdout}{result.stderr}'
            except (OSError, subprocess.TimeoutExpired) as exc:
                return f'Unavailable: {exc}'

        section('Collection scope', f'UTC: {datetime.utcnow().isoformat()}\nDirectory: {Path.cwd()}\nProjects: {projects}\nExisting logs, summary CSVs and scheduler records only. No jobs submitted or cancelled. No raw case files or model objects read.')
        section('Git revision', command(['git', 'log', '-1', '--format=%h %s']))
        section('Git working tree', command(['git', 'status', '--short']))
        override = Path('resume-resources.config')
        if override.exists():
            section(str(override), read(override))
        # Recover all attempts from project-specific logs, including rotated logs.
        logs = set(Path('.').glob('.nextflow.log*'))
        for run_root in roots:
            logs.update((run_root/'validation_plan').glob('nextflow.log*'))
        for log in sorted(logs):
            if not log.is_file():
                continue
            content = read(log)
            launch = next((line for line in content.splitlines() if 'nextflow run ' in line), '')
            owned_log = any(log.parent == run_root/'validation_plan' for run_root in roots)
            if not owned_log and not any(re.search(r'--projID\s+[\"\x27]?' + re.escape(p) + r'(?=[\"\x27\s]|$)', launch) for p in projects):
                continue
            lines = content.splitlines()
            selected = [line for line in lines if re.search(r'Launcher|Session UUID|Run name|Work-dir|submitted process|Submitted process|Re-submitted|Cached process|Task completed|Allocated CPUs|ERROR|WARN|exit status|Execution complete', line)]
            section(str(log) + ' selected events', '\n'.join(selected))
            for line in lines:
                for job in re.findall(r'jobId[:=]\s*(\d+)', line):
                    jobs.add(job)
                match = re.search(r'workDir:\s*(/[^\s;]+)', line)
                if match:
                    tasks.add(Path(match[1]))
                match = re.search(r'Work-dir:\s*(/\S+)', line)
                if match:
                    work_roots.add(Path(match[1]))
        for root in roots:
            section('Run output inventory: ' + str(root), '\n'.join(str(p.relative_to(root)) for p in sorted(root.rglob('*')) if p.is_file()))
            for trace in sorted(root.glob('pipeline_info/execution_trace_*.txt')):
                content = read(trace)
                section(str(trace), content)
                for row in csv.DictReader(content.splitlines(), delimiter='\t'):
                    job = row.get('native_id', '')
                    if job.isdigit():
                        jobs.add(job)
                    wd = row.get('workdir', '')
                    if wd and wd != '-':
                        tasks.add(Path(wd))
                    task_hash = row.get('hash', '')
                    if re.fullmatch(r'[0-9a-f]{2}/[0-9a-f]+', task_hash):
                        for work in work_roots:
                            tasks.update(work.glob(task_hash + '*'))
            for pattern in ('*convergence_diagnostics.csv', '*analysis_settings.csv', '*input_exclusions.csv', '*_error.txt'):
                for file in sorted(root.rglob(pattern)):
                    section(str(file), read(file))
        for task in sorted(tasks):
            if not task.is_dir():
                section('Task unavailable', str(task))
                continue
            wrapper = read(task / '.command.run')
            section(str(task) + ' submitted resources', '\n'.join(line for line in wrapper.splitlines() if line.startswith('#$')))
            section(str(task) + ' executed command', read(task / '.command.sh'))
            section(str(task) + ' exit status', read(task / '.exitcode'))
            for name in ('.command.out', '.command.err', '.command.log'):
                section(str(task / name) + ' last 80 lines', '\n'.join(read(task / name).splitlines()[-80:]))
        if not args.skip_accounting and shutil.which('qacct'):
            for i, job in enumerate(sorted(jobs, key=int), 1):
                print(f'Collecting scheduler record {i}/{len(jobs)}: {job}', flush=True)
                section('qacct -j ' + job, command(['qacct', '-j', job], timeout=10))
        else:
            section('Scheduler accounting', 'Skipped or qacct unavailable.')
        section('Collection complete', f'{len(tasks)} task directories; {len(jobs)} scheduler job IDs. Missing/expired records are reported above.')
    print(f'Report saved: {report.resolve()}')


if __name__ == '__main__':
    main()
