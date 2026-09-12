#!/usr/bin/env python3
"""Verify launcher plans and submissions without running any models."""
import ast
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root=Path(__file__).resolve().parent.parent
script=root/'scripts/run_feature_models.py'
ast.parse(script.read_text(),feature_version=(3,6))
with tempfile.TemporaryDirectory(prefix='foodnet-feature-launch-') as directory:
    temp=Path(directory)
    (temp/'scripts').mkdir();shutil.copyfile(script,temp/'scripts/run_feature_models.py')
    shutil.copyfile(root/'scripts/collect_run_diagnostics.py',temp/'scripts/collect_run_diagnostics.py')
    (temp/'analysis_configs').mkdir();shutil.copyfile(root/'analysis_configs/classification_rules.csv',temp/'analysis_configs/classification_rules.csv')
    (temp/'foodnet.sif').touch();(temp/'main.nf').touch()
    clean=temp/'output/completed/preprocessed/clean_mmwr.csv';clean.parent.mkdir(parents=True)
    clean.write_text('pathogen,serotypesummary2,sero1\nYERSINIA,ENTEROCOLITICA,OTHER\nYERSINIA,OTHER,ENTEROCOLITICA\nYERSINIA,,ENTEROCOLITICA\n')
    before=clean.read_bytes()
    data=temp/'data';data.mkdir()
    for name in ['mmwr9625.sas7bdat','cen9625.sas7bdat','cen9625_para.sas7bdat']: (data/name).touch()
    fake=temp/'fakebin';fake.mkdir()
    for tool in ['git','singularity']:
        p=fake/tool;p.write_text('#!/bin/sh\necho fixture\n');p.chmod(0o755)
    p=fake/'nextflow';p.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > submitted_args.txt\n');p.chmod(0o755)
    env=dict(os.environ,PATH=str(fake)+':'+os.environ['PATH'])
    command=['python3',str(temp/'scripts/run_feature_models.py'),'completed','--data-dir',str(data)]
    for prepare_only in [True,False]:
        result=subprocess.run(command+(['--prepare-only'] if prepare_only else []),env=env,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
        assert result.returncode==0,(result.stdout,result.stderr)
        if prepare_only: assert not (temp/'submitted_args.txt').exists()
    plans=list((temp/'output').glob('feature_validation_*/validation_plan'))
    assert len(plans)==2
    for plan in plans:
        params=json.loads((plan/'params.json').read_text());manifest=json.loads((plan/'manifest.json').read_text())
        groups=params['pathogen_grouping'].split('|')
        assert len(groups)==len(set(groups))==14
        assert 'YERSINIA~ENTEROCOLITICA' in groups
        assert params['preprocessed'] is True and params['cleanFile']==str(clean)
        assert params['chains']==6 and params['iterations']==10001 and params['baseline_year']==2019
        assert manifest['species_records_before_filters']==1 # no row-wise source fallback
        assert Path(params['classification_rules']).read_bytes()==(temp/'analysis_configs/classification_rules.csv').read_bytes()
        assert 'maxForks' not in (plan/'execution.config').read_text()
        assert manifest['maximum_simultaneous_models'] is None
        assert '-resume' not in manifest['command']
    assert sum((plan/'run_diagnostics.txt').exists() for plan in plans)==1
    assert clean.read_bytes()==before
    submitted=(temp/'submitted_args.txt').read_text()
    assert '-params-file\n' in submitted and 'resume-resources.config' not in submitted
    assert '-log\n' in submitted and '-resume' not in submitted
    result=subprocess.run(command+['--species','MISSING','--prepare-only'],env=env,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
    assert result.returncode!=0 and len(list((temp/'output').glob('feature_validation_*')))==2
print('PASS: 14-group plan, authoritative species selection, preserved inputs, unique projects, prepare-only, fresh submission, invalid-species rejection.')
