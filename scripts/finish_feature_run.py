#!/usr/bin/env python3
"""Complete the interrupted typhoidal fit using published results, not task caching."""
import argparse
import csv
import getpass
import json
from pathlib import Path
import re
import subprocess
import sys


def read_rows(path):
    with path.open(newline='') as handle:
        return list(csv.DictReader(handle))


def inspect(root, project):
    destination=root/'output'/project
    plan=destination/'validation_plan'
    params=json.loads((plan/'params.json').read_text())
    groups=params['pathogen_grouping'].split('|')
    target='SALMONELLA~TYPHOIDAL'
    if target not in groups or params.get('baseline_year')!=2019:
        raise ValueError('This completion helper requires the saved 2019 feature validation plan')
    log=(plan/'nextflow.log').read_text(errors='replace')
    if not re.search(r'Workflow completed >|Execution complete --',log):
        raise ValueError('The latest Nextflow launcher has not recorded shutdown. Stop the duplicate recovery in its foreground terminal first; no jobs started.')
    ids=set(re.findall(r'jobId[:=]\s*(\d+)',log))
    q=subprocess.run(['qstat','-u',getpass.getuser()],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    if q.returncode: raise ValueError('Cannot establish scheduler state: '+q.stderr)
    active=[line for line in q.stdout.splitlines() if line.split() and line.split()[0] in ids]
    if active: raise ValueError('Jobs from that launcher are still active; wait for cancellation to finish:\n'+'\n'.join(active))
    results=destination/'spline_results'
    missing=[]
    for group in groups:
        prefix=re.sub('_+','_',re.sub('[^a-zA-Z0-9_-]','_',group)).rstrip('_')
        suffixes=['_brm.Rds','_IRCatch.csv','_IRSite.csv','_EstIRRCatch_2019_2019.csv',
                  '_analysis_settings.csv','_convergence_diagnostics.csv']
        if any(not (results/(prefix+s)).is_file() or (results/(prefix+s)).stat().st_size==0 for s in suffixes):
            missing.append(group);continue
        if (results/(prefix+'_error.txt')).exists():
            raise ValueError('Saved error report requires review: '+prefix)
        settings=read_rows(results/(prefix+'_analysis_settings.csv'))
        if len(settings)!=1 or settings[0].get('subgroup')!=group.split('~')[1] or settings[0].get('baseline_start')!='2019' or settings[0].get('baseline_end')!='2019':
            raise ValueError('Published settings do not match the saved feature plan: '+group)
        if not read_rows(results/(prefix+'_IRCatch.csv')) or not read_rows(results/(prefix+'_EstIRRCatch_2019_2019.csv')):
            raise ValueError('Empty published result table: '+group)
    if missing not in ([],[target]):
        raise ValueError('Additional groups are incomplete; refusing to silently refit them: '+', '.join(missing))
    return destination,plan,params,missing


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project')
    parser.add_argument('--check-only',action='store_true')
    args=parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]+',args.project):parser.error('Invalid project ID')
    root=Path(__file__).resolve().parent.parent
    try: destination,plan,params,missing=inspect(root,args.project)
    except (OSError,ValueError,KeyError) as error:parser.error(str(error))
    print('Verified published results: {} of {}'.format(len(params['pathogen_grouping'].split('|'))-len(missing),len(params['pathogen_grouping'].split('|'))),flush=True)
    print('Models to fit: '+(', '.join(missing) if missing else 'none; dashboard only'),flush=True)
    if args.check_only:return
    if missing:
        completion=dict(params,pathogen='SALMONELLA',pathogen_grouping='SALMONELLA~TYPHOIDAL',skip_dashboard=True)
        file=plan/'completion_params.json'
        file.write_text(json.dumps(completion,indent=2)+'\n')
        status=subprocess.call(['nextflow','-log',str(plan/'completion_nextflow.log'),'run',str(root/'main.nf'),
                                '-profile','singularity','-params-file',str(file),'-ansi-log','false'],cwd=str(root))
        if status:raise SystemExit(status)
        # Successful process execution can also represent an intentionally empty group.
        remaining=inspect(root,args.project)[3]
        if remaining:raise SystemExit('Typhoidal results are still incomplete; dashboard not generated.')
    status=subprocess.call(['singularity','exec','--bind','/scicomp',str(root/'foodnet.sif'),
        'Rscript',str(root/'dashboard/generate_dashboard.R'),'--output_dir',str(destination),
        '--projID',args.project,'--output',str(destination/'dashboard.html'),
        '--cleanFile',params['cleanFile'],'--pipeline_params',str(plan/'params.json')],cwd=str(root))
    raise SystemExit(status)


if __name__=='__main__':main()
