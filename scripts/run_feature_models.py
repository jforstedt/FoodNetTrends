#!/usr/bin/env python3
"""Launch real feature models using a completed run's cleaned cases and a new project ID."""
import argparse
from collections import Counter
import csv
from datetime import datetime
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def prepare(args):
    root = Path(__file__).resolve().parent.parent
    source = root/'output'/args.source_project
    clean = source/'preprocessed/clean_mmwr.csv'
    data_dir = Path(args.data_dir).resolve()
    inputs = [clean, data_dir/'mmwr9625.sas7bdat', data_dir/'cen9625.sas7bdat',
              data_dir/'cen9625_para.sas7bdat', root/'foodnet.sif',
              root/'analysis_configs/classification_rules.csv']
    for path in inputs:
        if not path.is_file():
            raise ValueError('Required file missing: {}'.format(path))
    counts = Counter()
    with clean.open(newline='') as handle:
        rows = csv.DictReader(handle)
        field = next((f for f in ['serotypesummary2','serotypesummary_original','serotypesummary','sero1'] if f in rows.fieldnames), None)
        if not field:
            raise ValueError('Cleaned cases have no serotype/species source column')
        for row in rows:
            if row.get('pathogen','').strip().upper() == args.species_pathogen:
                value = row[field].strip().upper()
                if value: counts[value] += 1
    species = args.species.strip().upper()
    if not species or not counts[species] or any(c in species for c in '|~'):
        raise ValueError('Species label is absent or invalid for {}. Most frequent labels: {}'.format(args.species_pathogen, counts.most_common(10)))
    groups = ['STEC~O157','STEC~nonO157','STEC~NOT SEROGROUPED']
    groups += ['SALMONELLA~'+v for v in ['ENTERITIDIS','NEWPORT','TYPHIMURIUM','JAVIANA',
               'I 4,[5],12:i:-','OTHER SEROTYPES','NOT SEROTYPED','TYPHOIDAL','NONTYPHOIDAL','UNCLASSIFIED']]
    groups += [args.species_pathogen+'~'+species]
    project = 'feature_validation_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    destination = root/'output'/project
    destination.mkdir(parents=True, exist_ok=False)
    plan = destination/'validation_plan'
    plan.mkdir()
    shutil.copyfile(root/'analysis_configs/classification_rules.csv',plan/'classification_rules.csv')
    params = dict(mmwrFile=str(inputs[1]),censusFileB=str(inputs[2]),censusFileP=str(inputs[3]),
                  cleanFile=str(clean.resolve()),preprocessed=True,outdir=str(root/'output'),projID=project,
                  pathogen='STEC,SALMONELLA,'+args.species_pathogen,pathogen_grouping='|'.join(groups),
                  baseline_year=2019,classification_rules=str(plan/'classification_rules.csv'),
                  serotype_source='auto',colorado_coverage='historical',parasite_end_year=2024,
                  travel='NO,UNKNOWN,YES',cidt='CIDT+,CX+,PARASITIC',states=None,travel_stratify=False,
                  chains=6,iterations=10001,adapt_delta=0.99,max_treedepth=15,seed=123,
                  stan_backend='rstan',matching_sensitivity='MEDIUM',skip_dashboard=False)
    (plan/'params.json').write_text(json.dumps(params,indent=2)+'\n')
    config = plan/'execution.config'
    config.write_text("process { withName: 'FOODNETTRENDS:TRENDY' { maxForks = 3 } }\n")
    command = ['nextflow','-log',str(plan/'nextflow.log'),'run',str(root/'main.nf'),
               '-profile','singularity','-c',str(config),'-params-file',str(plan/'params.json')]
    version = subprocess.run(['git','rev-parse','HEAD'],cwd=str(root),stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,universal_newlines=True)
    summary = dict(source_project=args.source_project,project_id=project,git_revision=version.stdout.strip(),
                   baseline='2019 (validation example, not a final FoodNet specification)',
                   species=species,species_pathogen=args.species_pathogen,species_source=field,species_records_before_filters=counts[species],
                   groups=groups,maximum_simultaneous_models=3,
                   note='Serotype groups and typhoidal categories overlap intentionally; do not sum across both partitions.',
                   command=command)
    (plan/'manifest.json').write_text(json.dumps(summary,indent=2)+'\n')
    (plan/'resume.sh').write_text('#!/usr/bin/env bash\n# Resume only this run by its explicit session UUID.\n'+
        'cd '+shlex.quote(str(root))+'\nexec '+' '.join(shlex.quote(v) for v in command)+
        ' -resume "${1:?Supply the session UUID from validation_plan/nextflow.log}"\n')
    return root, project, plan, command, summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_project',nargs='?',default='20260911_140750')
    parser.add_argument('--data-dir',default='/scicomp/groups-pure/EDEB/foodnet/trends/data')
    parser.add_argument('--species',default='ENTEROCOLITICA',help='Exact species label; default is present in the saved audit')
    parser.add_argument('--species-pathogen',default='YERSINIA',choices=['YERSINIA','CAMPYLOBACTER','VIBRIO','SHIGELLA','LISTERIA','CRYPTOSPORIDIUM'])
    parser.add_argument('--prepare-only',action='store_true',help='Write the plan without submitting jobs')
    args=parser.parse_args()
    if Path(args.source_project).name != args.source_project or args.source_project in ('.','..'):
        parser.error('Source project must be a directory name')
    for tool in ('git','nextflow','singularity'):
        if not shutil.which(tool): parser.error('Required command unavailable: '+tool)
    try:
        root,project,plan,command,summary=prepare(args)
    except (OSError,ValueError) as error:
        parser.error(str(error))
    print('New project: '+project,flush=True)
    print('14 real model fits; baseline 2019; at most three models concurrently.',flush=True)
    print('Species: {} ({} records before model filters)'.format(summary['species_pathogen']+' / '+summary['species'],summary['species_records_before_filters']),flush=True)
    print('Existing cleaned data reused directly; preprocessing will not run.',flush=True)
    print('Plan and Nextflow log: '+str(plan),flush=True)
    if args.prepare_only:
        print('Prepared only. Launch command:\n'+' '.join(shlex.quote(v) for v in command))
        return
    status = subprocess.call(command,cwd=str(root))
    # Gather all attempts and final diagnostics even if the model run fails.
    diagnostics = plan/'run_diagnostics.txt'
    collection_status = subprocess.call([sys.executable,str(root/'scripts/collect_run_diagnostics.py'),
        project,'--compare',args.source_project,'--skip-accounting','--report',str(diagnostics)],cwd=str(root))
    print('Diagnostics report: '+str(diagnostics),flush=True)
    raise SystemExit(status or collection_status)


if __name__=='__main__': main()
